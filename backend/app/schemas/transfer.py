from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TransferTaskOut(BaseModel):
    id: int
    user_id: int | None
    type: str
    status: str
    file_name: str
    file_size: int | None
    source_path: str
    target_path: str
    mount_id: int | None
    source_mount_id: int | None = None
    target_mount_id: int | None = None
    conflict_policy: str = "error"
    transferred: int
    chunk_size: int
    speed: float | None
    download_limit_bps: int | None = None
    upload_limit_bps: int | None = None
    checkpoint: dict | None = None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransferCreateRequest(BaseModel):
    type: Literal["upload", "download", "copy", "move"]
    mount_id: int | None = None
    source_mount_id: int | None = None
    target_mount_id: int | None = None
    source_path: str
    target_path: str
    file_name: str
    file_size: int | None = None
    conflict_policy: Literal["error", "overwrite", "skip", "rename"] = "error"
    download_limit_kbps: int | None = None
    upload_limit_kbps: int | None = None
