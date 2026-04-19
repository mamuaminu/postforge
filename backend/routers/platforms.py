# © 2025 Mamu — All Rights Reserved
"""Platform connection management — OAuth flows and status."""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from models.database import ConnectedPlatform, PlatformEnum, async_session
from routers.auth import get_current_user
from sqlalchemy import select
import httpx, os

router = APIRouter()

# ─── OAuth configs ─────────────────────────────────────────────────────────────

OAUTH_CONFIGS = {
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scope": "pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish",
    },
    "x_twitter": {
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "scope": "tweet.read tweet.write users.read offline.access",
    },
    "instagram": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scope": "instagram_basic,instagram_content_publish,pages_read_engagement",
    },
    "threads": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scope": "pages_read_engagement,threads_basic,threads_content_publish",
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://api.linkedin.com/v2/oauth2/access_token",
        "scope": "openid profile w_member_social",
    },
}


class ConnectRequest(BaseModel):
    code: str  # OAuth authorization code
    platform: str
    redirect_uri: str  # Must match registered redirect URI


@router.get("/connect/{platform}/url")
async def get_oauth_url(
    platform: str,
    redirect_uri: str = Query(..., description="Registered OAuth redirect URI"),
    user=Depends(get_current_user),
):
    """Get the OAuth authorization URL for a platform."""
    if platform not in OAUTH_CONFIGS:
        raise HTTPException(400, f"Unsupported platform: {platform}")

    cfg = OAUTH_CONFIGS[platform]
    client_id = os.environ.get(f"{platform.upper()}_APP_ID", "")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope"],
        "state": f"tenant_{user['tenant_id']}",  # CSRF + tenant ID
    }

    auth_url = cfg["auth_url"]
    query_str = "&".join(f"{k}={v}" for k, v in params.items())
    return {"auth_url": f"{auth_url}?{query_str}"}


@router.post("/connect/{platform}")
async def complete_oauth(
    platform: str,
    req: ConnectRequest,
    user=Depends(get_current_user),
):
    """Exchange OAuth code for access token and store platform connection."""
    if platform not in OAUTH_CONFIGS:
        raise HTTPException(400, f"Unsupported platform: {platform}")

    cfg = OAUTH_CONFIGS[platform]
    client_id = os.environ.get(f"{platform.upper()}_APP_ID", "")
    client_secret = os.environ.get(f"{platform.upper()}_APP_SECRET", "")

    # Exchange code for token
    async with httpx.AsyncClient(timeout=30) as client:
        if platform == "linkedin":
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "code": req.code,
                    "redirect_uri": req.redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
        else:
            resp = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "code": req.code,
                    "redirect_uri": req.redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )

        if resp.status_code != 200:
            raise HTTPException(502, f"Token exchange failed: {resp.text}")

        token_data = resp.json()
        access_token = token_data.get("access_token")

    # Get account ID (page ID, user ID, etc.)
    account_id = await _get_platform_account_id(platform, access_token, user)

    # Store connection
    async with async_session() as sess:
        # Check if already connected
        existing = await sess.execute(
            select(ConnectedPlatform).where(
                ConnectedPlatform.tenant_id == user["tenant_id"],
                ConnectedPlatform.platform == platform,
            )
        )
        existing_platform = existing.scalar_one_or_none()
        if existing_platform:
            existing_platform.access_token_encrypted = access_token
            existing_platform.is_active = True
        else:
            cp = ConnectedPlatform(
                tenant_id=user["tenant_id"],
                platform=platform,
                account_id=account_id.get("id", ""),
                account_name=account_id.get("name", ""),
                access_token_encrypted=access_token,
            )
            sess.add(cp)
        await sess.commit()

    return {"connected": True, "platform": platform, "account": account_id}


@router.get("/")
async def list_connected_platforms(user=Depends(get_current_user)):
    """List all connected platforms for the current tenant."""
    async with async_session() as sess:
        result = await sess.execute(
            select(ConnectedPlatform).where(
                ConnectedPlatform.tenant_id == user["tenant_id"],
                ConnectedPlatform.is_active == True,
            )
        )
        platforms = result.scalars().all()
        return {
            "platforms": [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "account_name": p.account_name,
                    "account_id": p.account_id,
                    "connected_at": p.created_at.isoformat(),
                }
                for p in platforms
            ]
        }


@router.delete("/{platform}")
async def disconnect_platform(platform: str, user=Depends(get_current_user)):
    """Disconnect a platform."""
    async with async_session() as sess:
        result = await sess.execute(
            select(ConnectedPlatform).where(
                ConnectedPlatform.tenant_id == user["tenant_id"],
                ConnectedPlatform.platform == platform,
            )
        )
        cp = result.scalar_one_or_none()
        if not cp:
            raise HTTPException(404, f"{platform} not connected")

        cp.is_active = False
        await sess.commit()
    return {"disconnected": True, "platform": platform}


async def _get_platform_account_id(platform: str, token: str, user: dict) -> dict:
    """Query the platform API to get the canonical account ID and name."""
    async with httpx.AsyncClient(timeout=30) as client:
        if platform == "facebook":
            resp = await client.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={"access_token": token},
            )
            pages = resp.json().get("data", [])
            if not pages:
                raise HTTPException(400, "No Facebook Pages found for this account")
            page = pages[0]  # Use first page; multi-page support needs UI
            return {"id": page["id"], "name": page["name"]}

        elif platform == "x_twitter":
            resp = await client.get(
                "https://api.twitter.com/2/users/me",
                headers={"Authorization": f"Bearer {token}"},
                params={"user.fields": "name,username",
                        "expansions": "pinned_tweet_id",
                        "tweet.fields": "created_at"},
            )
            data = resp.json().get("data", {})
            return {"id": data.get("id", ""), "name": data.get("username", "")}

        elif platform in ("instagram", "threads"):
            # Get IG business account linked to FB page
            fb_resp = await client.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={"access_token": token},
            )
            pages = fb_resp.json().get("data", [])
            if pages:
                ig_resp = await client.get(
                    f"https://graph.facebook.com/v19.0/{pages[0]['id']}",
                    params={"fields": "instagram_business_account", "access_token": token},
                )
                ig_id = ig_resp.json().get("instagram_business_account", {}).get("id")
                if ig_id:
                    return {"id": ig_id, "name": pages[0]["name"]}
            return {"id": "", "name": ""}

        elif platform == "linkedin":
            resp = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            return {"id": data.get("sub", ""), "name": data.get("name", "")}

    return {"id": "", "name": ""}
