"""
WebDAV DAVProvider — 将 WebDAV 协议操作桥接到统一适配器层 (Adapter Layer)。

wsgidav 通过 DAVProvider 接口与文件系统交互, 本实现将所有操作
转发给 BaseAdapter, 从而复用已有的 FTP/SFTP/WebDAV/OSS/S3/Local 适配器,
无需重复实现协议逻辑。

wsgidav 4.x 使用 DAVCollection / DAVNonCollection / DAVProvider 体系。
"""
from __future__ import annotations

import asyncio
import io
import os
import time
from typing import TYPE_CHECKING

from wsgidav import dav_provider, util
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN, HTTP_NOT_FOUND, HTTP_INTERNAL_ERROR

from app.services.trash_service import is_trash_path

if TYPE_CHECKING:
    from app.adapters.base import BaseAdapter, FileInfo

# 运行异步代码的辅助: 在同步 WSGI 环境中调用异步适配器
_loop: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """获取或创建事件循环 (wsgidav 运行在同步线程中)"""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def _run_async(coro):
    """在同步上下文中运行异步协程"""
    loop = _get_loop()
    return loop.run_until_complete(coro)


class _AdapterMixin:
    """适配器操作混入类 — 提供文件读写等通用逻辑"""

    def __init__(self, adapter: "BaseAdapter", file_info: "FileInfo | None" = None):
        self._adapter = adapter
        self._info = file_info

    def _ensure_info(self):
        """延迟加载文件元数据"""
        if self._info is None:
            try:
                self._info = _run_async(self._adapter.get_info(self._adapter_path()))
            except Exception:
                self._info = None

    def _adapter_path(self, path: str | None = None) -> str:
        """将 WebDAV 路径 (/挂载名/子路径) 转成适配器路径 (/子路径)。"""
        resource_path = path if path is not None else self.path
        parts = resource_path.strip("/").split("/", 1)
        return "/" + parts[1] if len(parts) > 1 else "/"


class AdapterCollection(dav_provider.DAVCollection, _AdapterMixin):
    """WebDAV 目录资源 — 对应适配器层的目录"""

    def __init__(self, path: str, environ: dict, adapter: "BaseAdapter",
                 file_info: "FileInfo | None" = None):
        dav_provider.DAVCollection.__init__(self, path, environ)
        _AdapterMixin.__init__(self, adapter, file_info)

    def get_display_info(self) -> dict:
        return {"type": "Directory"}

    def get_member_names(self) -> list[str]:
        """列出目录下的成员名称"""
        try:
            entries = _run_async(self._adapter.list_dir(self._adapter_path()))
            return [e.name for e in entries if not is_trash_path(e.path)]
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, str(e))

    def get_member(self, name: str) -> dav_provider._DAVResource:
        """获取子资源 (文件或目录)"""
        child_path = util.join_uri(self.path, name)
        parts = child_path.strip("/").split("/", 1)
        adapter_path = "/" + parts[1] if len(parts) > 1 else "/"
        if is_trash_path(adapter_path):
            raise DAVError(HTTP_NOT_FOUND, f"资源不存在: {child_path}")
        try:
            info = _run_async(self._adapter.get_info(adapter_path))
            if info.is_dir:
                return AdapterCollection(child_path, self.environ, self._adapter, info)
            else:
                return AdapterNonCollection(child_path, self.environ, self._adapter, info)
        except Exception:
            raise DAVError(HTTP_NOT_FOUND, f"资源不存在: {child_path}")

    def create_collection(self, name: str):
        """创建子目录"""
        dir_path = util.join_uri(self.path, name)
        try:
            _run_async(self._adapter.mkdir(self._adapter_path(dir_path)))
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"创建目录失败: {e}")

    def delete(self):
        """删除目录"""
        try:
            _run_async(self._adapter.delete(self._adapter_path()))
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"删除失败: {e}")

    def copy_move_single(self, dest_path: str, is_move: bool):
        """复制或移动目录"""
        try:
            if is_move:
                _run_async(self._adapter.move(self._adapter_path(), self._adapter_path(dest_path)))
            else:
                _run_async(self._adapter.copy(self._adapter_path(), self._adapter_path(dest_path)))
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"{'移动' if is_move else '复制'}失败: {e}")

    def support_recursive_delete(self) -> bool:
        return False


class AdapterNonCollection(dav_provider.DAVNonCollection, _AdapterMixin):
    """WebDAV 文件资源 — 对应适配器层的文件"""

    def __init__(self, path: str, environ: dict, adapter: "BaseAdapter",
                 file_info: "FileInfo | None" = None):
        dav_provider.DAVNonCollection.__init__(self, path, environ)
        _AdapterMixin.__init__(self, adapter, file_info)

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
        """返回文件内容 (用于 GET 请求)"""
        chunks = []

        async def _collect():
            async for chunk in self._adapter.download(self._adapter_path()):
                chunks.append(chunk)

        try:
            _run_async(_collect())
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"下载失败: {e}")

        return io.BytesIO(b"".join(chunks))

    def begin_write(self, content_type: str = None):
        """开始写入 (用于 PUT 请求)"""
        return _WriteBuffer(self._adapter, self._adapter_path())

    def delete(self):
        """删除文件"""
        try:
            _run_async(self._adapter.delete(self._adapter_path()))
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"删除失败: {e}")

    def copy_move_single(self, dest_path: str, is_move: bool):
        """复制或移动文件"""
        try:
            if is_move:
                _run_async(self._adapter.move(self._adapter_path(), self._adapter_path(dest_path)))
            else:
                _run_async(self._adapter.copy(self._adapter_path(), self._adapter_path(dest_path)))
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"{'移动' if is_move else '复制'}失败: {e}")


class _WriteBuffer:
    """写入缓冲 — 收集 PUT 请求的数据, 关闭时提交到适配器"""

    def __init__(self, adapter: "BaseAdapter", path: str):
        self._adapter = adapter
        self._path = path
        self._buffer = io.BytesIO()

    def write(self, data: bytes):
        self._buffer.write(data)

    def close(self):
        """关闭时将缓冲数据上传到适配器"""
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

        try:
            _run_async(_upload())
        except Exception as e:
            raise DAVError(HTTP_INTERNAL_ERROR, f"上传失败: {e}")
        finally:
            self._buffer.close()


class MultiMountDAVProvider(dav_provider.DAVProvider):
    """
    多挂载点 DAVProvider — 将多个挂载点映射为 WebDAV 根目录下的子目录。

    例如:
      /local-files/   → LocalAdapter
      /ftp-server/    → FTPAdapter
      /oss-bucket/    → OSSAdapter
    """

    def __init__(self, mount_adapters: dict[str, "BaseAdapter"]):
        super().__init__()
        self._adapters = mount_adapters

    def get_resource_inst(self, path: str, environ: dict):
        """根据路径找到对应的适配器资源"""
        parts = path.strip("/").split("/", 1)
        if not parts or not parts[0]:
            # 根目录 — 虚拟集合
            return _RootCollection(path, environ, self._adapters)

        mount_name = parts[0]
        sub_path = "/" + parts[1] if len(parts) > 1 else "/"
        if is_trash_path(sub_path):
            return None

        adapter = self._adapters.get(mount_name)
        if adapter is None:
            return None

        try:
            info = _run_async(adapter.get_info(sub_path))
            if info.is_dir:
                return AdapterCollection(path, environ, adapter, info)
            else:
                return AdapterNonCollection(path, environ, adapter, info)
        except Exception:
            return None


class _RootCollection(dav_provider.DAVCollection):
    """WebDAV 根目录 — 虚拟集合, 包含所有挂载点名称"""

    def __init__(self, path: str, environ: dict, adapters: dict):
        super().__init__(path, environ)
        self._adapters = adapters

    def get_display_info(self) -> dict:
        return {"type": "Root"}

    def get_member_names(self) -> list[str]:
        return list(self._adapters.keys())

    def get_member(self, name: str):
        adapter = self._adapters.get(name)
        if adapter is None:
            raise DAVError(HTTP_NOT_FOUND, f"挂载点不存在: {name}")
        child_path = "/" + name
        try:
            # 尝试获取挂载点根目录信息
            info = _run_async(adapter.get_info("/"))
            return AdapterCollection(child_path, self.environ, adapter, info)
        except Exception:
            # 如果获取信息失败, 仍然返回集合 (可能是空目录)
            return AdapterCollection(child_path, self.environ, adapter)

    def get_content_length(self) -> int | None:
        return None

    def get_content_type(self) -> str:
        return "httpd/unix-directory"

    def get_creation_date(self) -> float | None:
        return None

    def get_last_modified(self) -> float | None:
        return time.time()
