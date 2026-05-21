import asyncio
import mimetypes
from datetime import datetime, timezone
from typing import AsyncIterator

import boto3
from botocore.config import Config as BotoConfig

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry

CHUNK_SIZE = 64 * 1024


@AdapterRegistry.register("s3")
class S3Adapter(BaseAdapter):
    """Amazon S3 / S3 兼容存储适配器"""

    def __init__(self, access_key_id: str = "", access_key_secret: str = "",
                 bucket: str = "", region: str = "us-east-1",
                 endpoint_url: str | None = None, prefix: str = "", **_kwargs):
        self._bucket_name = bucket
        self._prefix = prefix.strip("/")
        self._session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=access_key_secret,
            region_name=region,
        )
        self._endpoint_url = endpoint_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = self._session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                config=BotoConfig(signature_version="s3v4"),
            )
        return self._client

    def _to_key(self, path: str) -> str:
        cleaned = path.lstrip("/")
        if self._prefix:
            return f"{self._prefix}/{cleaned}" if cleaned else self._prefix
        return cleaned

    def _from_key(self, key: str) -> str:
        if self._prefix and key.startswith(self._prefix + "/"):
            return "/" + key[len(self._prefix) + 1:]
        return "/" + key

    async def connect(self) -> bool:
        def _connect():
            client = self._get_client()
            client.head_bucket(Bucket=self._bucket_name)
            return True
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
        prefix = self._to_key(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        def _list():
            items = []
            seen = set()

            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=self._bucket_name, Prefix=prefix, Delimiter="/"
            ):
                for cp in page.get("CommonPrefixes", []):
                    dir_name = cp["Prefix"][len(prefix):].rstrip("/")
                    if dir_name and "/" not in dir_name:
                        items.append(FileInfo(
                            name=dir_name,
                            path=f"{path.rstrip('/')}/{dir_name}" if path != "/" else f"/{dir_name}",
                            is_dir=True, size=0,
                            modified_at=None, created_at=None, mime_type=None, permissions=None,
                        ))
                        seen.add(dir_name)

                for obj in page.get("Contents", []):
                    name = obj["Key"][len(prefix):]
                    if not name or name in seen:
                        continue
                    mtime = obj["LastModified"].replace(tzinfo=timezone.utc) if obj.get("LastModified") else None
                    items.append(FileInfo(
                        name=name,
                        path=f"{path.rstrip('/')}/{name}" if path != "/" else f"/{name}",
                        is_dir=False, size=obj["Size"],
                        modified_at=mtime, created_at=None,
                        mime_type=mimetypes.guess_type(name)[0], permissions=None,
                    ))
            return items

        return await asyncio.to_thread(_list)

    async def get_info(self, path: str) -> FileInfo:
        client = self._get_client()
        key = self._to_key(path)

        def _info():
            if not key or key.endswith("/"):
                return FileInfo(
                    name=path.rstrip("/").rsplit("/", 1)[-1] or "/",
                    path=path, is_dir=True, size=0,
                    modified_at=None, created_at=None, mime_type=None, permissions=None,
                )
            resp = client.head_object(Bucket=self._bucket_name, Key=key)
            name = path.rsplit("/", 1)[-1]
            return FileInfo(
                name=name, path=path, is_dir=False,
                size=resp["ContentLength"],
                modified_at=resp.get("LastModified"),
                created_at=None,
                mime_type=resp.get("ContentType") or mimetypes.guess_type(name)[0],
                permissions=None,
            )

        return await asyncio.to_thread(_info)

    async def download(self, path: str) -> AsyncIterator[bytes]:
        client = self._get_client()
        key = self._to_key(path)

        def _get_body():
            resp = client.get_object(Bucket=self._bucket_name, Key=key)
            return resp["Body"]

        body = await asyncio.to_thread(_get_body)

        def _read_chunk():
            return body.read(CHUNK_SIZE)

        while True:
            chunk = await asyncio.to_thread(_read_chunk)
            if not chunk:
                break
            yield chunk

    async def download_range(self, path: str, start: int, end: int | None = None) -> AsyncIterator[bytes]:
        client = self._get_client()
        key = self._to_key(path)
        range_header = f"bytes={start}-{'' if end is None else end}"

        def _get_body():
            resp = client.get_object(Bucket=self._bucket_name, Key=key, Range=range_header)
            return resp["Body"]

        body = await asyncio.to_thread(_get_body)

        def _read_chunk():
            return body.read(CHUNK_SIZE)

        while True:
            chunk = await asyncio.to_thread(_read_chunk)
            if not chunk:
                break
            yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        client = self._get_client()
        key = self._to_key(path)
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"

        # 小文件 (< 8MB): 内存缓冲 + put_object
        # 大文件: multipart upload
        SMALL_THRESHOLD = 8 * 1024 * 1024

        if size is not None and size <= SMALL_THRESHOLD:
            buf = b""
            async for chunk in data:
                buf += chunk

            def _upload():
                client.put_object(
                    Bucket=self._bucket_name, Key=key, Body=buf,
                    ContentType=content_type,
                )
            await asyncio.to_thread(_upload)
        else:
            # Multipart upload — 真正流式
            def _init():
                return client.create_multipart_upload(
                    Bucket=self._bucket_name, Key=key,
                    ContentType=content_type,
                )

            resp = await asyncio.to_thread(_init)
            upload_id = resp["UploadId"]
            parts = []
            part_num = 0

            try:
                async for chunk in data:
                    part_num += 1
                    part_data = chunk

                    def _upload_part():
                        return client.upload_part(
                            Bucket=self._bucket_name, Key=key,
                            UploadId=upload_id, PartNumber=part_num,
                            Body=part_data,
                        )

                    part_resp = await asyncio.to_thread(_upload_part)
                    parts.append({"PartNumber": part_num, "ETag": part_resp["ETag"]})

                def _complete():
                    client.complete_multipart_upload(
                        Bucket=self._bucket_name, Key=key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )

                await asyncio.to_thread(_complete)
            except Exception:
                def _abort():
                    client.abort_multipart_upload(
                        Bucket=self._bucket_name, Key=key,
                        UploadId=upload_id,
                    )
                await asyncio.to_thread(_abort)
                raise

    async def delete(self, path: str) -> None:
        client = self._get_client()
        key = self._to_key(path)
        await asyncio.to_thread(client.delete_object, Bucket=self._bucket_name, Key=key)

    async def mkdir(self, path: str) -> None:
        client = self._get_client()
        key = self._to_key(path)
        if not key.endswith("/"):
            key += "/"
        await asyncio.to_thread(
            client.put_object, Bucket=self._bucket_name, Key=key, Body=b""
        )

    async def move(self, src: str, dst: str) -> None:
        client = self._get_client()
        src_key = self._to_key(src)
        dst_key = self._to_key(dst)

        def _move():
            client.copy_object(
                Bucket=self._bucket_name, Key=dst_key,
                CopySource={"Bucket": self._bucket_name, "Key": src_key},
            )
            client.delete_object(Bucket=self._bucket_name, Key=src_key)

        await asyncio.to_thread(_move)

    async def get_capacity(self) -> dict | None:
        return None
