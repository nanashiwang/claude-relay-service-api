from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import settings

CAPTCHA_LENGTH = 5
CAPTCHA_TTL_SECONDS = 180
CAPTCHA_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _sign(payload: str) -> str:
    digest = hmac.new(settings.jwt_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _build_svg(code: str) -> str:
    width = 140
    height = 48
    pad = 16
    text_x = pad
    text_y = 32
    lines = []
    for _ in range(4):
        x1 = secrets.randbelow(width)
        y1 = secrets.randbelow(height)
        x2 = secrets.randbelow(width)
        y2 = secrets.randbelow(height)
        opacity = 0.12 + secrets.randbelow(20) / 100
        lines.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#0f172a' stroke-opacity='{opacity}' stroke-width='1'/>")

    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
        f"<rect width='{width}' height='{height}' rx='10' fill='white'/>"
        f"<rect width='{width}' height='{height}' rx='10' fill='none' stroke='rgba(15,23,42,0.12)'/>"
        f"{''.join(lines)}"
        f"<text x='{text_x}' y='{text_y}' font-size='22' font-family='Segoe UI, sans-serif' font-weight='700' fill='#0f172a'>{code}</text>"
        "</svg>"
    )


def generate_captcha() -> dict:
    code = "".join(secrets.choice(CAPTCHA_CHARS) for _ in range(CAPTCHA_LENGTH))
    captcha_id = secrets.token_urlsafe(8)
    expires = int(time.time()) + CAPTCHA_TTL_SECONDS
    payload = f"{captcha_id}.{expires}.{code}"
    token = _sign(payload)

    svg = _build_svg(code)
    svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")

    return {
        "captcha_id": captcha_id,
        "captcha_expires": expires,
        "captcha_token": token,
        "captcha_svg": f"data:image/svg+xml;base64,{svg_b64}",
    }


def verify_captcha(*, code: str, captcha_id: str, captcha_expires: int, captcha_token: str) -> bool:
    if not code or not captcha_id or not captcha_token:
        return False
    now = int(time.time())
    if captcha_expires <= now:
        return False
    if captcha_expires - now > CAPTCHA_TTL_SECONDS + 60:
        return False

    payload = f"{captcha_id}.{captcha_expires}.{code.strip().upper()}"
    expected = _sign(payload)
    return hmac.compare_digest(expected, captcha_token)
