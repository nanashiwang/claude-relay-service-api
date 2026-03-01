from fastapi import APIRouter

from app.api.routes import (
    admin,
    announcement,
    auth,
    cards,
    merchants,
    orders,
    payment_config,
    payments,
    products,
    rebate_config,
    referral,
    share_links,
    wallet,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(payment_config.router, prefix="/payment-configs", tags=["payment-configs"])
api_router.include_router(announcement.router, prefix="/announcement", tags=["announcement"])
api_router.include_router(referral.router, prefix="/referrals", tags=["referrals"])
api_router.include_router(merchants.router, tags=["merchants"])
api_router.include_router(share_links.router, tags=["share-links"])
api_router.include_router(rebate_config.router, tags=["rebate-config"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Admin routes
api_router.include_router(merchants.admin_router)
api_router.include_router(rebate_config.admin_router)
