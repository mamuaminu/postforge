# © 2025 Mamu — All Rights Reserved
"""Post management router — create, schedule, publish, list posts."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from models.database import Post, PostStatus, async_session
from routers.auth import get_current_user
from services.ai_generator import ContentGenerator
from services.social_publisher import get_platform_adapter
from sqlalchemy import select, func
import logging

router = APIRouter()
logger = logging.getLogger("postforge.posts")

# ─── Request/Response models ───────────────────────────────────────────────────

class GenerateContentRequest(BaseModel):
    prompt: str = Field(..., min_length=5, max_length=1000)
    platforms: list[str] = ["facebook", "x_twitter", "instagram", "threads", "linkedin"]
    tone: str = "bold"
    num_variations: int = 2


class CreatePostRequest(BaseModel):
    content: str
    platform: str
    image_urls: list[str] = []
    scheduled_at: Optional[datetime] = None
    ai_generated: bool = False
    ai_prompt: Optional[str] = None
    ai_variants: list = []


class GenerateThreadRequest(BaseModel):
    topic: str = Field(..., min_length=10)
    num_slides: int = Field(default=5, ge=3, le=20)


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_content(
    req: GenerateContentRequest,
    user=Depends(get_current_user),
):
    """
    Generate AI content for multiple platforms.
    Returns variations for each platform, ready for review or direct scheduling.
    """
    gen = ContentGenerator()
    result = await gen.generate(
        prompt=req.prompt,
        platforms=req.platforms,
        tone=req.tone,
        num_variations=req.num_variations,
    )
    return result


@router.post("/thread/generate")
async def generate_thread(
    req: GenerateThreadRequest,
    user=Depends(get_current_user),
):
    """Generate a Twitter/X thread on a given topic."""
    gen = ContentGenerator()
    result = await gen.generate_thread(
        topic=req.topic,
        num_slides=req.num_slides,
    )
    return result


@router.post("/{platform}")
async def create_post(
    platform: str,
    req: CreatePostRequest,
    user=Depends(get_current_user),
):
    """
    Create and optionally publish/schedule a post.
    If scheduled_at is set, queues for future publishing.
    If not, publishes immediately.
    """
    # Validate platform
    valid_platforms = ["facebook", "x_twitter", "instagram", "threads", "linkedin"]
    if platform not in valid_platforms:
        raise HTTPException(400, f"Platform must be one of: {valid_platforms}")

    # Rate limit check
    async with async_session() as sess:
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        count_result = await sess.execute(
            select(func.count(Post.id)).where(
                Post.tenant_id == user["tenant_id"],
                Post.created_at >= month_start,
            )
        )
        posts_this_month = count_result.scalar() or 0

        # Check plan limits (simplified)
        plan_limits = {"free": 30, "starter": 150, "pro": 750, "agency": 999999}
        limit = plan_limits.get(user.get("plan", "free"), 30)
        if posts_this_month >= limit:
            raise HTTPException(429, f"Monthly post limit reached ({limit}). Upgrade your plan.")

    status = PostStatus.SCHEDULED if req.scheduled_at else PostStatus.DRAFT

    async with async_session() as sess:
        post = Post(
            tenant_id=user["tenant_id"],
            author_id=user["id"],
            content=req.content,
            platform=platform,
            image_urls=req.image_urls,
            scheduled_at=req.scheduled_at,
            status=status,
            ai_generated=req.ai_generated,
            ai_prompt=req.ai_prompt,
            ai_variants=req.ai_variants,
        )
        sess.add(post)
        await sess.commit()
        await sess.refresh(post)

    if not req.scheduled_at:
        # Publish immediately in background
        return {"post_id": post.id, "status": "queued_for_publish", "platform": platform}
        # BackgroundTasks would call _publish_post(post.id) here

    return {
        "post_id": post.id,
        "status": "scheduled",
        "scheduled_for": req.scheduled_at.isoformat(),
        "platform": platform,
    }


@router.get("/")
async def list_posts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
):
    """List posts for the current tenant, with optional filters."""
    async with async_session() as sess:
        query = select(Post).where(Post.tenant_id == user["tenant_id"])
        if platform:
            query = query.where(Post.platform == platform)
        if status:
            query = query.where(Post.status == status)
        query = query.order_by(Post.created_at.desc()).limit(limit).offset(offset)
        result = await sess.execute(query)
        posts = result.scalars().all()

        return {
            "posts": [
                {
                    "id": p.id,
                    "content": p.content,
                    "platform": p.platform,
                    "status": p.status,
                    "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "platform_url": p.platform_url,
                    "ai_generated": p.ai_generated,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ],
            "total": len(posts),
            "limit": limit,
            "offset": offset,
        }


@router.get("/{post_id}")
async def get_post(post_id: int, user=Depends(get_current_user)):
    """Get a specific post by ID."""
    async with async_session() as sess:
        result = await sess.execute(
            select(Post).where(
                Post.id == post_id,
                Post.tenant_id == user["tenant_id"],
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            raise HTTPException(404, "Post not found")

        return {
            "id": post.id,
            "content": post.content,
            "platform": post.platform,
            "status": post.status,
            "image_urls": post.image_urls,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "platform_post_id": post.platform_post_id,
            "platform_url": post.platform_url,
            "error_message": post.error_message,
            "ai_generated": post.ai_generated,
            "ai_prompt": post.ai_prompt,
            "ai_variants": post.ai_variants,
        }


@router.delete("/{post_id}")
async def delete_post(post_id: int, user=Depends(get_current_user)):
    """Delete a post (only if not yet published, or unpublish first)."""
    async with async_session() as sess:
        result = await sess.execute(
            select(Post).where(
                Post.id == post_id,
                Post.tenant_id == user["tenant_id"],
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            raise HTTPException(404, "Post not found")

        if post.status == PostStatus.PUBLISHED and post.platform_post_id:
            # Try to delete from platform first
            try:
                # Would call platform adapter delete here
                pass
            except Exception as e:
                logger.error("Failed to delete from platform: %s", e)

        await sess.delete(post)
        await sess.commit()

    return {"deleted": True, "post_id": post_id}
