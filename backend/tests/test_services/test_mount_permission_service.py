from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import mount_permission_service


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.execute_count = 0

    async def execute(self, _stmt):
        self.execute_count += 1
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_admin_has_readwrite_access_to_any_mount_without_lookup():
    db = FakeDB([])
    user = SimpleNamespace(id=42, role=SimpleNamespace(name="admin"))

    level = await mount_permission_service.check_mount_access(
        db,
        mount_id=999,
        user=user,
        required_level="readwrite",
    )

    assert level == "readwrite"
    assert db.execute_count == 0


@pytest.mark.asyncio
async def test_request_access_rejects_duplicate_pending_request():
    db = FakeDB([
        FakeResult([(7, "team-mount")]),
        FakeResult([({"requester_id": 42, "requested_level": "read"},)]),
    ])

    with pytest.raises(HTTPException) as exc:
        await mount_permission_service.request_access(
            db,
            mount_id=1,
            user_id=42,
            requested_level="readwrite",
            username="alice",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_request_access_allows_request_after_previous_handled(monkeypatch):
    created = []

    async def fake_create_notification(*args, **kwargs):
        created.append((args, kwargs))

    monkeypatch.setattr(
        "app.services.notification_service.create_notification",
        fake_create_notification,
    )
    db = FakeDB([
        FakeResult([(7, "team-mount")]),
        FakeResult([({"requester_id": 42, "action_status": "denied"},)]),
    ])

    await mount_permission_service.request_access(
        db,
        mount_id=1,
        user_id=42,
        requested_level="read",
        username="alice",
    )

    assert len(created) == 1
