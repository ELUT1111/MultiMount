"""
Transfer task service.

Creates background transfer jobs and streams data between mount adapters while
keeping progress in the database and over WebSocket.
"""
import asyncio
import logging
import time
from typing import AsyncIterator

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.mount import Mount
from app.models.user import User
from app.models.transfer_task import TransferTask
from app.services import file_service
from app.services.mount_service import get_adapter_for_mount
from app.utils.path_utils import normalize_path

logger = logging.getLogger("multimount.transfer")

DEFAULT_CHUNK_SIZE = 64 * 1024
TRANSFER_TYPES = {"copy", "move"}
QUEUED_STATUSES = {"queued", "pending"}

_ws_connections: dict[int, list] = {}
_running_tasks: dict[int, asyncio.Task] = {}
_scheduler_lock = asyncio.Lock()


class TransferPaused(Exception):
    """Raised internally when a task is paused or cancelled."""


def register_ws(user_id: int, ws):
    _ws_connections.setdefault(user_id, []).append(ws)


def unregister_ws(user_id: int, ws):
    conns = _ws_connections.get(user_id, [])
    if ws in conns:
        conns.remove(ws)


def _limit_bps(kbps: int | None) -> int | None:
    if kbps is None or kbps <= 0:
        return None
    return kbps * 1024


def _mount_ids_for_task(task: TransferTask) -> set[int]:
    return {item for item in (task.mount_id, task.source_mount_id, task.target_mount_id) if item is not None}


def _qos_int(qos: dict | None, *keys: str) -> int | None:
    if not qos:
        return None
    for key in keys:
        value = qos.get(key)
        if value is None:
            continue
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


async def broadcast_progress(task: TransferTask):
    conns = _ws_connections.get(task.user_id, [])
    if not conns:
        return
    data = {
        "type": "transfer_progress",
        "task_id": task.id,
        "status": task.status,
        "transferred": task.transferred,
        "file_size": task.file_size,
        "speed": task.speed,
        "progress": round(task.transferred / task.file_size * 100, 1) if task.file_size else 0,
    }
    for ws in conns[:]:
        try:
            await ws.send_json(data)
        except Exception:
            conns.remove(ws)


def _dispatch_scheduler() -> None:
    try:
        asyncio.create_task(schedule_transfers())
    except RuntimeError:
        logger.debug("transfer scheduler dispatch skipped: no running loop")


async def _load_user_limits(db: AsyncSession, user_id: int | None) -> dict:
    if user_id is None:
        return {}
    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.role:
        return {}
    return user.role.qos_limits or {}


async def _load_mount_qos(db: AsyncSession, mount_id: int | None) -> dict:
    if mount_id is None:
        return {}
    result = await db.execute(select(Mount).where(Mount.id == mount_id))
    mount = result.scalar_one_or_none()
    if not mount:
        return {}
    advanced = mount.advanced_config or {}
    nested = advanced.get("qos_limits") if isinstance(advanced.get("qos_limits"), dict) else {}
    return {**advanced, **nested}


async def _resolve_task_limits(
    db: AsyncSession,
    user_id: int | None,
    source_mount_id: int | None,
    target_mount_id: int | None,
    download_limit_kbps: int | None,
    upload_limit_kbps: int | None,
) -> tuple[int | None, int | None]:
    settings = get_settings()
    user_qos = await _load_user_limits(db, user_id)
    source_qos = await _load_mount_qos(db, source_mount_id)
    target_qos = await _load_mount_qos(db, target_mount_id)

    download_candidates = [
        _limit_bps(settings.TRANSFER_DEFAULT_DOWNLOAD_LIMIT_KBPS),
        _limit_bps(download_limit_kbps),
        _limit_bps(_qos_int(user_qos, "max_download_kbps", "download_kbps")),
        _limit_bps(_qos_int(source_qos, "max_download_kbps", "download_kbps")),
    ]
    upload_candidates = [
        _limit_bps(settings.TRANSFER_DEFAULT_UPLOAD_LIMIT_KBPS),
        _limit_bps(upload_limit_kbps),
        _limit_bps(_qos_int(user_qos, "max_upload_kbps", "upload_kbps")),
        _limit_bps(_qos_int(target_qos, "max_upload_kbps", "upload_kbps")),
    ]
    download_limits = [item for item in download_candidates if item]
    upload_limits = [item for item in upload_candidates if item]
    return (min(download_limits) if download_limits else None, min(upload_limits) if upload_limits else None)


async def _running_count(db: AsyncSession, *conditions) -> int:
    query = select(func.count(TransferTask.id)).where(TransferTask.status == "running")
    for condition in conditions:
        query = query.where(condition)
    result = await db.execute(query)
    return int(result.scalar() or 0)


async def _mount_running_count(db: AsyncSession, mount_id: int) -> int:
    return await _running_count(
        db,
        or_(
            TransferTask.mount_id == mount_id,
            TransferTask.source_mount_id == mount_id,
            TransferTask.target_mount_id == mount_id,
        ),
    )


async def _can_start_task(db: AsyncSession, task: TransferTask) -> bool:
    settings = get_settings()
    if await _running_count(db) >= settings.TRANSFER_MAX_CONCURRENT_GLOBAL:
        return False

    user_limit = settings.TRANSFER_MAX_CONCURRENT_PER_USER
    user_qos = await _load_user_limits(db, task.user_id)
    role_limit = _qos_int(user_qos, "max_concurrent", "max_concurrent_transfers")
    if role_limit:
        user_limit = min(user_limit, role_limit)
    if task.user_id is not None and await _running_count(db, TransferTask.user_id == task.user_id) >= user_limit:
        return False

    for mount_id in _mount_ids_for_task(task):
        mount_qos = await _load_mount_qos(db, mount_id)
        mount_limit = _qos_int(mount_qos, "max_concurrent", "max_concurrent_transfers")
        limit = min(settings.TRANSFER_MAX_CONCURRENT_PER_MOUNT, mount_limit) if mount_limit else settings.TRANSFER_MAX_CONCURRENT_PER_MOUNT
        if await _mount_running_count(db, mount_id) >= limit:
            return False

    return True


async def schedule_transfers() -> None:
    from app.database import async_session_factory

    async with _scheduler_lock:
        for task_id, runner in list(_running_tasks.items()):
            if runner.done():
                _running_tasks.pop(task_id, None)

        async with async_session_factory() as db:
            result = await db.execute(
                select(TransferTask)
                .where(TransferTask.status.in_(list(QUEUED_STATUSES)))
                .order_by(TransferTask.created_at.asc(), TransferTask.id.asc())
            )
            for task in result.scalars().all():
                if task.id in _running_tasks:
                    continue
                if not await _can_start_task(db, task):
                    continue

                task.status = "running"
                task.speed = 0
                task.error_message = None
                await db.commit()
                await db.refresh(task)
                await broadcast_progress(task)
                runner = asyncio.create_task(_execute_transfer(task.id))
                _running_tasks[task.id] = runner


async def list_tasks(db: AsyncSession, user_id: int | None = None,
                     status: str | None = None) -> list[TransferTask]:
    query = select(TransferTask).order_by(TransferTask.created_at.desc())
    if user_id is not None:
        query = query.where(TransferTask.user_id == user_id)
    if status:
        query = query.where(TransferTask.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: int) -> TransferTask:
    result = await db.execute(select(TransferTask).where(TransferTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise NotFoundException("传输任务不存在")
    return task


async def create_task(
    db: AsyncSession,
    user_id: int,
    task_type: str,
    mount_id: int | None,
    source_path: str,
    target_path: str,
    file_name: str,
    file_size: int | None = None,
    source_mount_id: int | None = None,
    target_mount_id: int | None = None,
    conflict_policy: str = "error",
    download_limit_kbps: int | None = None,
    upload_limit_kbps: int | None = None,
) -> TransferTask:
    if task_type not in TRANSFER_TYPES:
        raise BadRequestException(f"不支持的传输任务类型: {task_type}")
    if conflict_policy not in file_service.CONFLICT_POLICIES:
        raise BadRequestException(f"不支持的冲突策略: {conflict_policy}")

    source_mount_id = source_mount_id or mount_id
    target_mount_id = target_mount_id or mount_id
    if not source_mount_id or not target_mount_id:
        raise BadRequestException("跨挂载传输需要 source_mount_id 和 target_mount_id")

    download_limit_bps, upload_limit_bps = await _resolve_task_limits(
        db,
        user_id,
        source_mount_id,
        target_mount_id,
        download_limit_kbps,
        upload_limit_kbps,
    )

    task = TransferTask(
        user_id=user_id,
        type=task_type,
        mount_id=mount_id,
        source_mount_id=source_mount_id,
        target_mount_id=target_mount_id,
        source_path=normalize_path(source_path),
        target_path=normalize_path(target_path),
        file_name=file_name,
        file_size=file_size,
        conflict_policy=conflict_policy,
        download_limit_bps=download_limit_bps,
        upload_limit_bps=upload_limit_bps,
        checkpoint={},
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    _dispatch_scheduler()
    return task


async def pause_task(db: AsyncSession, task_id: int) -> TransferTask:
    task = await get_task(db, task_id)
    if task.status not in ("queued", "pending", "running"):
        raise BadRequestException(f"任务状态 {task.status} 不支持暂停")
    task.status = "paused"
    task.speed = 0
    await db.commit()
    await db.refresh(task)
    await broadcast_progress(task)
    _dispatch_scheduler()
    return task


async def resume_task(db: AsyncSession, task_id: int) -> TransferTask:
    task = await get_task(db, task_id)
    if task.status not in ("paused", "queued", "pending"):
        raise BadRequestException(f"任务状态 {task.status} 不支持恢复")
    task.status = "queued"
    task.transferred = 0
    task.speed = 0
    await db.commit()
    await db.refresh(task)
    _dispatch_scheduler()
    return task


async def cancel_task(db: AsyncSession, task_id: int) -> None:
    task = await get_task(db, task_id)
    if task.status in ("completed", "failed"):
        await db.delete(task)
    else:
        task.status = "failed"
        task.speed = 0
        task.error_message = "用户取消"
    await db.commit()
    await broadcast_progress(task)
    _dispatch_scheduler()


async def recover_unfinished_tasks() -> int:
    """Requeue unfinished transfer tasks after a service restart."""
    from app.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            select(TransferTask).where(TransferTask.status.in_(["running", "queued", "pending"]))
        )
        tasks = list(result.scalars().all())
        for task in tasks:
            task.status = "queued"
            task.speed = 0
            checkpoint = dict(task.checkpoint or {})
            checkpoint["recovered"] = True
            task.checkpoint = checkpoint
        await db.commit()

    if tasks:
        _dispatch_scheduler()
    return len(tasks)


async def _execute_transfer(task_id: int):
    from app.database import async_session_factory

    try:
        async with async_session_factory() as db:
            task = await get_task(db, task_id)
            if task.status != "running":
                return

            task.error_message = None
            task.speed = 0
            await db.commit()
            await db.refresh(task)
            await broadcast_progress(task)

            await _execute_mount_transfer(db, task)

            await db.refresh(task)
            if task.status == "running":
                if task.file_size is not None:
                    task.transferred = task.file_size
                task.status = "completed"
                task.speed = 0
                await db.commit()
                await db.refresh(task)
                await broadcast_progress(task)
                logger.info("transfer completed: id=%d file=%s", task.id, task.file_name)

    except TransferPaused:
        async with async_session_factory() as db:
            try:
                task = await get_task(db, task_id)
                task.speed = 0
                await db.commit()
                await broadcast_progress(task)
            except Exception:
                await db.rollback()
        logger.info("transfer paused: id=%d", task_id)
    except asyncio.CancelledError:
        logger.info("transfer cancelled by scheduler: id=%d", task_id)
    except Exception as exc:
        logger.error("transfer failed: id=%d error=%s", task_id, exc)
        async with async_session_factory() as db:
            try:
                task = await get_task(db, task_id)
                if task.status == "running":
                    task.status = "failed"
                task.speed = 0
                task.error_message = str(exc)[:500]
                checkpoint = task.checkpoint or {}
                checkpoint["last_error"] = str(exc)[:500]
                task.checkpoint = checkpoint
                await db.commit()
                await db.refresh(task)
                await broadcast_progress(task)
            except Exception:
                await db.rollback()
    finally:
        _running_tasks.pop(task_id, None)
        _dispatch_scheduler()


async def _execute_mount_transfer(db: AsyncSession, task: TransferTask) -> None:
    source_mount_id = task.source_mount_id
    target_mount_id = task.target_mount_id
    if not source_mount_id or not target_mount_id:
        raise BadRequestException("传输任务缺少源或目标挂载点")

    source_path = normalize_path(task.source_path)
    target_path = normalize_path(task.target_path)
    source_info = await file_service.get_info(db, source_mount_id, source_path)

    if source_info.is_dir:
        stats = await file_service.directory_stats(db, source_mount_id, source_path)
        task.file_size = stats["total_size"]
    else:
        task.file_size = source_info.size
    await db.commit()

    final_target_path, should_skip = await file_service.resolve_conflict(
        db, target_mount_id, target_path, task.conflict_policy
    )
    task.target_path = final_target_path
    if should_skip:
        task.transferred = source_info.size
        await db.commit()
        return

    _, source_adapter = await get_adapter_for_mount(db, source_mount_id)
    _, target_adapter = await get_adapter_for_mount(db, target_mount_id)
    await source_adapter.connect()
    if target_mount_id != source_mount_id:
        await target_adapter.connect()

    try:
        if source_mount_id == target_mount_id:
            if task.type == "copy":
                await source_adapter.copy(source_path, final_target_path)
            else:
                await source_adapter.move(source_path, final_target_path)
            from app.services import search_service
            if task.type == "move":
                await search_service.remove_path_index(db, source_mount_id, source_path)
            await search_service.refresh_path_index(db, target_mount_id, final_target_path)
            from app.services import share_service
            if task.type == "move":
                await share_service.handle_source_moved(db, source_mount_id, source_path, final_target_path)
            else:
                await share_service.handle_source_changed(db, target_mount_id, final_target_path)
            task.transferred = source_info.size
            await db.commit()
            await broadcast_progress(task)
            return

        if source_info.is_dir:
            await _transfer_directory_tree(
                db,
                task,
                source_mount_id,
                source_path,
                final_target_path,
                source_adapter,
                target_adapter,
            )
        else:
            await _transfer_single_file(
                db,
                task,
                source_adapter,
                target_adapter,
                source_path,
                final_target_path,
                source_info.size,
            )
        if task.type == "move":
            await source_adapter.delete(source_path)
        from app.services import search_service
        if task.type == "move":
            await search_service.remove_path_index(db, source_mount_id, source_path)
        await search_service.refresh_path_index(db, target_mount_id, final_target_path)
        from app.services import share_service
        if task.type == "move":
            await share_service.handle_source_deleted(db, source_mount_id, source_path)
        await share_service.handle_source_changed(db, target_mount_id, final_target_path)
    except TransferPaused:
        if target_mount_id != source_mount_id:
            try:
                await target_adapter.delete(final_target_path)
            except Exception:
                logger.warning("failed to remove partial transfer target: %s", final_target_path)
        raise
    finally:
        await _safe_disconnect(source_adapter)
        if target_mount_id != source_mount_id:
            await _safe_disconnect(target_adapter)


async def _transfer_directory_tree(
    db: AsyncSession,
    task: TransferTask,
    source_mount_id: int,
    source_path: str,
    target_root: str,
    source_adapter,
    target_adapter,
) -> None:
    await target_adapter.mkdir(target_root)

    async def _walk(current_source: str, current_target: str) -> None:
        for info in await file_service.list_dir(db, source_mount_id, current_source):
            target_path = normalize_path(current_target.rstrip("/") + "/" + info.name)
            checkpoint = dict(task.checkpoint or {})
            checkpoint["current_source_path"] = info.path
            checkpoint["current_target_path"] = target_path
            checkpoint["current_file_transferred"] = 0
            task.checkpoint = checkpoint
            await db.commit()

            if info.is_dir:
                await target_adapter.mkdir(target_path)
                await _walk(info.path, target_path)
                continue

            await _transfer_single_file(
                db,
                task,
                source_adapter,
                target_adapter,
                info.path,
                target_path,
                info.size,
            )

    await _walk(normalize_path(source_path), target_root)


async def _transfer_single_file(
    db: AsyncSession,
    task: TransferTask,
    source_adapter,
    target_adapter,
    source_path: str,
    target_path: str,
    file_size: int | None,
) -> None:
    checkpoint = dict(task.checkpoint or {})
    checkpoint["current_source_path"] = source_path
    checkpoint["current_target_path"] = target_path
    checkpoint["current_file_transferred"] = 0
    task.checkpoint = checkpoint
    await db.commit()

    await target_adapter.upload(
        target_path,
        _download_with_progress(db, task, source_adapter.download(source_path)),
        file_size,
    )

async def _download_with_progress(db: AsyncSession, task: TransferTask,
                                  chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    last_time = time.monotonic()
    last_transferred = task.transferred
    window_started = last_time
    window_bytes = 0
    limit = min(
        [value for value in (task.download_limit_bps, task.upload_limit_bps) if value] or [0]
    )

    async for chunk in chunks:
        await db.refresh(task)
        if task.status in ("paused", "failed"):
            task.speed = 0
            await db.commit()
            await broadcast_progress(task)
            raise TransferPaused()

        task.transferred += len(chunk)
        window_bytes += len(chunk)
        checkpoint = dict(task.checkpoint or {})
        checkpoint["transferred"] = task.transferred
        checkpoint["current_file_transferred"] = checkpoint.get("current_file_transferred", 0) + len(chunk)
        task.checkpoint = checkpoint

        if limit:
            elapsed = time.monotonic() - window_started
            expected = window_bytes / limit
            if expected > elapsed:
                await asyncio.sleep(expected - elapsed)
            if time.monotonic() - window_started >= 1:
                window_started = time.monotonic()
                window_bytes = 0

        now = time.monotonic()
        if now - last_time >= 0.5:
            task.speed = (task.transferred - last_transferred) / (now - last_time)
            last_time = now
            last_transferred = task.transferred
            await db.commit()
            await db.refresh(task)
            await broadcast_progress(task)
        yield chunk

    task.speed = 0
    await db.commit()
    await db.refresh(task)
    await broadcast_progress(task)


async def _safe_disconnect(adapter) -> None:
    try:
        await adapter.disconnect()
    except Exception:
        pass
