from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import RechargeRequest, RefundRequest
from app.models.enums import RequestStatus, WalletTxKind
from app.services.notification import notify_recharge_event, notify_refund_event
from app.services.wallet import apply_wallet_tx, lock_wallet


def approve_recharge(db: Session, request_id: int, admin_user_id: int, note: str | None) -> RechargeRequest:
    try:
        req = db.get(RechargeRequest, request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值申请不存在")
        if req.status != RequestStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="充值申请已处理")

        wallet = lock_wallet(db, req.user_id)
        try:
            apply_wallet_tx(
                db=db,
                wallet=wallet,
                amount_cents=req.amount_cents,
                kind=WalletTxKind.recharge,
                reference_type="recharge_request",
                reference_id=req.id,
                currency=req.currency,
                created_by_user_id=admin_user_id,
                note=note,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="重复入账") from exc

        req.status = RequestStatus.approved
        req.reviewed_at = utcnow()
        req.reviewed_by_user_id = admin_user_id
        req.review_note = note
        db.add(req)
        db.commit()
        db.refresh(req)
        notify_recharge_event(db, req, event="approved")
        return req
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def reject_recharge(db: Session, request_id: int, admin_user_id: int, note: str | None) -> RechargeRequest:
    try:
        req = db.get(RechargeRequest, request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="充值申请不存在")
        if req.status != RequestStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="充值申请已处理")

        req.status = RequestStatus.rejected
        req.reviewed_at = utcnow()
        req.reviewed_by_user_id = admin_user_id
        req.review_note = note
        db.add(req)
        db.commit()
        db.refresh(req)
        notify_recharge_event(db, req, event="rejected")
        return req
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def approve_refund(db: Session, request_id: int, admin_user_id: int, note: str | None) -> RefundRequest:
    try:
        req = db.get(RefundRequest, request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
        if req.status != RequestStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退款申请已处理")

        wallet = lock_wallet(db, req.user_id)
        try:
            apply_wallet_tx(
                db=db,
                wallet=wallet,
                amount_cents=-req.amount_cents,
                kind=WalletTxKind.refund,
                reference_type="refund_request",
                reference_id=req.id,
                currency=req.currency,
                created_by_user_id=admin_user_id,
                note=note,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="重复扣款") from exc

        req.status = RequestStatus.approved
        req.reviewed_at = utcnow()
        req.reviewed_by_user_id = admin_user_id
        req.review_note = note
        db.add(req)
        db.commit()
        db.refresh(req)
        notify_refund_event(db, req, event="approved")
        return req
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def reject_refund(db: Session, request_id: int, admin_user_id: int, note: str | None) -> RefundRequest:
    try:
        req = db.get(RefundRequest, request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
        if req.status != RequestStatus.pending:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退款申请已处理")

        req.status = RequestStatus.rejected
        req.reviewed_at = utcnow()
        req.reviewed_by_user_id = admin_user_id
        req.review_note = note
        db.add(req)
        db.commit()
        db.refresh(req)
        notify_refund_event(db, req, event="rejected")
        return req
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
