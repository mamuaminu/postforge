# © 2025 Mamu — All Rights Reserved
"""Users & tenant management router."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.database import User, async_session
from routers.auth import get_current_user
from sqlalchemy import select

router = APIRouter()


@router.get("/me/workspace")
async def get_workspace(user=Depends(get_current_user)):
    """Return workspace/tenant info and usage stats."""
    async with async_session() as sess:
        result = await sess.execute(
            select(User).where(User.tenant_id == user["tenant_id"])
        )
        members = result.scalars().all()
        return {
            "tenant_id": user["tenant_id"],
            "plan": "free",
            "members": [{"id": u.id, "email": u.email, "role": u.role} for u in members],
        }
