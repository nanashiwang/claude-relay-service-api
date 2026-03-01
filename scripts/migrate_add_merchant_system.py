"""
商户系统迁移脚本

运行方式:
    python scripts/migrate_add_merchant_system.py

说明:
    此脚本会添加商户系统相关的表和字段
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import engine


def migrate() -> None:
    """执行迁移"""

    with engine.begin() as conn:
        # ========================================
        # 创建新表
        # ========================================

        # 1. 创��商户表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS merchants (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '商户ID',
                user_id INT NOT NULL UNIQUE COMMENT '关联用户ID',
                merchant_name VARCHAR(128) NOT NULL COMMENT '商户名称',
                merchant_code VARCHAR(32) NOT NULL UNIQUE COMMENT '商户代码(用于链接)',
                description TEXT COMMENT '商户描述',
                status ENUM('approved', 'suspended') DEFAULT 'approved' COMMENT '状态',
                suspended_reason TEXT COMMENT '暂停原因',
                platform_fee_percent INT DEFAULT 10 COMMENT '平台抽成比例(0-100)',
                total_sales_cents INT DEFAULT 0 COMMENT '累计销售额(分)',
                total_earnings_cents INT DEFAULT 0 COMMENT '累计收益(分)',
                total_orders INT DEFAULT 0 COMMENT '累计订单数',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间(UTC)',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间(UTC)',
                INDEX idx_user_id (user_id),
                INDEX idx_merchant_code (merchant_code),
                INDEX idx_status (status)
            ) COMMENT='商户表'
        """))

        # 2. 创建商户收益表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS merchant_earnings (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '收益ID',
                merchant_id INT NOT NULL COMMENT '商户ID',
                card_claim_id INT NOT NULL COMMENT '卡密提取记录ID',
                product_id INT NOT NULL COMMENT '产品ID',
                sales_amount_cents INT NOT NULL COMMENT '销售金额(分)',
                earnings_cents INT NOT NULL COMMENT '商户收益(分)',
                platform_fee_cents INT DEFAULT 0 COMMENT '平台抽成(分)',
                referral_rebate_cents INT DEFAULT 0 COMMENT '推荐返利(分)',
                is_settled BOOLEAN DEFAULT FALSE COMMENT '是否已结算',
                settled_at DATETIME COMMENT '结算时间(UTC)',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间(UTC)',
                INDEX idx_merchant_id (merchant_id),
                INDEX idx_card_claim_id (card_claim_id),
                INDEX idx_product_id (product_id),
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
                FOREIGN KEY (card_claim_id) REFERENCES card_claims(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            ) COMMENT='商户收益记录表'
        """))

        # 3. 创建分享链接表
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS share_links (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '链接ID',
                user_id INT NOT NULL COMMENT '创建用户ID',
                merchant_id INT COMMENT '关联商户ID',
                link_code VARCHAR(32) NOT NULL UNIQUE COMMENT '链接代码',
                link_type ENUM('referral', 'merchant') DEFAULT 'referral' COMMENT '链接类型',
                name VARCHAR(128) COMMENT '链接名称',
                product_ids TEXT COMMENT '限制的产品ID列表(JSON)',
                click_count INT DEFAULT 0 COMMENT '点击次数',
                conversion_count INT DEFAULT 0 COMMENT '转化次数',
                total_sales_cents INT DEFAULT 0 COMMENT '累计销售额(分)',
                active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间(UTC)',
                INDEX idx_user_id (user_id),
                INDEX idx_merchant_id (merchant_id),
                INDEX idx_link_code (link_code),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
            ) COMMENT='分享链接表'
        """))

        # ========================================
        # 修改现有表
        # ========================================

        # 1. 给 users 表添加商户字段
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_merchant BOOLEAN DEFAULT FALSE COMMENT '是否商户',
            ADD COLUMN IF NOT EXISTS merchant_id INT COMMENT '关联商户ID',
            ADD INDEX IF NOT EXISTS idx_merchant_id (merchant_id),
            ADD FOREIGN KEY IF NOT EXISTS (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
        """))

        # 2. 给 products 表添加商户字段
        conn.execute(text("""
            ALTER TABLE products
            ADD COLUMN IF NOT EXISTS merchant_id INT COMMENT '所属商户ID(空=平台商品)',
            ADD COLUMN IF NOT EXISTS is_platform_product BOOLEAN DEFAULT TRUE COMMENT '是否平台商品',
            ADD INDEX IF NOT EXISTS idx_merchant_id (merchant_id),
            ADD FOREIGN KEY IF NOT EXISTS (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
        """))

        # 3. 给 card_claims 表添加收益关联字段
        conn.execute(text("""
            ALTER TABLE card_claims
            ADD COLUMN IF NOT EXISTS merchant_id INT COMMENT '收益商户ID',
            ADD COLUMN IF NOT EXISTS merchant_earning_id INT COMMENT '商户收益记录ID',
            ADD COLUMN IF NOT EXISTS share_link_id INT COMMENT '来源分享链接ID',
            ADD INDEX IF NOT EXISTS idx_merchant_id (merchant_id),
            ADD INDEX IF NOT EXISTS idx_merchant_earning_id (merchant_earning_id),
            ADD INDEX IF NOT EXISTS idx_share_link_id (share_link_id),
            ADD FOREIGN KEY IF NOT EXISTS (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL,
            ADD FOREIGN KEY IF NOT EXISTS (merchant_earning_id) REFERENCES merchant_earnings(id) ON DELETE SET NULL,
            ADD FOREIGN KEY IF NOT EXISTS (share_link_id) REFERENCES share_links(id) ON DELETE SET NULL
        """))

        # 4. 给 referral_rebates 表添加商户字段
        conn.execute(text("""
            ALTER TABLE referral_rebates
            ADD COLUMN IF NOT EXISTS merchant_id INT COMMENT '作为商户时的返利',
            ADD INDEX IF NOT EXISTS idx_merchant_id (merchant_id),
            ADD FOREIGN KEY IF NOT EXISTS (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
        """))

        # ========================================
        # 数据初始化
        # ========================================

        # 将现有商品标记为平台商品
        conn.execute(text("""
            UPDATE products SET is_platform_product = TRUE WHERE is_platform_product IS NULL
        """))

    print("✅ 商户系统迁移完成!")
    print("\n新增表:")
    print("  - merchants (商户表)")
    print("  - merchant_earnings (商户收益表)")
    print("  - share_links (分享链接表)")
    print("\n修改表:")
    print("  - users (添加 is_merchant, merchant_id)")
    print("  - products (添加 merchant_id, is_platform_product)")
    print("  - card_claims (添加 merchant_id, merchant_earning_id, share_link_id)")
    print("  - referral_rebates (添加 merchant_id)")


def rollback() -> None:
    """回滚迁移"""

    with engine.begin() as conn:
        # 删除外键约束和索引
        conn.execute(text("ALTER TABLE card_claims DROP FOREIGN KEY IF EXISTS fk_card_claims_merchant_id"))
        conn.execute(text("ALTER TABLE card_claims DROP FOREIGN KEY IF EXISTS fk_card_claims_merchant_earning_id"))
        conn.execute(text("ALTER TABLE card_claims DROP FOREIGN KEY IF EXISTS fk_card_claims_share_link_id"))
        conn.execute(text("ALTER TABLE products DROP FOREIGN KEY IF EXISTS fk_products_merchant_id"))
        conn.execute(text("ALTER TABLE users DROP FOREIGN KEY IF EXISTS fk_users_merchant_id"))
        conn.execute(text("ALTER TABLE referral_rebates DROP FOREIGN KEY IF EXISTS fk_referral_rebates_merchant_id"))

        # 删除表
        conn.execute(text("DROP TABLE IF EXISTS share_links"))
        conn.execute(text("DROP TABLE IF EXISTS merchant_earnings"))
        conn.execute(text("DROP TABLE IF EXISTS merchants"))

        # 删除字段
        conn.execute(text("ALTER TABLE referral_rebates DROP COLUMN IF EXISTS merchant_id"))
        conn.execute(text("ALTER TABLE card_claims DROP COLUMN IF EXISTS share_link_id"))
        conn.execute(text("ALTER TABLE card_claims DROP COLUMN IF EXISTS merchant_earning_id"))
        conn.execute(text("ALTER TABLE card_claims DROP COLUMN IF EXISTS merchant_id"))
        conn.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS is_platform_product"))
        conn.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS merchant_id"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS merchant_id"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS is_merchant"))

    print("✅ 迁移已回滚!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="商户系统迁移脚本")
    parser.add_argument("--rollback", action="store_true", help="回滚迁移")
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
