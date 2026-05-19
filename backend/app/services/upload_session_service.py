import json
import secrets
import shutil
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.services import file_service
from app.utils.path_utils import normalize_path, safe_upload_filename

SESSIONS_DIR = Path("data/upload_sessions")


def _session_dir(upload_id: str) -> Path:
    return SESSIONS_DIR / upload_id


async def init_session(
    filename: str,
    path: str,
    size: int,
    chunk_size: int,
    conflict_policy: str = "error",
    mount_id: int | None = None,
    user_id: int | None = None,
) -> dict:
    safe_name = safe_upload_filename(filename)
    target_dir = normalize_path(path)
    upload_id = secrets.token_urlsafe(18)
    directory = _session_dir(upload_id)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {
        "filename": safe_name,
        "path": target_dir,
        "size": size,
        "chunk_size": chunk_size,
        "conflict_policy": conflict_policy,
        "mount_id": mount_id,
        "user_id": user_id,
        "chunks": [],
    }
    async with aiofiles.open(directory / "meta.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(metadata, ensure_ascii=False))
    return {"upload_id": upload_id, "chunk_size": chunk_size}


async def _load_metadata(upload_id: str) -> dict:
    meta_path = _session_dir(upload_id) / "meta.json"
    if not meta_path.exists():
        raise NotFoundException("上传会话不存在")
    async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
        return json.loads(await f.read())


async def _load_authorized_metadata(upload_id: str, mount_id: int,
                                    user_id: int | None) -> dict:
    metadata = await _load_metadata(upload_id)
    if metadata.get("mount_id") != mount_id or metadata.get("user_id") != user_id:
        raise NotFoundException("上传会话不存在")
    return metadata


async def _save_metadata(upload_id: str, metadata: dict) -> None:
    async with aiofiles.open(_session_dir(upload_id) / "meta.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(metadata, ensure_ascii=False))


async def save_chunk(upload_id: str, index: int, data: AsyncIterator[bytes],
                     mount_id: int, user_id: int | None) -> dict:
    if index < 0:
        raise BadRequestException("分片序号无效")
    metadata = await _load_authorized_metadata(upload_id, mount_id, user_id)
    expected_chunks = (metadata["size"] + metadata["chunk_size"] - 1) // metadata["chunk_size"]
    if index >= expected_chunks:
        raise BadRequestException("分片序号超出范围")

    directory = _session_dir(upload_id)
    chunk_path = directory / f"{index}.part"
    written = 0
    async with aiofiles.open(chunk_path, "wb") as f:
        async for chunk in data:
            written += len(chunk)
            await f.write(chunk)

    chunks = set(metadata.get("chunks", []))
    chunks.add(index)
    metadata["chunks"] = sorted(chunks)
    await _save_metadata(upload_id, metadata)
    return {"upload_id": upload_id, "index": index, "size": written}


async def complete_session(db: AsyncSession, mount_id: int, upload_id: str,
                           user_id: int | None):
    metadata = await _load_authorized_metadata(upload_id, mount_id, user_id)
    directory = _session_dir(upload_id)
    expected_chunks = (metadata["size"] + metadata["chunk_size"] - 1) // metadata["chunk_size"]
    chunks = set(metadata.get("chunks", []))
    missing = [i for i in range(expected_chunks) if i not in chunks]
    if missing:
        raise BadRequestException(f"缺少分片: {missing[:10]}")

    target_path = metadata["path"].rstrip("/") + "/" + metadata["filename"]

    async def iter_chunks():
        for i in range(expected_chunks):
            async with aiofiles.open(directory / f"{i}.part", "rb") as f:
                while chunk := await f.read(1024 * 1024):
                    yield chunk

    try:
        info = await file_service.upload_file(
            db,
            mount_id,
            target_path,
            iter_chunks(),
            metadata["size"],
            conflict_policy=metadata.get("conflict_policy", "error"),
        )
    finally:
        await abort_session(upload_id, mount_id, user_id)
    return info


async def abort_session(upload_id: str, mount_id: int | None = None,
                        user_id: int | None = None) -> None:
    if mount_id is not None:
        await _load_authorized_metadata(upload_id, mount_id, user_id)
    directory = _session_dir(upload_id)
    if not directory.exists():
        return
    shutil.rmtree(directory)
