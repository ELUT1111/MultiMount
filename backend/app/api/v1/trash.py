from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import enforce_file_policy
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.file import TrashItemOut
from app.services import operation_log_service, trash_service
from app.services.mount_permission_service import get_accessible_mount_ids

router = APIRouter()


@router.get("", response_model=list[TrashItemOut])
async def list_trash(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mount_ids = await get_accessible_mount_ids(db, current_user)
    return await trash_service.list_trash_items(db, mount_ids)


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
    )
    return purged
