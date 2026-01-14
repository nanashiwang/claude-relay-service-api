from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.db.base import Base
from app.db.session import engine

# 创建所有数据库表（如果不存在）
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Card Platform API", version="0.1.0")
app.include_router(api_router, prefix="/api/v1")

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


def _should_set_csp(path: str) -> bool:
    if path.startswith(("/docs", "/redoc", "/openapi")):
        return False
    return path == "/" or path.startswith("/web")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        if k not in response.headers:
            response.headers[k] = v
    if _should_set_csp(request.url.path) and "Content-Security-Policy" not in response.headers:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/", include_in_schema=False)
def web_index():
    if WEB_DIR.exists():
        return FileResponse(str(WEB_DIR / "index.html"))
    return {"message": "Card Platform API. See /docs"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
