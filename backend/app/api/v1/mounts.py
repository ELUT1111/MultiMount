from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.mount import MountCreate, MountOut, MountUpdate
from app.services import mount_service

router = APIRouter()


def _mount_to_out(mount) -> MountOut:
    """将 ORM 对象转为响应模型, 脱敏配置"""
    data = {
        "id": mount.id,
        "name": mount.name,
        "type": mount.type,
        "status": mount.status,
        "config": mount_service.get_mount_config_masked(mount),
        "advanced_config": mount.advanced_config,
        "capacity_used": mount.capacity_used,
        "capacity_total": mount.capacity_total,
        "last_connected_at": mount.last_connected_at,
        "created_at": mount.created_at,
        "updated_at": mount.updated_at,
    }
    return MountOut(**data)


@router.get("", response_model=list[MountOut])
async def list_mounts(
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mounts = await mount_service.list_mounts(db)
    return [_mount_to_out(m) for m in mounts]


@router.post("", response_model=MountOut, status_code=201)
async def create_mount(
    body: MountCreate,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount = await mount_service.create_mount(
        db, body.name, body.type, body.config, body.advanced_config
    )
    return _mount_to_out(mount)


@router.get("/{mount_id}", response_model=MountOut)
async def get_mount(
    mount_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount = await mount_service.get_mount(db, mount_id)
    return _mount_to_out(mount)


@router.put("/{mount_id}", response_model=MountOut)
async def update_mount(
    mount_id: int,
    body: MountUpdate,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount = await mount_service.update_mount(
        db, mount_id,
        name=body.name,
        config=body.config,
        advanced_config=body.advanced_config,
    )
    return _mount_to_out(mount)


@router.delete("/{mount_id}", status_code=204)
async def delete_mount(
    mount_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await mount_service.delete_mount(db, mount_id)


@router.post("/{mount_id}/test")
async def test_connection(
    mount_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await mount_service.test_mount_connection(db, mount_id)
    return {"success": ok, "message": "连接成功" if ok else "连接失败"}
