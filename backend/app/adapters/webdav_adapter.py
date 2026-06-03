import asyncio
import mimetypes
from datetime import datetime
from pathlib import PurePosixPath
from typing import AsyncIterator
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from webdav3.client import Client

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry

CHUNK_SIZE = 64 * 1024


def _parse_webdav_time(time_str: str | None) -> datetime | None:
    if not time_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(time_str)
    except Exception:
        return None


def _normalize_webdav_url(url: str, port: int | None = None, root_path: str = "") -> tuple[str, str]:
    clean_url = url.strip()
    if not clean_url:
        return clean_url, ""

    parsed = urlsplit(clean_url)
    if not parsed.scheme or not parsed.netloc:
        return clean_url.rstrip("/"), ""

    port_number = None
    if port is not None:
        try:
            parsed_port = int(port)
        except (TypeError, ValueError):
            parsed_port = None
        if parsed_port is not None and 1 <= parsed_port <= 65535:
            port_number = parsed_port

    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    username = parsed.username or ""
    password = parsed.password or ""
    credentials = ""
    if username:
        credentials = username
        if password:
            credentials += f":{password}"
        credentials += "@"

    netloc = f"{credentials}{hostname}"
    if port_number is not None:
        netloc += f":{port_number}"
    elif parsed.port is not None:
        netloc += f":{parsed.port}"

    path = parsed.path
    if root_path:
        path = root_path if root_path.startswith("/") else f"/{root_path}"
    hostname = urlunsplit((parsed.scheme, netloc, "", parsed.query, parsed.fragment)).rstrip("/")
    return hostname, path.rstrip("/") or ""


def _normalize_auth_type(auth_type: str) -> str:
    value = (auth_type or "basic").strip().lower()
    return value if value in {"basic", "digest"} else "basic"


def _webdav_item_name(info: dict) -> str:
    raw_name = info.get("name")
    if raw_name:
        return str(raw_name).rstrip("/")

    raw_path = info.get("path") or ""
    path = unquote(urlsplit(str(raw_path)).path).rstrip("/")
    if not path:
        return ""
    return PurePosixPath(path).name


@AdapterRegistry.register("webdav")
class WebDAVAdapter(BaseAdapter):
    """WebDAV 客户端适配器 (基于 webdavclient3)"""

    def __init__(self, url: str, username: str = "", password: str = "",
                 verify_ssl: bool = True, port: int | None = None,
                 root_path: str = "", auth_type: str = "basic", **_kwargs):
        hostname, webdav_root = _normalize_webdav_url(url, port, root_path)
        self._auth_type = _normalize_auth_type(auth_type)
        self._options = {
            "webdav_hostname": hostname,
            "webdav_root": webdav_root,
            "webdav_login": username,
            "webdav_password": password,
            "webdav_verify": verify_ssl,
        }
        self._base_url = f"{hostname.rstrip('/')}{webdav_root}".rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._client: Client | None = None

    def _auth(self):
        if not self._username or not self._password:
            return None
        if self._auth_type == "digest":
            return HTTPDigestAuth(self._username, self._password)
        return HTTPBasicAuth(self._username, self._password)

    def _get_client(self) -> Client:
        if self._client is None:
            raise ConnectionError("WebDAV 未连接")
        return self._client

    def _get_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    async def connect(self) -> bool:
        def _connect():
            self._client = Client(self._options)
            self._client.session.auth = self._auth()
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
                name = _webdav_item_name(info)
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
        url = self._get_url(path)

        def _download():
            resp = requests.get(
                url, auth=self._auth(),
                verify=self._verify_ssl, stream=True,
            )
            resp.raise_for_status()
            return resp

        resp = await asyncio.to_thread(_download)

        def _read_chunk():
            return resp.raw.read(CHUNK_SIZE)

        while True:
            chunk = await asyncio.to_thread(_read_chunk)
            if not chunk:
                break
            yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        url = self._get_url(path)
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"

        # 使用 requests 直接上传, 支持 chunked transfer encoding
        import queue as queue_mod
        q: queue_mod.Queue[bytes | None] = queue_mod.Queue(maxsize=16)
        exc_holder: list[Exception] = []

        async def _producer():
            try:
                async for chunk in data:
                    q.put(chunk)
            except Exception as e:
                exc_holder.append(e)
            finally:
                q.put(None)

        def _chunk_iter():
            while True:
                chunk = q.get()
                if chunk is None:
                    break
                if exc_holder:
                    raise exc_holder[0]
                yield chunk

        def _upload():
            resp = requests.put(
                url, data=_chunk_iter(),
                auth=self._auth(),
                verify=self._verify_ssl,
                headers={"Content-Type": content_type},
            )
            resp.raise_for_status()

        producer_task = asyncio.create_task(_producer())
        try:
            await asyncio.to_thread(_upload)
        finally:
            await producer_task

    async def delete(self, path: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.clean, path)

    async def mkdir(self, path: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.mkdir, path)

    async def move(self, src: str, dst: str) -> None:
        client = self._get_client()
        await asyncio.to_thread(client.move, src, dst)
