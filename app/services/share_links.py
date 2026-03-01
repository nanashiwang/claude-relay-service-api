"""
分享链接服务

提供分享链接相关的业务逻辑
"""

from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ShareLink
from app.models.enums import LinkType

if TYPE_CHECKING:
    from app.models import Merchant, User


def generate_link_code() -> str:
    """生成唯一的链接代码"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def create_share_link(
    db: Session,
    user: User,
    link_type: LinkType = LinkType.referral,
    name: str | None = None,
    product_ids: list[int] | None = None,
    merchant_id: int | None = None,
) -> ShareLink:
    """
    创建分享链接

    Args:
        db: 数据库会话
        user: 创建用户
        link_type: 链接类型
        name: 链接名称
        product_ids: 限制的产品ID列表
        merchant_id: 关联商户ID

    Returns:
        创建的分享链接对象
    """
    import json

    # 生成唯一代码
    link_code = generate_link_code()
    while db.execute(
        select(ShareLink.id).where(ShareLink.link_code == link_code)
    ).first():
        link_code = generate_link_code()

    share_link = ShareLink(
        user_id=user.id,
        merchant_id=merchant_id,
        link_code=link_code,
        link_type=link_type,
        name=name,
        product_ids=json.dumps(product_ids) if product_ids else None,
    )
    db.add(share_link)
    db.commit()
    db.refresh(share_link)

    return share_link


def get_share_link_by_code(db: Session, link_code: str) -> ShareLink | None:
    """根据链接代码获取分享链接"""
    return db.execute(
        select(ShareLink).where(
            ShareLink.link_code == link_code,
            ShareLink.active == True,
        )
    ).scalar_one_or_none()


def get_user_share_links(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
) -> list[ShareLink]:
    """获取用户的分享链接列表"""
    return list(
        db.execute(
            select(ShareLink)
            .where(ShareLink.user_id == user_id)
            .order_by(ShareLink.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )


def update_share_link(
    db: Session,
    link_id: int,
    user_id: int,
    name: str | None = None,
    product_ids: list[int] | None = None,
    active: bool | None = None,
) -> ShareLink | None:
    """
    更新分享链接

    Args:
        db: 数据库会话
        link_id: 链接ID
        user_id: 用户ID（权限检查）
        name: 新名称
        product_ids: 产品ID列表
        active: 是否启用

    Returns:
        更新后的分享链接对象，如果不存在或无权限返回None
    """
    import json

    share_link = db.get(ShareLink, link_id)
    if not share_link or share_link.user_id != user_id:
        return None

    if name is not None:
        share_link.name = name

    if product_ids is not None:
        share_link.product_ids = json.dumps(product_ids) if product_ids else None

    if active is not None:
        share_link.active = active

    db.commit()
    db.refresh(share_link)

    return share_link


def delete_share_link(db: Session, link_id: int, user_id: int) -> bool:
    """
    删除分享链接

    Args:
        db: 数据库会话
        link_id: 链接ID
        user_id: 用户ID（权限检查）

    Returns:
        是否删除成功
    """
    share_link = db.get(ShareLink, link_id)
    if not share_link or share_link.user_id != user_id:
        return False

    db.delete(share_link)
    db.commit()

    return True


def record_click(db: Session, link_id: int) -> None:
    """
    记录链接点击

    Args:
        db: 数据库会话
        link_id: 链接ID
    """
    share_link = db.get(ShareLink, link_id)
    if share_link:
        share_link.click_count += 1
        db.commit()


def record_conversion(
    db: Session,
    link_id: int,
    sales_amount_cents: int,
) -> None:
    """
    记录转化

    Args:
        db: 数据库会话
        link_id: 链接ID
        sales_amount_cents: 销售金额(分)
    """
    share_link = db.get(ShareLink, link_id)
    if share_link:
        share_link.conversion_count += 1
        share_link.total_sales_cents += sales_amount_cents
        db.commit()


def get_link_stats(db: Session, link_code: str) -> dict | None:
    """
    获取链接统计信息

    Args:
        db: 数据库会话
        link_code: 链接代码

    Returns:
        统计信息字典
    """
    share_link = get_share_link_by_code(db, link_code)
    if not share_link:
        return None

    return {
        "link_id": share_link.id,
        "link_code": share_link.link_code,
        "link_type": share_link.link_type,
        "name": share_link.name,
        "click_count": share_link.click_count,
        "conversion_count": share_link.conversion_count,
        "total_sales_cents": share_link.total_sales_cents,
        "conversion_rate": (
            share_link.conversion_count / share_link.click_count
            if share_link.click_count > 0
            else 0
        ),
    }
