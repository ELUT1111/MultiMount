from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import BadRequestException
from app.adapters.base import FileInfo
from app.services import share_service


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return FakeScalars(self._rows)


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.flushed = False
        self.committed = False

    async def execute(self, _stmt):
        return FakeResult(self.rows)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_share_snapshot_keeps_original_file_content(monkeypatch, tmp_path):
    original = b"snapshot-version"

    async def fake_get_info(_db, _mount_id, path):
        assert path == "/report.txt"
        return FileInfo(
            name="report.txt",
            path="/report.txt",
            is_dir=False,
            size=len(original),
            modified_at=None,
            created_at=None,
            mime_type="text/plain",
            permissions=None,
        )

    async def fake_download_file(_db, _mount_id, path):
        assert path == "/report.txt"
        yield original

    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr("app.services.file_service.get_info", fake_get_info)
    monkeypatch.setattr("app.services.file_service.download_file", fake_download_file)

    snapshot = await share_service.create_snapshot(None, 1, "/report.txt")
    link = SimpleNamespace(
        file_path="/report.txt",
        file_name=snapshot["file_name"],
        is_dir=snapshot["is_dir"],
        file_size=snapshot["file_size"],
        mime_type=snapshot["mime_type"],
        snapshot_path=snapshot["snapshot_path"],
        snapshot_size=snapshot["snapshot_size"],
        created_at=None,
    )

    chunks = []
    async for chunk in share_service.stream_snapshot_file(link):
        chunks.append(chunk)

    assert b"".join(chunks) == original
    assert share_service.snapshot_info(link).name == "report.txt"
    assert share_service.snapshot_info(link).size == len(original)


def snapshot_dir(tmp_path, snapshot_path):
    return tmp_path / snapshot_path.rsplit("/", 1)[0]


def make_link(
    tmp_path,
    token="token-1",
    file_path="/report.txt",
    *,
    link_id=1,
    is_dir=False,
    active=True,
    expires_at=None,
):
    snapshot_path = share_service._snapshot_relative_path(1, file_path)
    content = tmp_path / snapshot_path
    content.parent.mkdir(parents=True, exist_ok=True)
    if is_dir:
        content.mkdir()
        (content / "child.txt").write_bytes(b"old")
    else:
        content.write_bytes(b"old")
    return SimpleNamespace(
        id=link_id,
        mount_id=1,
        file_path=file_path,
        file_name=file_path.rstrip("/").split("/")[-1] or "root",
        is_dir=is_dir,
        file_size=3,
        mime_type="text/plain",
        snapshot_path=snapshot_path,
        snapshot_size=3,
        token=token,
        created_at=None,
        expires_at=expires_at,
        max_views=0,
        view_count=0,
        is_active=active,
        access_code=None,
    )


@pytest.mark.asyncio
async def test_deactivate_link_deletes_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path)
    old_snapshot_path = link.snapshot_path
    db = FakeDB([link])

    await share_service.deactivate_link(db, link.id, user_id=None, is_admin=True)

    assert link.is_active is False
    assert link.snapshot_path is None
    assert not snapshot_dir(tmp_path, old_snapshot_path).exists()


@pytest.mark.asyncio
async def test_expired_access_deletes_snapshot_and_deactivates(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    old_snapshot_path = link.snapshot_path
    db = FakeDB([link])

    with pytest.raises(BadRequestException):
        await share_service.validate_and_access(db, link.token)

    assert db.committed is True
    assert link.is_active is False
    assert link.snapshot_path is None
    assert not snapshot_dir(tmp_path, old_snapshot_path).exists()


@pytest.mark.asyncio
async def test_naive_expiration_from_sqlite_is_handled(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1))
    old_snapshot_path = link.snapshot_path
    db = FakeDB([link])

    with pytest.raises(BadRequestException):
        await share_service.validate_and_access(db, link.token)

    assert link.is_active is False
    assert link.snapshot_path is None
    assert not snapshot_dir(tmp_path, old_snapshot_path).exists()


@pytest.mark.asyncio
async def test_reusable_snapshot_ignores_naive_expired_link(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path, expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1))
    db = FakeDB([link])

    async def fake_get_info(_db, _mount_id, path):
        return FileInfo(
            name="report.txt",
            path=path,
            is_dir=False,
            size=3,
            modified_at=None,
            created_at=None,
            mime_type="text/plain",
            permissions=None,
        )

    async def fake_download_file(_db, _mount_id, _path):
        yield b"new"

    monkeypatch.setattr("app.services.file_service.get_info", fake_get_info)
    monkeypatch.setattr("app.services.file_service.download_file", fake_download_file)

    snapshot = await share_service.ensure_share_snapshot(db, 1, "/report.txt")

    assert snapshot["snapshot_path"] == link.snapshot_path
    async for chunk in share_service.stream_snapshot_file(link):
        assert chunk == b"new"


@pytest.mark.asyncio
async def test_validate_without_count_does_not_consume_max_views(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path)
    link.max_views = 1
    db = FakeDB([link])

    await share_service.validate_and_access(db, link.token, count_view=False)

    assert link.view_count == 0
    assert db.flushed is False

    await share_service.validate_and_access(db, link.token)

    assert link.view_count == 1
    assert db.flushed is True


@pytest.mark.asyncio
async def test_source_change_refreshes_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path)
    db = FakeDB([link])

    async def fake_get_info(_db, _mount_id, path):
        return FileInfo(
            name="report.txt",
            path=path,
            is_dir=False,
            size=3,
            modified_at=None,
            created_at=None,
            mime_type="text/plain",
            permissions=None,
        )

    async def fake_download_file(_db, _mount_id, _path):
        yield b"new"

    monkeypatch.setattr("app.services.file_service.get_info", fake_get_info)
    monkeypatch.setattr("app.services.file_service.download_file", fake_download_file)

    result = await share_service.handle_source_changed(db, 1, "/report.txt")

    assert result["refreshed"] == 1
    async for chunk in share_service.stream_snapshot_file(link):
        assert chunk == b"new"


@pytest.mark.asyncio
async def test_source_delete_deactivates_direct_share(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path)
    old_snapshot_path = link.snapshot_path
    db = FakeDB([link])

    result = await share_service.handle_source_deleted(db, 1, "/report.txt")

    assert result["deactivated"] == 1
    assert link.is_active is False
    assert link.snapshot_path is None
    assert not snapshot_dir(tmp_path, old_snapshot_path).exists()


@pytest.mark.asyncio
async def test_shared_snapshot_is_deleted_only_after_last_link_released(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link_a = make_link(tmp_path, token="token-1", link_id=1)
    link_b = make_link(tmp_path, token="token-2", link_id=2)
    shared_snapshot_path = link_a.snapshot_path
    db = FakeDB([link_a, link_b])

    assert link_a.snapshot_path == link_b.snapshot_path

    await share_service.release_snapshot(db, link_a, deactivate=True)

    assert link_a.is_active is False
    assert link_a.snapshot_path is None
    assert snapshot_dir(tmp_path, shared_snapshot_path).exists()

    await share_service.release_snapshot(db, link_b, deactivate=True)

    assert link_b.is_active is False
    assert link_b.snapshot_path is None
    assert not snapshot_dir(tmp_path, shared_snapshot_path).exists()


@pytest.mark.asyncio
async def test_existing_same_source_snapshot_is_reused(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link = make_link(tmp_path)
    db = FakeDB([link])

    async def fail_download(*_args, **_kwargs):
        raise AssertionError("existing snapshot should be reused")
        yield b""

    monkeypatch.setattr("app.services.file_service.download_file", fail_download)

    snapshot = await share_service.ensure_share_snapshot(db, 1, "/report.txt")

    assert snapshot["snapshot_path"] == link.snapshot_path
    assert snapshot["snapshot_size"] == link.snapshot_size


@pytest.mark.asyncio
async def test_source_change_refreshes_shared_snapshot_once(monkeypatch, tmp_path):
    monkeypatch.setattr(share_service, "SNAPSHOT_ROOT", tmp_path)
    link_a = make_link(tmp_path, token="token-1", link_id=1)
    link_b = make_link(tmp_path, token="token-2", link_id=2)
    db = FakeDB([link_a, link_b])
    download_count = 0

    async def fake_get_info(_db, _mount_id, path):
        return FileInfo(
            name="report.txt",
            path=path,
            is_dir=False,
            size=3,
            modified_at=None,
            created_at=None,
            mime_type="text/plain",
            permissions=None,
        )

    async def fake_download_file(_db, _mount_id, _path):
        nonlocal download_count
        download_count += 1
        yield b"new"

    monkeypatch.setattr("app.services.file_service.get_info", fake_get_info)
    monkeypatch.setattr("app.services.file_service.download_file", fake_download_file)

    result = await share_service.handle_source_changed(db, 1, "/report.txt")

    assert result["refreshed"] == 2
    assert download_count == 1
    assert link_a.snapshot_path == link_b.snapshot_path
    async for chunk in share_service.stream_snapshot_file(link_b):
        assert chunk == b"new"
