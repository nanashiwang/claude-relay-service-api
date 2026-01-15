from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123456"
DEFAULT_AGENT_USERNAME = "agent001"
DEFAULT_AGENT_PASSWORD = "agent123456"
DEFAULT_RECHARGE_REJECT_NOTE = "未收到转账信息，如有疑问请联系qq：438274867"


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _python_exe() -> str:
    return sys.executable


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_http_ok(url: str, timeout_s: float = 25) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if 200 <= int(resp.status) < 300:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(0.25)
    raise RuntimeError(f"服务未就绪: {url}; last_error={last_err}")


def _seed_demo_data(*, database_url: str) -> None:
    root = _root_dir()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("JWT_SECRET", "screenshot-" + uuid.uuid4().hex)
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_ACCESS_TOKEN_EXP_MINUTES", "10080")
    os.environ.setdefault("DEFAULT_CURRENCY", "CNY")
    os.environ.setdefault("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    os.environ.setdefault("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.session import SessionLocal, engine
    from app.models import Base, CardCode, PaymentConfig, Product, RechargeRequest, RefundRequest, User, Wallet
    from app.models.enums import CardCodeStatus
    from app.services.products import seed_default_products
    from app.services.requests import approve_recharge, reject_recharge
    from app.services.wallet import lock_wallet

    Base.metadata.create_all(bind=engine)

    try:
        with SessionLocal() as db:
            seed_default_products(db)

            admin = db.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME)).scalar_one_or_none()
            if not admin:
                admin = User(
                    username=DEFAULT_ADMIN_USERNAME,
                    password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                    is_admin=True,
                    is_active=True,
                )
                db.add(admin)
                db.flush()
                db.add(Wallet(user_id=admin.id, balance_cents=0, currency="CNY"))

            agent = db.execute(select(User).where(User.username == DEFAULT_AGENT_USERNAME)).scalar_one_or_none()
            if not agent:
                agent = User(
                    username=DEFAULT_AGENT_USERNAME,
                    password_hash=hash_password(DEFAULT_AGENT_PASSWORD),
                    is_admin=False,
                    is_active=True,
                )
                db.add(agent)
                db.flush()
                db.add(Wallet(user_id=agent.id, balance_cents=0, currency="CNY"))

            # 给产品设置演示价格（单位：分）
            products = db.execute(select(Product)).scalars().all()
            for p in products:
                if p.kind.value == "day":
                    if p.duration_days == 1:
                        p.price_cents = 500
                    elif p.duration_days == 7:
                        p.price_cents = 2500
                    else:
                        p.price_cents = 8800
                else:
                    if p.usage_usd == 10:
                        p.price_cents = 900
                    elif p.usage_usd == 30:
                        p.price_cents = 2600
                    else:
                        p.price_cents = 8200
                p.currency = "CNY"
                p.active = True

            # 准备一批卡密库存（用于店铺与库存统计）
            demo_skus = {"codex_day_1": 18, "gemini_day_7": 12, "claude_usage_10": 10}
            for sku, count in demo_skus.items():
                product = db.execute(select(Product).where(Product.sku == sku)).scalar_one_or_none()
                if not product:
                    continue
                for i in range(1, count + 1):
                    code = f"{sku.upper()}-DEMO-{i:04d}"
                    code_hash = hashlib.sha256(code.encode("utf-8")).digest()
                    exists = db.execute(select(CardCode.id).where(CardCode.code_sha256 == code_hash)).first()
                    if exists:
                        continue
                    db.add(
                        CardCode(
                            product_id=product.id,
                            code=code,
                            code_sha256=code_hash,
                            status=CardCodeStatus.available,
                            imported_by_user_id=admin.id,
                        )
                    )

            # 支付方式：使用内联 SVG，避免依赖上传目录
            qr_svg = (
                "<svg width='220' height='220' viewBox='0 0 110 110' xmlns='http://www.w3.org/2000/svg'>"
                "<rect width='110' height='110' fill='white'/>"
                "<rect x='6' y='6' width='26' height='26' fill='black'/>"
                "<rect x='78' y='6' width='26' height='26' fill='black'/>"
                "<rect x='6' y='78' width='26' height='26' fill='black'/>"
                "<rect x='42' y='42' width='10' height='10' fill='black'/>"
                "<rect x='56' y='42' width='10' height='10' fill='black'/>"
                "<rect x='42' y='56' width='10' height='10' fill='black'/>"
                "<rect x='70' y='60' width='8' height='8' fill='black'/>"
                "<rect x='60' y='70' width='8' height='8' fill='black'/>"
                "<rect x='52' y='80' width='6' height='6' fill='black'/>"
                "</svg>"
            )
            payment = db.execute(select(PaymentConfig).where(PaymentConfig.name == "支付宝")).scalar_one_or_none()
            if not payment:
                db.add(
                    PaymentConfig(
                        name="支付宝",
                        icon="alipay",
                        account_info=(
                            "<div>请使用支付宝扫码支付</div>"
                            "<div style='margin-top:12px;background:#fff;padding:12px;border-radius:12px;"
                            "border:1px solid rgba(0,0,0,0.08);width:fit-content'>"
                            f"{qr_svg}"
                            "</div>"
                        ),
                        instructions="转账时请备注用户名",
                        sort_order=0,
                        active=True,
                    )
                )

            db.commit()

            # 充值记录：approved / pending / rejected（用于用户侧展示审核备注、管理员侧审核列表）
            approved = RechargeRequest(
                user_id=agent.id,
                amount_cents=10000,
                currency="CNY",
                payment_method="支付宝",
                payment_reference="DEMO-10000",
                note="演示充值（已到账）",
            )
            db.add(approved)
            db.commit()
            approve_recharge(db=db, request_id=approved.id, admin_user_id=admin.id, note="已到账")

            pending = RechargeRequest(
                user_id=agent.id,
                amount_cents=5000,
                currency="CNY",
                payment_method="支付宝",
                payment_reference="DEMO-5000",
                note="演示充值（待审核）",
            )
            db.add(pending)
            db.commit()

            rejected = RechargeRequest(
                user_id=agent.id,
                amount_cents=3000,
                currency="CNY",
                payment_method="支付宝",
                payment_reference="DEMO-3000",
                note="演示充值（将被拒绝）",
            )
            db.add(rejected)
            db.commit()
            reject_recharge(db=db, request_id=rejected.id, admin_user_id=admin.id, note=DEFAULT_RECHARGE_REJECT_NOTE)

            # 退款申请：留一个待审核
            db.add(
                RefundRequest(
                    user_id=agent.id,
                    amount_cents=2000,
                    currency="CNY",
                    reason="演示退款申请（待审核）",
                )
            )

            # 确保钱包存在并有余额（便于展示控制台）
            lock_wallet(db, agent.id)
            db.commit()
    finally:
        engine.dispose()


def _run_uvicorn(*, base_env: dict[str, str], port: int) -> subprocess.Popen:
    cmd = [
        _python_exe(),
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(_root_dir()),
        env=base_env,
    )


def _capture(base_url: str, out_dir: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "未安装 Playwright。请先执行：\n"
            f'  "{_python_exe()}" -m pip install playwright\n'
            f'  "{_python_exe()}" -m playwright install chromium\n'
        ) from exc

    admin_token = _http_json(
        "POST",
        f"{base_url}/api/v1/auth/login",
        {"username": DEFAULT_ADMIN_USERNAME, "password": DEFAULT_ADMIN_PASSWORD},
    )["access_token"]
    agent_token = _http_json(
        "POST",
        f"{base_url}/api/v1/auth/login",
        {"username": DEFAULT_AGENT_USERNAME, "password": DEFAULT_AGENT_PASSWORD},
    )["access_token"]

    out_dir.mkdir(parents=True, exist_ok=True)

    def _safe_js_string(value: str) -> str:
        return json.dumps(value)

    def _capture_page(*, token: str | None, path: str, outfile: Path, wait_selector: str, after=None) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
            if token:
                context.add_init_script(f"localStorage.setItem('access_token', {_safe_js_string(token)});")
            page = context.new_page()
            page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
            page.wait_for_selector(wait_selector, timeout=15000)
            if after:
                after(page)
            page.wait_for_timeout(600)
            page.screenshot(path=str(outfile), full_page=True)
            context.close()
            browser.close()

    # 公开页
    _capture_page(token=None, path="/", outfile=out_dir / "01_login.png", wait_selector="#loginBtn")

    # 代理端
    _capture_page(token=agent_token, path="/web/dashboard.html", outfile=out_dir / "02_dashboard.png", wait_selector="#balanceText")
    _capture_page(token=agent_token, path="/web/shop.html", outfile=out_dir / "03_shop.png", wait_selector="#productGrid")

    def _recharge_after(page):
        # 点击第一个支付方式，展示收款信息/二维码区域
        card = page.locator(".payment-card").first
        if card:
            card.click()

    _capture_page(token=agent_token, path="/web/recharge.html", outfile=out_dir / "04_recharge.png", wait_selector="#paymentMethods", after=_recharge_after)
    _capture_page(token=agent_token, path="/web/refund.html", outfile=out_dir / "05_refund.png", wait_selector="#submitRefundBtn")

    # 管理端
    _capture_page(token=admin_token, path="/web/admin.html", outfile=out_dir / "06_admin_dashboard.png", wait_selector="#statUsers")

    def _admin_recharges(page):
        page.locator('button.nav-item[data-page=\"recharges\"]').click()
        page.wait_for_selector('#page-recharges.active', timeout=15000)

    _capture_page(token=admin_token, path="/web/admin.html", outfile=out_dir / "07_admin_recharges.png", wait_selector="#sidebar", after=_admin_recharges)

    def _admin_users(page):
        page.locator('button.nav-item[data-page=\"users\"]').click()
        page.wait_for_selector('#page-users.active', timeout=15000)

    _capture_page(token=admin_token, path="/web/admin.html", outfile=out_dir / "08_admin_users.png", wait_selector="#sidebar", after=_admin_users)

    def _admin_payments(page):
        page.locator('button.nav-item[data-page=\"payments\"]').click()
        page.wait_for_selector('#page-payments.active', timeout=15000)

    _capture_page(token=admin_token, path="/web/admin.html", outfile=out_dir / "09_admin_payments.png", wait_selector="#sidebar", after=_admin_payments)


def main() -> int:
    parser = argparse.ArgumentParser(description="自动启动服务并截取关键页面截图（用于 README）")
    parser.add_argument("--output", default="docs/screenshots", help="截图输出目录（默认：docs/screenshots）")
    parser.add_argument("--port", type=int, default=0, help="服务端口（默认：随机可用端口）")
    args = parser.parse_args()

    out_dir = (_root_dir() / args.output).resolve()
    port = int(args.port or _find_free_port())
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="card_platform_screenshots_", ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "demo.db"
        database_url = f"sqlite+pysqlite:///{db_path.as_posix()}?check_same_thread=false"

        base_env = os.environ.copy()
        base_env.update(
            {
                "DATABASE_URL": database_url,
                "JWT_SECRET": "screenshot-" + uuid.uuid4().hex,
                "JWT_ALGORITHM": "HS256",
                "JWT_ACCESS_TOKEN_EXP_MINUTES": "10080",
                "DEFAULT_CURRENCY": "CNY",
                "ADMIN_USERNAME": DEFAULT_ADMIN_USERNAME,
                "ADMIN_PASSWORD": DEFAULT_ADMIN_PASSWORD,
            }
        )

        _seed_demo_data(database_url=database_url)

        proc = _run_uvicorn(base_env=base_env, port=port)
        try:
            _wait_http_ok(f"{base_url}/health")
            _capture(base_url, out_dir)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

    print(f"截图已生成：{out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
