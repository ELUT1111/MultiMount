import secrets
from datetime import datetime, timezone
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.trash_item import TrashItem
from app.services.mount_service import get_adapter_for_mount
from app.utils.path_utils import normalize_path

TRASH_ROOT = "/.mounthub_trash"


def is_trash_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized == TRASH_ROOT or normalized.startswith(TRASH_ROOT + "/")


def _trash_path_for(original_path: str) -> str:
    name = PurePosixPath(normalize_path(original_path)).name
    token = secrets.token_hex(8)
    return f"{TRASH_ROOT}/{token}_{name}"


async def _ensure_trash_root(adapter) -> None:
    try:
        await adapter.mkdir(TRASH_ROOT)
    except Exception:
        pass


async def trash_file(db: AsyncSession, mount_id: int, path: str, user=None) -> TrashItem:
    original_path = normalize_path(path)
    if original_path == "/":
        raise BadRequestException("不能删除根目录")
    if is_trash_path(original_path):
        raise BadRequestException("不能将回收站内部项目再次移入回收站")

    _, adapter = await get_adapter_for_mount(db, mount_id)
    await adapter.connect()
    try:
        info = await adapter.get_info(original_path)
        await _ensure_trash_root(adapter)
        trash_path = _trash_path_for(original_path)
        await adapter.move(original_path, trash_path)
    except FileNotFoundError:
        raise NotFoundException(f"文件不存在: {original_path}")
    except Exception as exc:
        raise BadRequestException(f"移入回收站失败: {exc}")

    item = TrashItem(
        mount_id=mount_id,
        original_path=original_path,
        trash_path=trash_path,
        name=info.name,
        is_dir=info.is_dir,
        size=info.size,
        deleted_by=getattr(user, "id", None),
        deleted_by_name=getattr(user, "username", None),
        deleted_at=datetime.now(timezone.utc),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def list_trash_items(db: AsyncSession, mount_ids: set[int] | None = None) -> list[TrashItem]:
    query = select(TrashItem).order_by(TrashItem.deleted_at.desc(), TrashItem.id.desc())
    if mount_ids is not None:
        if not mount_ids:
            return []
        query = query.where(TrashItem.mount_id.in_(mount_ids))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_trash_item(db: AsyncSession, item_id: int) -> TrashItem:
    result = await db.execute(select(TrashItem).where(TrashItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundException("回收站项目不存在")
    return item


async def restore_trash_item(db: AsyncSession, item_id: int, conflict_policy: str = "rename") -> TrashItem:
    from app.services import file_service

    item = await get_trash_item(db, item_id)
    target_path, should_skip = await file_service.resolve_conflict(
        db, item.mount_id, item.original_path, conflict_policy
    )
    if should_skip:
        raise BadRequestException("目标路径已存在，已跳过恢复")

    _, adapter = await get_adapter_for_mount(db, item.mount_id)
    await adapter.connect()
    try:
        await adapter.move(item.trash_path, target_path)
    except FileNotFoundError:
        raise NotFoundException("回收站中的文件不存在")
    except Exception as exc:
        raise BadRequestException(f"恢复失败: {exc}")

    item.original_path = target_path
    await db.delete(item)
    await db.flush()
    return item


async def purge_trash_item(db: AsyncSession, item_id: int) -> TrashItem:
    item = await get_trash_item(db, item_id)
    _, adapter = await get_adapter_for_mount(db, item.mount_id)
    await adapter.connect()
    try:
        await adapter.delete(item.trash_path)
    except FileNotFoundError:
        pass
    except Exception as exc:
        raise BadRequestException(f"彻底删除失败: {exc}")

    await db.delete(item)
    await db.flush()
    return item
