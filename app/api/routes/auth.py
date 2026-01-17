from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.captcha import generate_captcha, verify_captcha
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User, Wallet
from app.api.deps import get_current_user
from app.schemas.auth import CaptchaOut, LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter()


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> User:
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在") from exc

    db.add(Wallet(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    if not verify_captcha(
        code=payload.captcha_code,
        captcha_id=payload.captcha_id,
        captcha_expires=payload.captcha_expires,
        captcha_token=payload.captcha_token,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")

    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号不可用")

    token = create_access_token(subject=str(user.id), is_admin=user.is_admin)
    return TokenOut(access_token=token)


@router.get("/captcha", response_model=CaptchaOut)
def captcha() -> dict:
    return generate_captcha()


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)) -> User:
    return user
