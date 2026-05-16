from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import PageResult
from app.schemas.user import RoleCreate, RoleOut, RoleUpdate, UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter()


# ── 用户管理 ──────────────────────────────────────────────

@router.get("", response_model=PageResult)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.list_users(db, page, page_size)
    return PageResult(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/all")
async def list_all_users(
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回所有活跃用户的 id 和 username (供权限对话框使用)"""
    result = await db.execute(
        select(User.id, User.username, User.is_active).where(User.is_active == True)
    )
    return [{"id": row[0], "username": row[1]} for row in result.all()]


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.create_user(db, body.username, body.email, body.password, body.role_id)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # 记录旧值用于变更通知
    old_user = await user_service.get_user(db, user_id)
    old_role_id = old_user.role_id
    old_is_active = old_user.is_active

    updated = await user_service.update_user(
        db, user_id,
        email=body.email,
        role_id=body.role_id,
        is_active=body.is_active,
    )

    # 角色变更通知
    if body.role_id is not None and body.role_id != old_role_id:
        from app.services.notification_service import create_notification
        new_role = await user_service.get_role(db, body.role_id)
        await create_notification(
            db, user_id,
            "permission_changed",
            "权限变更",
            f"您的角色已变更为 \"{new_role.name}\"。",
            related_id=body.role_id,
        )

    # 账号禁用通知
    if body.is_active is False and old_is_active:
        from app.services.notification_service import create_notification
        await create_notification(
            db, user_id,
            "account_disabled",
            "账号已被禁用",
            "您的账号已被管理员禁用, 如有疑问请联系管理员。",
        )

    return updated


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_user(db, user_id)


# ── 角色管理 ──────────────────────────────────────────────

@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.list_roles(db)


@router.post("/roles", response_model=RoleOut, status_code=201)
async def create_role(
    body: RoleCreate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.create_role(
        db,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        mount_permissions=body.mount_permissions,
        qos_limits=body.qos_limits,
    )


@router.put("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    body: RoleUpdate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # 检查权限是否变更
    old_role = await user_service.get_role(db, role_id)
    perms_changed = (
        (body.permissions is not None and body.permissions != old_role.permissions)
        or (body.mount_permissions is not None and body.mount_permissions != old_role.mount_permissions)
        or (body.qos_limits is not None and body.qos_limits != old_role.qos_limits)
    )

    updated = await user_service.update_role(
        db, role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        mount_permissions=body.mount_permissions,
        qos_limits=body.qos_limits,
    )

    # 权限变更 → 通知该角色下所有用户
    if perms_changed:
        from sqlalchemy import select as sa_select
        from app.models.user import User
        from app.services.notification_service import create_notification
        result = await db.execute(sa_select(User.id).where(User.role_id == role_id))
        user_ids = [row[0] for row in result.all()]
        for uid in user_ids:
            await create_notification(
                db, uid,
                "permission_changed",
                "角色权限变更",
                f"您所在的角色 \"{updated.name}\" 的权限配置已被管理员更新。",
                related_id=role_id,
            )

    return updated


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_role(db, role_id)
