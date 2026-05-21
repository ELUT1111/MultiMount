"""
文件操作服务 — 编排跨协议统一文件操作逻辑。
负责: 路径校验 → 权限检查 → 调用适配器 → 返回结果。
"""
import logging
from pathlib import PurePosixPath
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import FileInfo
from app.core.exceptions import BadRequestException, NotFoundException
from app.services.mount_service import get_adapter_for_mount
from app.services.trash_service import is_trash_path
from app.utils.path_utils import normalize_path

logger = logging.getLogger("multimount.file")

CONFLICT_POLICIES = {"error", "overwrite", "skip", "rename"}


def _split_path(path: str) -> tuple[str, str]:
    normalized = normalize_path(path)
    if normalized == "/":
        return "/", ""
    parent, _, name = normalized.rpartition("/")
    return parent or "/", name


def _rename_candidate(path: str, index: int) -> str:
    parent, name = _split_path(path)
    stem, dot, suffix = name.rpartition(".")
    if dot and stem:
        new_name = f"{stem} ({index}).{suffix}"
    else:
        new_name = f"{name} ({index})"
    return parent.rstrip("/") + "/" + new_name if parent != "/" else "/" + new_name


async def resolve_conflict(db: AsyncSession, mount_id: int, path: str,
                           policy: str = "error") -> tuple[str, bool]:
    """
    解析目标路径冲突。

    返回 (最终路径, 是否应跳过写入)。
    """
    path = normalize_path(path)
    if policy not in CONFLICT_POLICIES:
        raise BadRequestException(f"不支持的冲突策略: {policy}")

    exists = True
    try:
        await get_info(db, mount_id, path)
    except NotFoundException:
        exists = False

    if not exists:
        return path, False
    if policy == "skip":
        return path, True
    if policy == "overwrite":
        await delete_file_permanently(db, mount_id, path)
        return path, False
    if policy == "rename":
        for i in range(1, 1000):
            candidate = _rename_candidate(path, i)
            try:
                await get_info(db, mount_id, candidate)
            except NotFoundException:
                return candidate, False
        raise BadRequestException("无法生成可用的自动重命名路径")

    raise BadRequestException(f"目标已存在: {path}")


async def list_dir(db: AsyncSession, mount_id: int, path: str = "/") -> list[FileInfo]:
    """列出指定挂载点的目录内容"""
    path = normalize_path(path)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        items = await adapter.list_dir(path)
        return [item for item in items if not is_trash_path(item.path)]
    except FileNotFoundError:
        raise NotFoundException(f"目录不存在: {path}")
    except Exception as e:
        logger.error("list_dir 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"列出目录失败: {e}")


async def get_info(db: AsyncSession, mount_id: int, path: str) -> FileInfo:
    """获取文件/目录元数据"""
    path = normalize_path(path)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        return await adapter.get_info(path)
    except FileNotFoundError:
        raise NotFoundException(f"文件不存在: {path}")
    except Exception as e:
        logger.error("get_info 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"获取文件信息失败: {e}")


async def download_file(db: AsyncSession, mount_id: int, path: str) -> AsyncIterator[bytes]:
    """流式下载文件 (返回异步字节迭代器, 由 StreamingResponse 消费)"""
    path = normalize_path(path)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        async for chunk in adapter.download(path):
            yield chunk
    except FileNotFoundError:
        raise NotFoundException(f"文件不存在: {path}")
    except Exception as e:
        logger.error("download 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"下载失败: {e}")


async def download_file_range(
    db: AsyncSession,
    mount_id: int,
    path: str,
    start: int = 0,
    end: int | None = None,
) -> AsyncIterator[bytes]:
    """Stream a byte range without buffering the whole file in memory."""
    if start < 0 or (end is not None and end < start):
        raise BadRequestException("无效的 Range 请求")

    skipped = 0
    emitted = 0
    limit = None if end is None else end - start + 1

    async for chunk in download_file(db, mount_id, path):
        if skipped < start:
            skip = min(start - skipped, len(chunk))
            chunk = chunk[skip:]
            skipped += skip
            if not chunk:
                continue

        if limit is not None:
            remaining = limit - emitted
            if remaining <= 0:
                break
            chunk = chunk[:remaining]

        emitted += len(chunk)
        yield chunk

        if limit is not None and emitted >= limit:
            break


async def upload_file(db: AsyncSession, mount_id: int, path: str,
                      data: AsyncIterator[bytes], size: int | None = None,
                      conflict_policy: str = "error") -> FileInfo:
    """上传文件到指定挂载点"""
    path, should_skip = await resolve_conflict(db, mount_id, path, conflict_policy)
    if should_skip:
        return await get_info(db, mount_id, path)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        await adapter.upload(path, data, size)
        info = await adapter.get_info(path)
        from app.services import search_service
        await search_service.refresh_path_index(db, mount_id, path, recursive=False)
        return info
    except Exception as e:
        logger.error("upload 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"上传失败: {e}")


async def delete_file_permanently(db: AsyncSession, mount_id: int, path: str) -> None:
    """删除文件或目录"""
    path = normalize_path(path)
    if path == "/":
        raise BadRequestException("不能删除根目录")
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        await adapter.delete(path)
        from app.services import search_service
        await search_service.remove_path_index(db, mount_id, path)
    except FileNotFoundError:
        raise NotFoundException(f"文件不存在: {path}")
    except Exception as e:
        logger.error("delete 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"删除失败: {e}")


async def delete_file(db: AsyncSession, mount_id: int, path: str, user=None) -> None:
    """Move a file or directory into the recycle bin."""
    from app.services import trash_service

    await trash_service.trash_file(db, mount_id, path, user=user)
    from app.services import search_service
    await search_service.remove_path_index(db, mount_id, path)


async def make_directory(db: AsyncSession, mount_id: int, path: str) -> FileInfo:
    """创建目录"""
    path = normalize_path(path)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        await adapter.mkdir(path)
        info = await adapter.get_info(path)
        from app.services import search_service
        await search_service.refresh_path_index(db, mount_id, path, recursive=False)
        return info
    except Exception as e:
        logger.error("mkdir 失败 mount=%d path=%s: %s", mount_id, path, e)
        raise BadRequestException(f"创建目录失败: {e}")


async def move_file(db: AsyncSession, mount_id: int, src: str, dst: str,
                    conflict_policy: str = "error") -> FileInfo:
    """移动/重命名文件或目录"""
    src = normalize_path(src)
    dst = normalize_path(dst)
    dst, should_skip = await resolve_conflict(db, mount_id, dst, conflict_policy)
    if should_skip:
        return await get_info(db, mount_id, dst)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        await adapter.move(src, dst)
        info = await adapter.get_info(dst)
        from app.services import search_service
        await search_service.remove_path_index(db, mount_id, src)
        await search_service.refresh_path_index(db, mount_id, dst)
        return info
    except FileNotFoundError:
        raise NotFoundException(f"源文件不存在: {src}")
    except Exception as e:
        logger.error("move 失败 mount=%d %s -> %s: %s", mount_id, src, dst, e)
        raise BadRequestException(f"移动失败: {e}")


async def copy_file(db: AsyncSession, mount_id: int, src: str, dst: str,
                    conflict_policy: str = "error") -> FileInfo:
    """复制文件或目录"""
    src = normalize_path(src)
    dst = normalize_path(dst)
    dst, should_skip = await resolve_conflict(db, mount_id, dst, conflict_policy)
    if should_skip:
        return await get_info(db, mount_id, dst)
    _, adapter = await get_adapter_for_mount(db, mount_id)
    try:
        await adapter.connect()
        await adapter.copy(src, dst)
        info = await adapter.get_info(dst)
        from app.services import search_service
        await search_service.refresh_path_index(db, mount_id, dst)
        return info
    except FileNotFoundError:
        raise NotFoundException(f"源文件不存在: {src}")
    except Exception as e:
        logger.error("copy 失败 mount=%d %s -> %s: %s", mount_id, src, dst, e)
        raise BadRequestException(f"复制失败: {e}")


async def iter_files_recursive(
    db: AsyncSession,
    mount_id: int,
    path: str,
    *,
    base_name: str | None = None,
) -> AsyncIterator[tuple[str, FileInfo]]:
    """Yield (relative archive path, info) for a file or directory tree."""
    root = normalize_path(path)
    info = await get_info(db, mount_id, root)
    root_name = base_name or info.name or PurePosixPath(root).name or "root"
    if not info.is_dir:
        yield root_name, info
        return

    async def _walk(current_path: str, relative_prefix: str):
        for item in await list_dir(db, mount_id, current_path):
            if is_trash_path(item.path):
                continue
            relative = f"{relative_prefix}/{item.name}" if relative_prefix else item.name
            if item.is_dir:
                async for child in _walk(item.path, relative):
                    yield child
            else:
                yield relative, item

    async for child in _walk(root, root_name):
        yield child


async def directory_stats(db: AsyncSession, mount_id: int, path: str) -> dict:
    """Return recursive directory size and item counts."""
    root = normalize_path(path)
    info = await get_info(db, mount_id, root)
    if not info.is_dir:
        return {"path": root, "total_size": info.size, "file_count": 1, "dir_count": 0}

    stats = {"path": root, "total_size": 0, "file_count": 0, "dir_count": 0}

    async def _walk(current_path: str):
        for item in await list_dir(db, mount_id, current_path):
            if item.is_dir:
                stats["dir_count"] += 1
                await _walk(item.path)
            else:
                stats["file_count"] += 1
                stats["total_size"] += item.size or 0

    await _walk(root)
    return stats
