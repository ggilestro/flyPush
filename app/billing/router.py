"""Billing router — checkout config, portal, webhook, downgrade endpoints."""

import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.billing.paddle_service import (
    cancel_subscription,
    get_subscription_management_urls,
    verify_webhook_signature,
)
from app.billing.webhook_handler import dispatch_event
from app.config import get_settings
from app.db.models import PlanTier, SubscriptionStatus
from app.dependencies import CurrentAdmin, DbSession

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.get("/checkout-config")
async def checkout_config(user: CurrentAdmin):
    """Return Paddle client-side config for initialising checkout.

    Only admins can trigger checkouts (they manage billing for the lab).
    """
    tenant = user.tenant
    return {
        "client_token": settings.paddle_client_token,
        "environment": settings.paddle_environment,
        "price_id_lite": settings.paddle_price_id_lite,
        "price_id_pro": settings.paddle_price_id_pro,
        "tenant_id": tenant.id,
        "email": user.email,
        "paddle_customer_id": tenant.paddle_customer_id,
        "current_plan": tenant.plan.value,
        "subscription_status": tenant.subscription_status.value,
        "paddle_subscription_id": tenant.paddle_subscription_id,
        "scheduled_change": tenant.paddle_subscription_scheduled_change,
    }


@router.get("/portal")
async def billing_portal(user: CurrentAdmin):
    """Return Paddle subscription management URLs (update payment, cancel)."""
    tenant = user.tenant
    if not tenant.paddle_subscription_id:
        return JSONResponse(
            status_code=404,
            content={"detail": "No active subscription found"},
        )

    urls = await get_subscription_management_urls(tenant.paddle_subscription_id)
    if not urls:
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch management URLs from Paddle"},
        )

    return urls


@router.post("/webhook")
async def paddle_webhook(request: Request, db: DbSession):
    """Receive and process Paddle webhook events.

    This endpoint is public but protected by HMAC signature verification.
    """
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        logger.warning("Paddle webhook signature verification failed")
        return Response(status_code=403)

    payload = await request.json()
    event_type = payload.get("event_type", "")
    event_data = payload.get("data", {})

    logger.info("Paddle webhook received: %s", event_type)
    dispatch_event(db, event_type, event_data)

    return Response(status_code=200)


@router.post("/downgrade-to-free")
async def downgrade_to_free(user: CurrentAdmin, db: DbSession):
    """Cancel Paddle subscription at period end, or directly downgrade if no subscription."""
    tenant = user.tenant

    if tenant.paddle_subscription_id and tenant.subscription_status in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.TRIALING,
    ):
        success = await cancel_subscription(
            tenant.paddle_subscription_id,
            effective_from="next_billing_period",
        )
        if not success:
            return JSONResponse(
                status_code=502,
                content={"detail": "Failed to cancel subscription with Paddle"},
            )
        return {"detail": "Subscription will be cancelled at the end of the current billing period"}

    # No active Paddle subscription — downgrade immediately
    tenant.plan = PlanTier.FREE
    tenant.subscription_status = SubscriptionStatus.CANCELLED
    tenant.paddle_subscription_scheduled_change = None
    db.commit()

    return {"detail": "Downgraded to Free plan"}
