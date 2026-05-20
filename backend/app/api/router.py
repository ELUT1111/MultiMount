from fastapi import APIRouter

from app.api.v1 import auth, mounts, users, files, transfers, webdav, system, shares, notifications, mount_permissions, search, trash

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(mounts.router, prefix="/mounts", tags=["挂载管理"])
api_router.include_router(files.router, prefix="/files", tags=["文件操作"])
api_router.include_router(transfers.router, prefix="/transfers", tags=["传输任务"])
api_router.include_router(webdav.router, prefix="/webdav", tags=["WebDAV 服务管理"])
api_router.include_router(system.router, prefix="/system", tags=["系统设置"])
api_router.include_router(shares.router, prefix="/shares", tags=["分享链接"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
api_router.include_router(mount_permissions.router, prefix="/mounts", tags=["挂载权限"])
api_router.include_router(search.router, prefix="/search", tags=["搜索"])
api_router.include_router(trash.router, prefix="/trash", tags=["回收站"])
