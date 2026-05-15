"""
分享链接服务 — 创建、查询、验证、删除分享链接。
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.share_link import ShareLink


def _generate_token() -> str:
    """生成 URL 安全的随机令牌"""
    return secrets.token_urlsafe(24)


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
        access_code=access_code if access_code else None,
    )
    db.add(link)
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

    if not link.is_active:
        raise BadRequestException("分享链接已失效")

    # 检查过期
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise BadRequestException("分享链接已过期")

    # 检查访问次数
    if link.max_views > 0 and link.view_count >= link.max_views:
        raise BadRequestException("分享链接访问次数已达上限")

    # 检查提取码
    if link.access_code and link.access_code != access_code:
        raise BadRequestException("提取码错误")

    # 记录访问
    link.view_count += 1
    await db.flush()
    return link


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


async def deactivate_link(db: AsyncSession, link_id: int) -> None:
    """停用分享链接"""
    result = await db.execute(select(ShareLink).where(ShareLink.id == link_id))
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundException("分享链接不存在")
    link.is_active = False
    await db.flush()
