from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException
from app.core.roles import ROLE_ADMIN, ROLE_SUPER_ADMIN, is_super_admin, is_protected_role_name
from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_super_admin
from app.models.user import User
from app.schemas.common import PageResult
from app.schemas.user import RoleCreate, RoleOut, RoleUpdate, UpdateMeRequest, UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter()


def _role_name(user: User) -> str | None:
    return user.role.name if user.role else None


async def _validate_role_assignment(
    db: AsyncSession,
    actor: User,
    target_user: User | None,
    next_role_id: int | None,
    role_id_provided: bool = True,
) -> None:
    if not role_id_provided:
        return

    next_role_name = None
    if next_role_id is not None:
        next_role = await user_service.get_role(db, next_role_id)
        next_role_name = next_role.name
    current_role_name = _role_name(target_user) if target_user is not None else None

    if next_role_name == ROLE_SUPER_ADMIN:
        raise ForbiddenException("超级管理员身份不可通过权限面板授予")

    if current_role_name == ROLE_SUPER_ADMIN:
        raise ForbiddenException("超级管理员账号不可变更角色")

    was_admin = current_role_name == ROLE_ADMIN
    will_be_admin = next_role_name == ROLE_ADMIN
    if was_admin != will_be_admin and not is_super_admin(actor):
        raise ForbiddenException("只有超级管理员可以指定或取消管理员身份")


def _validate_user_mutation(actor: User, target_user: User, body: UserUpdate) -> None:
    target_role = _role_name(target_user)
    if target_role == ROLE_SUPER_ADMIN:
        if body.role_id is not None:
            raise ForbiddenException("超级管理员账号不可变更角色")
        if body.is_active is False:
            raise ForbiddenException("超级管理员账号不可禁用")
        if not is_super_admin(actor):
            raise ForbiddenException("普通管理员不可修改超级管理员账号")
    if target_role == ROLE_ADMIN and not is_super_admin(actor):
        raise ForbiddenException("只有超级管理员可以修改管理员账号")


async def _validate_role_mutation(db: AsyncSession, role_id: int, next_name: str | None = None) -> None:
    role = await user_service.get_role(db, role_id)
    if is_protected_role_name(role.name) and next_name is not None and next_name != role.name:
        raise BadRequestException("内置权限身份不可重命名")
    if next_name is not None and is_protected_role_name(next_name) and next_name != role.name:
        raise BadRequestException("不能创建或重命名为内置权限身份")


# ── 用户管理 ──────────────────────────────────────────────

@router.get("", response_model=PageResult)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.list_users(db, page, page_size, include_admins=is_super_admin(admin))
    return PageResult(
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/all")
async def list_all_users(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """返回所有活跃用户的 id 和 username (仅管理员)"""
    result = await db.execute(
        select(User.id, User.username, User.is_active).where(User.is_active == True)
    )
    return [{"id": row[0], "username": row[1]} for row in result.all()]


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateMeRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_me(
        db, current_user.id,
        username=body.username,
        email=body.email,
        password=body.password,
        current_password=body.current_password,
    )


@router.get("/check-unique")
async def check_unique(
    field: str = Query(..., description="字段: account, username, email"),
    value: str = Query(..., description="要检查的值"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    available = await user_service.check_unique(db, field, value, exclude_id=current_user.id)
    return {"available": available}


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await _validate_role_assignment(db, admin, None, body.role_id)
    return await user_service.create_user(db, body.account, body.username, body.email, body.password, body.role_id)


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # 记录旧值用于变更通知
    old_user = await user_service.get_user(db, user_id)
    _validate_user_mutation(admin, old_user, body)
    role_id_provided = "role_id" in body.model_fields_set
    await _validate_role_assignment(db, admin, old_user, body.role_id, role_id_provided=role_id_provided)
    old_role_id = old_user.role_id
    old_is_active = old_user.is_active

    updated = await user_service.update_user(
        db, user_id,
        email=body.email,
        role_id=body.role_id,
        is_active=body.is_active,
        allow_null_fields={"role_id"} if role_id_provided else None,
    )

    # 角色变更通知
    if role_id_provided and body.role_id != old_role_id:
        from app.services.notification_service import create_notification
        new_role = await user_service.get_role(db, body.role_id) if body.role_id is not None else None
        await create_notification(
            db, user_id,
            "permission_changed",
            "权限变更",
            f"您的角色已变更为 \"{new_role.name if new_role else '未分配'}\"。",
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
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.get_user(db, user_id)
    if _role_name(user) == ROLE_SUPER_ADMIN:
        raise ForbiddenException("超级管理员账号不可删除")
    if _role_name(user) == ROLE_ADMIN and not is_super_admin(admin):
        raise ForbiddenException("只有超级管理员可以删除管理员账号")
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
    _admin=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if is_protected_role_name(body.name):
        raise BadRequestException("不能创建内置权限身份")
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
    _admin=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    await _validate_role_mutation(db, role_id, body.name)
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
    _admin=Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    role = await user_service.get_role(db, role_id)
    if is_protected_role_name(role.name):
        raise BadRequestException("内置权限身份不可删除")
    await user_service.delete_role(db, role_id)
