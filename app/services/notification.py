from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RechargeRequest, RefundRequest, User

logger = logging.getLogger(__name__)


def _admin_link() -> str:
    base = (settings.public_base_url or "").strip().rstrip("/")
    path = "/web/admin.html"
    return f"{base}{path}" if base else path


def _format_amount(amount_cents: int, currency: str) -> str:
    return f"{amount_cents / 100:.2f} {currency}"


def _format_user(user_id: int, username: str | None) -> str:
    if username:
        return f"{username} (ID {user_id})"
    return f"ID {user_id}"


def _extract_first_url(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = re.search(r"https?://\\S+", text)
        if match:
            return match.group(0).rstrip(").,;\"'")
    return None


def _post_wecom(payload: dict) -> None:
    if not settings.wecom_webhook_url:
        return
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        settings.wecom_webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        try:
            result = json.loads(body or "{}")
        except json.JSONDecodeError:
            result = {}
        if result.get("errcode") not in (None, 0):
            logger.warning("wecom notify failed: %s", body)
    except Exception as exc:
        logger.warning("wecom notify error: %s", exc)


def _send_wecom_markdown(content: str) -> None:
    if not settings.wecom_webhook_url:
        return
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    threading.Thread(target=_post_wecom, args=(payload,), daemon=True).start()


def notify_recharge_event(
    db: Session,
    req: RechargeRequest,
    *,
    event: str,
    requester_name: str | None = None,
    admin_name: str | None = None,
) -> None:
    user = db.get(User, req.user_id) if requester_name is None else None
    requester_display = _format_user(req.user_id, requester_name or (user.username if user else None))
    admin_display = None
    if admin_name:
        admin_display = admin_name
    elif req.reviewed_by_user_id:
        admin = db.get(User, req.reviewed_by_user_id)
        admin_display = admin.username if admin else f"ID {req.reviewed_by_user_id}"

    title_map = {
        "created": "充值申请待审核",
        "approved": "充值申请已通过",
        "rejected": "充值申请已拒绝",
    }
    title = title_map.get(event, "充值申请通知")
    operator_id = req.user_id if event == "created" else req.reviewed_by_user_id
    detail_parts: list[str] = []
    if req.payment_method:
        detail_parts.append(f"方式：{req.payment_method}")
    if req.payment_reference:
        detail_parts.append(f"流水：{req.payment_reference}")
    if req.note:
        detail_parts.append(f"备注：{req.note}")
    detail_text = "，".join(detail_parts) if detail_parts else "无"
    screenshot_url = req.payment_proof_url or _extract_first_url(req.payment_reference, req.note)

    lines = [
        f"**{title}**",
        f"- 申请ID：{req.id}",
        f"- 用户：{requester_display}",
        f"- 金额：{_format_amount(req.amount_cents, req.currency)}",
        f"- 时间：{req.created_at}",
        f"- 订单详情：{detail_text}",
    ]
    if screenshot_url:
        lines.append(f"- 支付截图链接：{screenshot_url}")
    if operator_id:
        lines.append(f"- 操作人ID：{operator_id}")
    if admin_display:
        lines.append(f"- 审核人：{admin_display}")
    if req.review_note:
        lines.append(f"- 审核说明：{req.review_note}")
    lines.append(f"- 入口：{_admin_link()}")
    _send_wecom_markdown("\n".join(lines))


def notify_refund_event(
    db: Session,
    req: RefundRequest,
    *,
    event: str,
    requester_name: str | None = None,
    admin_name: str | None = None,
) -> None:
    user = db.get(User, req.user_id) if requester_name is None else None
    requester_display = _format_user(req.user_id, requester_name or (user.username if user else None))
    admin_display = None
    if admin_name:
        admin_display = admin_name
    elif req.reviewed_by_user_id:
        admin = db.get(User, req.reviewed_by_user_id)
        admin_display = admin.username if admin else f"ID {req.reviewed_by_user_id}"

    title_map = {
        "created": "退款申请待审核",
        "approved": "退款申请已通过",
        "rejected": "退款申请已拒绝",
    }
    title = title_map.get(event, "退款申请通知")
    operator_id = req.user_id if event == "created" else req.reviewed_by_user_id
    detail_parts: list[str] = []
    if req.reason:
        detail_parts.append(f"原因：{req.reason}")
    detail_text = "，".join(detail_parts) if detail_parts else "无"
    screenshot_url = _extract_first_url(req.reason, req.review_note)

    lines = [
        f"**{title}**",
        f"- 申请ID：{req.id}",
        f"- 用户：{requester_display}",
        f"- 金额：{_format_amount(req.amount_cents, req.currency)}",
        f"- 时间：{req.created_at}",
        f"- 订单详情：{detail_text}",
    ]
    if screenshot_url:
        lines.append(f"- 支付截图链接：{screenshot_url}")
    if operator_id:
        lines.append(f"- 操作人ID：{operator_id}")
    if admin_display:
        lines.append(f"- 审核人：{admin_display}")
    if req.review_note:
        lines.append(f"- 审核说明：{req.review_note}")
    lines.append(f"- 入口：{_admin_link()}")
    _send_wecom_markdown("\n".join(lines))
