from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Announcement

DEFAULT_ANNOUNCEMENT_TITLE = "平台公告"
DEFAULT_ANNOUNCEMENT_CONTENT = """## 福利接口
- 每天 10 美金限额，隔天自动刷新，可用 codex 所有模型
- 使用教程：crss.nanashiwang.com
- 密钥：`cr_05dabd15a3e0eb0ccbf1d23932e959ab493bb527fa5280937fd147d96b52aea9`

## 官方地址
- 官网地址：https://crss.nanashiwang.com/
- codex 接口地址（URL）：https://crss.nanashiwang.com/openai/

## 购买链接
- 【淘宝】https://e.tb.cn/h.7Oai5PAbDifvN2f?tk=ZkQIUetqqIK CZ225 「codex按量天计费 codex中转」
- 点击链接直接打开 或者 淘宝搜索直接打开
- 【闲鱼】https://m.tb.cn/h.7lLxkHK?tk=ThljUetIS6S HU293 「我在闲鱼发布了【Codex自动发货不限额】」
- 点击链接直接打开

## codex 新定价（按量计费）
- codex 10 刀：2.68
- codex 30 刀：7.68
- codex 100 刀：23.68

## codex 新定价（按日计费）
- codex 1.68 元/天
- codex 10.68 元/7 天
- codex 48.36 元/31 天

---

## claude 20max 代订阅和代挂服务
- 单代订阅：1800
- 单代挂：268
- 🌟代订阅+代挂：2038

## claude 拼车服务
- 6 人车：每天 40 刀，周限额跟随官方，人均 367
- 3 人车：每天 70 刀，每周 300 刀，人均 717
- 服务稳定，上车不退，封号换号"""


def seed_default_announcement(db: Session) -> bool:
    exists = db.execute(select(Announcement.id)).first()
    if exists:
        return False
    db.add(
        Announcement(
            title=DEFAULT_ANNOUNCEMENT_TITLE,
            content=DEFAULT_ANNOUNCEMENT_CONTENT,
            active=True,
        )
    )
    db.commit()
    return True
