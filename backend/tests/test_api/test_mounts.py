from types import SimpleNamespace
from datetime import datetime, timezone

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


@pytest.mark.asyncio
async def test_list_mounts_includes_no_access_mounts_for_permission_request(monkeypatch):
    now = datetime.now(timezone.utc)
    mount = SimpleNamespace(
        id=1,
        name="other-user-mount",
        type="local",
        status="offline",
        config={"path": "/private"},
        advanced_config={"timeout": 30},
        capacity_used=10,
        capacity_total=100,
        last_connected_at=None,
        user_id=7,
        created_at=now,
        updated_at=now,
    )

    async def fake_list_mounts(_db):
        return [mount]

    async def fake_enrich_owner_names(items, _db):
        for item in items:
            item.owner_name = "owner"
        return items

    async def fake_check_mount_access(_db, _mount_id, _user, _required_level="read"):
        raise HTTPException(status_code=403, detail="无权访问此挂载点")

    monkeypatch.setattr(mounts.mount_service, "list_mounts", fake_list_mounts)
    monkeypatch.setattr(mounts, "_enrich_owner_names", fake_enrich_owner_names)
    monkeypatch.setattr(mounts, "check_mount_access", fake_check_mount_access)

    user = SimpleNamespace(id=42, role=SimpleNamespace(name="user"))

    response = await mounts.list_mounts(user=user, db=None)

    assert len(response) == 1
    assert response[0].id == 1
    assert response[0].my_level == "none"
    assert response[0].config == {}
    assert response[0].advanced_config is None
    assert response[0].capacity_used is None
    assert response[0].capacity_total is None
