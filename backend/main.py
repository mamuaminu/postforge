# © 2025 Mamu — All Rights Reserved
"""PostForge AI — Multi-tenant social media automation platform."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import auth, posts, platforms, users, billing, webhooks
from models.database import engine, Base, async_session
from services.redis import init_redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("postforge")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("PostForge AI starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_redis()
    logger.info("PostForge AI ready")
    yield
    logger.info("PostForge AI shutting down...")


app = FastAPI(
    title="PostForge AI",
    version="2.0.0",
    description="AI-powered multi-tenant social media automation platform",
    lifespan=lifespan,
)

# Security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://postforge.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["posts"])
app.include_router(platforms.router, prefix="/api/v1/platforms", tags=["platforms"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/api/v1/health")
async def health():
    return {"status": "healthy", "service": "postforge-ai", "version": "2.0.0"}


@app.get("/api/v1")
async def root():
    return {
        "name": "PostForge AI",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
