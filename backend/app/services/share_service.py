"""
分享链接服务 — 创建、查询、验证、删除分享链接。
"""
import secrets
import hashlib
import hmac
import json
import mimetypes
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import FileInfo
from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.operation_log import OperationLog
from app.models.share_link import ShareLink
from app.utils.path_utils import normalize_path

settings = get_settings()
POLICY_FILE = Path("data/share_policy.json")
SNAPSHOT_ROOT = Path("data/share_snapshots")
DEFAULT_POLICY = {
    "enabled": True,
    "force_access_code": False,
    "default_expires_hours": 0,
    "max_access_per_hour": 0,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_expired(expires_at: datetime | None, now: datetime | None = None) -> bool:
    expires_at = as_aware_utc(expires_at)
    if expires_at is None:
        return False
    now = as_aware_utc(now) or utc_now()
    return expires_at < now


def _snapshot_key(mount_id: int, file_path: str) -> str:
    source = f"{mount_id}:{normalize_path(file_path)}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _snapshot_relative_path(mount_id: int, file_path: str) -> str:
    return f"sources/{mount_id}/{_snapshot_key(mount_id, file_path)}/content"


def _snapshot_abs_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    root = SNAPSHOT_ROOT.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise BadRequestException("分享快照路径无效")
    return target


def _snapshot_file_info(path: Path, root: Path) -> FileInfo:
    stat = path.stat()
    if path == root:
        rel_path = "/"
        name = path.name
    else:
        rel = str(path.relative_to(root)).replace("\\", "/")
        rel_path = "/" + rel
        name = path.name
    return FileInfo(
        name=name,
        path=rel_path,
        is_dir=path.is_dir(),
        size=stat.st_size if path.is_file() else 0,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
        mime_type=mimetypes.guess_type(path.name)[0] if path.is_file() else None,
        permissions=None,
    )


def _safe_snapshot_child(root: Path, path: str) -> Path:
    cleaned = normalize_path(path).lstrip("/")
    target = (root / cleaned).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        raise BadRequestException("分享目录路径无效")
    return target


async def _write_stream_to_path(data: AsyncIterator[bytes], target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    async with aiofiles.open(target, "wb") as f:
        async for chunk in data:
            total += len(chunk)
            await f.write(chunk)
    return total


async def create_snapshot(db: AsyncSession, mount_id: int, file_path: str) -> dict:
    """Copy the current source file or directory into the local share snapshot."""
    from app.services import file_service

    file_path = normalize_path(file_path)
    info = await file_service.get_info(db, mount_id, file_path)
    snapshot_path = _snapshot_relative_path(mount_id, file_path)
    content = _snapshot_abs_path(snapshot_path)
    if content is None:
        raise BadRequestException("分享快照路径无效")
    snapshot_dir = content.parent
    staging_dir = snapshot_dir.with_name(f"{snapshot_dir.name}.tmp-{secrets.token_urlsafe(8)}")
    staging_content = staging_dir / "content"

    total_size = 0
    try:
        if info.is_dir:
            staging_content.mkdir(parents=True, exist_ok=True)

            async def _copy_dir(current_source: str, current_target: Path) -> None:
                nonlocal total_size
                current_target.mkdir(parents=True, exist_ok=True)
                for item in await file_service.list_dir(db, mount_id, current_source):
                    target_child = current_target / item.name
                    if item.is_dir:
                        await _copy_dir(item.path, target_child)
                    else:
                        total_size += await _write_stream_to_path(
                            file_service.download_file(db, mount_id, item.path),
                            target_child,
                        )

            await _copy_dir(file_path, staging_content)
        else:
            total_size = await _write_stream_to_path(
                file_service.download_file(db, mount_id, file_path),
                staging_content,
            )
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        staging_dir.replace(snapshot_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return {
        "file_name": info.name,
        "is_dir": info.is_dir,
        "file_size": info.size,
        "mime_type": info.mime_type,
        "snapshot_path": snapshot_path,
        "snapshot_size": total_size,
    }


def snapshot_exists(link: ShareLink) -> bool:
    path = _snapshot_abs_path(link.snapshot_path)
    return bool(path and path.exists())


def snapshot_info(link: ShareLink) -> FileInfo | None:
    path = _snapshot_abs_path(link.snapshot_path)
    if not path or not path.exists():
        return None
    return FileInfo(
        name=link.file_name or path.name,
        path=link.file_path,
        is_dir=bool(link.is_dir),
        size=link.file_size or link.snapshot_size or 0,
        modified_at=link.created_at,
        created_at=link.created_at,
        mime_type=link.mime_type,
        permissions=None,
    )


def _snapshot_metadata_from_link(link: ShareLink) -> dict:
    return {
        "file_name": link.file_name,
        "is_dir": link.is_dir,
        "file_size": link.file_size or 0,
        "mime_type": link.mime_type,
        "snapshot_path": link.snapshot_path,
        "snapshot_size": link.snapshot_size or 0,
    }


async def reusable_snapshot(db: AsyncSession, mount_id: int, file_path: str) -> dict | None:
    """Return an existing active snapshot for the same source file, if one is usable."""
    normalized_path = normalize_path(file_path)
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.mount_id == mount_id)
        .where(ShareLink.file_path == normalized_path)
        .where(ShareLink.is_active == True)
        .where(ShareLink.snapshot_path.is_not(None))
    )
    now = utc_now()
    for link in result.scalars().all():
        if link.mount_id != mount_id:
            continue
        if normalize_path(link.file_path) != normalized_path:
            continue
        if not link.is_active or not link.snapshot_path:
            continue
        if is_expired(link.expires_at, now):
            continue
        if snapshot_exists(link):
            return _snapshot_metadata_from_link(link)
    return None


async def ensure_share_snapshot(db: AsyncSession, mount_id: int, file_path: str) -> dict:
    snapshot = await reusable_snapshot(db, mount_id, file_path)
    if snapshot:
        return snapshot
    return await create_snapshot(db, mount_id, file_path)


def list_snapshot_dir(link: ShareLink, path: str = "/") -> list[FileInfo]:
    root = _snapshot_abs_path(link.snapshot_path)
    if not root or not root.exists():
        raise NotFoundException("分享快照不存在")
    if not root.is_dir():
        raise BadRequestException("该分享不是目录")
    target = _safe_snapshot_child(root, path)
    if not target.exists() or not target.is_dir():
        raise NotFoundException(f"目录不存在: {path}")
    return [_snapshot_file_info(child, root) for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))]


def write_snapshot_zip(link: ShareLink, tmp_path: str) -> int:
    root = _snapshot_abs_path(link.snapshot_path)
    if not root or not root.exists():
        raise NotFoundException("分享快照不存在")
    if not root.is_dir():
        raise BadRequestException("该分享不是目录")

    base_name = link.file_name or "share"
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for child in sorted(root.rglob("*")):
            if child.is_dir():
                continue
            relative = child.relative_to(root)
            zf.write(child, f"{base_name}/{relative.as_posix()}")
    return Path(tmp_path).stat().st_size


async def stream_snapshot_file(link: ShareLink) -> AsyncIterator[bytes]:
    path = _snapshot_abs_path(link.snapshot_path)
    if not path or not path.exists() or not path.is_file():
        raise NotFoundException("分享快照不存在")
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(64 * 1024):
            yield chunk


def _snapshot_dir(snapshot_path: str | None) -> Path | None:
    path = _snapshot_abs_path(snapshot_path)
    if not path:
        return None
    snapshot_dir = path.parent if path.name == "content" else path
    if snapshot_dir.name == "content":
        snapshot_dir = snapshot_dir.parent
    return snapshot_dir


def delete_snapshot_path(snapshot_path: str | None) -> None:
    snapshot_dir = _snapshot_dir(snapshot_path)
    if not snapshot_dir:
        return
    shutil.rmtree(snapshot_dir, ignore_errors=True)


async def snapshot_has_references(db: AsyncSession, snapshot_path: str, current_link: ShareLink | None = None) -> bool:
    result = await db.execute(select(ShareLink).where(ShareLink.snapshot_path == snapshot_path))
    current_id = getattr(current_link, "id", None)
    for link in result.scalars().all():
        if link is current_link:
            continue
        if current_id is not None and getattr(link, "id", None) == current_id:
            continue
        if getattr(link, "snapshot_path", None) == snapshot_path:
            return True
    return False


async def release_snapshot(db: AsyncSession, link: ShareLink, *, deactivate: bool = False) -> None:
    snapshot_path = link.snapshot_path
    link.snapshot_path = None
    link.snapshot_size = 0
    if deactivate:
        link.is_active = False
    if snapshot_path and not await snapshot_has_references(db, snapshot_path, link):
        delete_snapshot_path(snapshot_path)


async def deactivate_with_snapshot_cleanup(db: AsyncSession, link: ShareLink) -> None:
    await release_snapshot(db, link, deactivate=True)


def _path_contains(parent: str, child: str) -> bool:
    parent = normalize_path(parent)
    child = normalize_path(child)
    return child == parent or child.startswith(parent.rstrip("/") + "/")


async def refresh_share_snapshot(db: AsyncSession, link: ShareLink) -> bool:
    """Rebuild one share snapshot from its current source path."""
    try:
        snapshot = await create_snapshot(db, link.mount_id, link.file_path)
    except NotFoundException:
        await deactivate_with_snapshot_cleanup(db, link)
        return False

    link.file_path = normalize_path(link.file_path)
    link.file_name = snapshot["file_name"]
    link.is_dir = snapshot["is_dir"]
    link.file_size = snapshot["file_size"]
    link.mime_type = snapshot["mime_type"]
    link.snapshot_path = snapshot["snapshot_path"]
    link.snapshot_size = snapshot["snapshot_size"]
    return True


def _apply_snapshot(link: ShareLink, snapshot: dict) -> None:
    link.file_name = snapshot["file_name"]
    link.is_dir = snapshot["is_dir"]
    link.file_size = snapshot["file_size"]
    link.mime_type = snapshot["mime_type"]
    link.snapshot_path = snapshot["snapshot_path"]
    link.snapshot_size = snapshot["snapshot_size"]


async def refresh_share_group(db: AsyncSession, links: list[ShareLink]) -> bool:
    """Rebuild one source snapshot and apply its metadata to all links that share it."""
    if not links:
        return True
    source = links[0]
    try:
        snapshot = await create_snapshot(db, source.mount_id, source.file_path)
    except NotFoundException:
        for link in links:
            await deactivate_with_snapshot_cleanup(db, link)
        return False

    normalized_path = normalize_path(source.file_path)
    for link in links:
        link.file_path = normalized_path
        _apply_snapshot(link, snapshot)
    return True


async def handle_source_changed(db: AsyncSession, mount_id: int, path: str) -> dict:
    """Refresh active snapshots affected by a source file or directory update."""
    changed = normalize_path(path)
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.mount_id == mount_id)
        .where(ShareLink.is_active == True)
        .where(ShareLink.snapshot_path.is_not(None))
    )
    groups: dict[tuple[int, str], list[ShareLink]] = {}
    for link in result.scalars().all():
        if link.file_path == changed or (link.is_dir and _path_contains(link.file_path, changed)):
            groups.setdefault((link.mount_id, normalize_path(link.file_path)), []).append(link)

    refreshed = 0
    failed = 0
    for links in groups.values():
        if await refresh_share_group(db, links):
            refreshed += len(links)
        else:
            failed += len(links)
    await db.flush()
    return {"refreshed": refreshed, "failed": failed}


async def handle_source_deleted(db: AsyncSession, mount_id: int, path: str) -> dict:
    """Delete snapshots whose source path was removed and deactivate their links."""
    removed = normalize_path(path)
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.mount_id == mount_id)
        .where(ShareLink.is_active == True)
        .where(ShareLink.snapshot_path.is_not(None))
    )
    deactivated_links: list[ShareLink] = []
    refresh_groups: dict[tuple[int, str], list[ShareLink]] = {}
    for link in result.scalars().all():
        if _path_contains(removed, link.file_path):
            deactivated_links.append(link)
        elif link.is_dir and _path_contains(link.file_path, removed):
            refresh_groups.setdefault((link.mount_id, normalize_path(link.file_path)), []).append(link)

    for link in deactivated_links:
        await deactivate_with_snapshot_cleanup(db, link)

    refreshed = 0
    deactivated = len(deactivated_links)
    for links in refresh_groups.values():
        if await refresh_share_group(db, links):
            refreshed += len(links)
        else:
            deactivated += len(links)
    await db.flush()
    return {"deactivated": deactivated, "refreshed": refreshed}


async def handle_source_moved(db: AsyncSession, mount_id: int, src: str, dst: str) -> dict:
    """Treat source moves as deletion of shares rooted at src and refresh affected parents."""
    source_changed = await handle_source_changed(db, mount_id, src)
    deleted = await handle_source_deleted(db, mount_id, src)
    target_changed = await handle_source_changed(db, mount_id, dst)
    return {
        "source_refreshed": source_changed.get("refreshed", 0),
        "source_failed": source_changed.get("failed", 0),
        "deactivated": deleted.get("deactivated", 0),
        "deleted_parent_refreshed": deleted.get("refreshed", 0),
        "target_refreshed": target_changed.get("refreshed", 0),
        "target_failed": target_changed.get("failed", 0),
    }


async def cleanup_expired_snapshots(db: AsyncSession, now: datetime | None = None) -> dict:
    """Remove snapshots for expired links and deactivate those links."""
    now = as_aware_utc(now) or utc_now()
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.expires_at.is_not(None))
    )
    cleaned = 0
    for link in result.scalars().all():
        if is_expired(link.expires_at, now) and (link.snapshot_path or link.is_active):
            await deactivate_with_snapshot_cleanup(db, link)
            cleaned += 1
    await db.flush()
    return {"cleaned": cleaned}


async def sync_active_snapshots(db: AsyncSession) -> dict:
    """Reconcile active snapshots with their current source files."""
    await cleanup_expired_snapshots(db)
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.is_active == True)
        .where(ShareLink.snapshot_path.is_not(None))
    )
    groups: dict[tuple[int, str], list[ShareLink]] = {}
    for link in result.scalars().all():
        groups.setdefault((link.mount_id, normalize_path(link.file_path)), []).append(link)

    refreshed = 0
    deactivated = 0
    for links in groups.values():
        if await refresh_share_group(db, links):
            refreshed += len(links)
        else:
            deactivated += len(links)
    await db.flush()
    return {"refreshed": refreshed, "deactivated": deactivated}


def _generate_token() -> str:
    """生成 URL 安全的随机令牌"""
    return secrets.token_urlsafe(24)


def _verify_access_code(stored_code: str, provided_code: str) -> bool:
    """验证提取码。兼容历史明文提取码，新提取码使用哈希。"""
    if stored_code.startswith("hmac_sha256$"):
        return hmac.compare_digest(stored_code, _hash_access_code(provided_code))
    return stored_code == provided_code


def _hash_access_code(access_code: str) -> str:
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode(),
        access_code.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac_sha256${digest}"


def get_share_policy() -> dict:
    if not POLICY_FILE.exists():
        return DEFAULT_POLICY.copy()
    try:
        data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_POLICY.copy()
    return {**DEFAULT_POLICY, **data}


def update_share_policy(policy: dict) -> dict:
    next_policy = {**DEFAULT_POLICY, **policy}
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    POLICY_FILE.write_text(json.dumps(next_policy, ensure_ascii=False, indent=2), encoding="utf-8")
    return next_policy


async def create_share_link(
    db: AsyncSession,
    mount_id: int,
    file_path: str,
    created_by: int,
    expires_hours: int = 0,
    max_views: int = 0,
    access_code: str = "",
) -> ShareLink:
    """
    创建分享链接。
    expires_hours: 有效小时数, 0 表示永不过期。
    max_views: 最大访问次数, 0 表示不限制。
    access_code: 提取码, 空字符串表示不需要。
    """
    policy = get_share_policy()
    if not policy.get("enabled", True):
        raise BadRequestException("分享功能已被管理员关闭")
    if policy.get("force_access_code") and not access_code:
        raise BadRequestException("管理员要求分享必须设置提取码")
    if expires_hours == 0 and policy.get("default_expires_hours", 0) > 0:
        expires_hours = int(policy["default_expires_hours"])

    file_path = normalize_path(file_path)
    token = _generate_token()

    # 确保令牌唯一
    existing = await db.execute(select(ShareLink).where(ShareLink.token == token))
    while existing.scalar_one_or_none():
        token = _generate_token()
        existing = await db.execute(select(ShareLink).where(ShareLink.token == token))

    expires_at = None
    if expires_hours > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    snapshot = await ensure_share_snapshot(db, mount_id, file_path)

    link = ShareLink(
        mount_id=mount_id,
        file_path=file_path,
        file_name=snapshot["file_name"],
        is_dir=snapshot["is_dir"],
        file_size=snapshot["file_size"],
        mime_type=snapshot["mime_type"],
        snapshot_path=snapshot["snapshot_path"],
        snapshot_size=snapshot["snapshot_size"],
        token=token,
        created_by=created_by,
        expires_at=expires_at,
        max_views=max_views,
        access_code=_hash_access_code(access_code) if access_code else None,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def update_share_link(
    db: AsyncSession,
    link_id: int,
    user_id: int,
    is_admin: bool = False,
    *,
    expires_hours: int | None = None,
    max_views: int | None = None,
    access_code: str | None = None,
    is_active: bool | None = None,
) -> ShareLink:
    result = await db.execute(select(ShareLink).where(ShareLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundException("分享链接不存在")
    if not is_admin and link.created_by != user_id:
        raise BadRequestException("无权修改此分享链接")

    policy = get_share_policy()
    if policy.get("force_access_code") and access_code == "":
        raise BadRequestException("管理员要求分享必须设置提取码")
    if expires_hours is not None:
        link.expires_at = None if expires_hours == 0 else datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    if max_views is not None:
        link.max_views = max_views
    if access_code is not None:
        link.access_code = _hash_access_code(access_code) if access_code else None
    if is_active is not None:
        if is_active:
            link.is_active = True
            if not link.snapshot_path:
                _apply_snapshot(link, await ensure_share_snapshot(db, link.mount_id, link.file_path))
        else:
            await deactivate_with_snapshot_cleanup(db, link)
    await db.flush()
    await db.refresh(link)
    return link


async def get_share_link(db: AsyncSession, token: str) -> ShareLink | None:
    """通过令牌查询分享链接"""
    result = await db.execute(select(ShareLink).where(ShareLink.token == token))
    return result.scalar_one_or_none()


async def validate_and_access(
    db: AsyncSession,
    token: str,
    access_code: str = "",
    *,
    count_view: bool = True,
) -> ShareLink:
    """
    验证分享链接有效性并记录访问。
    失败抛出 BadRequestException。
    """
    link = await get_share_link(db, token)
    if link is None:
        raise NotFoundException("分享链接不存在")

    policy = get_share_policy()
    if not policy.get("enabled", True):
        raise BadRequestException("分享功能已关闭")

    if not link.is_active:
        raise BadRequestException("分享链接已失效")

    # 检查过期
    if is_expired(link.expires_at):
        await deactivate_with_snapshot_cleanup(db, link)
        await db.flush()
        await db.commit()
        raise BadRequestException("分享链接已过期")

    # 检查访问次数
    if link.max_views > 0 and link.view_count >= link.max_views:
        raise BadRequestException("分享链接访问次数已达上限")

    max_access_per_hour = int(policy.get("max_access_per_hour", 0) or 0)
    if max_access_per_hour > 0:
        recent_logs = (
            await db.execute(
                select(OperationLog)
                .where(OperationLog.resource_type == "share")
                .where(OperationLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=1))
                .order_by(OperationLog.created_at.desc())
                .limit(max_access_per_hour + 50)
            )
        ).scalars().all()
        recent_count = sum(
            1 for log in recent_logs
            if (log.detail or {}).get("share_id") == link.id and log.action in {"share_access", "share_download"}
        )
        if recent_count >= max_access_per_hour:
            raise BadRequestException("分享访问过于频繁，请稍后再试")

    # 检查提取码
    if link.access_code and not _verify_access_code(link.access_code, access_code):
        raise BadRequestException("提取码错误")

    # 记录访问
    if count_view:
        link.view_count += 1
        await db.flush()
    return link


async def share_stats(db: AsyncSession, link_id: int, user_id: int, is_admin: bool = False) -> dict:
    result = await db.execute(select(ShareLink).where(ShareLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundException("分享链接不存在")
    if not is_admin and link.created_by != user_id:
        raise BadRequestException("无权查看此分享链接")

    logs = [
        log for log in (
        await db.execute(
            select(OperationLog)
            .where(OperationLog.resource_type == "share")
            .order_by(OperationLog.created_at.desc())
            .limit(1000)
        )
    ).scalars().all()
        if (log.detail or {}).get("share_id") == link_id
    ][:200]
    return {
        "share_id": link_id,
        "view_count": link.view_count,
        "download_count": sum(1 for log in logs if log.action == "share_download"),
        "events": [
            {
                "action": log.action,
                "status": log.status,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at,
                "detail": log.detail,
            }
            for log in logs
        ],
    }


async def list_user_links(db: AsyncSession, user_id: int) -> list[ShareLink]:
    """列出用户创建的所有分享链接"""
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.created_by == user_id)
        .order_by(ShareLink.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_links(db: AsyncSession) -> list[ShareLink]:
    """管理员: 列出所有分享链接"""
    result = await db.execute(select(ShareLink).order_by(ShareLink.created_at.desc()))
    return list(result.scalars().all())


async def delete_share_link(db: AsyncSession, link_id: int, user_id: int, is_admin: bool = False) -> None:
    """删除分享链接 (仅创建者或管理员可操作)"""
    result = await db.execute(select(ShareLink).where(ShareLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundException("分享链接不存在")
    if not is_admin and link.created_by != user_id:
        raise BadRequestException("无权删除此分享链接")
    await release_snapshot(db, link)
    await db.delete(link)
    await db.flush()


async def deactivate_link(db: AsyncSession, link_id: int, user_id: int | None = None, is_admin: bool = False) -> None:
    """停用分享链接。管理员可停用任意链接，普通用户仅可停用自己创建的链接。"""
    result = await db.execute(select(ShareLink).where(ShareLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundException("分享链接不存在")
    if user_id is not None and not is_admin and link.created_by != user_id:
        raise BadRequestException("无权停用此分享链接")
    await deactivate_with_snapshot_cleanup(db, link)
    await db.flush()


async def batch_update_links(
    db: AsyncSession,
    link_ids: list[int],
    user_id: int,
    is_admin: bool,
    action: str,
) -> dict:
    success_count = 0
    failed = []
    for link_id in link_ids:
        try:
            if action == "delete":
                await delete_share_link(db, link_id, user_id, is_admin)
            elif action == "deactivate":
                await deactivate_link(db, link_id, user_id, is_admin)
            else:
                raise BadRequestException("不支持的批量操作")
            success_count += 1
        except Exception as exc:
            failed.append({"id": link_id, "message": getattr(exc, "detail", str(exc))})
    return {"success_count": success_count, "failed_count": len(failed), "failed": failed}
