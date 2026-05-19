"""
系统设置 API — HTTPS 配置、日志管理、系统信息, 本地目录浏览, 访问监控, IP 黑名单。
"""
import os
import platform

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_admin
from app.core.mount_permissions import check_basic_permission
from app.database import get_db
from app.models.access_log import AccessLog
from app.models.ip_blacklist import IPBlacklist
from app.schemas.ip_blacklist import IPBlacklistCreate, IPBlacklistOut
from app.services import system_service
from app.services import ip_blacklist_service
from app.services import operation_log_service

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
    _user=Depends(check_basic_permission("can_manage_mounts")),
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


# ── 访问日志与统计 ───────────────────────────────────────────

@router.get("/access-logs")
async def get_access_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ip: str = Query("", description="按 IP 筛选"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """分页查询访问日志"""
    query = select(AccessLog)
    count_query = select(func.count(AccessLog.id))

    if ip:
        query = query.where(AccessLog.ip_address.contains(ip))
        count_query = count_query.where(AccessLog.ip_address.contains(ip))

    # 总数
    total = (await db.execute(count_query)).scalar() or 0

    # 分页数据 (按时间倒序)
    query = query.order_by(AccessLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id, "ip_address": r.ip_address, "method": r.method,
                "path": r.path, "status_code": r.status_code,
                "response_time_ms": r.response_time_ms, "user_agent": r.user_agent,
                "user_id": r.user_id, "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in logs
        ],
    }


@router.get("/access-stats")
async def get_access_stats(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """访问统计摘要: 总请求数、今日请求数、Top IP、Top 路径"""
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total = (await db.execute(select(func.count(AccessLog.id)))).scalar() or 0
    today = (await db.execute(
        select(func.count(AccessLog.id)).where(AccessLog.created_at >= today_start)
    )).scalar() or 0

    # Top 10 IP
    top_ips = (await db.execute(
        select(AccessLog.ip_address, func.count(AccessLog.id).label("cnt"))
        .group_by(AccessLog.ip_address).order_by(func.count(AccessLog.id).desc()).limit(10)
    )).all()

    # Top 10 路径
    top_paths = (await db.execute(
        select(AccessLog.path, func.count(AccessLog.id).label("cnt"))
        .group_by(AccessLog.path).order_by(func.count(AccessLog.id).desc()).limit(10)
    )).all()

    # 活跃 IP 数 (今日)
    active_ips = (await db.execute(
        select(func.count(func.distinct(AccessLog.ip_address))).where(AccessLog.created_at >= today_start)
    )).scalar() or 0

    return {
        "total_requests": total,
        "today_requests": today,
        "active_ips_today": active_ips,
        "top_ips": [{"ip": ip, "count": cnt} for ip, cnt in top_ips],
        "top_paths": [{"path": p, "count": cnt} for p, cnt in top_paths],
    }


@router.get("/operation-logs")
async def get_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str = Query("", description="按操作类型筛选"),
    username: str = Query("", description="按用户名筛选"),
    mount_id: int | None = Query(None, description="按挂载 ID 筛选"),
    status: str = Query("", regex="^(|success|failed)$"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """分页查询业务操作审计日志。"""
    return await operation_log_service.list_operation_logs(
        db,
        page=page,
        page_size=page_size,
        action=action,
        username=username,
        mount_id=mount_id,
        status=status,
    )


# ── IP 黑名单管理 ────────────────────────────────────────────

@router.get("/ip-blacklist", response_model=list[IPBlacklistOut])
async def get_ip_blacklist(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """获取 IP 黑名单列表"""
    return await ip_blacklist_service.get_all(db)


@router.post("/ip-blacklist", response_model=IPBlacklistOut)
async def add_ip_blacklist(
    body: IPBlacklistCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """添加 IP 到黑名单"""
    return await ip_blacklist_service.add(db, body.ip_address, body.reason)


@router.delete("/ip-blacklist/{ip:path}")
async def remove_ip_blacklist(
    ip: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """从黑名单移除 IP"""
    removed = await ip_blacklist_service.remove(db, ip)
    if not removed:
        raise HTTPException(status_code=404, detail="IP 不在黑名单中")
    return {"success": True, "message": f"已解封 {ip}"}
