"""Preview and thumbnail helpers for large-file friendly previews."""
from __future__ import annotations

import html
import hashlib
import io
from pathlib import Path

from app.adapters.base import FileInfo
from app.services import file_service
from app.services.search_service import classify_file

THUMB_ROOT = Path("data/preview_cache/thumbnails")
TEXT_PREVIEW_LIMIT = 256 * 1024
IMAGE_CACHE_LIMIT = 8 * 1024 * 1024
THUMBNAIL_SIZE = (320, 200)


def preview_kind(info: FileInfo) -> str:
    kind, _ = classify_file(info.name, info.mime_type, info.is_dir)
    return kind


def _cache_key(mount_id: int, info: FileInfo) -> str:
    marker = f"{mount_id}:{info.path}:{info.size}:{info.modified_at}"
    return hashlib.sha256(marker.encode("utf-8", errors="ignore")).hexdigest()


def _placeholder_svg(title: str, subtitle: str, color: str) -> bytes:
    title = html.escape(title[:24])
    subtitle = html.escape(subtitle[:36])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200">
<rect width="320" height="200" rx="14" fill="{color}"/>
<rect x="22" y="24" width="276" height="152" rx="10" fill="rgba(255,255,255,.16)"/>
<text x="160" y="92" text-anchor="middle" font-family="Arial,sans-serif" font-size="34" font-weight="700" fill="#fff">{title}</text>
<text x="160" y="126" text-anchor="middle" font-family="Arial,sans-serif" font-size="18" fill="rgba(255,255,255,.82)">{subtitle}</text>
</svg>"""
    return svg.encode("utf-8")


async def thumbnail_bytes(db, mount_id: int, path: str) -> tuple[bytes, str]:
    info = await file_service.get_info(db, mount_id, path)
    kind = preview_kind(info)
    key = _cache_key(mount_id, info)
    THUMB_ROOT.mkdir(parents=True, exist_ok=True)
    if kind == "image":
        jpeg_cache = THUMB_ROOT / f"{key}.jpg"
        original_cache = THUMB_ROOT / f"{key}.orig"
        if jpeg_cache.exists():
            return jpeg_cache.read_bytes(), "image/jpeg"
        if original_cache.exists():
            return original_cache.read_bytes(), info.mime_type or "application/octet-stream"
        cache_path = jpeg_cache
    else:
        cache_path = THUMB_ROOT / f"{key}.svg"
        if cache_path.exists():
            return cache_path.read_bytes(), "image/svg+xml"

    if kind == "image" and info.size <= IMAGE_CACHE_LIMIT:
        data = bytearray()
        async for chunk in file_service.download_file(db, mount_id, path):
            data.extend(chunk)
            if len(data) > IMAGE_CACHE_LIMIT:
                break
        if len(data) <= IMAGE_CACHE_LIMIT:
            thumb, media_type, cache_as_thumbnail = _make_image_thumbnail(bytes(data), info.mime_type)
            cache_path = cache_path if cache_as_thumbnail else THUMB_ROOT / f"{key}.orig"
            cache_path.write_bytes(thumb)
            return thumb, media_type

    labels = {
        "image": ("IMAGE", info.name, "#2d6cdf"),
        "video": ("VIDEO", info.name, "#2d6cdf"),
        "audio": ("AUDIO", info.name, "#6f42c1"),
        "pdf": ("PDF", info.name, "#c93c37"),
        "office": ("OFFICE", info.name, "#2b7a4b"),
        "text": ("TEXT", info.name, "#596273"),
        "directory": ("DIR", info.name, "#637381"),
        "other": ("FILE", info.name, "#596273"),
    }
    title, subtitle, color = labels.get(kind, labels["other"])
    data = _placeholder_svg(title, subtitle, color)
    if kind == "image":
        cache_path = THUMB_ROOT / f"{key}.svg"
    cache_path.write_bytes(data)
    return data, "image/svg+xml"


def _make_image_thumbnail(data: bytes, mime_type: str | None) -> tuple[bytes, str, bool]:
    if (mime_type or "").lower() == "image/svg+xml":
        return data, "image/svg+xml", False
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", THUMBNAIL_SIZE, (248, 250, 252))
            x = (THUMBNAIL_SIZE[0] - image.width) // 2
            y = (THUMBNAIL_SIZE[1] - image.height) // 2
            if image.mode in ("RGBA", "LA"):
                canvas.paste(image.convert("RGBA"), (x, y), image.convert("RGBA"))
            else:
                canvas.paste(image.convert("RGB"), (x, y))
            out = io.BytesIO()
            canvas.save(out, format="JPEG", quality=82, optimize=True)
            return out.getvalue(), "image/jpeg", True
    except Exception:
        return data, mime_type or "application/octet-stream", False


def detect_encoding(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def language_for_file(name: str, mime_type: str | None) -> str:
    ext = Path(name).suffix.lower().lstrip(".")
    if ext in {"js", "ts", "py", "json", "xml", "html", "css", "md", "vue", "yaml", "yml", "sql", "sh", "log"}:
        return ext
    if mime_type == "application/json":
        return "json"
    if mime_type == "application/xml":
        return "xml"
    if mime_type and mime_type.startswith("text/"):
        return "text"
    return "text"


async def text_preview(db, mount_id: int, path: str, offset: int, limit: int) -> dict:
    info = await file_service.get_info(db, mount_id, path)
    if info.is_dir:
        return {"content": "", "encoding": "utf-8", "offset": offset, "next_offset": None, "size": 0, "truncated": False}
    limit = min(max(limit, 1), TEXT_PREVIEW_LIMIT)
    end = min((info.size or 0) - 1, offset + limit - 1)
    if end < offset:
        return {
            "content": "",
            "encoding": "utf-8",
            "language": language_for_file(info.name, info.mime_type),
            "offset": offset,
            "next_offset": None,
            "size": info.size or 0,
            "truncated": False,
        }

    data = bytearray()
    async for chunk in file_service.download_file_range(db, mount_id, path, offset, end):
        data.extend(chunk)
    content, encoding = detect_encoding(bytes(data))
    next_offset = end + 1 if end + 1 < (info.size or 0) else None
    return {
        "content": content,
        "encoding": encoding,
        "language": language_for_file(info.name, info.mime_type),
        "offset": offset,
        "next_offset": next_offset,
        "size": info.size or 0,
        "truncated": next_offset is not None,
    }


async def preview_meta(db, mount_id: int, path: str) -> dict:
    info = await file_service.get_info(db, mount_id, path)
    kind = preview_kind(info)
    return {
        "name": info.name,
        "path": info.path,
        "size": info.size,
        "mime_type": info.mime_type,
        "kind": kind,
        "download_url": f"/api/v1/files/{mount_id}/download?path={info.path}",
        "thumbnail_url": f"/api/v1/files/{mount_id}/thumbnail?path={info.path}",
        "text_preview": kind in {"text", "pdf", "office"} or (info.mime_type or "").startswith("text/"),
    }
