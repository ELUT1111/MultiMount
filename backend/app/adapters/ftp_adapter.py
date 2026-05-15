import asyncio
import ftplib
import mimetypes
from datetime import datetime
from io import BytesIO
from typing import AsyncIterator

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry


def _parse_ftp_time(time_str: str) -> datetime | None:
    """尝试解析 FTP LIST 返回的时间格式"""
    try:
        # 常见格式: "May 15 14:00" 或 "May 15  2024"
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(time_str)
    except Exception:
        return None


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

        def _download():
            buf = BytesIO()
            ftp.retrbinary(f"RETR {real}", buf.write)
            buf.seek(0)
            return buf.read()

        data = await asyncio.to_thread(_download)
        chunk_size = 64 * 1024
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        real = self._resolve(path)
        ftp = self._get_ftp()

        # 收集所有数据
        buf = BytesIO()
        async for chunk in data:
            buf.write(chunk)
        buf.seek(0)

        def _upload():
            ftp.storbinary(f"STOR {real}", buf)

        await asyncio.to_thread(_upload)

    async def delete(self, path: str) -> None:
        real = self._resolve(path)
        ftp = self._get_ftp()

        def _delete():
            try:
                ftp.delete(real)
            except ftplib.error_perm:
                # 可能是目录
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
