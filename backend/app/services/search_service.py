"""
File search service with a persisted metadata index.

The index keeps search responsive for common filters while preserving a live
recursive fallback for mounts that have not been indexed yet.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Callable

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import FileInfo
from app.models.file_index import FileIndex
from app.models.mount import Mount
from app.models.user import User
from app.services.trash_service import is_trash_path
from app.services.mount_permission_service import get_accessible_mount_ids
from app.services.mount_service import get_adapter_for_mount
from app.utils.path_utils import normalize_path

logger = logging.getLogger("multimount.search")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
TEXT_EXTS = {".txt", ".md", ".json", ".xml", ".csv", ".log", ".yaml", ".yml", ".py", ".js", ".ts", ".vue", ".css", ".html"}
OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}


def classify_file(name: str, mime_type: str | None, is_dir: bool) -> tuple[str, str]:
    if is_dir:
        return "directory", ""
    ext = PurePosixPath(name).suffix.lower()
    mime = (mime_type or "").lower()
    if mime.startswith("image/") or ext in IMAGE_EXTS:
        return "image", ext
    if mime.startswith("video/") or ext in VIDEO_EXTS:
        return "video", ext
    if mime.startswith("audio/") or ext in AUDIO_EXTS:
        return "audio", ext
    if mime == "application/pdf" or ext == ".pdf":
        return "pdf", ext
    if ext in OFFICE_EXTS:
        return "office", ext
    if mime.startswith("text/") or mime in {"application/json", "application/xml"} or ext in TEXT_EXTS:
        return "text", ext
    return "other", ext


def _parent_path(path: str) -> str:
    normalized = normalize_path(path)
    if normalized == "/":
        return "/"
    parent = normalized.rpartition("/")[0]
    return parent or "/"


def _row_to_result(row: FileIndex) -> dict:
    return {
        "name": row.name,
        "path": row.path,
        "is_dir": row.is_dir,
        "size": row.size,
        "modified_at": row.modified_at.isoformat() if row.modified_at else None,
        "created_at": row.file_created_at.isoformat() if row.file_created_at else None,
        "mime_type": row.mime_type,
        "mount_id": row.mount_id,
        "mount_name": row.mount_name,
        "mount_owner": row.mount_owner,
        "file_type": row.file_type,
        "extension": row.extension,
        "indexed": True,
    }


def _make_matcher(query: str, use_regex: bool) -> Callable[[str], bool] | None:
    if use_regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            return None
        return lambda name: bool(pattern.search(name))
    q = query.lower()
    return lambda name: q in name.lower()


async def refresh_index(
    db: AsyncSession,
    user: User,
    mount_ids: list[int] | None = None,
    max_depth: int = 10,
) -> dict:
    accessible = await get_accessible_mount_ids(db, user)
    if mount_ids:
        accessible &= set(mount_ids)
    if not accessible:
        return {"indexed": 0, "mounts": 0}

    mounts_result = await db.execute(select(Mount).where(Mount.id.in_(accessible)))
    mounts = list(mounts_result.scalars().all())
    owner_ids = {mount.user_id for mount in mounts if mount.user_id}
    owner_map = {}
    if owner_ids:
        owner_result = await db.execute(select(User.id, User.username).where(User.id.in_(owner_ids)))
        owner_map = {uid: username for uid, username in owner_result.all()}

    total = 0
    now = datetime.now(timezone.utc)
    for mount in mounts:
        await db.execute(delete(FileIndex).where(FileIndex.mount_id == mount.id))
        await db.flush()
        try:
            _, adapter = await get_adapter_for_mount(db, mount.id)
            await adapter.connect()
            total += await _index_mount_tree(
                db,
                adapter,
                mount,
                owner_map.get(mount.user_id, ""),
                now,
                max_depth,
            )
        except Exception as exc:
            logger.warning("index mount failed mount=%s(%d): %s", mount.name, mount.id, exc)
    await db.commit()
    return {"indexed": total, "mounts": len(mounts)}


async def refresh_all_indexes(db: AsyncSession, max_depth: int = 10) -> dict:
    """Refresh indexes for every mount; intended for startup and scheduled jobs."""
    mounts_result = await db.execute(select(Mount))
    mounts = list(mounts_result.scalars().all())
    owner_ids = {mount.user_id for mount in mounts if mount.user_id}
    owner_map = {}
    if owner_ids:
        owner_result = await db.execute(select(User.id, User.username).where(User.id.in_(owner_ids)))
        owner_map = {uid: username for uid, username in owner_result.all()}

    total = 0
    now = datetime.now(timezone.utc)
    for mount in mounts:
        await db.execute(delete(FileIndex).where(FileIndex.mount_id == mount.id))
        await db.flush()
        try:
            _, adapter = await get_adapter_for_mount(db, mount.id)
            await adapter.connect()
            total += await _index_mount_tree(
                db,
                adapter,
                mount,
                owner_map.get(mount.user_id, ""),
                now,
                max_depth,
            )
        except Exception as exc:
            logger.warning("scheduled index mount failed mount=%s(%d): %s", mount.name, mount.id, exc)
    await db.commit()
    return {"indexed": total, "mounts": len(mounts)}


async def _index_mount_tree(
    db: AsyncSession,
    adapter,
    mount: Mount,
    mount_owner: str,
    indexed_at: datetime,
    max_depth: int,
) -> int:
    count = 0

    async def walk(path: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth:
            return
        try:
            items: list[FileInfo] = await adapter.list_dir(path)
        except Exception:
            return
        for item in items:
            if is_trash_path(item.path):
                continue
            file_type, extension = classify_file(item.name, item.mime_type, item.is_dir)
            db.add(FileIndex(
                mount_id=mount.id,
                owner_id=mount.user_id,
                mount_name=mount.name,
                mount_owner=mount_owner,
                name=item.name,
                path=normalize_path(item.path),
                parent_path=_parent_path(item.path),
                is_dir=item.is_dir,
                size=item.size or 0,
                mime_type=item.mime_type,
                extension=extension,
                file_type=file_type,
                modified_at=item.modified_at,
                file_created_at=item.created_at,
                indexed_at=indexed_at,
            ))
            count += 1
            if item.is_dir:
                await walk(item.path, depth + 1)

    await walk("/", 0)
    return count


async def refresh_path_index(
    db: AsyncSession,
    mount_id: int,
    path: str,
    recursive: bool = True,
) -> int:
    """Incrementally refresh one path and its children in the search index."""
    normalized = normalize_path(path)
    prefix = normalized.rstrip("/") + "/"
    await db.execute(
        delete(FileIndex).where(
            FileIndex.mount_id == mount_id,
            or_(FileIndex.path == normalized, FileIndex.path.like(f"{prefix}%")),
        )
    )
    await db.flush()

    mount_result = await db.execute(select(Mount).where(Mount.id == mount_id))
    mount = mount_result.scalar_one_or_none()
    if not mount:
        return 0

    mount_owner = ""
    if mount.user_id:
        owner_result = await db.execute(select(User.username).where(User.id == mount.user_id))
        mount_owner = owner_result.scalar_one_or_none() or ""

    try:
        _, adapter = await get_adapter_for_mount(db, mount_id)
        await adapter.connect()
        root = await adapter.get_info(normalized)
    except Exception as exc:
        logger.debug("incremental index skipped mount=%d path=%s: %s", mount_id, normalized, exc)
        return 0

    indexed_at = datetime.now(timezone.utc)
    count = 0

    async def add_item(item: FileInfo) -> None:
        nonlocal count
        if is_trash_path(item.path):
            return
        file_type, extension = classify_file(item.name, item.mime_type, item.is_dir)
        db.add(FileIndex(
            mount_id=mount.id,
            owner_id=mount.user_id,
            mount_name=mount.name,
            mount_owner=mount_owner,
            name=item.name,
            path=normalize_path(item.path),
            parent_path=_parent_path(item.path),
            is_dir=item.is_dir,
            size=item.size or 0,
            mime_type=item.mime_type,
            extension=extension,
            file_type=file_type,
            modified_at=item.modified_at,
            file_created_at=item.created_at,
            indexed_at=indexed_at,
        ))
        count += 1

    async def walk_dir(dir_path: str) -> None:
        try:
            children = await adapter.list_dir(dir_path)
        except Exception:
            return
        for child in children:
            await add_item(child)
            if recursive and child.is_dir:
                await walk_dir(child.path)

    await add_item(root)
    if recursive and root.is_dir:
        await walk_dir(root.path)
    await db.flush()
    return count


async def remove_path_index(db: AsyncSession, mount_id: int, path: str) -> None:
    normalized = normalize_path(path)
    prefix = normalized.rstrip("/") + "/"
    await db.execute(
        delete(FileIndex).where(
            FileIndex.mount_id == mount_id,
            or_(FileIndex.path == normalized, FileIndex.path.like(f"{prefix}%")),
        )
    )
    await db.flush()


async def search_files(
    db: AsyncSession,
    user: User,
    query: str,
    use_regex: bool = False,
    mount_ids: list[int] | None = None,
    max_depth: int = 5,
    limit: int = 200,
    size_min: int | None = None,
    size_max: int | None = None,
    modified_from: datetime | None = None,
    modified_to: datetime | None = None,
    file_type: str | None = None,
    extension: str | None = None,
    path_prefix: str | None = None,
    owner: str | None = None,
) -> list[dict]:
    matcher = _make_matcher(query, use_regex)
    if matcher is None:
        return []

    accessible = await get_accessible_mount_ids(db, user)
    if mount_ids:
        accessible &= set(mount_ids)
    if not accessible:
        return []

    indexed_count = await db.scalar(select(func.count(FileIndex.id)).where(FileIndex.mount_id.in_(accessible)))
    if indexed_count:
        return await _search_index(
            db,
            matcher,
            query,
            use_regex,
            accessible,
            limit,
            size_min,
            size_max,
            modified_from,
            modified_to,
            file_type,
            extension,
            path_prefix,
            owner,
        )

    return await _search_live(db, user, matcher, accessible, max_depth, limit)


async def _search_index(
    db: AsyncSession,
    matcher: Callable[[str], bool],
    query_text: str,
    use_regex: bool,
    accessible: set[int],
    limit: int,
    size_min: int | None,
    size_max: int | None,
    modified_from: datetime | None,
    modified_to: datetime | None,
    file_type: str | None,
    extension: str | None,
    path_prefix: str | None,
    owner: str | None,
) -> list[dict]:
    stmt = select(FileIndex).where(FileIndex.mount_id.in_(accessible))
    if not use_regex:
        like = f"%{query_text.lower()}%"
        stmt = stmt.where(or_(func.lower(FileIndex.name).like(like), func.lower(FileIndex.path).like(like)))
    if size_min is not None:
        stmt = stmt.where(FileIndex.size >= size_min)
    if size_max is not None:
        stmt = stmt.where(FileIndex.size <= size_max)
    if modified_from is not None:
        stmt = stmt.where(FileIndex.modified_at >= modified_from)
    if modified_to is not None:
        stmt = stmt.where(FileIndex.modified_at <= modified_to)
    if file_type:
        stmt = stmt.where(FileIndex.file_type == file_type)
    if extension:
        ext = extension.lower()
        if ext and not ext.startswith("."):
            ext = "." + ext
        stmt = stmt.where(FileIndex.extension == ext)
    if path_prefix:
        prefix = normalize_path(path_prefix).rstrip("/")
        stmt = stmt.where(FileIndex.path.like(f"{prefix}%"))
    if owner:
        stmt = stmt.where(FileIndex.mount_owner == owner)

    stmt = stmt.order_by(FileIndex.is_dir.desc(), FileIndex.name.asc()).limit(limit * 3 if use_regex else limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    if use_regex:
        rows = [row for row in rows if matcher(row.name) or matcher(row.path)][:limit]
    return [_row_to_result(row) for row in rows[:limit]]


async def _search_live(
    db: AsyncSession,
    user: User,
    matcher: Callable[[str], bool],
    accessible: set[int],
    max_depth: int,
    limit: int,
) -> list[dict]:
    result = await db.execute(select(Mount).where(Mount.id.in_(accessible)))
    mounts_db = result.scalars().all()
    owner_ids = {m.user_id for m in mounts_db if m.user_id}
    owner_map = {}
    if owner_ids:
        users_result = await db.execute(select(User.id, User.username).where(User.id.in_(owner_ids)))
        owner_map = {uid: uname for uid, uname in users_result.all()}

    results = []
    for mount in mounts_db:
        if len(results) >= limit:
            break
        try:
            _, adapter = await get_adapter_for_mount(db, mount.id)
            await adapter.connect()
            await _recursive_search(
                adapter, "/", matcher, mount.id, mount.name,
                owner_map.get(mount.user_id, ""),
                results, limit, max_depth, 0,
            )
        except Exception as e:
            logger.warning("search mount failed %s(%d): %s", mount.name, mount.id, e)
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
    if len(results) >= limit or current_depth > max_depth:
        return
    try:
        items: list[FileInfo] = await adapter.list_dir(path)
    except Exception:
        return

    for item in items:
        if len(results) >= limit:
            break
        if is_trash_path(item.path):
            continue
        file_type, extension = classify_file(item.name, item.mime_type, item.is_dir)
        if matches(item.name):
            results.append({
                "name": item.name,
                "path": item.path,
                "is_dir": item.is_dir,
                "size": item.size,
                "modified_at": item.modified_at.isoformat() if item.modified_at else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "mime_type": item.mime_type,
                "mount_id": mount_id,
                "mount_name": mount_name,
                "mount_owner": mount_owner,
                "file_type": file_type,
                "extension": extension,
                "indexed": False,
            })
        if item.is_dir and current_depth < max_depth:
            await _recursive_search(
                adapter, item.path, matches, mount_id, mount_name,
                mount_owner, results, limit, max_depth, current_depth + 1,
            )
