# © 2025 Mamu — All Rights Reserved
"""
PostForge AI — Social Media Publishing Service

Platform adapters for Facebook, X (Twitter), Instagram, Threads, LinkedIn.
Each platform has its own OAuth flow, API quirks, media handling, and rate limits.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger("postforge.platforms")

# ─── Base Adapter ──────────────────────────────────────────────────────────────

class PlatformAdapter(ABC):
    """Base class for all platform adapters."""

    platform_name: str = ""

    def __init__(self, access_token: str, account_id: str):
        self.access_token = access_token
        self.account_id = account_id

    @abstractmethod
    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        """Publish a post. Returns dict with platform_post_id and post_url."""
        pass

    @abstractmethod
    async def get_post(self, post_id: str) -> Dict[str, Any]:
        """Fetch a published post's status and stats."""
        pass

    @abstractmethod
    async def delete_post(self, post_id: str) -> bool:
        """Delete a published post."""
        pass

    @abstractmethod
    async def refresh_token_if_needed(self) -> str:
        """Refresh OAuth token if expired. Returns new token."""
        pass

    def _log_result(self, action: str, post_id: str = None, success: bool = True,
                    error: str = None):
        status = "SUCCESS" if success else "FAIL"
        msg = f"[{self.platform_name}] {action} | post_id={post_id} | {status}"
        if error:
            msg += f" | error={error}"
        if success:
            logger.info(msg)
        else:
            logger.error(msg)


# ─── Facebook / Meta Graph API ─────────────────────────────────────────────────

class FacebookAdapter(PlatformAdapter):
    """
    Meta Graph API v19.0 — Facebook + Instagram.
    Docs: https://developers.facebook.com/docs/graph-api
    """

    platform_name = "facebook"

    def __init__(self, access_token: str, account_id: str):
        super().__init__(access_token, account_id)
        self.base_url = "https://graph.facebook.com/v19.0"

    async def _get_page_access_token(self) -> str:
        """Facebook requires matching page token; extend long-lived tokens."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": os.getenv("META_APP_ID"),
                    "client_secret": os.getenv("META_APP_SECRET"),
                    "fb_exchange_token": self.access_token,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["access_token"]

    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        """Publish to Facebook Page. Supports: text, image, link, scheduled."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Image upload
                image_id = None
                if image_urls:
                    img_resp = await client.post(
                        f"{self.base_url}/{self.account_id}/photos",
                        params={"access_token": self.access_token},
                        data={
                            "url": image_urls[0],
                            "published": "false" if scheduled_at else "true",
                        }
                    )
                    img_resp.raise_for_status()
                    image_id = img_resp.json().get("id")

                # Post creation
                post_payload = {
                    "message": content[:63206],  # FB max
                    "access_token": self.access_token,
                }
                if image_id:
                    post_payload["attached_media"] = f'{{"media_fbid":"{image_id}"}}'
                if scheduled_at:
                    post_payload["publish_immediately"] = "false"
                    post_payload["scheduled_publish_time"] = int(scheduled_at.timestamp())

                resp = await client.post(
                    f"{self.base_url}/{self.account_id}/feed",
                    data=post_payload,
                )
                resp.raise_for_status()
                result = resp.json()

                self._log_result("publish", post_id=result.get("id"))
                return {
                    "platform_post_id": result.get("id"),
                    "post_url": f"https://facebook.com/{self.account_id}/posts/{result.get('id')}",
                    "success": True,
                }
        except Exception as e:
            self._log_result("publish", success=False, error=str(e))
            raise

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/{post_id}",
                params={"fields": "message,full_picture,created_time,likes.summary(true),comments.summary(true),shares", "access_token": self.access_token}
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/{post_id}",
                params={"access_token": self.access_token}
            )
            resp.raise_for_status()
            return resp.json().get("success", False)

    async def refresh_token_if_needed(self) -> str:
        # Facebook tokens last ~60 days; extend via exchange endpoint
        return await self._get_page_access_token()


# ─── X / Twitter ──────────────────────────────────────────────────────────────

class XTwitterAdapter(PlatformAdapter):
    """
    X API v2 — tweets, images, threads.
    Docs: https://developer.x.com/en/docs/twitter-api
    """

    platform_name = "x_twitter"

    def __init__(self, bearer_token: str, api_key: str, api_secret: str,
                 access_token: str, access_secret: str):
        super().__init__(access_token, api_key)
        self.bearer_token = bearer_token
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_secret = access_secret
        self.base_url = "https://api.twitter.com/2"

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.bearer_token}", "Content-Type": "application/json"}

    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        """Tweet text or image. X v2 API supports 280 chars base, long-form via NoteFS."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                media_ids = []
                if image_urls:
                    for url in image_urls[:4]:  # X allows max 4 images
                        # Download image first
                        img_resp = await client.get(url, timeout=30)
                        img_resp.raise_for_status()
                        files = {"media": ("image.jpg", img_resp.content, "image/jpeg")}
                        upload_resp = await client.post(
                            "https://upload.twitter.com/1.1/media/upload.json",
                            auth=httpx.Auth(self.api_key, self.api_secret),
                            files=files,
                        )
                        upload_resp.raise_for_status()
                        media_ids.append(upload_resp.json()["media_id_string"])

                payload = {"text": content[:280]}
                if media_ids:
                    payload["media"] = {"media_ids": media_ids}

                resp = await client.post(
                    f"{self.base_url}/tweets",
                    headers=self._auth_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()
                tweet_id = result["data"]["id"]

                self._log_result("publish", post_id=tweet_id)
                return {
                    "platform_post_id": tweet_id,
                    "post_url": f"https://twitter.com/i/status/{tweet_id}",
                    "success": True,
                }
        except Exception as e:
            self._log_result("publish", success=False, error=str(e))
            raise

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/tweets/{post_id}",
                params={"tweet.fields": "public_metrics,created_at"},
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/tweets/{post_id}",
                headers=self._auth_headers(),
            )
            return resp.status_code == 200

    async def refresh_token_if_needed(self) -> str:
        return self.access_token


# ─── Instagram ────────────────────────────────────────────────────────────────

class InstagramAdapter(PlatformAdapter):
    """
    Instagram Graph API (professional accounts only).
    Handles carousel, Reels, stories via Meta Graph API.
    """

    platform_name = "instagram"

    def __init__(self, access_token: str, account_id: str):
        super().__init__(access_token, account_id)  # account_id = IG User ID
        self.base_url = "https://graph.facebook.com/v19.0"

    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        """Instagram requires image. Caption is separate from image."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                image_id = None
                if image_urls:
                    img_resp = await client.post(
                        f"{self.base_url}/{self.account_id}/children",
                        params={
                            "image_url": image_urls[0],
                            "access_token": self.access_token,
                        }
                    )
                    img_resp.raise_for_status()
                    image_id = img_resp.json().get("id")

                container_payload = {
                    "caption": content[:2200],  # IG caption limit
                    "access_token": self.access_token,
                }
                if image_id:
                    container_payload["children_media_ids"] = image_id
                    container_payload["media_type"] = "IMAGE"
                elif not image_urls:
                    container_payload["media_type"] = "TEXT"

                container_resp = await client.post(
                    f"{self.base_url}/{self.account_id}/media",
                    data=container_payload,
                )
                container_resp.raise_for_status()
                container_id = container_resp.json()["id"]

                publish_payload = {
                    "creation_id": container_id,
                    "access_token": self.access_token,
                }
                if scheduled_at:
                    publish_payload["publish_at"] = int(scheduled_at.timestamp())

                resp = await client.post(
                    f"{self.base_url}/{self.account_id}/media_publish",
                    data=publish_payload,
                )
                resp.raise_for_status()
                result = resp.json()

                self._log_result("publish", post_id=result.get("id"))
                return {
                    "platform_post_id": result.get("id"),
                    "post_url": f"https://instagram.com/p/{result.get('id')}",
                    "success": True,
                }
        except Exception as e:
            self._log_result("publish", success=False, error=str(e))
            raise

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/{post_id}",
                params={"fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count", "access_token": self.access_token}
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/{post_id}",
                params={"access_token": self.access_token}
            )
            return resp.json().get("success", False)

    async def refresh_token_if_needed(self) -> str:
        return self.access_token


# ─── Threads ──────────────────────────────────────────────────────────────────

class ThreadsAdapter(PlatformAdapter):
    """
    Threads API via Meta Graph API.
    Threads posts mirror to Instagram — same auth token.
    """

    platform_name = "threads"

    def __init__(self, access_token: str, account_id: str):
        super().__init__(access_token, account_id)
        self.base_url = "https://graph.facebook.com/v19.0"

    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Create text-only or image thread
                payload = {
                    "text": content[:500],
                    "access_token": self.access_token,
                }
                if image_urls:
                    img_resp = await client.post(
                        f"{self.base_url}/{self.account_id}/media",
                        params={"media_type": "IMAGE", "image_url": image_urls[0], "access_token": self.access_token}
                    )
                    img_resp.raise_for_status()
                    payload["media_ids"] = [img_resp.json()["id"]]

                container_resp = await client.post(
                    f"{self.base_url}/{self.account_id}/threads",
                    data=payload,
                )
                container_resp.raise_for_status()
                container_id = container_resp.json()["id"]

                publish_resp = await client.post(
                    f"{self.base_url}/{self.account_id}/threads_publish",
                    data={"creation_id": container_id, "access_token": self.access_token},
                )
                publish_resp.raise_for_status()
                result = publish_resp.json()

                self._log_result("publish", post_id=result.get("id"))
                return {
                    "platform_post_id": result.get("id"),
                    "post_url": f"https://threads.net/@threaderuser/post/{result.get('id')}",
                    "success": True,
                }
        except Exception as e:
            self._log_result("publish", success=False, error=str(e))
            raise

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/{post_id}",
                params={"fields": "id,text,created_at,like_count", "access_token": self.access_token}
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/{post_id}",
                params={"access_token": self.access_token}
            )
            return resp.json().get("success", False)

    async def refresh_token_if_needed(self) -> str:
        return self.access_token


# ─── LinkedIn ─────────────────────────────────────────────────────────────────

class LinkedInAdapter(PlatformAdapter):
    """
    LinkedIn API v2 — Organization posts.
    Requires: openid, profile, w_member_social scopes.
    """

    platform_name = "linkedin"

    def __init__(self, access_token: str, account_id: str):
        super().__init__(access_token, account_id)  # account_id = URN
        self.base_url = "https://api.linkedin.com/v2"

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202404",
        }

    async def publish(self, content: str, image_urls: List[str] = None,
                      scheduled_at: datetime = None, **kwargs) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                author = f"urn:li:organization:{self.account_id}"
                lifecycle = "published" if not scheduled_at else "scheduled"

                article = {
                    "author": author,
                    "commentary": content[:3000],
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MainFeed",
                        "targetEntities": [],
                        "thirdPartyDistributionChannels": [],
                    },
                    "lifecycleStateInfo": {"action": "ACTION", "state": lifecycle.upper()},
                }

                if scheduled_at:
                    article["scheduledTime"] = int(scheduled_at.timestamp() * 1000)

                # Image registration + upload
                if image_urls:
                    reg_resp = await client.post(
                        f"{self.base_url}/assets",
                        headers=self._auth_headers(),
                        json={"registerUploadRequest": {
                            "recipes": ["urn:li:digitalmediaRecipe:shareimage"],
                            "owner": author,
                            "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userSystem"}],
                        }},
                    )
                    reg_resp.raise_for_status()
                    upload_url = reg_resp.json()["value"]["assetUploadRequest"]["uploadUrl"]
                    asset_urn = reg_resp.json()["value"]["asset"]

                    img_resp = await client.put(upload_url, content=image_urls[0].encode(), headers={"Content-Type": "application/octet-stream"})
                    img_resp.raise_for_status()
                    article["content"] = {"media": [{"status": "READY", "originalUrl": image_urls[0], "asset": asset_urn}]}

                resp = await client.post(
                    f"{self.base_url}/ugcPosts",
                    headers=self._auth_headers(),
                    json=article,
                )
                resp.raise_for_status()
                result = resp.json()
                post_urn = result.get("id", "")

                self._log_result("publish", post_id=post_urn)
                return {
                    "platform_post_id": post_urn,
                    "post_url": f"https://linkedin.com/feed/update/{post_urn}",
                    "success": True,
                }
        except Exception as e:
            self._log_result("publish", success=False, error=str(e))
            raise

    async def get_post(self, post_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/ugcPosts/{post_id}",
                params={"projection": "(id,text,created,likeCount,commentCount,reshareCount)",
                        "q": "id", "id": post_id},
                headers=self._auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_post(self, post_id: str) -> bool:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{self.base_url}/ugcPosts/{post_id}",
                headers=self._auth_headers(),
            )
            return resp.status_code in (200, 204)

    async def refresh_token_if_needed(self) -> str:
        return self.access_token


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_platform_adapter(platform: str, credentials: Dict[str, str]) -> PlatformAdapter:
    """Resolve platform string to adapter instance."""
    adapters = {
        "facebook": FacebookAdapter,
        "x_twitter": XTwitterAdapter,
        "instagram": InstagramAdapter,
        "threads": ThreadsAdapter,
        "linkedin": LinkedInAdapter,
    }
    adapter_class = adapters.get(platform.lower())
    if not adapter_class:
        raise ValueError(f"Unsupported platform: {platform}")
    return adapter_class(**credentials)
