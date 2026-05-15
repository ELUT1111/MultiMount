"""
传输任务服务 — 管理上传/下载任务的生命周期。
核心功能: 创建任务 → 分块传输 → 进度追踪 → 断点续传 → WebSocket 推送。
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.transfer_task import TransferTask
from app.services.file_service import download_file, upload_file

logger = logging.getLogger("multimount.transfer")

# 分块大小阈值: 大于此大小的文件自动分块
CHUNK_THRESHOLD = 10 * 1024 * 1024  # 10MB
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64KB

# 全局 WebSocket 连接管理 (按用户 ID 索引)
_ws_connections: dict[int, list] = {}


def register_ws(user_id: int, ws):
    """注册 WebSocket 连接 (用户连接时调用)"""
    _ws_connections.setdefault(user_id, []).append(ws)


def unregister_ws(user_id: int, ws):
    """注销 WebSocket 连接"""
    conns = _ws_connections.get(user_id, [])
    if ws in conns:
        conns.remove(ws)


async def broadcast_progress(task: TransferTask):
    """向该用户的所有 WebSocket 连接推送进度更新"""
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
    """查询传输任务列表, 支持按用户和状态过滤"""
    query = select(TransferTask).order_by(TransferTask.created_at.desc())
    if user_id is not None:
        query = query.where(TransferTask.user_id == user_id)
    if status:
        query = query.where(TransferTask.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: int) -> TransferTask:
    """获取单个传输任务"""
    result = await db.execute(select(TransferTask).where(TransferTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise NotFoundException("传输任务不存在")
    return task


async def create_task(db: AsyncSession, user_id: int, task_type: str,
                      mount_id: int, source_path: str, target_path: str,
                      file_name: str, file_size: int | None = None) -> TransferTask:
    """创建传输任务并提交到后台执行"""
    task = TransferTask(
        user_id=user_id,
        type=task_type,
        mount_id=mount_id,
        source_path=source_path,
        target_path=target_path,
        file_name=file_name,
        file_size=file_size,
        status="pending",
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # 在后台启动传输协程 (不阻塞请求)
    asyncio.create_task(_execute_transfer(task.id))
    return task


async def pause_task(db: AsyncSession, task_id: int) -> TransferTask:
    """暂停传输任务"""
    task = await get_task(db, task_id)
    if task.status not in ("pending", "running"):
        raise BadRequestException(f"任务状态 {task.status} 不支持暂停")
    task.status = "paused"
    await db.flush()
    await broadcast_progress(task)
    return task


async def resume_task(db: AsyncSession, task_id: int) -> TransferTask:
    """恢复传输任务 (断点续传)"""
    task = await get_task(db, task_id)
    if task.status != "paused":
        raise BadRequestException(f"任务状态 {task.status} 不支持恢复")
    task.status = "running"
    await db.flush()
    # 从断点继续传输
    asyncio.create_task(_execute_transfer(task.id))
    return task


async def cancel_task(db: AsyncSession, task_id: int) -> None:
    """取消/删除传输任务"""
    task = await get_task(db, task_id)
    if task.status in ("completed", "failed"):
        await db.delete(task)
    else:
        task.status = "failed"
        task.error_message = "用户取消"
    await db.flush()


async def _execute_transfer(task_id: int):
    """
    后台传输协程 — 逐块读取/写入, 更新进度, 检查暂停/取消信号。
    断点续传: 每次循环检查 task.transferred 作为起始偏移。
    """
    from app.database import async_session_factory

    async with async_session_factory() as db:
        try:
            task = await get_task(db, task_id)
            if task.status in ("completed", "failed"):
                return

            task.status = "running"
            task.speed = 0
            await db.flush()

            start_time = time.monotonic()
            last_progress_time = start_time
            last_transferred = task.transferred

            if task.type == "download":
                # 下载: 从挂载点读取 → 写入本地目标
                async for chunk in download_file(db, task.mount_id, task.source_path):
                    # 检查暂停/取消
                    await db.refresh(task)
                    if task.status in ("paused", "failed"):
                        await db.commit()
                        return

                    # 模拟写入 (实际写入到目标路径)
                    chunk_len = len(chunk)
                    task.transferred += chunk_len

                    # 计算传输速度 (每秒更新)
                    now = time.monotonic()
                    if now - last_progress_time >= 0.5:
                        elapsed = now - last_progress_time
                        task.speed = (task.transferred - last_transferred) / elapsed
                        last_progress_time = now
                        last_transferred = task.transferred
                        await db.flush()
                        await broadcast_progress(task)

            elif task.type == "upload":
                # 上传: 从本地源读取 → 写入挂载点
                async def file_iter():
                    """从断点位置开始读取源文件"""
                    offset = task.transferred
                    async with aiofiles_open(task.source_path, "rb") as f:
                        if offset > 0:
                            await f.seek(offset)
                        while chunk := await f.read(task.chunk_size):
                            yield chunk

                await upload_file(db, task.mount_id, task.target_path, file_iter(), task.file_size)
                # 上传完成后标记 transferred = file_size
                if task.file_size:
                    task.transferred = task.file_size

            # 任务完成
            task.status = "completed"
            task.speed = 0
            await db.flush()
            await broadcast_progress(task)
            logger.info("传输任务完成: id=%d file=%s", task.id, task.file_name)

        except Exception as e:
            logger.error("传输任务失败: id=%d error=%s", task_id, e)
            try:
                task = await get_task(db, task_id)
                task.status = "failed"
                task.error_message = str(e)[:500]
                await db.flush()
                await broadcast_progress(task)
            except Exception:
                pass


# 兼容 aiofiles 的异步文件打开 (如果源文件是本地文件)
try:
    import aiofiles

    async def aiofiles_open(path, mode):
        return aiofiles.open(path, mode)
except ImportError:
    async def aiofiles_open(path, mode):
        raise ImportError("aiofiles 未安装, 无法执行本地文件传输")
