"""
分享链接服务 — 创建、查询、验证、删除分享链接。
"""
import secrets
import hashlib
import hmac
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.operation_log import OperationLog
from app.models.share_link import ShareLink

settings = get_settings()
POLICY_FILE = Path("data/share_policy.json")
DEFAULT_POLICY = {
    "enabled": True,
    "force_access_code": False,
    "default_expires_hours": 0,
    "max_access_per_hour": 0,
}


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

    token = _generate_token()

    # 确保令牌唯一
    existing = await db.execute(select(ShareLink).where(ShareLink.token == token))
    while existing.scalar_one_or_none():
        token = _generate_token()
        existing = await db.execute(select(ShareLink).where(ShareLink.token == token))

    expires_at = None
    if expires_hours > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    link = ShareLink(
        mount_id=mount_id,
        file_path=file_path,
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
        link.is_active = is_active
    await db.flush()
    await db.refresh(link)
    return link


async def get_share_link(db: AsyncSession, token: str) -> ShareLink | None:
    """通过令牌查询分享链接"""
    result = await db.execute(select(ShareLink).where(ShareLink.token == token))
    return result.scalar_one_or_none()


async def validate_and_access(db: AsyncSession, token: str, access_code: str = "") -> ShareLink:
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
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
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
    link.is_active = False
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
