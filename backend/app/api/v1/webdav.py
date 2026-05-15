"""
WebDAV 服务管理路由 — 状态查询、启停、配置更新。

所有接口需要管理员权限。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import require_admin
from app.services import webdav_service

router = APIRouter()


class WebDAVStartRequest(BaseModel):
    """启动 WebDAV 服务请求"""
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    root_mount: int | None = None
    access_log: bool = True
    log_path: str = ""


class WebDAVConfigRequest(BaseModel):
    """更新 WebDAV 配置请求"""
    host: str | None = None
    port: int | None = None
    ssl: bool | None = None
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    root_mount: int | None = None
    access_log: bool | None = None
    log_path: str | None = None


@router.get("/status")
async def get_status(_user=Depends(require_admin)):
    """获取 WebDAV 服务状态"""
    return await webdav_service.get_status()


@router.post("/start")
async def start_service(
    body: WebDAVStartRequest | None = None,
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """启动 WebDAV 服务"""
    config = body.model_dump() if body else None
    return await webdav_service.start_service(db, config)


@router.post("/stop")
async def stop_service(_user=Depends(require_admin)):
    """停止 WebDAV 服务"""
    return await webdav_service.stop_service()


@router.put("/config")
async def update_config(
    body: WebDAVConfigRequest,
    _user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新 WebDAV 服务配置 (热更新)"""
    config = {k: v for k, v in body.model_dump().items() if v is not None}
    return await webdav_service.update_service_config(db, config)
