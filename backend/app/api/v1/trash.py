from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import enforce_file_policy
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.file import TrashItemOut
from app.services import operation_log_service, trash_service
from app.services.mount_permission_service import get_accessible_mount_ids

router = APIRouter()


class TrashClearRequest(BaseModel):
    scope: str = Field("selected", pattern="^(selected|filtered|mount|all)$")
    item_ids: list[int] = Field(default_factory=list)
    mount_id: int | None = None
    retention_days: int = Field(0, ge=0)
    max_total_size: int = Field(0, ge=0)


@router.get("", response_model=list[TrashItemOut])
async def list_trash(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount_ids = await get_accessible_mount_ids(db, current_user)
    return await trash_service.list_trash_items(db, mount_ids)


@router.get("/stats")
async def trash_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount_ids = await get_accessible_mount_ids(db, current_user)
    return await trash_service.trash_stats(db, mount_ids)


@router.post("/clear")
async def clear_trash(
    request: Request,
    body: TrashClearRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    accessible = await get_accessible_mount_ids(db, current_user)
    target_mounts = accessible
    if body.mount_id:
        await enforce_file_policy(db, current_user, body.mount_id, "delete")
        target_mounts = {body.mount_id}
    else:
        for mount_id in accessible:
            await enforce_file_policy(db, current_user, mount_id, "delete")

    if body.retention_days or body.max_total_size:
        result = await trash_service.cleanup_trash(
            db,
            target_mounts,
            retention_days=body.retention_days,
            max_total_size=body.max_total_size,
        )
        action = "trash_cleanup"
    elif body.scope in ("selected", "filtered"):
        result = await trash_service.clear_trash(db, target_mounts, body.item_ids)
        action = "trash_clear_selected"
    else:
        result = await trash_service.clear_trash(db, target_mounts)
        action = "trash_clear"

    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action=action,
        user=current_user,
        resource_type="trash",
        mount_id=body.mount_id,
        status="success" if result["failed_count"] == 0 else "partial_failed",
        ip_address=ip,
        user_agent=user_agent,
        detail={**result, "scope": body.scope, "item_ids": body.item_ids},
    )
    return result


@router.post("/{item_id}/restore", response_model=TrashItemOut)
async def restore_trash_item(
    request: Request,
    item_id: int,
    conflict_policy: str = Query("rename", pattern="^(error|overwrite|skip|rename)$"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await trash_service.get_trash_item(db, item_id)
    await enforce_file_policy(db, current_user, item.mount_id, "delete")
    restored = await trash_service.restore_trash_item(db, item_id, conflict_policy)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="trash_restore",
        user=current_user,
        mount_id=restored.mount_id,
        path=restored.trash_path,
        target_path=restored.original_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={
            "trash_item_id": item_id,
            "original_path": item.original_path,
            "trash_path": item.trash_path,
            "restore_target_path": restored.original_path,
            "conflict_policy": conflict_policy,
        },
    )
    return restored


@router.delete("/{item_id}", response_model=TrashItemOut)
async def purge_trash_item(
    request: Request,
    item_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await trash_service.get_trash_item(db, item_id)
    await enforce_file_policy(db, current_user, item.mount_id, "delete")
    purged = await trash_service.purge_trash_item(db, item_id)
    ip, user_agent = operation_log_service.request_context(request)
    await operation_log_service.log_operation(
        db,
        action="trash_purge",
        user=current_user,
        mount_id=purged.mount_id,
        path=purged.trash_path,
        target_path=purged.original_path,
        ip_address=ip,
        user_agent=user_agent,
        detail={
            "trash_item_id": item_id,
            "original_path": purged.original_path,
            "trash_path": purged.trash_path,
        },
    )
    return purged
