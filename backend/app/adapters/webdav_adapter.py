import asyncio
import mimetypes
from datetime import datetime
from io import BytesIO
from typing import AsyncIterator

from webdav3.client import Client

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry


def _parse_webdav_time(time_str: str | None) -> datetime | None:
    if not time_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(time_str)
    except Exception:
        return None


@AdapterRegistry.register("webdav")
class WebDAVAdapter(BaseAdapter):
    """WebDAV 客户端适配器 (基于 webdavclient3)"""

    def __init__(self, url: str, username: str = "", password: str = "",
                 verify_ssl: bool = True, **_kwargs):
        self._options = {
            "webdav_hostname": url,
            "webdav_login": username,
            "webdav_password": password,
            "webdav_verify": verify_ssl,
        }
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            raise ConnectionError("WebDAV 未连接")
        return self._client

    async def connect(self) -> bool:
        def _connect():
            self._client = Client(self._options)
            return self._client.check()
        return await asyncio.to_thread(_connect)

    async def disconnect(self) -> None:
        self._client = None

    async def test_connection(self) -> bool:
        try:
            return await self.connect()
        except Exception:
            return False

    async def list_dir(self, path: str) -> list[FileInfo]:
        client = self._get_client()
        clean = path if path.endswith("/") else path + "/"

        def _list():
            items = []
            info_list = client.list(clean, get_info=True)
            for info in info_list:
                name = info.get("name", "").rstrip("/")
                if not name or name in (".", ".."):
                    continue
                is_dir = info.get("isdir", False)
                size = int(info.get("size", 0)) if not is_dir else 0
                items.append(FileInfo(
                    name=name,
                    path=f"{clean}{name}" if clean != "/" else f"/{name}",
                    is_dir=is_dir,
                    size=size,
                    modified_at=_parse_webdav_time(info.get("modified")),
                    created_at=None,
                    mime_type=mimetypes.guess_type(name)[0] if not is_dir else None,
                    permissions=None,
                ))
            return items

        return await asyncio.to_thread(_list)

    async def get_info(self, path: str) -> FileInfo:
        client = self._get_client()

        def _info():
            info = client.info(path)
            name = path.rstrip("/").rsplit("/", 1)[-1] or "/"
            is_dir = info.get("isdir", False)
            return FileInfo(
                name=name,
                path=path,
                is_dir=is_dir,
                size=int(info.get("size", 0)) if not is_dir else 0,
                modified_at=_parse_webdav_time(info.get("modified")),
                created_at=None,
                mime_type=mimetypes.guess_type(name)[0] if not is_dir else None,
                permissions=None,
            )

        return await asyncio.to_thread(_info)

    async def download(self, path: str) -> AsyncIterator[bytes]:
        client = self._get_client()
        buf = BytesIO()

        def _download():
            client.download_from(buff=buf, path=path)

        await asyncio.to_thread(_download)
        buf.seek(0)
        while chunk := buf.read(64 * 1024):
            yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        client = self._get_client()
        buf = BytesIO()
        async for chunk in data:
            buf.write(chunk)
        buf.seek(0)

        def _upload():
            client.upload_to(buff=buf, path=path)

        await asyncio.to_thread(_upload)

    async def delete(self, path: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.clean, path)

    async def mkdir(self, path: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.mkdir, path)

    async def move(self, src: str, dst: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.move, src, dst)
