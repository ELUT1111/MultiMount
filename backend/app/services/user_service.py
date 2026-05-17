from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


async def list_users(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[User], int]:
    """分页查询用户列表"""
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar()

    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(User.id)
    )
    users = list(result.scalars().all())
    return users, total


async def get_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("用户不存在")
    return user


async def create_user(
    db: AsyncSession, account: str, username: str, email: str, password: str, role_id: int | None = None
) -> User:
    existing = await db.execute(
        select(User).where(
            (User.account == account) | (User.username == username) | (User.email == email)
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException("账号、用户名或邮箱已被注册")

    user = User(
        account=account,
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role_id=role_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, **kwargs) -> User:
    user = await get_user(db, user_id)
    for key, value in kwargs.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user(db, user_id)
    await db.delete(user)
    await db.flush()


async def update_me(db: AsyncSession, user_id: int, username: str | None, email: str | None,
                    password: str | None, current_password: str | None) -> User:
    """普通用户修改自己的资料"""
    from app.core.security import verify_password
    user = await get_user(db, user_id)

    # 修改密码需要验证当前密码
    if password is not None:
        if not current_password or not verify_password(current_password, user.hashed_password):
            raise BadRequestException("当前密码不正确")
        user.hashed_password = hash_password(password)

    # 修改用户名 (检查唯一性)
    if username is not None and username != user.username:
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            raise ConflictException("用户名已被使用")
        user.username = username

    # 修改邮箱 (检查唯一性)
    if email is not None and email != user.email:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictException("邮箱已被使用")
        user.email = email

    await db.flush()
    await db.refresh(user)
    return user


async def check_unique(db: AsyncSession, field: str, value: str, exclude_id: int | None = None) -> bool:
    """检查字段值是否唯一, 返回 True 表示可用"""
    if field not in ("account", "username", "email"):
        return False
    col = getattr(User, field)
    query = select(User).where(col == value)
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is None


# ── 角色 CRUD ─────────────────────────────────────────────

async def list_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).order_by(Role.id))
    return list(result.scalars().all())


async def get_role(db: AsyncSession, role_id: int) -> Role:
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise NotFoundException("角色不存在")
    return role


async def create_role(db: AsyncSession, **kwargs) -> Role:
    role = Role(**kwargs)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


async def update_role(db: AsyncSession, role_id: int, **kwargs) -> Role:
    role = await get_role(db, role_id)
    for key, value in kwargs.items():
        if value is not None and hasattr(role, key):
            setattr(role, key, value)
    await db.flush()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, role_id: int) -> None:
    role = await get_role(db, role_id)
    # 检查是否有用户引用此角色
    count_result = await db.execute(select(func.count(User.id)).where(User.role_id == role_id))
    if count_result.scalar() > 0:
        raise BadRequestException("该角色下仍有用户, 无法删除")
    await db.delete(role)
    await db.flush()
