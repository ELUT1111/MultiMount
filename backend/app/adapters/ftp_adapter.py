import asyncio
import ftplib
import mimetypes
import queue
import threading
from datetime import datetime
from typing import AsyncIterator

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry

CHUNK_SIZE = 64 * 1024


class _AsyncChunkReader:
    """将 AsyncIterator[bytes] 包装为 file-like 对象, 供同步 FTP SDK 使用"""

    def __init__(self, aiter: AsyncIterator[bytes], loop: asyncio.AbstractEventLoop):
        self._aiter = aiter
        self._loop = loop
        self._buf = b""
        self._done = False

    def read(self, n: int = -1) -> bytes:
        if n == -1:
            while not self._done:
                self._fill_buf()
            data = self._buf
            self._buf = b""
            return data
        while len(self._buf) < n and not self._done:
            self._fill_buf()
        data = self._buf[:n]
        self._buf = self._buf[n:]
        return data

    def _fill_buf(self):
        try:
            chunk = self._loop.run_until_complete(self._aiter.__anext__())
            self._buf += chunk
        except StopAsyncIteration:
            self._done = True


@AdapterRegistry.register("ftp")
class FTPAdapter(BaseAdapter):
    """FTP 协议适配器"""

    def __init__(self, host: str, port: int = 21, username: str = "",
                 password: str = "", passive_mode: bool = True,
                 base_path: str = "/", **_kwargs):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._passive = passive_mode
        self._base_path = base_path
        self._ftp: ftplib.FTP | None = None

    def _get_ftp(self) -> ftplib.FTP:
        if self._ftp is None:
            raise ConnectionError("FTP 未连接")
        return self._ftp

    def _resolve(self, path: str) -> str:
        cleaned = path.lstrip("/") if path != "/" else ""
        return f"{self._base_path.rstrip('/')}/{cleaned}" if cleaned else self._base_path

    async def connect(self) -> bool:
        def _connect():
            ftp = ftplib.FTP()
            ftp.connect(self._host, self._port, timeout=30)
            ftp.login(self._username, self._password)
            if self._passive:
                ftp.set_pasv(True)
            ftp.encoding = "utf-8"
            self._ftp = ftp
            return True

        return await asyncio.to_thread(_connect)

    async def disconnect(self) -> None:
        if self._ftp:
            await asyncio.to_thread(self._ftp.quit)
            self._ftp = None

    async def test_connection(self) -> bool:
        try:
            ok = await self.connect()
            await self.disconnect()
            return ok
        except Exception:
            return False

    async def list_dir(self, path: str) -> list[FileInfo]:
        real = self._resolve(path)
        ftp = self._get_ftp()

        def _list():
            items = []
            ftp.cwd(real)
            lines = []
            ftp.retrlines("LIST", lines.append)
            for line in lines:
                parts = line.split(None, 8)
                if len(parts) < 9:
                    continue
                name = parts[8]
                if name in (".", ".."):
                    continue
                is_dir = parts[0].startswith("d")
                size = int(parts[4]) if not is_dir else 0
                items.append(FileInfo(
                    name=name,
                    path=f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}",
                    is_dir=is_dir,
                    size=size,
                    modified_at=None,
                    created_at=None,
                    mime_type=mimetypes.guess_type(name)[0] if not is_dir else None,
                    permissions=parts[0],
                ))
            return items

        return await asyncio.to_thread(_list)

    async def get_info(self, path: str) -> FileInfo:
        if path in ("", "/"):
            return FileInfo(
                name="/", path="/", is_dir=True, size=0,
                modified_at=None, created_at=None, mime_type=None, permissions=None,
            )
        parent = str(path.rsplit("/", 1)[0]) if "/" in path else "/"
        name = path.rsplit("/", 1)[-1]
        items = await self.list_dir(parent)
        for item in items:
            if item.name == name:
                return item
        raise FileNotFoundError(f"FTP 文件不存在: {path}")

    async def download(self, path: str) -> AsyncIterator[bytes]:
        real = self._resolve(path)
        ftp = self._get_ftp()

        # 使用队列桥接: 线程中通过 transfercmd 读取 → 队列 → 异步 yield
        q: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        exc_holder: list[Exception] = []

        def _reader():
            try:
                with ftp.transfercmd(f"RETR {real}") as conn:
                    while True:
                        chunk = conn.recv(CHUNK_SIZE)
                        if not chunk:
                            break
                        q.put(chunk)
                ftp.voidresp()
            except Exception as e:
                exc_holder.append(e)
            finally:
                q.put(None)

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
        ftp = self._get_ftp()
        loop = asyncio.get_event_loop()

        reader = _AsyncChunkReader(data, loop)

        def _upload():
            ftp.storbinary(f"STOR {real}", reader)

        await asyncio.to_thread(_upload)

    async def delete(self, path: str) -> None:
        real = self._resolve(path)
        ftp = self._get_ftp()

        def _delete():
            try:
                ftp.delete(real)
            except ftplib.error_perm:
                ftp.rmd(real)

        await asyncio.to_thread(_delete)

    async def mkdir(self, path: str) -> None:
        real = self._resolve(path)
        ftp = self._get_ftp()
        await asyncio.to_thread(ftp.mkd, real)

    async def move(self, src: str, dst: str) -> None:
        real_src = self._resolve(src)
        real_dst = self._resolve(dst)
        ftp = self._get_ftp()
        await asyncio.to_thread(ftp.rename, real_src, real_dst)

    async def get_capacity(self) -> dict | None:
        return None
