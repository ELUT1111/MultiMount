from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    login_id: str = Field(..., min_length=1, max_length=64, description="账号、用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    account: str = Field(..., min_length=2, max_length=64)
    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
