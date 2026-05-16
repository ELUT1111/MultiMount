import asyncio
import mimetypes
from datetime import datetime, timezone
from typing import AsyncIterator

import oss2

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry

CHUNK_SIZE = 64 * 1024


@AdapterRegistry.register("oss")
class OSSAdapter(BaseAdapter):
    """阿里云 OSS 适配器"""

    def __init__(self, access_key_id: str = "", access_key_secret: str = "",
                 bucket: str = "", endpoint: str = "", prefix: str = "", **_kwargs):
        self._bucket_name = bucket
        self._prefix = prefix.strip("/")
        self._auth = oss2.Auth(access_key_id, access_key_secret)
        self._endpoint = endpoint
        self._bucket: oss2.Bucket | None = None

    def _get_bucket(self) -> oss2.Bucket:
        if self._bucket is None:
            raise ConnectionError("OSS 未连接")
        return self._bucket

    def _to_key(self, path: str) -> str:
        cleaned = path.lstrip("/")
        if self._prefix:
            return f"{self._prefix}/{cleaned}" if cleaned else self._prefix
        return cleaned

    def _from_key(self, key: str) -> str:
        if self._prefix and key.startswith(self._prefix + "/"):
            return "/" + key[len(self._prefix) + 1:]
        elif self._prefix and key == self._prefix:
            return "/"
        return "/" + key

    async def connect(self) -> bool:
        def _connect():
            self._bucket = oss2.Bucket(self._auth, self._endpoint, self._bucket_name)
            self._bucket.get_bucket_info()
            return True
        return await asyncio.to_thread(_connect)

    async def disconnect(self) -> None:
        self._bucket = None

    async def test_connection(self) -> bool:
        try:
            return await self.connect()
        except Exception:
            return False

    async def list_dir(self, path: str) -> list[FileInfo]:
        bucket = self._get_bucket()
        prefix = self._to_key(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        def _list():
            items = []
            seen = set()
            for obj in oss2.ObjectIterator(bucket, prefix=prefix, delimiter="/"):
                if hasattr(obj, "is_prefix") and obj.is_prefix:
                    dir_name = obj.key[len(prefix):].rstrip("/")
                    if dir_name and "/" not in dir_name:
                        items.append(FileInfo(
                            name=dir_name,
                            path=f"{path.rstrip('/')}/{dir_name}" if path != "/" else f"/{dir_name}",
                            is_dir=True, size=0,
                            modified_at=None, created_at=None, mime_type=None, permissions=None,
                        ))
                        seen.add(dir_name)
                else:
                    name = obj.key[len(prefix):]
                    if not name or name in seen:
                        continue
                    mtime = datetime.fromtimestamp(obj.last_modified, tz=timezone.utc) if obj.last_modified else None
                    items.append(FileInfo(
                        name=name,
                        path=f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}",
                        is_dir=False, size=obj.size,
                        modified_at=mtime, created_at=None,
                        mime_type=mimetypes.guess_type(name)[0], permissions=None,
                    ))
            return items

        return await asyncio.to_thread(_list)

    async def get_info(self, path: str) -> FileInfo:
        bucket = self._get_bucket()
        key = self._to_key(path)

        def _info():
            if not key or key.endswith("/"):
                return FileInfo(
                    name=path.rstrip("/").rsplit("/", 1)[-1] or "/",
                    path=path, is_dir=True, size=0,
                    modified_at=None, created_at=None, mime_type=None, permissions=None,
                )
            meta = bucket.get_object_meta(key)
            name = path.rsplit("/", 1)[-1]
            return FileInfo(
                name=name, path=path, is_dir=False,
                size=meta.content_length,
                modified_at=datetime.fromtimestamp(meta.last_modified, tz=timezone.utc) if meta.last_modified else None,
                created_at=None,
                mime_type=meta.content_type or mimetypes.guess_type(name)[0],
                permissions=None,
            )

        return await asyncio.to_thread(_info)

    async def download(self, path: str) -> AsyncIterator[bytes]:
        bucket = self._get_bucket()
        key = self._to_key(path)

        def _get_result():
            return bucket.get_object(key)

        result = await asyncio.to_thread(_get_result)

        def _read_chunk():
            return result.read(CHUNK_SIZE)

        while True:
            chunk = await asyncio.to_thread(_read_chunk)
            if not chunk:
                break
            yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        bucket = self._get_bucket()
        key = self._to_key(path)
        content_type = mimetypes.guess_type(path)[0]

        # 小文件 (< 8MB): put_object
        # 大文件: multipart (append_object 或 multipart upload)
        SMALL_THRESHOLD = 8 * 1024 * 1024

        if size is not None and size <= SMALL_THRESHOLD:
            buf = b""
            async for chunk in data:
                buf += chunk

            def _upload():
                headers = {}
                if content_type:
                    headers["Content-Type"] = content_type
                bucket.put_object(key, buf, headers=headers if headers else None)

            await asyncio.to_thread(_upload)
        else:
            # Multipart upload — 流式分片上传
            part_size = 10 * 1024 * 1024  # 10MB per part
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type

            def _init():
                return bucket.init_multipart_upload(key, headers=headers if headers else None)

            result = await asyncio.to_thread(_init)
            upload_id = result.upload_id
            parts = []
            part_num = 0
            buf = b""

            try:
                async for chunk in data:
                    buf += chunk
                    while len(buf) >= part_size:
                        part_data = buf[:part_size]
                        buf = buf[part_size:]
                        part_num += 1

                        def _upload_part(data_to_upload=part_data, num=part_num):
                            return bucket.upload_part(key, upload_id, num, data_to_upload)

                        part_result = await asyncio.to_thread(_upload_part)
                        parts.append(oss2.models.PartInfo(part_num, part_result.etag))

                # 上传剩余数据
                if buf:
                    part_num += 1

                    def _upload_last():
                        return bucket.upload_part(key, upload_id, part_num, buf)

                    part_result = await asyncio.to_thread(_upload_last)
                    parts.append(oss2.models.PartInfo(part_num, part_result.etag))

                def _complete():
                    bucket.complete_multipart_upload(key, upload_id, parts)

                await asyncio.to_thread(_complete)
            except Exception:
                def _abort():
                    bucket.abort_multipart_upload(key, upload_id)

                await asyncio.to_thread(_abort)
                raise

    async def delete(self, path: str) -> None:
        bucket = self._get_bucket()
        key = self._to_key(path)
        await asyncio.to_thread(bucket.delete_object, key)

    async def mkdir(self, path: str) -> None:
        bucket = self._get_bucket()
        key = self._to_key(path)
        if not key.endswith("/"):
            key += "/"
        await asyncio.to_thread(bucket.put_object, key, b"")

    async def move(self, src: str, dst: str) -> None:
        bucket = self._get_bucket()
        src_key = self._to_key(src)
        dst_key = self._to_key(dst)

        def _move():
            bucket.copy_object(self._bucket_name, src_key, dst_key)
            bucket.delete_object(src_key)

        await asyncio.to_thread(_move)

    async def get_capacity(self) -> dict | None:
        return None
