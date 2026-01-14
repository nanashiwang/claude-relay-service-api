from fastapi import APIRouter

from app.api.routes import admin, auth, cards, payment_config, products, recharge, refund, wallet

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(recharge.router, prefix="/recharge-requests", tags=["recharge"])
api_router.include_router(refund.router, prefix="/refund-requests", tags=["refund"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(payment_config.router, prefix="/payment-configs", tags=["payment-configs"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
