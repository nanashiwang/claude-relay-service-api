from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import LinkType, MerchantStatus
from app.schemas.common import ORMModel


# ==================== 商户相关 ====================

class MerchantApplyIn(BaseModel):
    """商户申请输入"""
    merchant_name: str = Field(..., min_length=1, max_length=128, description="商户名称")
    description: str | None = Field(None, description="商户描述")


class MerchantOut(ORMModel):
    """商户输出"""
    id: int
    user_id: int
    merchant_name: str
    merchant_code: str
    description: str | None
    status: MerchantStatus
    suspended_reason: str | None
    platform_fee_percent: int
    total_sales_cents: int
    total_earnings_cents: int
    total_orders: int
    created_at: datetime
    updated_at: datetime


class MerchantStatsOut(BaseModel):
    """商户统计输出"""
    merchant_id: int
    merchant_name: str
    merchant_code: str
    status: MerchantStatus
    total_sales_cents: int
    total_earnings_cents: int
    total_orders: int
    product_count: int
    share_link_count: int
    unsettled_earnings_cents: int
    settled_earnings_cents: int
    platform_fee_percent: int


class MerchantUpdateIn(BaseModel):
    """商户更新输入"""
    description: str | None = None
    platform_fee_percent: int | None = Field(None, ge=0, le=100)


# ==================== 商户收益相关 ====================

class MerchantEarningOut(ORMModel):
    """商户收益输出"""
    id: int
    merchant_id: int
    card_claim_id: int
    product_id: int
    sales_amount_cents: int
    earnings_cents: int
    platform_fee_cents: int
    referral_rebate_cents: int
    is_settled: bool
    settled_at: datetime | None
    created_at: datetime


# ==================== 分享链接相关 ====================

class ShareLinkCreateIn(BaseModel):
    """创建分享链接输入"""
    link_type: LinkType = LinkType.referral
    name: str | None = Field(None, max_length=128, description="链接名称")
    product_ids: list[int] | None = Field(None, description="限制的产品ID列表")


class ShareLinkUpdateIn(BaseModel):
    """更新分享链接输入"""
    name: str | None = Field(None, max_length=128)
    product_ids: list[int] | None = None
    active: bool | None = None


class ShareLinkOut(ORMModel):
    """分享链接输出"""
    id: int
    user_id: int
    merchant_id: int | None
    link_code: str
    link_type: LinkType
    name: str | None
    product_ids: str | None
    click_count: int
    conversion_count: int
    total_sales_cents: int
    active: bool
    created_at: datetime


class ShareLinkStatsOut(BaseModel):
    """分享链接统计输出"""
    link_id: int
    link_code: str
    link_type: LinkType
    name: str | None
    click_count: int
    conversion_count: int
    total_sales_cents: int
    conversion_rate: float


# ==================== 返利配置相关 ====================

class RebateConfigOut(BaseModel):
    """返利配置输出"""
    rebate_percent: int = Field(..., description="推荐返利比例(0-100)")
    platform_fee_percent: int = Field(..., description="平台抽成比例(0-100)")


class RebateConfigUpdateIn(BaseModel):
    """返利配置更新输入（管理员）"""
    rebate_percent: int = Field(..., ge=0, le=100, description="推荐返利比例(0-100)")
    platform_fee_percent: int = Field(..., ge=0, le=100, description="平台抽成比例(0-100)")


class MerchantRebateConfigUpdateIn(BaseModel):
    """商户返利配置更新输入（商户）"""
    platform_fee_percent: int = Field(..., ge=0, le=100, description="平台抽成比例(0-100)")
