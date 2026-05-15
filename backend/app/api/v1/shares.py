"""
分享链接 API — 创建、查询、访问、删除分享链接。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.services import share_service

router = APIRouter()


# ── 请求/响应模型 ──────────────────────────────────────────

class ShareLinkCreate(BaseModel):
    mount_id: int
    file_path: str = Field(..., min_length=1)
    expires_hours: int = Field(0, ge=0, le=8760)  # 最长 1 年
    max_views: int = Field(0, ge=0)
    access_code: str = ""


class ShareLinkOut(BaseModel):
    id: int
    mount_id: int
    file_path: str
    token: str
    created_by: int
    expires_at: datetime | None
    max_views: int
    view_count: int
    is_active: bool
    access_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareAccessRequest(BaseModel):
    access_code: str = ""


# ── 创建分享链接 ──────────────────────────────────────────

@router.post("", response_model=ShareLinkOut, status_code=201)
async def create_link(
    body: ShareLinkCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建文件分享链接"""
    link = await share_service.create_share_link(
        db,
        mount_id=body.mount_id,
        file_path=body.file_path,
        created_by=current_user.id,
        expires_hours=body.expires_hours,
        max_views=body.max_views,
        access_code=body.access_code,
    )
    return link


# ── 查询当前用户的分享链接 ────────────────────────────────

@router.get("", response_model=list[ShareLinkOut])
async def list_my_links(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户创建的分享链接列表"""
    return await share_service.list_user_links(db, current_user.id)


# ── 管理员: 查询所有分享链接 ──────────────────────────────

@router.get("/all", response_model=list[ShareLinkOut])
async def list_all_links(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员: 获取所有分享链接"""
    return await share_service.list_all_links(db)


# ── 访问分享链接 (无需登录) ────────────────────────────────

@router.get("/{token}/info")
async def get_link_info(token: str, db: AsyncSession = Depends(get_db)):
    """获取分享链接基本信息 (无需登录, 不含文件内容)"""
    link = await share_service.get_share_link(db, token)
    if link is None:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("分享链接不存在")
    from app.core.exceptions import BadRequestException
    if not link.is_active:
        raise BadRequestException("分享链接已失效")
    if link.expires_at and link.expires_at < __import__("datetime").datetime.now(__import__("datetime").timezone.utc):
        raise BadRequestException("分享链接已过期")
    return {
        "file_path": link.file_path,
        "mount_id": link.mount_id,
        "has_access_code": bool(link.access_code),
        "expires_at": link.expires_at,
        "view_count": link.view_count,
        "max_views": link.max_views,
    }


@router.post("/{token}/access")
async def access_link(
    token: str,
    body: ShareAccessRequest = ShareAccessRequest(),
    db: AsyncSession = Depends(get_db),
):
    """验证并访问分享链接 (检查提取码/过期/次数)"""
    link = await share_service.validate_and_access(db, token, body.access_code)
    return {
        "mount_id": link.mount_id,
        "file_path": link.file_path,
        "view_count": link.view_count,
    }


# ── 删除/停用分享链接 ─────────────────────────────────────

@router.delete("/{link_id}", status_code=204)
async def delete_link(
    link_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除分享链接"""
    is_admin = current_user.role and current_user.role.name == "admin"
    await share_service.delete_share_link(db, link_id, current_user.id, is_admin)


@router.post("/{link_id}/deactivate", status_code=204)
async def deactivate_link(
    link_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """停用分享链接 (管理员)"""
    await share_service.deactivate_link(db, link_id)
