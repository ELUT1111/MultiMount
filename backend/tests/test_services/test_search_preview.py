from types import SimpleNamespace

import pytest

from app.services.preview_service import detect_encoding, language_for_file, text_preview
from app.services.search_service import classify_file


def test_classify_file_detects_common_preview_types():
    assert classify_file("photo.jpg", "image/jpeg", False) == ("image", ".jpg")
    assert classify_file("movie.mp4", None, False) == ("video", ".mp4")
    assert classify_file("manual.pdf", "application/pdf", False) == ("pdf", ".pdf")
    assert classify_file("report.docx", None, False) == ("office", ".docx")
    assert classify_file("notes.md", None, False) == ("text", ".md")
    assert classify_file("folder", None, True) == ("directory", "")


def test_detect_encoding_supports_utf8_sig_and_gb18030():
    assert detect_encoding(b"\xef\xbb\xbfhello") == ("hello", "utf-8-sig")
    content, encoding = detect_encoding("中文".encode("gb18030"))
    assert content == "中文"
    assert encoding == "gb18030"


def test_language_for_file_prefers_extension_and_mime():
    assert language_for_file("app.py", None) == "py"
    assert language_for_file("data.bin", "application/json") == "json"
    assert language_for_file("readme.unknown", "text/plain") == "text"


@pytest.mark.asyncio
async def test_text_preview_loads_requested_chunk(monkeypatch):
    info = SimpleNamespace(
        name="data.json",
        path="/data.json",
        is_dir=False,
        size=11,
        mime_type="application/json",
    )

    async def fake_get_info(_db, _mount_id, _path):
        return info

    async def fake_download_range(_db, _mount_id, _path, start, end):
        assert (start, end) == (0, 4)
        yield b'{"a":'

    monkeypatch.setattr("app.services.preview_service.file_service.get_info", fake_get_info)
    monkeypatch.setattr("app.services.preview_service.file_service.download_file_range", fake_download_range)

    result = await text_preview(None, 1, "/data.json", 0, 5)

    assert result["content"] == '{"a":'
    assert result["language"] == "json"
    assert result["next_offset"] == 5
    assert result["truncated"] is True
