from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import mounts


@pytest.mark.asyncio
async def test_connection_test_requires_mount_owner(monkeypatch):
    async def fake_get_mount(_db, _mount_id):
        return SimpleNamespace(id=1, user_id=7)

    async def fake_test_mount_connection(_db, _mount_id):
        return True

    monkeypatch.setattr(mounts.mount_service, "get_mount", fake_get_mount)
    monkeypatch.setattr(mounts.mount_service, "test_mount_connection", fake_test_mount_connection)

    user = SimpleNamespace(id=42, role=SimpleNamespace(name="admin"))

    with pytest.raises(HTTPException) as exc:
        await mounts.test_connection(1, user=user, db=None)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_connection_test_allows_owner(monkeypatch):
    async def fake_get_mount(_db, _mount_id):
        return SimpleNamespace(id=1, user_id=42)

    async def fake_test_mount_connection(_db, _mount_id):
        return True

    monkeypatch.setattr(mounts.mount_service, "get_mount", fake_get_mount)
    monkeypatch.setattr(mounts.mount_service, "test_mount_connection", fake_test_mount_connection)

    user = SimpleNamespace(id=42, role=None)

    response = await mounts.test_connection(1, user=user, db=None)

    assert response == {"success": True, "message": "连接成功"}
