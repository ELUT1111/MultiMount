from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.mount import MountCreate, MountOut, MountUpdate
from app.services import mount_service
from app.core.mount_permissions import check_basic_permission
from app.services.mount_permission_service import check_mount_access

router = APIRouter()


def _mount_to_out(mount) -> MountOut:
    """将 ORM 对象转为响应模型, 脱敏配置, 附加创建者信息"""
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
        "user_id": mount.user_id,
        "created_at": mount.created_at,
        "updated_at": mount.updated_at,
    }
    return MountOut(**data)


async def _enrich_owner_names(mounts: list[MountOut], db: AsyncSession) -> list[MountOut]:
    """批量填充创建者用户名"""
    user_ids = {m.user_id for m in mounts if m.user_id}
    if not user_ids:
        return mounts
    result = await db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))
    name_map = {uid: uname for uid, uname in result.all()}
    for m in mounts:
        m.owner_name = name_map.get(m.user_id)
    return mounts


async def _enrich_my_level(mounts: list[MountOut], user, db: AsyncSession) -> list[MountOut]:
    """批量填充当前用户对每个挂载的权限等级"""
    is_admin = user.role and user.role.name == "admin"
    for m in mounts:
        if is_admin:
            m.my_level = "readwrite"
        elif m.user_id == user.id:
            m.my_level = "readwrite"
        else:
            try:
                m.my_level = await check_mount_access(db, m.id, user, "read")
            except HTTPException:
                m.my_level = "none"
    return mounts


@router.get("", response_model=list[MountOut])
async def list_mounts(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    all_mounts = await mount_service.list_mounts(db)
    out = [_mount_to_out(m) for m in all_mounts]
    out = await _enrich_owner_names(out, db)
    out = await _enrich_my_level(out, user, db)
    return out


@router.post("", response_model=MountOut, status_code=201)
async def create_mount(
    body: MountCreate,
    user=Depends(check_basic_permission("can_manage_mounts")),
    db: AsyncSession = Depends(get_db),
):
    mount = await mount_service.create_mount(
        db, body.name, body.type, body.config, body.advanced_config,
        user_id=user.id,
    )
    return _mount_to_out(mount)


@router.get("/{mount_id}", response_model=MountOut)
async def get_mount(
    mount_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount = await mount_service.get_mount(db, mount_id)
    out = _mount_to_out(mount)
    out = (await _enrich_owner_names([out], db))[0]
    out = (await _enrich_my_level([out], user, db))[0]
    return out


@router.put("/{mount_id}", response_model=MountOut)
async def update_mount(
    mount_id: int,
    body: MountUpdate,
    user=Depends(check_basic_permission("can_manage_mounts")),
    db: AsyncSession = Depends(get_db),
):
    # 管理员可编辑任意挂载, 普通用户仅可编辑自己的
    is_admin = user.role and user.role.name == "admin"
    existing = await mount_service.get_mount(db, mount_id)
    if not is_admin and existing.user_id and existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能编辑自己创建的挂载")
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
    user=Depends(check_basic_permission("can_manage_mounts")),
    db: AsyncSession = Depends(get_db),
):
    is_admin = user.role and user.role.name == "admin"
    await mount_service.delete_mount(db, mount_id, user_id=user.id, is_admin=is_admin)


@router.post("/{mount_id}/test")
async def test_connection(
    mount_id: int,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await mount_service.test_mount_connection(db, mount_id)
    return {"success": ok, "message": "连接成功" if ok else "连接失败"}
