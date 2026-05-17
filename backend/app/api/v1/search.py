"""
文件搜索 API — 跨挂载点递归搜索文件。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.search_service import search_files

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    regex: bool = Query(False, description="是否正则匹配"),
    mount_id: str = Query("", description="限定挂载 ID, 逗号分隔"),
    max_depth: int = Query(5, ge=1, le=10, description="递归深度限制"),
    limit: int = Query(200, ge=1, le=500, description="最大结果数"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """跨挂载点搜索文件"""
    # 解析挂载 ID 过滤
    mount_ids = None
    if mount_id.strip():
        try:
            mount_ids = [int(x) for x in mount_id.split(",") if x.strip()]
        except ValueError:
            mount_ids = None

    results = await search_files(
        db, user, q,
        use_regex=regex,
        mount_ids=mount_ids,
        max_depth=max_depth,
        limit=limit,
    )
    return results
