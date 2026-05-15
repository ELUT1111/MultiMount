"""
WebDAV 服务业务逻辑层 — 管理 WebDAV 服务的配置与生命周期。

提供:
  - 查询服务状态
  - 启动/停止服务
  - 更新配置 (端口/SSL/根目录/日志)
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.webdav_server.manager import WebDAVConfig, WebDAVManager, get_webdav_manager


async def get_status() -> dict:
    """获取 WebDAV 服务当前状态"""
    manager = get_webdav_manager()
    s = manager.status
    return {
        "running": s.running,
        "host": s.host,
        "port": s.port,
        "ssl": s.ssl,
        "mount_count": s.mount_count,
        "error": s.error,
    }


async def start_service(db: AsyncSession, config: dict | None = None) -> dict:
    """启动 WebDAV 服务"""
    manager = get_webdav_manager()
    wconfig = WebDAVConfig()
    if config:
        wconfig.host = config.get("host", wconfig.host)
        wconfig.port = config.get("port", wconfig.port)
        wconfig.ssl = config.get("ssl", wconfig.ssl)
        wconfig.ssl_cert_path = config.get("ssl_cert_path", "")
        wconfig.ssl_key_path = config.get("ssl_key_path", "")
        wconfig.root_mount_id = config.get("root_mount")
        wconfig.access_log = config.get("access_log", True)
        wconfig.log_path = config.get("log_path", "")

    status = await manager.start(db, wconfig)
    return {
        "running": status.running,
        "host": status.host,
        "port": status.port,
        "ssl": status.ssl,
        "mount_count": status.mount_count,
        "error": status.error,
    }


async def stop_service() -> dict:
    """停止 WebDAV 服务"""
    manager = get_webdav_manager()
    status = await manager.stop()
    return {
        "running": status.running,
        "host": status.host,
        "port": status.port,
        "ssl": status.ssl,
        "mount_count": status.mount_count,
        "error": status.error,
    }


async def update_service_config(db: AsyncSession, config: dict) -> dict:
    """更新 WebDAV 服务配置 (热更新: 如正在运行则重启)"""
    manager = get_webdav_manager()
    wconfig = WebDAVConfig(
        host=config.get("host", manager.status.host),
        port=config.get("port", manager.status.port),
        ssl=config.get("ssl", manager.status.ssl),
        ssl_cert_path=config.get("ssl_cert_path", ""),
        ssl_key_path=config.get("ssl_key_path", ""),
        root_mount_id=config.get("root_mount"),
        access_log=config.get("access_log", True),
        log_path=config.get("log_path", ""),
    )
    status = await manager.update_config(db, wconfig)
    return {
        "running": status.running,
        "host": status.host,
        "port": status.port,
        "ssl": status.ssl,
        "mount_count": status.mount_count,
        "error": status.error,
    }
