"""
分享链接API路由

提供分享链接创建、管理、统计等接口
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_merchant
from app.db.session import get_db
from app.models import ShareLink, User
from app.schemas.merchant import (
    ShareLinkCreateIn,
    ShareLinkOut,
    ShareLinkStatsOut,
    ShareLinkUpdateIn,
)
from app.services.share_links import (
    create_share_link,
    delete_share_link,
    get_link_stats,
    get_share_link_by_code,
    get_user_share_links,
    record_click,
    update_share_link,
)

router = APIRouter(prefix="/share-links", tags=["分享链接"])


@router.post("", response_model=ShareLinkOut)
def create_link(
    data: ShareLinkCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareLink:
    """
    创建分享链接

    - **link_type**: 链接类型（referral/merchant）
    - **name**: 链接名称（可选）
    - **product_ids**: 限制的产品ID列表（可选）
    """
    merchant_id = None
    if user.is_merchant and user.merchant_id:
        merchant_id = user.merchant_id

    return create_share_link(
        db,
        user=user,
        link_type=data.link_type,
        name=data.name,
        product_ids=data.product_ids,
        merchant_id=merchant_id,
    )


@router.get("", response_model=list[ShareLinkOut])
def list_links(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ShareLink]:
    """获取我的分享链接列表"""
    return get_user_share_links(db, user.id, skip=skip, limit=limit)


@router.get("/{link_id}", response_model=ShareLinkOut)
def get_link(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareLink:
    """获取分享链接详情"""
    link = db.get(ShareLink, link_id)
    if not link or link.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在")

    return link


@router.patch("/{link_id}", response_model=ShareLinkOut)
def update_link(
    link_id: int,
    data: ShareLinkUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareLink:
    """更新分享链接"""
    link = update_share_link(
        db,
        link_id=link_id,
        user_id=user.id,
        name=data.name,
        product_ids=data.product_ids,
        active=data.active,
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在或无权限")

    return link


@router.delete("/{link_id}")
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """删除分享链接"""
    success = delete_share_link(db, link_id, user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在或无权限")

    return {"message": "删除成功"}


@router.get("/stats/{link_code}", response_model=ShareLinkStatsOut)
def get_link_stats_public(
    link_code: str,
    db: Session = Depends(get_db),
) -> dict:
    """获取分享链接统计（公开）"""
    stats = get_link_stats(db, link_code)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在")

    return stats


@router.get("/s/{link_code}")
def redirect_share_link(
    link_code: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    访问分享链接（重定向）

    记录点击次数并重定向到首页
    """
    link = get_share_link_by_code(db, link_code)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在")

    # 记录点击
    record_click(db, link.id)

    # 重定向到首页，携带推荐码
    from app.core.config import settings
    base_url = settings.public_base_url or "/"
    return RedirectResponse(url=f"{base_url}?ref={link_code}")
