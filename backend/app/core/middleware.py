import asyncio
import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from app.services.ip_blacklist_service import is_blocked

logger = logging.getLogger("multimount.access")

_bg_tasks: set = set()


class IPBlacklistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if is_blocked(client_ip):
            logger.warning("Blocked blacklisted IP: %s %s", client_ip, request.url.path)
            return JSONResponse(status_code=403, content={"detail": "IP is blocked"})
        return await call_next(request)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from app.core.ssl_manager import load_config

        config = load_config()
        if not config.force_https or not config.auto_redirect:
            return await call_next(request)

        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto.lower() == "https":
            return await call_next(request)

        url = request.url.replace(scheme="https")
        return RedirectResponse(str(url), status_code=308)


async def _write_access_log(ip, method, path, status, elapsed_ms, user_agent, user_id):
    try:
        from app.database import async_session_factory
        from app.models.access_log import AccessLog

        async with async_session_factory() as db:
            db.add(AccessLog(
                ip_address=ip,
                method=method,
                path=path,
                status_code=status,
                response_time_ms=round(elapsed_ms, 1),
                user_agent=user_agent[:512] if user_agent else None,
                user_id=user_id,
            ))
            await db.commit()
    except Exception:
        logger.debug("Failed to write access log", exc_info=True)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        path = request.url.path
        if not path.startswith("/health"):
            task = asyncio.create_task(_write_access_log(
                ip=request.client.host if request.client else "unknown",
                method=request.method,
                path=path,
                status=response.status_code,
                elapsed_ms=elapsed_ms,
                user_agent=request.headers.get("user-agent"),
                user_id=None,
            ))
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)

        return response


def register_middleware(app: FastAPI):
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(IPBlacklistMiddleware)
