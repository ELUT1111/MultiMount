import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiofiles

from app.adapters.base import BaseAdapter, FileInfo
from app.adapters.registry import AdapterRegistry


def _to_file_info(path: Path, base: Path) -> FileInfo:
    """将本地路径转为统一 FileInfo"""
    stat = path.stat()
    rel = str(path.relative_to(base)).replace("\\", "/")
    return FileInfo(
        name=path.name,
        path="/" + rel if not rel.startswith("/") else rel,
        is_dir=path.is_dir(),
        size=stat.st_size if path.is_file() else 0,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
        mime_type=mimetypes.guess_type(path.name)[0] if path.is_file() else None,
        permissions=oct(stat.st_mode)[-3:],
    )


@AdapterRegistry.register("local")
@AdapterRegistry.register("managed")
class LocalAdapter(BaseAdapter):
    """本地文件系统适配器"""

    def __init__(self, path: str, **_kwargs):
        self._root = Path(path).resolve()
        if not self._root.exists():
            self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """将虚拟路径解析为真实路径, 防止目录遍历"""
        cleaned = path.lstrip("/").replace("\\", "/")
        target = (self._root / cleaned).resolve()
        try:
            target.relative_to(self._root)
        except ValueError:
            raise ValueError("路径越界")
        return target

    async def connect(self) -> bool:
        return self._root.is_dir()

    async def disconnect(self) -> None:
        pass

    async def test_connection(self) -> bool:
        return self._root.is_dir() and os.access(self._root, os.R_OK)

    async def list_dir(self, path: str) -> list[FileInfo]:
        real = self._resolve(path)
        if not real.is_dir():
            raise FileNotFoundError(f"不是目录: {path}")
        items = []
        for entry in sorted(real.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            items.append(_to_file_info(entry, self._root))
        return items

    async def get_info(self, path: str) -> FileInfo:
        real = self._resolve(path)
        if not real.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        return _to_file_info(real, self._root)

    async def download(self, path: str) -> AsyncIterator[bytes]:
        real = self._resolve(path)
        async with aiofiles.open(real, "rb") as f:
            while chunk := await f.read(64 * 1024):
                yield chunk

    async def download_range(self, path: str, start: int, end: int | None = None) -> AsyncIterator[bytes]:
        real = self._resolve(path)
        if start < 0 or (end is not None and end < start):
            raise ValueError("invalid range")
        remaining = None if end is None else end - start + 1
        async with aiofiles.open(real, "rb") as f:
            await f.seek(start)
            while remaining is None or remaining > 0:
                read_size = 64 * 1024 if remaining is None else min(64 * 1024, remaining)
                chunk = await f.read(read_size)
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk

    async def upload(self, path: str, data: AsyncIterator[bytes], size: int | None = None) -> None:
        real = self._resolve(path)
        real.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(real, "wb") as f:
            async for chunk in data:
                await f.write(chunk)

    async def delete(self, path: str) -> None:
        real = self._resolve(path)
        if real.is_dir():
            shutil.rmtree(real)
        else:
            real.unlink()

    async def mkdir(self, path: str) -> None:
        real = self._resolve(path)
        real.mkdir(parents=True, exist_ok=True)

    async def move(self, src: str, dst: str) -> None:
        real_src = self._resolve(src)
        real_dst = self._resolve(dst)
        real_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(real_src), str(real_dst))

    async def copy(self, src: str, dst: str) -> None:
        real_src = self._resolve(src)
        real_dst = self._resolve(dst)
        real_dst.parent.mkdir(parents=True, exist_ok=True)
        if real_src.is_dir():
            shutil.copytree(str(real_src), str(real_dst))
        else:
            shutil.copy2(str(real_src), str(real_dst))

    async def get_capacity(self) -> dict | None:
        usage = shutil.disk_usage(str(self._root))
        return {"used": usage.used, "total": usage.total}

    async def get_tree_stats(self, root: str = "/") -> dict:
        real_root = self._resolve(root)
        file_count = 0
        total_size = 0
        for entry in real_root.rglob("*"):
            if entry.is_file():
                file_count += 1
                total_size += entry.stat().st_size
        return {"file_count": file_count, "total_size": total_size}
