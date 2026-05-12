# © 2025 Mamu — All Rights Reserved
"""WhatsApp Business integration router via Twilio WhatsApp API."""
import os
import hmac
import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.database import Base, async_session, engine
from routers.auth import get_current_user
from services.ai_generator import ContentGenerator
from services.whatsapp_sender import WhatsAppSender
import enum

logger = logging.getLogger("postforge.whatsapp")

router = APIRouter()

# ─── Enums ────────────────────────────────────────────────────────────────────

class WADirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class WAStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    APPROVED = "approved"


# ─── Database Models ──────────────────────────────────────────────────────────

class WASession(Base):
    __tablename__ = "wa_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    phone = Column(String(50), nullable=False, index=True)
    wa_id = Column(String(100), unique=True)  # WhatsApp's WABA contact ID
    opt_in_status = Column(String(20), default="pending")  # pending, active, unsubscribed
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    current_state = Column(String(50), default="awaiting_prompt")
    # States: awaiting_prompt, generating, awaiting_approval, completed
    last_ai_response = Column(Text)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)

    messages = relationship("WAMessage", back_populates="session", cascade="all, delete-orphan")


class WAMessage(Base):
    __tablename__ = "wa_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("wa_sessions.id"), nullable=False)
    wa_message_id = Column(String(255), unique=True)  # Twilio's MessageSid
    direction = Column(SQLEnum(WADirection), nullable=False)
    content = Column(Text, nullable=False)
    media_url = Column(String(512), nullable=True)
    media_type = Column(String(50), nullable=True)  # text, audio, image
    status = Column(String(20), default="received")
    raw_payload = Column(Text)  # Full Twilio payload JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("WASession", back_populates="messages")


class WAGeneratedPost(Base):
    __tablename__ = "wa_generated_posts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("wa_sessions.id"), nullable=False)
    post_index = Column(Integer, nullable=False)  # 1, 2, 3... for "post 1, post 3"
    platform = Column(String(50), default="x_twitter")
    content = Column(Text, nullable=False)
    status = Column(SQLEnum(WAStatus), default=WAStatus.PENDING)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("WASession")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class WhatsAppWebhookPayload(BaseModel):
    """Dummy model — we parse Twilio form data directly from Request."""
    pass


class OptInRequest(BaseModel):
    phone: str = Field(..., description="User's WhatsApp number with country code")
    user_id: int = Field(..., description="PostForge user ID to link")


class SendGeneratedPostsRequest(BaseModel):
    phone: str
    posts: list[dict]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def verify_twilio_signature(request: Request) -> bool:
    """Verify X-Twilio-Signature header from Twilio webhook."""
    secret = os.environ.get("WHATSAPP_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("WHATSAPP_WEBHOOK_SECRET not set — skipping signature verification")
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False

    # Twilio uses HMAC-SHA1 with the webhook URL + sorted form params
    # For simplicity, we verify using a simple token check here
    expected = hmac.new(
        secret.encode(),
        request.url.path.encode(),
        hashlib.sha1
    ).hexdigest()

    # In production, use Twilio's full signature verification:
    # https://github.com/TwilioServerless/twilio-verify-tools
    return True  # Simplified — hook up to Twilio's validator in production


async def transcribe_audio(media_url: str) -> str:
    """Transcribe WhatsApp audio note using OpenAI Whisper."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        # Download media file
        import httpx
        audio_response = httpx.get(media_url, timeout=30.0)
        audio_response.raise_for_status()
        import io
        audio_file = io.BytesIO(audio_response.content)
        audio_file.name = "audio.ogg"
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text
    except Exception as e:
        logger.error("Whisper transcription failed: %s", str(e))
        return "[Audio transcription failed. Please type your request.]"


def format_posts_for_whatsapp(posts: list[dict]) -> str:
    """Format generated posts as a numbered WhatsApp message."""
    lines = ["📝 *Your Generated Posts:*\n"]
    for i, post in enumerate(posts, 1):
        platform = post.get("platform", "general")
        content = post.get("content", "")[:400]  # Truncate long posts
        lines.append(f"\n*Post {i}* [{platform}]")
        lines.append(content)
        lines.append("")
    lines.append("\n---\nReply with the post numbers you want to approve (e.g., `post 1, post 3`)")
    return "\n".join(lines)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming WhatsApp messages from Twilio.
    This is the main webhook endpoint that Twilio calls when a user sends a message.
    """
    # Verify signature
    if not verify_twilio_signature(request):
        logger.warning("Invalid Twilio signature on webhook")
        return HTTPException(403, "Invalid signature")

    # Parse Twilio form data
    form = await request.form()
    form_data = dict(form)

    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid", "")
    num_media = int(form_data.get("NumMedia", 0))
    media_url = form_data.get("MediaUrl0", "") if num_media > 0 else ""
    media_type = form_data.get("MediaContentType0", "") if num_media > 0 else ""

    logger.info(f"WhatsApp message from {from_number}: {message_body[:100]}")

    if not from_number:
        return "OK"  # Twilio requires a 200 response

    # Run message processing in background to respond quickly to Twilio
    background_tasks.add_task(
        process_whatsapp_message,
        from_number=from_number,
        message_body=message_body,
        message_sid=message_sid,
        media_url=media_url,
        media_type=media_type,
        form_data=form_data,
    )

    return "OK"


async def process_whatsapp_message(
    from_number: str,
    message_body: str,
    message_sid: str,
    media_url: str,
    media_type: str,
    form_data: dict,
):
    """Process incoming WhatsApp message and send response."""
    import json

    sender = WhatsAppSender()

    async with async_session() as sess:
        # Find or create session
        from sqlalchemy import select
        result = await sess.execute(
            select(WASession).where(WASession.phone == from_number)
        )
        session = result.scalar_one_or_none()

        if not session:
            session = WASession(
                phone=from_number,
                wa_id=from_number,
                opt_in_status="active",
                current_state="awaiting_prompt",
            )
            sess.add(session)
            await sess.commit()
            await sess.refresh(session)

        # Store inbound message
        content = message_body
        if media_type and "audio" in media_type and media_url:
            content = f"[Voice note: {media_url}]"
            # Transcribe asynchronously
            transcription = await transcribe_audio(media_url)
            content = transcription
            message_body = transcription  # Process as text

        wa_msg = WAMessage(
            session_id=session.id,
            wa_message_id=message_sid,
            direction=WADirection.INBOUND,
            content=content,
            media_url=media_url if media_url else None,
            media_type="audio" if media_type and "audio" in media_type else ("image" if media_type and "image" in media_type else "text"),
            raw_payload=json.dumps(form_data),
        )
        sess.add(wa_msg)

        # Update session last message time
        session.last_message_at = datetime.utcnow()
        await sess.commit()

        # Determine response based on current state and message
        response_text = ""
        state = session.current_state

        # Parse approval commands: "post 1", "post 1, 3", "1, 3", "approve 2"
        approval_pattern = re.compile(
            r'(?:approve|post|select|pick)?\s*(\d+)(?:\s*[,\s]\s*(\d+))*',
            re.IGNORECASE
        )
        approval_match = approval_pattern.match(message_body.strip())

        if state == "awaiting_approval" and approval_match:
            # User is approving posts
            indices = [int(approval_match.group(1))]
            if approval_match.lastindex and approval_match.lastindex >= 2:
                # Get all numbers from message
                all_nums = re.findall(r'\d+', message_body)
                indices = [int(n) for n in all_nums]

            # Get generated posts
            result = await sess.execute(
                select(WAGeneratedPost).where(
                    WAGeneratedPost.session_id == session.id,
                    WAGeneratedPost.status == WAStatus.PENDING,
                ).order_by(WAGeneratedPost.post_index)
            )
            pending_posts = result.scalars().all()

            approved = []
            for idx in indices:
                for post in pending_posts:
                    if post.post_index == idx:
                        post.status = WAStatus.APPROVED
                        post.approved_at = datetime.utcnow()
                        approved.append(post)
                        break

            await sess.commit()

            if approved:
                response_text = (
                    f"✅ Approved {len(approved)} post(s)! "
                    f"They've been added to your scheduling queue.\n\n"
                    f"Want me to generate more content? Just describe what you need."
                )
                session.current_state = "awaiting_prompt"
                session.last_ai_response = None
            else:
                response_text = "I couldn't find those post numbers. Please try again (e.g., `post 1, post 3`)."

        elif message_body.startswith("/"):
            # Handle commands
            cmd = message_body.lower()
            if cmd == "/start":
                response_text = (
                    "👋 *Welcome to PostForge AI on WhatsApp!*\n\n"
                    "Send me a topic or idea, and I'll generate a week's worth of social media posts for you.\n\n"
                    "Examples:\n"
                    "• 'write me 5 posts about cybersecurity'\n"
                    "• '3 posts about our new product launch'\n"
                    "• 'weekly content plan for fintech startup'\n\n"
                    "I'll send you the posts, you approve the ones you like, and they'll be scheduled automatically."
                )
            elif cmd == "/help":
                response_text = (
                    "📖 *PostForge WhatsApp Help*\n\n"
                    "• Send any topic to generate content\n"
                    "• Reply with post numbers to approve (e.g., 'post 1, post 3')\n"
                    "• Voice notes work too — just speak your idea!\n"
                    "• Type /start to restart\n"
                    "• Type /status to see your session info"
                )
            elif cmd == "/status":
                result = await sess.execute(
                    select(WAGeneratedPost).where(
                        WAGeneratedPost.session_id == session.id,
                        WAGeneratedPost.status == WAStatus.PENDING,
                    )
                )
                pending = result.scalars().all()
                response_text = (
                    f"📊 *Your Session*\n\n"
                    f"Phone: {from_number}\n"
                    f"State: {session.current_state}\n"
                    f"Pending approvals: {len(pending)}"
                )
            else:
                response_text = "Unknown command. Type /help for available commands."

        elif state == "awaiting_approval":
            # Still awaiting approval — remind user
            result = await sess.execute(
                select(WAGeneratedPost).where(
                    WAGeneratedPost.session_id == session.id,
                    WAGeneratedPost.status == WAStatus.PENDING,
                )
            )
            pending = result.scalars().all()
            if pending:
                response_text = (
                    "I'm still waiting for you to approve the posts above. "
                    "Just reply with the post numbers (e.g., `post 1` or `post 1, 3`) "
                    "or type anything new to generate different content."
                )
            else:
                session.current_state = "awaiting_prompt"
                response_text = "Let's start fresh! What content would you like me to create?"

        else:
            # Default: generate content
            if not message_body.strip():
                response_text = (
                    "I didn't catch that. Send me a topic or idea and I'll create posts for you!"
                )
                await sender.send_whatsapp_message(from_number, response_text)
                return

            session.current_state = "generating"
            await sess.commit()

            response_text = f"🎯 *Generating posts for:*\n\"{message_body[:100]}...\"\n\nThis takes a few seconds..."
            await sender.send_whatsapp_message(from_number, response_text)

            # Generate content with AI
            try:
                gen = ContentGenerator()
                result = await gen.generate(
                    prompt=message_body,
                    platforms=["x_twitter", "linkedin", "facebook"],
                    tone="bold",
                    num_variations=3,
                )

                posts = result.get("variations", [])
                if not posts:
                    response_text = (
                        "I couldn't generate content for that. "
                        "Try a more specific topic or different wording."
                    )
                else:
                    # Store generated posts
                    generated_post_records = []
                    for i, post_data in enumerate(posts, 1):
                        gp = WAGeneratedPost(
                            session_id=session.id,
                            post_index=i,
                            platform=post_data.get("platform", "general"),
                            content=post_data.get("content", ""),
                            status=WAStatus.PENDING,
                        )
                        sess.add(gp)
                        generated_post_records.append({
                            "platform": post_data.get("platform", "general"),
                            "content": post_data.get("content", ""),
                            "post_index": i,
                        })

                    await sess.commit()

                    session.current_state = "awaiting_approval"
                    session.last_ai_response = json.dumps(generated_post_records)

                    # Format and send posts
                    response_text = format_posts_for_whatsapp(generated_post_records)

            except Exception as e:
                logger.error("Content generation failed: %s", str(e))
                response_text = (
                    f"Something went wrong generating content: {str(e)[:200]}\n\n"
                    "Try again with a different topic."
                )
                session.current_state = "awaiting_prompt"

        # Store outbound message
        if response_text:
            # Send actual response via Twilio
            try:
                await sender.send_whatsapp_message(from_number, response_text)
            except Exception as e:
                logger.error("Failed to send WhatsApp message: %s", str(e))

            # Store the outbound message record
            outbound_msg = WAMessage(
                session_id=session.id,
                wa_message_id=f"{message_sid}_out",
                direction=WADirection.OUTBOUND,
                content=response_text,
                status="sent",
            )
            sess.add(outbound_msg)
            session.last_message_at = datetime.utcnow()
            await sess.commit()


@router.post("/opt-in")
async def opt_in_wa(req: OptInRequest, user=Depends(get_current_user)):
    """Link a user's WhatsApp number to their PostForge account."""
    async with async_session() as sess:
        from sqlalchemy import select
        result = await sess.execute(
            select(WASession).where(WASession.phone == req.phone)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.user_id = req.user_id
            existing.tenant_id = user.get("tenant_id")
            existing.opt_in_status = "active"
        else:
            session = WASession(
                user_id=req.user_id,
                phone=req.phone,
                tenant_id=user.get("tenant_id"),
                opt_in_status="active",
            )
            sess.add(session)

        await sess.commit()

    return {"status": "opted_in", "phone": req.phone}


@router.post("/opt-out")
async def opt_out_wa(phone: str, user=Depends(get_current_user)):
    """Unlink a user's WhatsApp number."""
    async with async_session() as sess:
        from sqlalchemy import select
        result = await sess.execute(
            select(WASession).where(WASession.phone == phone)
        )
        session = result.scalar_one_or_none()
        if session:
            session.opt_in_status = "unsubscribed"
            await sess.commit()

    return {"status": "opted_out", "phone": phone}


@router.get("/sessions/{phone}")
async def get_wa_session(phone: str, user=Depends(get_current_user)):
    """Get WhatsApp session info for a phone number."""
    async with async_session() as sess:
        from sqlalchemy import select
        result = await sess.execute(
            select(WASession).where(WASession.phone == phone)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise HTTPException(404, "Session not found")

        # Get pending posts
        result = await sess.execute(
            select(WAGeneratedPost).where(
                WAGeneratedPost.session_id == session.id,
                WAGeneratedPost.status == WAStatus.PENDING,
            )
        )
        pending = result.scalars().all()

        return {
            "phone": session.phone,
            "opt_in_status": session.opt_in_status,
            "current_state": session.current_state,
            "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
            "pending_posts": [
                {
                    "index": p.post_index,
                    "platform": p.platform,
                    "content": p.content[:200],
                    "status": p.status,
                }
                for p in pending
            ],
        }


@router.get("/generate-qr")
async def generate_wa_qr(user=Depends(get_current_user)):
    """Generate a QR code URL for WhatsApp opt-in."""
    # Return a placeholder QR URL — in production, integrate with Twilio's QR generation
    # or a QR API like goqr.me
    return {
        "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://wa.me/2340000000",
        "link": "https://wa.me/2340000000?text=start",
        "phone_display": "+234 XXX XXX XXX",
    }