"""
系统设置 API — HTTPS 配置、日志管理、系统信息, 本地目录浏览。
"""
import os
import platform

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from app.dependencies import require_admin
from app.services import system_service

router = APIRouter()


# ── 请求模型 ───────────────────────────────────────────────

class HTTPSConfigRequest(BaseModel):
    force_https: bool | None = None
    auto_redirect: bool | None = None


# ── 系统信息 ───────────────────────────────────────────────

@router.get("/info")
async def get_system_info(_admin=Depends(require_admin)):
    """获取系统基本信息"""
    return system_service.get_system_info()


# ── HTTPS 配置 ─────────────────────────────────────────────

@router.get("/https")
async def get_https_status(_admin=Depends(require_admin)):
    """获取 HTTPS 配置状态"""
    return system_service.get_https_status()


@router.post("/https/cert")
async def upload_cert(cert: UploadFile = File(...), _admin=Depends(require_admin)):
    """上传 SSL 证书文件"""
    content = await cert.read()
    return system_service.upload_certificate(content, cert.filename)


@router.post("/https/key")
async def upload_key(key: UploadFile = File(...), _admin=Depends(require_admin)):
    """上传 SSL 私钥文件"""
    content = await key.read()
    return system_service.upload_key(content, key.filename)


@router.put("/https")
async def update_https_config(body: HTTPSConfigRequest, _admin=Depends(require_admin)):
    """更新 HTTPS 配置 (强制跳转/自动重定向)"""
    return system_service.update_https_config(
        force_https=body.force_https,
        auto_redirect=body.auto_redirect,
    )


# ── 日志管理 ───────────────────────────────────────────────

@router.get("/logs")
async def list_logs(
    log_type: str = Query("system", regex="^(system|access|transfer)$"),
    start_date: str = Query(""),
    end_date: str = Query(""),
    _admin=Depends(require_admin),
):
    """获取日志列表"""
    return system_service.list_logs(log_type, start_date, end_date)


@router.post("/logs/export")
async def export_logs(
    log_type: str = Query("system", regex="^(system|access|transfer)$"),
    _admin=Depends(require_admin),
):
    """导出日志文件"""
    path = system_service.export_logs(log_type)
    if path is None:
        return {"error": "日志文件不存在"}
    return {"path": path}


@router.post("/logs/clear")
async def clear_logs(
    log_type: str = Query("system", regex="^(system|access|transfer)$"),
    _admin=Depends(require_admin),
):
    """清空日志"""
    result = system_service.clear_logs(log_type)
    return {"success": result}


# ── 本地目录浏览 ─────────────────────────────────────────────

@router.get("/browse")
async def browse_local_folders(
    path: str = Query("", description="要浏览的目录路径, 空则返回磁盘列表"),
    _admin=Depends(require_admin),
):
    """浏览服务器本地文件系统目录 (仅返回文件夹)"""
    if not path:
        # 返回磁盘列表 (Windows) 或根目录 (Linux/Mac)
        if platform.system() == "Windows":
            import string
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": drive, "path": drive, "is_dir": True})
            return drives
        else:
            path = "/"

    # 规范化路径
    path = os.path.normpath(path)

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {path}")

    try:
        entries = []
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                entries.append({"name": name, "path": full_path, "is_dir": True})
        entries.sort(key=lambda e: e["name"].lower())
        return entries
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有权限访问该目录")
