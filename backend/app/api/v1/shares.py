"""
分享链接 API — 创建、查询、访问、删除分享链接。
"""
from datetime import datetime

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.core.policy import enforce_file_policy
from app.services import file_service, operation_log_service, share_service

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
    request: Request,
    body: ShareLinkCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建文件分享链接"""
    await enforce_file_policy(db, current_user, body.mount_id, "share")
    await file_service.get_info(db, body.mount_id, body.file_path)
    link = await share_service.create_share_link(
        db,
        mount_id=body.mount_id,
        file_path=body.file_path,
        created_by=current_user.id,
        expires_hours=body.expires_hours,
        max_views=body.max_views,
        access_code=body.access_code,
    )
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="share_create",
        resource_type="share",
        user=current_user,
        mount_id=body.mount_id,
        path=body.file_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"share_id": link.id, "expires_at": link.expires_at.isoformat() if link.expires_at else None},
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
    request: Request,
    token: str,
    body: ShareAccessRequest = ShareAccessRequest(),
    db: AsyncSession = Depends(get_db),
):
    """验证并访问分享链接 (检查提取码/过期/次数)"""
    link = await share_service.validate_and_access(db, token, body.access_code)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="share_access",
        resource_type="share",
        mount_id=link.mount_id,
        path=link.file_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"share_id": link.id, "token": token},
    )
    return {
        "mount_id": link.mount_id,
        "file_path": link.file_path,
        "view_count": link.view_count,
    }


@router.get("/{token}/download")
async def download_link(
    request: Request,
    token: str,
    access_code: str = Query("", description="提取码"),
    db: AsyncSession = Depends(get_db),
):
    """通过分享链接匿名下载文件。"""
    link = await share_service.validate_and_access(db, token, access_code)
    info = await file_service.get_info(db, link.mount_id, link.file_path)
    mime = info.mime_type or "application/octet-stream"
    filename = info.name

    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="share_download",
        resource_type="share",
        mount_id=link.mount_id,
        path=link.file_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={"share_id": link.id, "token": token, "size": info.size},
    )

    async def stream():
        async for chunk in file_service.download_file(db, link.mount_id, link.file_path):
            yield chunk

    encoded = quote(filename)
    return StreamingResponse(
        stream(),
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Content-Length": str(info.size) if info.size else "",
        },
    )


# ── 删除/停用分享链接 ─────────────────────────────────────

@router.delete("/{link_id}", status_code=204)
async def delete_link(
    request: Request,
    link_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除分享链接"""
    is_admin = current_user.role and current_user.role.name == "admin"
    await share_service.delete_share_link(db, link_id, current_user.id, is_admin)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="share_delete",
        resource_type="share",
        user=current_user,
        ip_address=ip,
        user_agent=user_agent,
        detail={"share_id": link_id},
    )


@router.post("/{link_id}/deactivate", status_code=204)
async def deactivate_link(
    request: Request,
    link_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """停用分享链接。创建者或管理员可操作。"""
    is_admin = current_user.role and current_user.role.name == "admin"
    await share_service.deactivate_link(db, link_id, current_user.id, is_admin)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="share_deactivate",
        resource_type="share",
        user=current_user,
        ip_address=ip,
        user_agent=user_agent,
        detail={"share_id": link_id},
    )
