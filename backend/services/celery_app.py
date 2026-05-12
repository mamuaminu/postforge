# © 2025 Mamu — All Rights Reserved
"""Celery app for PostForge AI — lazy init so no Redis connection on import."""

import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Create app lazily — only connects to broker when first task is dispatched
celery_app = None

def _get_celery_app():
    global celery_app
    if celery_app is None:
        from celery import Celery
        celery_app = Celery(
            "postforge",
            broker=REDIS_URL,
            backend=None,  # No result backend needed — we update DB directly
            include=["services.tasks"],
        )
        celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
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
    return celery_app
