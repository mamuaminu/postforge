# © 2025 Mamu — All Rights Reserved
"""Billing router — Stripe subscription management."""
from fastapi import APIRouter, HTTPException, Depends
from routers.auth import get_current_user

router = APIRouter()

PLANS = {
    "free":  {"name": "Free", "price": 0, "posts": 30, "platforms": 2},
    "starter": {"name": "Starter", "price": 29, "posts": 150, "platforms": 5},
    "pro":    {"name": "Pro", "price": 99, "posts": 750, "platforms": 5},
    "agency": {"name": "Agency", "price": 299, "posts": -1, "platforms": 5},
}


@router.get("/plans")
async def get_plans():
    return {"plans": PLANS}


@router.post("/subscribe/{plan}")
async def subscribe(plan: str, user=Depends(get_current_user)):
    if plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    return {"url": "https://checkout.stripe.com/...", "plan": plan}
