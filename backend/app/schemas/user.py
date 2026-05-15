from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None
    permissions: dict
    mount_permissions: dict
    qos_limits: dict | None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role_id: int | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    role: RoleOut | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role_id: int | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role_id: int | None = None
    is_active: bool | None = None


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = None
    permissions: dict = {}
    mount_permissions: dict = {}
    qos_limits: dict | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: dict | None = None
    mount_permissions: dict | None = None
    qos_limits: dict | None = None
