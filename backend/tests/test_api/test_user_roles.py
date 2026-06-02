from types import SimpleNamespace

import pytest

from app.api.v1 import users
from app.core.exceptions import ForbiddenException
from app.dependencies import require_admin
from app.services import user_service


def user_with_role(role_name: str | None):
    role = SimpleNamespace(name=role_name) if role_name else None
    return SimpleNamespace(id=1, role=role)


@pytest.mark.asyncio
async def test_require_admin_accepts_super_admin():
    super_admin = user_with_role("super_admin")

    assert await require_admin(super_admin) is super_admin


@pytest.mark.asyncio
async def test_admin_cannot_grant_admin_role(monkeypatch):
    async def fake_get_role(_db, _role_id):
        return SimpleNamespace(id=_role_id, name="admin")

    monkeypatch.setattr(users.user_service, "get_role", fake_get_role)

    with pytest.raises(ForbiddenException):
        await users._validate_role_assignment(
            db=None,
            actor=user_with_role("admin"),
            target_user=user_with_role("user"),
            next_role_id=2,
        )


@pytest.mark.asyncio
async def test_super_admin_can_grant_admin_role(monkeypatch):
    async def fake_get_role(_db, _role_id):
        return SimpleNamespace(id=_role_id, name="admin")

    monkeypatch.setattr(users.user_service, "get_role", fake_get_role)

    await users._validate_role_assignment(
        db=None,
        actor=user_with_role("super_admin"),
        target_user=user_with_role("user"),
        next_role_id=2,
    )


@pytest.mark.asyncio
async def test_admin_cannot_remove_admin_role(monkeypatch):
    async def fake_get_role(_db, _role_id):
        return SimpleNamespace(id=_role_id, name="user")

    monkeypatch.setattr(users.user_service, "get_role", fake_get_role)

    with pytest.raises(ForbiddenException):
        await users._validate_role_assignment(
            db=None,
            actor=user_with_role("admin"),
            target_user=user_with_role("admin"),
            next_role_id=3,
        )


@pytest.mark.asyncio
async def test_super_admin_can_remove_admin_role():
    await users._validate_role_assignment(
        db=None,
        actor=user_with_role("super_admin"),
        target_user=user_with_role("admin"),
        next_role_id=None,
    )


@pytest.mark.asyncio
async def test_super_admin_role_cannot_be_assigned(monkeypatch):
    async def fake_get_role(_db, _role_id):
        return SimpleNamespace(id=_role_id, name="super_admin")

    monkeypatch.setattr(users.user_service, "get_role", fake_get_role)

    with pytest.raises(ForbiddenException):
        await users._validate_role_assignment(
            db=None,
            actor=user_with_role("super_admin"),
            target_user=user_with_role("user"),
            next_role_id=1,
        )


@pytest.mark.asyncio
async def test_update_user_can_clear_role_id_when_explicitly_allowed(monkeypatch):
    target = SimpleNamespace(id=9, role_id=2)

    async def fake_get_user(_db, _user_id):
        return target

    class FakeDB:
        async def flush(self):
            return None

        async def refresh(self, _user):
            return None

    monkeypatch.setattr(user_service, "get_user", fake_get_user)

    await user_service.update_user(FakeDB(), 9, role_id=None)
    assert target.role_id == 2

    await user_service.update_user(FakeDB(), 9, role_id=None, allow_null_fields={"role_id"})
    assert target.role_id is None
