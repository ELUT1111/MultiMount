from datetime import datetime
from pydantic import BaseModel, Field


class MountConfig(BaseModel):
    """挂载配置 — 各协议共用字段, 通过 type 区分"""
    pass


class LocalConfig(MountConfig):
    path: str = Field(..., description="本地目录路径")


class ManagedConfig(MountConfig):
    path: str = Field(..., description="系统托管挂载目录路径")
    directory_name: str = Field(..., description="系统生成的目录名")


class FTPConfig(MountConfig):
    host: str
    port: int = 21
    username: str = ""
    password: str = ""
    passive_mode: bool = True
    base_path: str = "/"


class SFTPConfig(MountConfig):
    host: str
    port: int = 22
    username: str
    password: str = ""
    private_key: str = ""  # PEM 格式私钥内容
    base_path: str = "/"


class WebDAVConfig(MountConfig):
    url: str = Field(..., description="WebDAV 服务地址")
    username: str = ""
    password: str = ""
    verify_ssl: bool = True


class OSSConfig(MountConfig):
    access_key_id: str
    access_key_secret: str
    bucket: str
    endpoint: str
    prefix: str = ""


class S3Config(MountConfig):
    access_key_id: str
    access_key_secret: str
    bucket: str
    region: str = "us-east-1"
    endpoint_url: str | None = None
    prefix: str = ""


class MountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., pattern="^(managed|local|ftp|sftp|webdav|oss|s3)$")
    config: dict
    advanced_config: dict | None = None


class MountUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    advanced_config: dict | None = None


class MountOut(BaseModel):
    id: int
    name: str
    type: str
    status: str
    config: dict
    advanced_config: dict | None
    capacity_used: int | None
    capacity_total: int | None
    last_connected_at: datetime | None
    user_id: int | None = None  # 创建者 ID (None = 系统预置)
    owner_name: str | None = None  # 创建者用户名 (仅用于展示)
    my_level: str | None = None  # 当前用户对该挂载的权限等级
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
