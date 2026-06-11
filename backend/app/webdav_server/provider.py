from __future__ import annotations

import asyncio
import io
import os
import threading
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

_thread_state = threading.local()
MOUNT_CACHE_TTL_SECONDS = 15


def _get_loop() -> asyncio.AbstractEventLoop:
    # WsgiDAV/cheroot 用多线程同步模型处理请求；每个线程独立 event loop，
    # 避免多个线程同时 run_until_complete 同一个 loop。
    loop = getattr(_thread_state, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_state.loop = loop
    return loop


def _run_async(coro):
    try:
        return _get_loop().run_until_complete(coro)
    except RuntimeError:
        # 如果协程还没被 loop 接管就失败，主动 close 避免 RuntimeWarning。
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        raise


@dataclass
class MountHandle:
    # WebDAV 请求处理期间使用的挂载句柄，缓存了已创建并连接的适配器。
    mount_id: int
    name: str
    safe_name: str
    adapter: "BaseAdapter"


def _safe_mount_name(name: str) -> str:
    # WebDAV URL 用 /mount-name/path 表示挂载，挂载名中的斜杠必须替换掉。
    return name.replace("/", "_").replace("\\", "_")


def _dav_status(exc: Exception) -> int:
    # 将项目内部异常粗略映射为 WebDAV/HTTP 状态码。
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
            # WebDAV 文件动作复用和前端 API 一致的文件权限策略。
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
            # WebDAV DELETE 默认也走项目回收站策略，保持和前端文件浏览器一致。
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
            # WebDAV 写入同样要同步搜索索引和分享快照，否则前端搜索/分享会看到旧状态。
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
                # 某些 WsgiDAV 属性查询会重复访问元数据，已传入 file_info 时优先复用。
                self._info = _run_async(self._adapter.get_info(self._adapter_path()))
            except Exception:
                self._info = None

    def _adapter_path(self, path: str | None = None) -> str:
        resource_path = path if path is not None else self.path
        parts = resource_path.strip("/").split("/", 1)
        # WebDAV 路径第一段是挂载点安全名称，第二段以后才是适配器内部路径。
        return normalize_path("/" + parts[1] if len(parts) > 1 else "/")

    def _target_adapter_path(self, dest_path: str) -> str:
        parts = dest_path.strip("/").split("/", 1)
        if not parts or parts[0] != self._handle.safe_name:
            # WsgiDAV copy/move 目标可能跨集合；当前实现只允许同一挂载内移动/复制。
            raise DAVError(HTTP_FORBIDDEN, "Cross-mount WebDAV copy/move is not supported")
        return normalize_path("/" + parts[1] if len(parts) > 1 else "/")

    def _require(self, action: str, adapter_path: str | None = None) -> None:
        path = adapter_path if adapter_path is not None else self._adapter_path()
        if trash_service.is_trash_path(path):
            # 内部回收站目录不对 WebDAV 客户端暴露。
            raise DAVError(HTTP_NOT_FOUND, f"Resource not found: {path}")
        try:
            _run_async(self._context.enforce(self._mount_id, action))
        except Exception as exc:
            raise _dav_error(exc, f"Forbidden: {action}")

    def _log(self, action: str, path: str, target_path: str | None = None, detail: dict | None = None) -> None:
        _run_async(self._context.log(self._mount_id, action, path, target_path, detail=detail))


class AdapterCollection(dav_provider.DAVCollection, _AdapterMixin):
    # 目录资源: 负责列目录、创建子目录、删除目录、目录级 copy/move。
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
            # 避免 Windows 客户端看到 /.mounthub_trash 等内部目录。
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
            # 根据适配器返回的 FileInfo 类型，动态创建目录或文件 DAVResource。
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
        # Windows Explorer 上传新文件时会先创建空资源，再调用 begin_write 写入内容。
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
        # 递归删除交给适配器/回收站服务处理，不让 WsgiDAV 自己逐个子项递归。
        return False


class AdapterNonCollection(dav_provider.DAVNonCollection, _AdapterMixin):
    # 文件资源: 负责下载内容、接收上传写入、删除文件、文件级 copy/move。
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

    def support_etag(self) -> bool:
        # 远端协议不一定能稳定提供 ETag；显式关闭以满足 WsgiDAV 4.x 抽象接口。
        return False

    def get_etag(self) -> str | None:
        return None

    def get_display_info(self) -> dict:
        return {"type": "File"}

    def get_content(self):
        self._require("download")
        chunks = []

        async def _collect():
            # WsgiDAV 期望同步文件对象，这里把异步下载收集到 BytesIO 后返回。
            # 大文件如需优化，可改为兼容 WsgiDAV 的流式 file-like 对象。
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

    def begin_write(self, *, content_type: str = None):
        adapter_path = self._adapter_path()
        self._require("upload", adapter_path)
        # 返回 file-like 对象供 WsgiDAV 写入；真正上传发生在 _WriteBuffer.close。
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
    # WsgiDAV 的 PUT 写入接口是同步 file-like 协议，这里用内存缓冲桥接到异步适配器上传。
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
                # WsgiDAV 以同步 write 写入缓冲区；关闭时再拆成异步块交给适配器上传。
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
    # 根 Provider 将 / 映射为挂载点列表，将 /挂载名/... 映射为具体挂载内路径。
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
        self._mount_cache: dict[tuple[int, int], tuple[float, list[MountHandle]]] = {}

    def get_resource_inst(self, path: str, environ: dict):
        # WsgiDAV 每个请求都通过此方法把 URL 路径解析为 DAVResource 对象。
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
                # 预加载 role，后续权限判断需要读取用户角色。
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
        cache_key = (threading.get_ident(), user.id)
        cached = self._mount_cache.get(cache_key)
        if cached and now - cached[0] < MOUNT_CACHE_TTL_SECONDS:
            return cached[1]

        async def _load():
            async with self._session_factory() as db:
                # 只暴露当前用户可访问的挂载；管理员/超级管理员由权限服务返回全部挂载。
                accessible = await get_accessible_mount_ids(db, user)
                if self._root_mount_id is not None:
                    # 系统设置选择单个 WebDAV 根挂载时，在权限结果上再取交集。
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
                            # WebDAV 服务线程需要直接创建适配器，因此这里重复做敏感字段解密。
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
                            # WebDAV URL 中用 safe_name 区分挂载；同名挂载追加数字后缀。
                            safe_name = f"{base_name}-{suffix}"
                            suffix += 1
                        used_names.add(safe_name)
                        handles.append(MountHandle(mount.id, mount.name, safe_name, adapter))
                    except Exception:
                        continue
                return handles

        handles = _run_async(_load())
        # 按线程缓存挂载句柄，避免每次 PROPFIND 都重新解密配置并连接远端协议。
        self._mount_cache[cache_key] = (now, handles)
        return handles

    def _mount_for_name(self, user: User, safe_name: str) -> MountHandle | None:
        for handle in self._visible_mounts(user):
            if handle.safe_name == safe_name:
                return handle
        return None


class _RootCollection(dav_provider.DAVCollection):
    # WebDAV 根目录资源: 展示当前用户可见的挂载点名称。
    def __init__(self, path: str, environ: dict, provider: MultiMountDAVProvider, user: User):
        super().__init__(path, environ)
        self._provider = provider
        self._user = user

    def get_display_info(self) -> dict:
        return {"type": "Root"}

    def get_member_names(self) -> list[str]:
        # Windows Explorer 打开根目录时会调用此方法列出所有“子文件夹”。
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
            # 根目录信息读取失败时仍返回集合资源，让客户端后续操作再得到具体错误。
            return AdapterCollection("/" + name, self.environ, handle, context)

    def get_content_length(self) -> int | None:
        return None

    def get_content_type(self) -> str:
        return "httpd/unix-directory"

    def get_creation_date(self) -> float | None:
        return None

    def get_last_modified(self) -> float | None:
        return time.time()
