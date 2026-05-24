from __future__ import annotations

import asyncio
import io
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from wsgidav import dav_provider, util
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR, HTTP_NOT_FOUND

from app.adapters import *  # noqa: F401,F403
from app.adapters.registry import AdapterRegistry
from app.core.policy import enforce_file_policy
from app.core.security import decrypt_field
from app.models.mount import Mount
from app.models.user import User
from app.services import operation_log_service, trash_service
from app.services.mount_permission_service import get_accessible_mount_ids
from app.utils.path_utils import normalize_path

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter, FileInfo
    from sqlalchemy.ext.asyncio import async_sessionmaker

_loop: asyncio.AbstractEventLoop | None = None
MOUNT_CACHE_TTL_SECONDS = 15


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def _run_async(coro):
    return _get_loop().run_until_complete(coro)


@dataclass
class MountHandle:
    mount_id: int
    name: str
    safe_name: str
    adapter: "BaseAdapter"


def _safe_mount_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_")


def _dav_status(exc: Exception) -> int:
    if isinstance(exc, HTTPException) and exc.status_code == 403:
        return HTTP_FORBIDDEN
    if isinstance(exc, FileNotFoundError):
        return HTTP_NOT_FOUND
    return HTTP_INTERNAL_ERROR


def _dav_error(exc: Exception, fallback: str) -> DAVError:
    detail = getattr(exc, "detail", None) or str(exc) or fallback
    return DAVError(_dav_status(exc), detail)


class WebDAVRequestContext:
    def __init__(
        self,
        session_factory: "async_sessionmaker",
        user: User,
        recycle_delete: bool,
        environ: dict,
    ):
        self.session_factory = session_factory
        self.user = user
        self.recycle_delete = recycle_delete
        self.environ = environ

    async def enforce(self, mount_id: int, action: str) -> None:
        async with self.session_factory() as db:
            await enforce_file_policy(db, self.user, mount_id, action)

    async def log(
        self,
        mount_id: int,
        action: str,
        path: str,
        target_path: str | None = None,
        status: str = "success",
        detail: dict | None = None,
    ) -> None:
        try:
            async with self.session_factory() as db:
                await operation_log_service.log_operation(
                    db,
                    action=f"webdav.{action}",
                    resource_type="file",
                    user=self.user,
                    mount_id=mount_id,
                    path=path,
                    target_path=target_path,
                    status=status,
                    ip_address=self.environ.get("REMOTE_ADDR"),
                    user_agent=(self.environ.get("HTTP_USER_AGENT") or "")[:512] or None,
                    detail=detail,
                )
                await db.commit()
        except Exception:
            pass

    async def trash_or_delete(self, mount_id: int, adapter: "BaseAdapter", path: str) -> None:
        if self.recycle_delete:
            async with self.session_factory() as db:
                await trash_service.trash_file(db, mount_id, path, user=self.user)
                from app.services import search_service, share_service
                await search_service.remove_path_index(db, mount_id, path)
                await share_service.handle_source_deleted(db, mount_id, path)
                await db.commit()
        else:
            await adapter.delete(path)
            async with self.session_factory() as db:
                from app.services import search_service, share_service
                await search_service.remove_path_index(db, mount_id, path)
                await share_service.handle_source_deleted(db, mount_id, path)
                await db.commit()

    async def refresh_index(self, mount_id: int, path: str) -> None:
        async with self.session_factory() as db:
            from app.services import search_service, share_service
            await search_service.refresh_path_index(db, mount_id, path)
            await share_service.handle_source_changed(db, mount_id, path)
            await db.commit()

    async def remove_index(self, mount_id: int, path: str) -> None:
        async with self.session_factory() as db:
            from app.services import search_service
            await search_service.remove_path_index(db, mount_id, path)
            await db.commit()

    async def source_moved(self, mount_id: int, src: str, dst: str) -> None:
        async with self.session_factory() as db:
            from app.services import share_service
            await share_service.handle_source_moved(db, mount_id, src, dst)
            await db.commit()


class _AdapterMixin:
    def __init__(
        self,
        handle: MountHandle,
        context: WebDAVRequestContext,
        file_info: "FileInfo | None" = None,
    ):
        self._handle = handle
        self._adapter = handle.adapter
        self._context = context
        self._info = file_info

    @property
    def _mount_id(self) -> int:
        return self._handle.mount_id

    def _ensure_info(self):
        if self._info is None:
            try:
                self._info = _run_async(self._adapter.get_info(self._adapter_path()))
            except Exception:
                self._info = None

    def _adapter_path(self, path: str | None = None) -> str:
        resource_path = path if path is not None else self.path
        parts = resource_path.strip("/").split("/", 1)
        return normalize_path("/" + parts[1] if len(parts) > 1 else "/")

    def _target_adapter_path(self, dest_path: str) -> str:
        parts = dest_path.strip("/").split("/", 1)
        if not parts or parts[0] != self._handle.safe_name:
            raise DAVError(HTTP_FORBIDDEN, "Cross-mount WebDAV copy/move is not supported")
        return normalize_path("/" + parts[1] if len(parts) > 1 else "/")

    def _require(self, action: str, adapter_path: str | None = None) -> None:
        path = adapter_path if adapter_path is not None else self._adapter_path()
        if trash_service.is_trash_path(path):
            raise DAVError(HTTP_NOT_FOUND, f"Resource not found: {path}")
        try:
            _run_async(self._context.enforce(self._mount_id, action))
        except Exception as exc:
            raise _dav_error(exc, f"Forbidden: {action}")

    def _log(self, action: str, path: str, target_path: str | None = None, detail: dict | None = None) -> None:
        _run_async(self._context.log(self._mount_id, action, path, target_path, detail=detail))


class AdapterCollection(dav_provider.DAVCollection, _AdapterMixin):
    def __init__(self, path: str, environ: dict, handle: MountHandle,
                 context: WebDAVRequestContext, file_info: "FileInfo | None" = None):
        dav_provider.DAVCollection.__init__(self, path, environ)
        _AdapterMixin.__init__(self, handle, context, file_info)

    def get_display_info(self) -> dict:
        return {"type": "Directory"}

    def get_member_names(self) -> list[str]:
        self._require("list")
        try:
            entries = _run_async(self._adapter.list_dir(self._adapter_path()))
            return [e.name for e in entries if not trash_service.is_trash_path(e.path)]
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "List failed")

    def get_member(self, name: str) -> dav_provider._DAVResource:
        child_path = util.join_uri(self.path, name)
        adapter_path = self._adapter_path(child_path)
        self._require("info", adapter_path)
        try:
            info = _run_async(self._adapter.get_info(adapter_path))
            if info.is_dir:
                return AdapterCollection(child_path, self.environ, self._handle, self._context, info)
            return AdapterNonCollection(child_path, self.environ, self._handle, self._context, info)
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, f"Resource not found: {child_path}")

    def create_collection(self, name: str):
        dir_path = util.join_uri(self.path, name)
        adapter_path = self._adapter_path(dir_path)
        self._require("mkdir", adapter_path)
        try:
            _run_async(self._adapter.mkdir(adapter_path))
            self._log("mkdir", adapter_path)
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Create directory failed")

    def create_empty_resource(self, name: str) -> dav_provider._DAVResource:
        file_path = util.join_uri(self.path, name)
        adapter_path = self._adapter_path(file_path)
        self._require("upload", adapter_path)
        return AdapterNonCollection(file_path, self.environ, self._handle, self._context)

    def delete(self):
        adapter_path = self._adapter_path()
        self._require("delete", adapter_path)
        try:
            _run_async(self._context.trash_or_delete(self._mount_id, self._adapter, adapter_path))
            self._log("delete", adapter_path, detail={"recycle": self._context.recycle_delete})
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Delete failed")

    def copy_move_single(self, dest_path: str, is_move: bool):
        source_path = self._adapter_path()
        target_path = self._target_adapter_path(dest_path)
        self._require("move" if is_move else "copy", source_path)
        self._require("move" if is_move else "copy", target_path)
        try:
            if is_move:
                _run_async(self._adapter.move(source_path, target_path))
                _run_async(self._context.remove_index(self._mount_id, source_path))
            else:
                _run_async(self._adapter.copy(source_path, target_path))
            _run_async(self._context.refresh_index(self._mount_id, target_path))
            if is_move:
                _run_async(self._context.source_moved(self._mount_id, source_path, target_path))
            self._log("move" if is_move else "copy", source_path, target_path)
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Copy/move failed")

    def support_recursive_delete(self) -> bool:
        return False


class AdapterNonCollection(dav_provider.DAVNonCollection, _AdapterMixin):
    def __init__(self, path: str, environ: dict, handle: MountHandle,
                 context: WebDAVRequestContext, file_info: "FileInfo | None" = None):
        dav_provider.DAVNonCollection.__init__(self, path, environ)
        _AdapterMixin.__init__(self, handle, context, file_info)

    def get_content_length(self) -> int | None:
        self._ensure_info()
        return self._info.size if self._info else None

    def get_content_type(self) -> str:
        self._ensure_info()
        if self._info and self._info.mime_type:
            return self._info.mime_type
        _, ext = os.path.splitext(self.path)
        return util.guess_mime_type(ext)

    def get_creation_date(self) -> float | None:
        self._ensure_info()
        if self._info and self._info.created_at:
            return self._info.created_at.timestamp()
        return None

    def get_last_modified(self) -> float | None:
        self._ensure_info()
        if self._info and self._info.modified_at:
            return self._info.modified_at.timestamp()
        return time.time()

    def get_display_info(self) -> dict:
        return {"type": "File"}

    def get_content(self):
        self._require("download")
        chunks = []

        async def _collect():
            async for chunk in self._adapter.download(self._adapter_path()):
                chunks.append(chunk)

        try:
            _run_async(_collect())
            self._log("download", self._adapter_path())
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Download failed")

        return io.BytesIO(b"".join(chunks))

    def begin_write(self, content_type: str = None):
        adapter_path = self._adapter_path()
        self._require("upload", adapter_path)
        return _WriteBuffer(self._adapter, adapter_path, self._context, self._mount_id)

    def delete(self):
        adapter_path = self._adapter_path()
        self._require("delete", adapter_path)
        try:
            _run_async(self._context.trash_or_delete(self._mount_id, self._adapter, adapter_path))
            self._log("delete", adapter_path, detail={"recycle": self._context.recycle_delete})
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Delete failed")

    def copy_move_single(self, dest_path: str, is_move: bool):
        source_path = self._adapter_path()
        target_path = self._target_adapter_path(dest_path)
        self._require("move" if is_move else "copy", source_path)
        self._require("move" if is_move else "copy", target_path)
        try:
            if is_move:
                _run_async(self._adapter.move(source_path, target_path))
                _run_async(self._context.remove_index(self._mount_id, source_path))
            else:
                _run_async(self._adapter.copy(source_path, target_path))
            _run_async(self._context.refresh_index(self._mount_id, target_path))
            if is_move:
                _run_async(self._context.source_moved(self._mount_id, source_path, target_path))
            self._log("move" if is_move else "copy", source_path, target_path)
        except DAVError:
            raise
        except Exception as exc:
            raise _dav_error(exc, "Copy/move failed")


class _WriteBuffer:
    def __init__(self, adapter: "BaseAdapter", path: str, context: WebDAVRequestContext, mount_id: int):
        self._adapter = adapter
        self._path = path
        self._context = context
        self._mount_id = mount_id
        self._buffer = io.BytesIO()

    def write(self, data: bytes):
        self._buffer.write(data)

    def close(self):
        self._buffer.seek(0)
        data = self._buffer.read()

        async def _upload():
            async def _iter():
                chunk_size = 65536
                offset = 0
                while offset < len(data):
                    yield data[offset:offset + chunk_size]
                    offset += chunk_size

            await self._adapter.upload(self._path, _iter(), size=len(data))
            await self._context.refresh_index(self._mount_id, self._path)
            await self._context.log(
                self._mount_id,
                "upload",
                self._path,
                detail={"size": len(data), "source": "webdav"},
            )

        try:
            _run_async(_upload())
        except Exception as exc:
            raise _dav_error(exc, "Upload failed")
        finally:
            self._buffer.close()


class MultiMountDAVProvider(dav_provider.DAVProvider):
    def __init__(
        self,
        session_factory: "async_sessionmaker",
        recycle_delete: bool = True,
        root_mount_id: int | None = None,
    ):
        super().__init__()
        self._session_factory = session_factory
        self._recycle_delete = recycle_delete
        self._root_mount_id = root_mount_id
        self._mount_cache: dict[int, tuple[float, list[MountHandle]]] = {}

    def get_resource_inst(self, path: str, environ: dict):
        user = self._user_from_environ(environ)
        if user is None:
            return None

        if path.strip("/") == "":
            return _RootCollection(path, environ, self, user)

        parts = path.strip("/").split("/", 1)
        handle = self._mount_for_name(user, parts[0])
        if handle is None:
            return None

        context = WebDAVRequestContext(self._session_factory, user, self._recycle_delete, environ)
        sub_path = normalize_path("/" + parts[1] if len(parts) > 1 else "/")
        if trash_service.is_trash_path(sub_path):
            return None

        try:
            _run_async(context.enforce(handle.mount_id, "info"))
            info = _run_async(handle.adapter.get_info(sub_path))
            if info.is_dir:
                return AdapterCollection(path, environ, handle, context, info)
            return AdapterNonCollection(path, environ, handle, context, info)
        except Exception:
            return None

    def _user_from_environ(self, environ: dict) -> User | None:
        username = environ.get("wsgidav.auth.user_name") or ""
        if not username:
            return None

        async def _load():
            async with self._session_factory() as db:
                result = await db.execute(
                    select(User)
                    .options(selectinload(User.role))
                    .where(User.username == username, User.is_active == True)
                )
                return result.scalar_one_or_none()

        try:
            return _run_async(_load())
        except Exception:
            return None

    def _visible_mounts(self, user: User) -> list[MountHandle]:
        now = time.monotonic()
        cached = self._mount_cache.get(user.id)
        if cached and now - cached[0] < MOUNT_CACHE_TTL_SECONDS:
            return cached[1]

        async def _load():
            async with self._session_factory() as db:
                accessible = await get_accessible_mount_ids(db, user)
                if self._root_mount_id is not None:
                    accessible &= {self._root_mount_id}
                if not accessible:
                    return []
                result = await db.execute(select(Mount).where(Mount.id.in_(accessible)).order_by(Mount.name.asc()))
                handles = []
                used_names: set[str] = set()
                for mount in result.scalars().all():
                    try:
                        config = {}
                        for key, value in (mount.config or {}).items():
                            if key in ("password", "access_key_secret", "private_key"):
                                try:
                                    config[key] = decrypt_field(value)
                                except Exception:
                                    config[key] = value
                            else:
                                config[key] = value
                        adapter = AdapterRegistry.create(mount.type, config)
                        await adapter.connect()
                        base_name = _safe_mount_name(mount.name) or f"mount-{mount.id}"
                        safe_name = base_name
                        suffix = 2
                        while safe_name in used_names:
                            safe_name = f"{base_name}-{suffix}"
                            suffix += 1
                        used_names.add(safe_name)
                        handles.append(MountHandle(mount.id, mount.name, safe_name, adapter))
                    except Exception:
                        continue
                return handles

        handles = _run_async(_load())
        self._mount_cache[user.id] = (now, handles)
        return handles

    def _mount_for_name(self, user: User, safe_name: str) -> MountHandle | None:
        for handle in self._visible_mounts(user):
            if handle.safe_name == safe_name:
                return handle
        return None


class _RootCollection(dav_provider.DAVCollection):
    def __init__(self, path: str, environ: dict, provider: MultiMountDAVProvider, user: User):
        super().__init__(path, environ)
        self._provider = provider
        self._user = user

    def get_display_info(self) -> dict:
        return {"type": "Root"}

    def get_member_names(self) -> list[str]:
        return [handle.safe_name for handle in self._provider._visible_mounts(self._user)]

    def get_member(self, name: str):
        handle = self._provider._mount_for_name(self._user, name)
        if handle is None:
            raise DAVError(HTTP_NOT_FOUND, f"Mount not found: {name}")
        context = WebDAVRequestContext(
            self._provider._session_factory,
            self._user,
            self._provider._recycle_delete,
            self.environ,
        )
        try:
            _run_async(context.enforce(handle.mount_id, "list"))
            info = _run_async(handle.adapter.get_info("/"))
            return AdapterCollection("/" + name, self.environ, handle, context, info)
        except Exception:
            return AdapterCollection("/" + name, self.environ, handle, context)

    def get_content_length(self) -> int | None:
        return None

    def get_content_type(self) -> str:
        return "httpd/unix-directory"

    def get_creation_date(self) -> float | None:
        return None

    def get_last_modified(self) -> float | None:
        return time.time()
