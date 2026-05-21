"""File search API: indexed search, refresh, and advanced filters."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.search_service import refresh_index, search_files

router = APIRouter()


def _parse_mount_ids(raw: str) -> list[int] | None:
    if not raw.strip():
        return None
    try:
        return [int(item) for item in raw.split(",") if item.strip()]
    except ValueError:
        return None


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    regex: bool = Query(False),
    mount_id: str = Query(""),
    max_depth: int = Query(5, ge=1, le=10),
    limit: int = Query(200, ge=1, le=500),
    size_min: int | None = Query(None, ge=0),
    size_max: int | None = Query(None, ge=0),
    modified_from: datetime | None = Query(None),
    modified_to: datetime | None = Query(None),
    file_type: str | None = Query(None, pattern="^(directory|image|video|audio|pdf|office|text|other)$"),
    extension: str | None = Query(None),
    path_prefix: str | None = Query(None),
    owner: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_files(
        db,
        user,
        q,
        use_regex=regex,
        mount_ids=_parse_mount_ids(mount_id),
        max_depth=max_depth,
        limit=limit,
        size_min=size_min,
        size_max=size_max,
        modified_from=modified_from,
        modified_to=modified_to,
        file_type=file_type,
        extension=extension,
        path_prefix=path_prefix,
        owner=owner,
    )


@router.post("/index/refresh")
async def refresh_search_index(
    mount_id: str = Query(""),
    max_depth: int = Query(10, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await refresh_index(db, user, mount_ids=_parse_mount_ids(mount_id), max_depth=max_depth)
