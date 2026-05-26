from __future__ import annotations

import logging
from pathlib import Path
import time

logger = logging.getLogger("webdav.access")


class AccessLogMiddleware:
    """WSGI middleware that logs WebDAV requests to the app log and optional file."""

    def __init__(self, app, log_path: str = ""):
        self._app = app
        self._logger = logger
        if log_path:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._logger = logging.getLogger(f"webdav.access.file.{id(self)}")
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = True
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
            self._logger.addHandler(handler)

    def __call__(self, environ, start_response):
        start_time = time.time()
        method = environ.get("REQUEST_METHOD", "UNKNOWN")
        path = environ.get("PATH_INFO", "/")
        remote_addr = environ.get("REMOTE_ADDR", "-")
        username = environ.get("REMOTE_USER") or environ.get("wsgidav.auth.user_name") or "-"
        status_code = [None]

        def _start_response(status, headers, exc_info=None):
            status_code[0] = status.split(" ")[0] if status else "???"
            return start_response(status, headers, exc_info)

        try:
            return self._app(environ, _start_response)
        finally:
            elapsed = time.time() - start_time
            self._logger.info(
                "%s [%s] %s %s -> %s (%.3fs)",
                remote_addr,
                username,
                method,
                path,
                status_code[0],
                elapsed,
            )
