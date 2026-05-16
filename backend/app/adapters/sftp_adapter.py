import asyncio
import mimetypes
import queue
import stat
from datetime import datetime, timezone
from typing import AsyncIterator

import paramiko

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry

CHUNK_SIZE = 64 * 1024


@AdapterRegistry.register("sftp")
class SFTPAdapter(BaseAdapter):
    """SFTP 协议适配器 (基于 paramiko)"""

    def __init__(self, host: str, port: int = 22, username: str = "",
                 password: str = "", private_key: str = "",
                 base_path: str = "/", **_kwargs):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._private_key = private_key
        self._base_path = base_path
        self._transport: paramiko.Transport | None = None
        self._sftp: paramiko.SFTPClient | None = None

    def _get_sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise ConnectionError("SFTP 未连接")
        return self._sftp

    def _resolve(self, path: str) -> str:
        import posixpath
        cleaned = path.lstrip("/") if path != "/" else ""
        resolved = posixpath.normpath(f"{self._base_path.rstrip('/')}/{cleaned}") if cleaned else self._base_path
        base = self._base_path.rstrip("/")
        if not resolved.startswith(base) and resolved != base:
            raise ValueError("路径越界")
        return resolved

    async def connect(self) -> bool:
        def _connect():
            transport = paramiko.Transport((self._host, self._port))
            transport.connect()
            if self._private_key:
                pkey = paramiko.RSAKey.from_private_key_file(self._private_key)
                transport.auth_publickey(self._username, pkey)
            else:
                transport.auth_password(self._username, self._password)
            self._transport = transport
            self._sftp = paramiko.SFTPClient.from_transport(transport)
            return True

        return await asyncio.to_thread(_connect)

    async def disconnect(self) -> None:
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._transport:
            self._transport.close()
            self._transport = None

    async def test_connection(self) -> bool:
        try:
            ok = await self.connect()
            await self.disconnect()
            return ok
        except Exception:
            return False

    async def list_dir(self, path: str) -> list[FileInfo]:
        real = self._resolve(path)
        sftp = self._get_sftp()

        def _list():
            items = []
            for entry in sorted(sftp.listdir_attr(real), key=lambda e: e.filename):
                name = entry.filename
                if name in (".", ".."):
                    continue
                is_dir = stat.S_ISDIR(entry.st_mode) if entry.st_mode else False
                rel = f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}"
                mtime = datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc) if entry.st_mtime else None
                items.append(FileInfo(
                    name=name,
                    path=rel,
                    is_dir=is_dir,
                    size=entry.st_size or 0,
                    modified_at=mtime,
                    created_at=None,
                    mime_type=mimetypes.guess_type(name)[0] if not is_dir else None,
                    permissions=oct(entry.st_mode)[-3:] if entry.st_mode else None,
                ))
            return items

        return await asyncio.to_thread(_list)

    async def get_info(self, path: str) -> FileInfo:
        real = self._resolve(path)
        sftp = self._get_sftp()

        def _info():
            st = sftp.stat(real)
            is_dir = stat.S_ISDIR(st.st_mode) if st.st_mode else False
            name = path.rsplit("/", 1)[-1] or "/"
            return FileInfo(
                name=name,
                path=path,
                is_dir=is_dir,
                size=st.st_size or 0,
                modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc) if st.st_mtime else None,
                created_at=None,
                mime_type=mimetypes.guess_type(name)[0] if not is_dir else None,
                permissions=oct(st.st_mode)[-3:] if st.st_mode else None,
            )

        return await asyncio.to_thread(_info)

    async def download(self, path: str) -> AsyncIterator[bytes]:
        real = self._resolve(path)
        sftp = self._get_sftp()

        # 使用队列桥接: 线程中读取 SFTP → 队列 → 异步生成器 yield
        q: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        exc_holder: list[Exception] = []

        def _reader():
            try:
                with sftp.open(real, "rb") as f:
                    f.prefetch()
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        q.put(chunk)
            except Exception as e:
                exc_holder.append(e)
            finally:
                q.put(None)

        import threading
        t = threading.Thread(target=_reader, daemon=True)
        t.start()

        loop = asyncio.get_event_loop()

        while True:
            chunk = await loop.run_in_executor(None, q.get)
            if exc_holder:
                raise exc_holder[0]
            if chunk is None:
                break
            yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        real = self._resolve(path)
        sftp = self._get_sftp()

        # 使用队列桥接: 异步迭代器 → 队列 → 线程中写入 SFTP
        q: queue.Queue[bytes | None] = queue.Queue(maxsize=16)
        exc_holder: list[Exception] = []
        loop = asyncio.get_event_loop()

        async def _producer():
            try:
                async for chunk in data:
                    q.put(chunk)
            except Exception as e:
                exc_holder.append(e)
            finally:
                q.put(None)

        def _consumer():
            with sftp.open(real, "wb") as f:
                while True:
                    chunk = q.get()
                    if chunk is None:
                        break
                    if exc_holder:
                        raise exc_holder[0]
                    f.write(chunk)

        producer_task = asyncio.create_task(_producer())
        try:
            await asyncio.to_thread(_consumer)
        finally:
            await producer_task

    async def delete(self, path: str) -> None:
        real = self._resolve(path)
        sftp = self._get_sftp()

        def _delete():
            st = sftp.stat(real)
            if stat.S_ISDIR(st.st_mode):
                sftp.rmdir(real)
            else:
                sftp.remove(real)

        await asyncio.to_thread(_delete)

    async def mkdir(self, path: str) -> None:
        real = self._resolve(path)
        sftp = self._get_sftp()
        await asyncio.to_thread(sftp.mkdir, real)

    async def move(self, src: str, dst: str) -> None:
        real_src = self._resolve(src)
        real_dst = self._resolve(dst)
        sftp = self._get_sftp()
        await asyncio.to_thread(sftp.rename, real_src, real_dst)

    async def get_capacity(self) -> dict | None:
        sftp = self._get_sftp()

        def _cap():
            st = sftp.stat(self._base_path)
            return None

        return await asyncio.to_thread(_cap)
