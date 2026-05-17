"""
文件搜索服务 — 跨挂载点递归搜索文件名。
支持普通关键词匹配和正则匹配。
"""
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.base import FileInfo
from app.models.mount import Mount
from app.models.user import User
from app.services.mount_permission_service import get_accessible_mount_ids
from app.services.mount_service import get_adapter_for_mount

logger = logging.getLogger("multimount.search")


async def search_files(
    db: AsyncSession,
    user: User,
    query: str,
    use_regex: bool = False,
    mount_ids: list[int] | None = None,
    max_depth: int = 5,
    limit: int = 200,
) -> list[dict]:
    """
    跨挂载点递归搜索文件名。
    返回匹配的文件列表，每项包含文件信息 + 挂载元数据。
    """
    # 编译匹配器
    if use_regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            return []
        def matches(name: str) -> bool:
            return bool(pattern.search(name))
    else:
        q = query.lower()
        def matches(name: str) -> bool:
            return q in name.lower()

    # 获取用户可访问的挂载 ID
    accessible = await get_accessible_mount_ids(db, user)
    if mount_ids:
        accessible &= set(mount_ids)
    if not accessible:
        return []

    # 查询挂载信息
    result = await db.execute(
        select(Mount).where(Mount.id.in_(accessible))
    )
    mounts_db = result.scalars().all()

    # 构建 mount_id → (mount_name, owner_name) 映射
    owner_ids = {m.user_id for m in mounts_db if m.user_id}
    owner_map = {}
    if owner_ids:
        users_result = await db.execute(
            select(User.id, User.username).where(User.id.in_(owner_ids))
        )
        owner_map = {uid: uname for uid, uname in users_result.all()}

    results = []

    for mount in mounts_db:
        if len(results) >= limit:
            break
        try:
            _, adapter = await get_adapter_for_mount(db, mount.id)
            await adapter.connect()
            await _recursive_search(
                adapter, "/", matches, mount.id, mount.name,
                owner_map.get(mount.user_id, ""),
                results, limit, max_depth, 0,
            )
        except Exception as e:
            logger.warning("搜索挂载 %s(%d) 失败: %s", mount.name, mount.id, e)
            continue

    return results[:limit]


async def _recursive_search(
    adapter,
    path: str,
    matches,
    mount_id: int,
    mount_name: str,
    mount_owner: str,
    results: list,
    limit: int,
    max_depth: int,
    current_depth: int,
):
    """递归搜索目录"""
    if len(results) >= limit or current_depth > max_depth:
        return

    try:
        items: list[FileInfo] = await adapter.list_dir(path)
    except Exception:
        return

    for item in items:
        if len(results) >= limit:
            break

        if matches(item.name):
            results.append({
                "name": item.name,
                "path": item.path,
                "is_dir": item.is_dir,
                "size": item.size,
                "modified_at": item.modified_at.isoformat() if item.modified_at else None,
                "mime_type": item.mime_type,
                "mount_id": mount_id,
                "mount_name": mount_name,
                "mount_owner": mount_owner,
            })

        # 递归进入子目录
        if item.is_dir and current_depth < max_depth:
            await _recursive_search(
                adapter, item.path, matches, mount_id, mount_name,
                mount_owner, results, limit, max_depth, current_depth + 1,
            )
