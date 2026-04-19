# © 2025 Mamu — All Rights Reserved
"""Celery tasks for PostForge AI — handles async publishing to social platforms."""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("postforge.tasks")

# Lazily resolved Celery app — no Redis connection until first task dispatch
_celery_app = None

def _get_celery():
    global _celery_app
    if _celery_app is None:
        from celery import Celery
        _celery_app = Celery(
            "postforge",
            broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            include=["services.tasks"],
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_acks_late=True,
            worker_prefetch_multiplier=1,
            task_soft_time_limit=120,
            task_time_limit=180,
            task_default_retry_delay=30,
            task_max_retries=3,
        )
    return _celery_app


def run_sync(coro):
    """Run an async coroutine in a new event loop (for Celery sync workers)."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def task(*args, **kwargs):
    """Decorator that resolves the Celery app lazily."""
    return _get_celery().task(*args, **kwargs)


async def _update_post_status(
    post_id: int,
    status,  # PostStatus enum
    platform_post_id: str = None,
    platform_url: str = None,
    error_message: str = None,
):
    import models.database
    async with models.database.async_session() as sess:
        from sqlalchemy import select
        result = await sess.execute(select(models.database.Post).where(models.database.Post.id == post_id))
        post = result.scalar_one_or_none()
        if post:
            post.status = status
            if platform_post_id:
                post.platform_post_id = platform_post_id
            if platform_url:
                post.platform_url = platform_url
            if error_message:
                post.error_message = error_message
            from datetime import datetime
            post.published_at = datetime.utcnow()
            await sess.commit()


@task(bind=True, max_retries=3, default_retry_delay=60, autoretry_for=(Exception,), retry_backoff=True)
def publish_post(self, post_id: int, platform: str, credentials: dict, content: str, image_urls: list = None):
    """
    Celery task: publish a post to the specified social platform.

    Args:
        post_id:     Internal PostForge Post ID
        platform:    facebook | x_twitter | instagram | threads | linkedin
        credentials: dict with access_token and account_id
        content:     Post text
        image_urls:  Optional list of image URLs
    """
    from services.social_publisher import get_platform_adapter

    logger.info(f"[publish_post] post_id={post_id} platform={platform}")

    try:
        adapter = get_platform_adapter(platform, credentials)
        result = run_sync(adapter.publish(content=content, image_urls=image_urls or []))

        platform_post_id = result.get("platform_post_id", "")
        platform_url = result.get("post_url", "")

        logger.info(f"[publish_post] Success post_id={post_id} url={platform_url}")

        import models.database
        run_sync(_update_post_status(post_id, models.database.PostStatus.PUBLISHED, platform_post_id, platform_url))

        return {"ok": True, "post_id": post_id, "url": platform_url}

    except Exception as exc:
        logger.error(f"[publish_post] Failed post_id={post_id}: {exc}")
        import models.database
        run_sync(_update_post_status(post_id, models.database.PostStatus.FAILED, error_message=str(exc)[:500]))
        raise self.retry(exc=exc)
