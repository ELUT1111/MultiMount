from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.services import share_service


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeDB:
    def __init__(self, *values):
        self.values = list(values)
        self.deleted = []
        self.flushed = False

    async def execute(self, _stmt):
        return FakeResult(self.values.pop(0))

    async def delete(self, item):
        self.deleted.append(item)

    async def flush(self):
        self.flushed = True


def actor(user_id: int, role_name: str):
    return SimpleNamespace(id=user_id, role=SimpleNamespace(name=role_name))


def link(created_by: int):
    return SimpleNamespace(
        id=10,
        created_by=created_by,
        snapshot_path=None,
        snapshot_size=0,
    )


@pytest.mark.asyncio
async def test_admin_cannot_delete_other_admin_share():
    target = link(created_by=7)
    db = FakeDB(target, "admin")

    with pytest.raises(BadRequestException):
        await share_service.delete_share_link(
            db,
            target.id,
            user_id=2,
            is_admin=True,
            actor=actor(2, "admin"),
        )

    assert db.deleted == []


@pytest.mark.asyncio
async def test_admin_can_delete_regular_user_share():
    target = link(created_by=7)
    db = FakeDB(target, "user")

    await share_service.delete_share_link(
        db,
        target.id,
        user_id=2,
        is_admin=True,
        actor=actor(2, "admin"),
    )

    assert db.deleted == [target]


@pytest.mark.asyncio
async def test_super_admin_lists_all_links(monkeypatch):
    expected = [link(created_by=1), link(created_by=2)]

    async def fake_list_all_links(_db):
        return expected

    monkeypatch.setattr(share_service, "list_all_links", fake_list_all_links)

    visible = await share_service.list_visible_links(FakeDB(), actor(1, "super_admin"))

    assert visible == expected


@pytest.mark.asyncio
async def test_regular_user_lists_only_own_links(monkeypatch):
    expected = [link(created_by=5)]

    async def fake_list_user_links(_db, user_id):
        assert user_id == 5
        return expected

    monkeypatch.setattr(share_service, "list_user_links", fake_list_user_links)

    visible = await share_service.list_visible_links(FakeDB(), actor(5, "user"))

    assert visible == expected


@pytest.mark.asyncio
async def test_admin_lists_filtered_links_from_query():
    own = link(created_by=2)
    regular_user = link(created_by=7)
    db = FakeDB([own, regular_user])

    visible = await share_service.list_visible_links(db, actor(2, "admin"))

    assert visible == [own, regular_user]


@pytest.mark.asyncio
async def test_super_admin_can_delete_admin_share():
    target = link(created_by=7)
    db = FakeDB(target)

    await share_service.delete_share_link(
        db,
        target.id,
        user_id=1,
        is_admin=True,
        actor=actor(1, "super_admin"),
    )

    assert db.deleted == [target]
