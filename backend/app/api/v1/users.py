from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin
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
    return await user_service.update_user(
        db, user_id,
        email=body.email,
        role_id=body.role_id,
        is_active=body.is_active,
    )


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
    return await user_service.update_role(
        db, role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        mount_permissions=body.mount_permissions,
        qos_limits=body.qos_limits,
    )


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_service.delete_role(db, role_id)
