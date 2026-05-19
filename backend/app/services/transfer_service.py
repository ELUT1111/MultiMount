"""
Transfer task service.

Creates background transfer jobs and streams data between mount adapters while
keeping progress in the database and over WebSocket.
"""
import asyncio
import logging
import time
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.transfer_task import TransferTask
from app.services import file_service
from app.services.mount_service import get_adapter_for_mount
from app.utils.path_utils import normalize_path

logger = logging.getLogger("multimount.transfer")

DEFAULT_CHUNK_SIZE = 64 * 1024
TRANSFER_TYPES = {"upload", "download", "copy", "move"}

_ws_connections: dict[int, list] = {}


class TransferPaused(Exception):
    """Raised internally when a task is paused or cancelled."""


def register_ws(user_id: int, ws):
    _ws_connections.setdefault(user_id, []).append(ws)


def unregister_ws(user_id: int, ws):
    conns = _ws_connections.get(user_id, [])
    if ws in conns:
        conns.remove(ws)


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
) -> TransferTask:
    if task_type not in TRANSFER_TYPES:
        raise BadRequestException(f"不支持的传输任务类型: {task_type}")
    if conflict_policy not in file_service.CONFLICT_POLICIES:
        raise BadRequestException(f"不支持的冲突策略: {conflict_policy}")

    source_mount_id = source_mount_id or mount_id
    target_mount_id = target_mount_id or mount_id
    if task_type in ("copy", "move") and (not source_mount_id or not target_mount_id):
        raise BadRequestException("跨挂载传输需要 source_mount_id 和 target_mount_id")
    if task_type in ("upload", "download") and not mount_id:
        raise BadRequestException("上传/下载传输任务需要 mount_id")

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
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(_execute_transfer(task.id))
    return task


async def pause_task(db: AsyncSession, task_id: int) -> TransferTask:
    task = await get_task(db, task_id)
    if task.status not in ("pending", "running"):
        raise BadRequestException(f"任务状态 {task.status} 不支持暂停")
    task.status = "paused"
    task.speed = 0
    await db.commit()
    await db.refresh(task)
    await broadcast_progress(task)
    return task


async def resume_task(db: AsyncSession, task_id: int) -> TransferTask:
    task = await get_task(db, task_id)
    if task.status not in ("paused", "pending"):
        raise BadRequestException(f"任务状态 {task.status} 不支持恢复")
    task.status = "pending"
    task.transferred = 0
    task.speed = 0
    await db.commit()
    await db.refresh(task)
    asyncio.create_task(_execute_transfer(task.id))
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


async def _execute_transfer(task_id: int):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        try:
            task = await get_task(db, task_id)
            if task.status in ("completed", "failed"):
                return

            task.status = "running"
            task.error_message = None
            task.speed = 0
            await db.commit()
            await db.refresh(task)
            await broadcast_progress(task)

            if task.type in ("copy", "move"):
                await _execute_mount_transfer(db, task)
            else:
                raise BadRequestException("队列式上传/下载已由普通上传和分片上传接口处理")

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
            await db.rollback()
            logger.info("transfer paused: id=%d", task_id)
        except Exception as exc:
            logger.error("transfer failed: id=%d error=%s", task_id, exc)
            try:
                task = await get_task(db, task_id)
                task.status = "failed"
                task.speed = 0
                task.error_message = str(exc)[:500]
                await db.commit()
                await db.refresh(task)
                await broadcast_progress(task)
            except Exception:
                await db.rollback()


async def _execute_mount_transfer(db: AsyncSession, task: TransferTask) -> None:
    source_mount_id = task.source_mount_id
    target_mount_id = task.target_mount_id
    if not source_mount_id or not target_mount_id:
        raise BadRequestException("传输任务缺少源或目标挂载点")

    source_path = normalize_path(task.source_path)
    target_path = normalize_path(task.target_path)
    source_info = await file_service.get_info(db, source_mount_id, source_path)
    if source_info.is_dir and source_mount_id != target_mount_id:
        raise BadRequestException("暂不支持跨挂载传输目录")

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
            task.transferred = source_info.size
            await db.commit()
            await broadcast_progress(task)
            return

        await target_adapter.upload(
            final_target_path,
            _download_with_progress(db, task, source_adapter.download(source_path)),
            source_info.size,
        )
        if task.type == "move":
            await source_adapter.delete(source_path)
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


async def _download_with_progress(db: AsyncSession, task: TransferTask,
                                  chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    last_time = time.monotonic()
    last_transferred = task.transferred

    async for chunk in chunks:
        await db.refresh(task)
        if task.status in ("paused", "failed"):
            task.speed = 0
            await db.commit()
            await broadcast_progress(task)
            raise TransferPaused()

        task.transferred += len(chunk)
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
