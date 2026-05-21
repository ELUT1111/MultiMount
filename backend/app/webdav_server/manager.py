from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.webdav_server.domain_controller import UserDomainController
from app.webdav_server.provider import MultiMountDAVProvider

logger = logging.getLogger(__name__)


@dataclass
class WebDAVConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    root_mount_id: int | None = None
    access_log: bool = True
    log_path: str = ""
    recycle_delete: bool = True


@dataclass
class WebDAVStatus:
    running: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    ssl: bool = False
    ssl_cert_path: str = ""
    ssl_key_path: str = ""
    mount_count: int = 0
    error: str | None = None
    recycle_delete: bool = True
    root_mount_id: int | None = None
    access_log: bool = True
    log_path: str = ""


class WebDAVManager:
    _instance: "WebDAVManager | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._server_thread: threading.Thread | None = None
        self._server = None
        self._running = False
        self._config = WebDAVConfig()
        self._domain_controller: UserDomainController | None = None
        self._error: str | None = None

    @property
    def status(self) -> WebDAVStatus:
        return WebDAVStatus(
            running=self._running,
            host=self._config.host,
            port=self._config.port,
            ssl=self._config.ssl,
            ssl_cert_path=self._config.ssl_cert_path,
            ssl_key_path=self._config.ssl_key_path,
            mount_count=0,
            error=self._error,
            recycle_delete=self._config.recycle_delete,
            root_mount_id=self._config.root_mount_id,
            access_log=self._config.access_log,
            log_path=self._config.log_path,
        )

    async def start(self, db: AsyncSession, config: WebDAVConfig | None = None) -> WebDAVStatus:
        if self._running:
            return self.status

        if config:
            self._config = config

        try:
            provider = MultiMountDAVProvider(
                async_session_factory,
                recycle_delete=self._config.recycle_delete,
                root_mount_id=self._config.root_mount_id,
            )
            self._domain_controller = UserDomainController()
            wsgidav_config = self._build_wsgidav_config(provider)

            self._server_thread = threading.Thread(
                target=self._run_server,
                args=(wsgidav_config,),
                daemon=True,
                name="webdav-server",
            )
            self._server_thread.start()
            self._running = True
            self._error = None
            logger.info("WebDAV service started on %s:%s", self._config.host, self._config.port)
        except Exception as exc:
            self._error = str(exc)
            self._running = False
            logger.error("WebDAV service failed to start: %s", exc)

        return self.status

    async def stop(self) -> WebDAVStatus:
        if not self._running:
            return self.status

        try:
            if self._server:
                self._server.stop()
            self._running = False
            self._error = None
            if self._domain_controller:
                self._domain_controller.close()
                self._domain_controller = None
            logger.info("WebDAV service stopped")
        except Exception as exc:
            self._error = str(exc)
            logger.error("WebDAV service failed to stop: %s", exc)

        return self.status

    async def update_config(self, db: AsyncSession, config: WebDAVConfig) -> WebDAVStatus:
        was_running = self._running
        if was_running:
            await self.stop()
        self._config = config
        if was_running:
            return await self.start(db, config)
        return self.status

    def _build_wsgidav_config(self, provider: MultiMountDAVProvider) -> dict:
        config = {
            "host": self._config.host,
            "port": self._config.port,
            "provider_mapping": {"/": provider},
            "domaincontroller": self._domain_controller,
            "verbose": 1 if self._config.access_log else 0,
            "logging": {
                "enable": self._config.access_log,
                "verbose": 1,
            },
            "accept_anonymous": False,
            "lock_manager": True,
            "response_headers": {
                "Server": "MountHub WebDAV",
            },
        }

        if self._config.ssl and self._config.ssl_cert_path:
            config["ssl_certificate"] = self._config.ssl_cert_path
            config["ssl_private_key"] = self._config.ssl_key_path

        return config

    def _run_server(self, wsgidav_config: dict):
        try:
            from cheroot import wsgi as cheroot_wsgi
            from wsgidav.wsgidav_app import WsgiDAVApp

            app = WsgiDAVApp(wsgidav_config)
            self._server = cheroot_wsgi.Server(
                (wsgidav_config["host"], wsgidav_config["port"]),
                app,
            )

            if "ssl_certificate" in wsgidav_config:
                self._server.ssl_adapter = _create_ssl_adapter(
                    wsgidav_config["ssl_certificate"],
                    wsgidav_config.get("ssl_private_key"),
                )

            self._server.start()
        except Exception as exc:
            self._error = str(exc)
            self._running = False
            logger.error("WebDAV server thread failed: %s", exc)


def _create_ssl_adapter(cert_path: str, key_path: str | None):
    try:
        from cheroot.ssl.builtin import BuiltinSSLAdapter
        return BuiltinSSLAdapter(cert_path, key_path)
    except ImportError:
        logger.warning("Cheroot SSL adapter is unavailable; WebDAV will keep using HTTP")
        return None


def get_webdav_manager() -> WebDAVManager:
    return WebDAVManager()
