# © 2025 Mamu — All Rights Reserved
"""Billing router — Paystack subscription management for Nigerian Naira."""
import os
import hmac
import hashlib
import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel
import httpx
import requests

from routers.auth import get_current_user
from models.database import Subscription, Tenant, async_session, PlanEnum
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger("postforge.billing")

# Paystack API configuration
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_BASE_URL = "https://api.paystack.co"

# Naira pricing plans
PLANS = {
    "free":   {"name": "Free",   "price": 0,       "price_kobo": 0,        "posts": 30,   "platforms": 2},
    "starter": {"name": "Starter", "price": 5000,   "price_kobo": 500000,   "posts": 150,  "platforms": 5},
    "pro":    {"name": "Pro",    "price": 15000,   "price_kobo": 1500000,  "posts": 750,  "platforms": 5},
    "agency": {"name": "Agency", "price": 45000,   "price_kobo": 4500000,  "posts": -1,   "platforms": 5},
}


class PlanResponse(BaseModel):
    plan_id: str
    name: str
    price: int
    price_display: str
    posts: int
    platforms: int


@router.get("/plans")
async def get_plans():
    """Return available subscription plans with Naira pricing."""
    plans_list = []
    for plan_id, plan in PLANS.items():
        price_display = f"₦{plan['price']:,}" if plan['price'] > 0 else "Free"
        plans_list.append({
            "plan_id": plan_id,
            "name": plan["name"],
            "price": plan["price"],
            "price_display": price_display,
            "posts": plan["posts"],
            "platforms": plan["platforms"],
        })
    return {"plans": plans_list}


@router.post("/subscribe/{plan}")
async def subscribe(plan: str, user: dict = Depends(get_current_user)):
    """Create a Paystack checkout session for the selected plan."""
    if plan not in PLANS:
        raise HTTPException(400, "Invalid plan selected")
    if plan == "free":
        raise HTTPException(400, "Free plan does not require payment")

    plan_data = PLANS[plan]

    if not PAYSTACK_SECRET_KEY:
        logger.error("PAYSTACK_SECRET_KEY not configured")
        raise HTTPException(500, "Payment provider not configured")

    # Get user details
    user_id = user.get("id")
    email = user.get("email")

    # Create Paystack transaction
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": email,
        "amount": plan_data["price_kobo"],  # Amount in kobo
        "currency": "NGN",
        "callback_url": f"https://postforge.ai/api/v1/billing/subscribe-callback?plan={plan}&user_id={user_id}",
        "metadata": {
            "plan": plan,
            "user_id": user_id,
            "plan_name": plan_data["name"],
            "price": plan_data["price"],
        },
    }

    try:
        response = requests.post(
            f"{PAYSTACK_BASE_URL}/transaction/initialize",
            headers=headers,
            json=payload,
            timeout=30,
        )
        result = response.json()
        logger.info("Paystack initialize response: %s", result)

        if result.get("status"):
            reference = result["data"]["reference"]
            checkout_url = result["data"]["authorization_url"]
            return {
                "checkout_url": checkout_url,
                "reference": reference,
                "plan": plan,
                "amount": plan_data["price"],
                "currency": "NGN",
            }
        else:
            logger.error("Paystack error: %s", result)
            raise HTTPException(400, f"Paystack error: {result.get('message', 'Failed to create checkout')}")
    except requests.RequestException as e:
        logger.error("Paystack request failed: %s", str(e))
        raise HTTPException(500, "Failed to connect to payment provider")


@router.get("/subscribe-callback")
async def subscribe_callback(reference: str, plan: str, user_id: int):
    """Handle Paystack redirect after payment — verify and activate plan."""
    return await verify_payment_and_activate(reference, plan, user_id)


async def verify_payment_and_activate(reference: str, plan: str, user_id: int):
    """Verify Paystack transaction and upgrade user's subscription."""
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(500, "Payment provider not configured")

    # Verify the transaction
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=headers,
            timeout=30,
        )
        result = response.json()
        logger.info("Paystack verify response: %s", result)

        if not result.get("status"):
            raise HTTPException(400, "Payment verification failed")

        data = result["data"]
        if data.get("status") != "success":
            raise HTTPException(400, "Payment was not successful")

        # Payment successful — activate subscription
        async with async_session() as sess:
            # Get tenant for user
            user_result = await sess.execute(
                select(Subscription).where(Subscription.tenant_id == user_id)
            )
            # Actually need to get the user's tenant_id first
            from models.database import User
            user_row = await sess.get(User, user_id)
            if not user_row:
                raise HTTPException(404, "User not found")

            tenant_id = user_row.tenant_id

            # Check for existing subscription
            existing = await sess.execute(
                select(Subscription).where(Subscription.tenant_id == tenant_id)
            )
            sub = existing.scalar_one_or_none()

            if sub:
                sub.plan = PlanEnum[plan.upper()]
                sub.subscription_tier = plan
                sub.status = "active"
                sub.paystack_customer_id = data.get("customer", {}).get("id", "")
            else:
                sub = Subscription(
                    tenant_id=tenant_id,
                    plan=PlanEnum[plan.upper()],
                    subscription_tier=plan,
                    status="active",
                    paystack_customer_id=data.get("customer", {}).get("id", ""),
                )
                sess.add(sub)

            # Update tenant plan
            tenant = await sess.get(Tenant, tenant_id)
            if tenant:
                tenant.plan = PlanEnum[plan.upper()]

            await sess.commit()

            return {
                "success": True,
                "plan": plan,
                "message": "Subscription activated successfully",
            }

    except requests.RequestException as e:
        logger.error("Paystack verify failed: %s", str(e))
        raise HTTPException(500, "Failed to verify payment")


@router.get("/verify-payment/{reference}")
async def verify_payment(reference: str, user: dict = Depends(get_current_user)):
    """Verify a payment and activate subscription (called by frontend after redirect)."""
    user_id = user.get("id")
    return await verify_payment_and_activate(reference, "starter", user_id)


@router.post("/webhooks/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
):
    """Handle Paystack webhook events."""
    if not PAYSTACK_SECRET_KEY:
        logger.warning("Paystack webhook received but secret key not configured")
        return {"status": "ignored"}

    # Read raw body for signature verification
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify Paystack signature
    expected_sig = hmac.new(
        PAYSTACK_SECRET_KEY.encode("utf-8"),
        body_str.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()

    if x_paystack_signature != expected_sig:
        logger.warning("Paystack webhook signature mismatch")
        raise HTTPException(400, "Invalid webhook signature")

    try:
        event = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")

    event_type = event.get("event", "")

    if event_type == "charge.success":
        data = event.get("data", {})
        metadata = data.get("metadata", {})
        plan = metadata.get("plan", "starter")
        user_id = metadata.get("user_id")

        if user_id:
            await activate_subscription(plan, user_id, data)

    logger.info("Paystack webhook processed: %s", event_type)
    return {"status": "received"}


async def activate_subscription(plan: str, user_id: int, paystack_data: dict):
    """Activate a subscription for a user after payment confirmation."""
    async with async_session() as sess:
        from models.database import User

        user_row = await sess.get(User, user_id)
        if not user_row:
            logger.error("User not found for subscription activation: %s", user_id)
            return

        tenant_id = user_row.tenant_id

        # Check existing subscription
        existing = await sess.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        sub = existing.scalar_one_or_none()

        customer_id = paystack_data.get("customer", {}).get("id", "") if isinstance(paystack_data.get("customer"), dict) else ""

        if sub:
            sub.plan = PlanEnum[plan.upper()]
            sub.subscription_tier = plan
            sub.status = "active"
            sub.paystack_customer_id = customer_id
        else:
            sub = Subscription(
                tenant_id=tenant_id,
                plan=PlanEnum[plan.upper()],
                subscription_tier=plan,
                status="active",
                paystack_customer_id=customer_id,
            )
            sess.add(sub)

        # Update tenant plan
        tenant = await sess.get(Tenant, tenant_id)
        if tenant:
            tenant.plan = PlanEnum[plan.upper()]

        await sess.commit()
        logger.info("Subscription activated for user %s: plan=%s", user_id, plan)


@router.get("/subscription")
async def get_subscription(user: dict = Depends(get_current_user)):
    """Get current user's subscription status."""
    user_id = user.get("id")

    async with async_session() as sess:
        from models.database import User

        user_row = await sess.get(User, user_id)
        if not user_row:
            raise HTTPException(404, "User not found")

        tenant_id = user_row.tenant_id

        result = await sess.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            return {
                "subscription_tier": "free",
                "status": "active",
                "plan": "free",
                "posts": PLANS["free"]["posts"],
                "platforms": PLANS["free"]["platforms"],
            }

        return {
            "subscription_tier": sub.subscription_tier or "free",
            "status": sub.status,
            "plan": sub.plan.value if sub.plan else "free",
            "posts": PLANS.get(sub.subscription_tier, PLANS["free"])["posts"],
            "platforms": PLANS.get(sub.subscription_tier, PLANS["free"])["platforms"],
        }