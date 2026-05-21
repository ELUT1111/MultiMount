from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.webdav_server.manager import WebDAVConfig, get_webdav_manager


def _status_dict(status) -> dict:
    scheme = "https" if status.ssl else "http"
    host = "localhost" if status.host in ("0.0.0.0", "::") else status.host
    return {
        "running": status.running,
        "host": status.host,
        "port": status.port,
        "ssl": status.ssl,
        "mount_count": status.mount_count,
        "error": status.error,
        "root_mount": status.root_mount_id,
        "recycle_delete": status.recycle_delete,
        "access_log": status.access_log,
        "log_path": status.log_path,
        "ssl_cert_path": status.ssl_cert_path,
        "ssl_key_path": status.ssl_key_path,
        "url": f"{scheme}://{host}:{status.port}/",
        "permissions": {
            "root_listing": "Only mounts accessible to the authenticated user are listed.",
            "read": "download/list/info/share permissions map to read access.",
            "write": "upload/mkdir/copy/move/delete permissions map to readwrite access.",
        },
    }


def _config_from_dict(config: dict, base: WebDAVConfig | None = None) -> WebDAVConfig:
    current = base or WebDAVConfig()
    return WebDAVConfig(
        host=config.get("host", current.host),
        port=config.get("port", current.port),
        ssl=config.get("ssl", current.ssl),
        ssl_cert_path=config.get("ssl_cert_path", current.ssl_cert_path),
        ssl_key_path=config.get("ssl_key_path", current.ssl_key_path),
        root_mount_id=config.get("root_mount", current.root_mount_id),
        access_log=config.get("access_log", current.access_log),
        log_path=config.get("log_path", current.log_path),
        recycle_delete=config.get("recycle_delete", current.recycle_delete),
    )


async def get_status() -> dict:
    manager = get_webdav_manager()
    return _status_dict(manager.status)


async def start_service(db: AsyncSession, config: dict | None = None) -> dict:
    manager = get_webdav_manager()
    wconfig = _config_from_dict(config or {})
    status = await manager.start(db, wconfig)
    return _status_dict(status)


async def stop_service() -> dict:
    manager = get_webdav_manager()
    status = await manager.stop()
    return _status_dict(status)


async def update_service_config(db: AsyncSession, config: dict) -> dict:
    manager = get_webdav_manager()
    base = WebDAVConfig(
        host=manager.status.host,
        port=manager.status.port,
        ssl=manager.status.ssl,
        ssl_cert_path=manager.status.ssl_cert_path,
        ssl_key_path=manager.status.ssl_key_path,
        root_mount_id=manager.status.root_mount_id,
        access_log=manager.status.access_log,
        log_path=manager.status.log_path,
        recycle_delete=manager.status.recycle_delete,
    )
    wconfig = _config_from_dict(config, base)
    status = await manager.update_config(db, wconfig)
    return _status_dict(status)
