from types import SimpleNamespace

import pytest

from app.api.v1.files import _parse_range_header
from app.schemas.transfer import TransferCreateRequest
from app.services import file_service, transfer_service


def test_parse_range_header_supports_start_end():
    assert _parse_range_header("bytes=10-19", 100) == (10, 19)


def test_parse_range_header_supports_suffix_range():
    assert _parse_range_header("bytes=-10", 100) == (90, 99)


def test_transfer_create_request_rejects_upload_download_tasks():
    with pytest.raises(Exception):
        TransferCreateRequest(
            type="upload",
            mount_id=1,
            source_path="/local.bin",
            target_path="/remote.bin",
            file_name="local.bin",
        )

    with pytest.raises(Exception):
        TransferCreateRequest(
            type="download",
            mount_id=1,
            source_path="/remote.bin",
            target_path="/local.bin",
            file_name="remote.bin",
        )


@pytest.mark.asyncio
async def test_download_file_range_streams_only_requested_bytes(monkeypatch):
    class FakeAdapter:
        async def connect(self):
            return True

        async def download_range(self, path, start, end=None):
            assert path == "/file.bin"
            assert start == 2
            assert end == 6
            yield b"cde"
            yield b"fg"

    async def fake_get_adapter_for_mount(_db, mount_id):
        assert mount_id == 1
        return None, FakeAdapter()

    monkeypatch.setattr(file_service, "get_adapter_for_mount", fake_get_adapter_for_mount)

    chunks = []
    async for chunk in file_service.download_file_range(None, 1, "/file.bin", 2, 6):
        chunks.append(chunk)

    assert b"".join(chunks) == b"cdefg"


@pytest.mark.asyncio
async def test_resolve_task_limits_uses_lowest_positive_limit(monkeypatch):
    monkeypatch.setattr(
        transfer_service,
        "get_settings",
        lambda: SimpleNamespace(
            TRANSFER_DEFAULT_DOWNLOAD_LIMIT_KBPS=0,
            TRANSFER_DEFAULT_UPLOAD_LIMIT_KBPS=0,
        ),
    )

    async def fake_user_limits(_db, _user_id):
        return {"max_download_kbps": 200, "max_upload_kbps": 500}

    async def fake_mount_qos(_db, mount_id):
        if mount_id == 1:
            return {"max_download_kbps": 100}
        return {"max_upload_kbps": 300}

    monkeypatch.setattr(transfer_service, "_load_user_limits", fake_user_limits)
    monkeypatch.setattr(transfer_service, "_load_mount_qos", fake_mount_qos)

    download_bps, upload_bps = await transfer_service._resolve_task_limits(
        None,
        user_id=7,
        source_mount_id=1,
        target_mount_id=2,
        download_limit_kbps=150,
        upload_limit_kbps=400,
    )

    assert download_bps == 100 * 1024
    assert upload_bps == 300 * 1024
