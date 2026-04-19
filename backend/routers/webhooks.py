# © 2025 Mamu — All Rights Reserved
"""Incoming webhooks — Stripe, platform callbacks, n8n triggers."""
from fastapi import APIRouter, Request, HTTPException
import logging

router = APIRouter()
logger = logging.getLogger("postforge.webhooks")


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe events: payment_succeeded, customer.subscription.updated, etc."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    # In production: verify signature with stripe.webhooks.construct_event
    logger.info("Stripe webhook received (sig=%s)", sig[:16])
    return {"received": True}


@router.post("/n8n/{event}")
async def n8n_webhook(event: str, request: Request):
    """n8n automation events — post published, thread reply, engagement alert."""
    payload = await request.json()
    logger.info("n8n webhook: %s", event)
    return {"event": event, "processed": True}


@router.post("/platform/{platform}/callback")
async def platform_callback(platform: str, request: Request):
    """Handle platform OAuth callbacks and webhook subscriptions."""
    payload = await request.json()
    logger.info("Platform callback: %s", platform)
    return {"platform": platform, "ok": True}