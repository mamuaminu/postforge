# © 2025 Mamu — All Rights Reserved
"""Auth router — signup, login, JWT tokens."""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from models.database import User, Tenant, async_session
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALG = "HS256"


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, h: str) -> bool:
    return pwd_context.verify(pw, h)


def create_token(data: dict) -> str:
    d = data.copy()
    d["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(d, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(cred=Depends(security)) -> dict:
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    async with async_session() as sess:
        result = await sess.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(401, "User not found or inactive")

        return {
            "id": user.id,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "plan": "free",
        }


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""
    workspace_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
async def signup(req: SignupRequest):
    """Create tenant + first user account."""
    async with async_session() as sess:
        # Check existing
        existing = await sess.execute(select(User).where(User.email == req.email))
        if existing.scalar_one_or_none():
            raise HTTPException(409, "Email already registered")

        # Create tenant
        slug = (req.workspace_name or req.email.split("@")[0]).lower().replace(" ", "-")
        tenant = Tenant(name=req.workspace_name or slug, slug=slug)
        sess.add(tenant)
        await sess.flush()

        # Create user
        user = User(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
            tenant_id=tenant.id,
            role="owner",
        )
        sess.add(user)
        await sess.commit()

        token = create_token({"sub": str(user.id), "tenant_id": tenant.id})
        return {"token": token, "user": {"id": user.id, "email": user.email, "tenant_id": tenant.id}}


@router.post("/login")
async def login(req: LoginRequest):
    async with async_session() as sess:
        result = await sess.execute(select(User).where(User.email == req.email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(401, "Invalid email or password")

        token = create_token({"sub": str(user.id), "tenant_id": user.tenant_id})
        return {"token": token, "user": {"id": user.id, "email": user.email, "tenant_id": user.tenant_id}}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return user
