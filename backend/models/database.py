# © 2025 Mamu — All Rights Reserved
"""Database models for PostForge AI."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

ASYNC_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./postforge.db"
)

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


class PlanEnum(str, enum.Enum):
    FREE = "free"       # 30 posts/mo, 1 user, 2 platforms
    STARTER = "starter" # 150 posts/mo, 3 users, all platforms
    PRO = "pro"         # 750 posts/mo, 10 users, all platforms + analytics
    AGENCY = "agency"   # Unlimited, unlimited users, all platforms + white-label


class PlatformEnum(str, enum.Enum):
    FACEBOOK = "facebook"
    X_TWITTER = "x_twitter"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    LINKEDIN = "linkedin"


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    PUBLISHED = "published"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    plan = Column(Enum(PlanEnum), default=PlanEnum.FREE)
    max_users = Column(Integer, default=1)
    max_posts_per_month = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # OAuth credentials (encrypted at rest in production)
    oauth_credentials = Column(JSON, default={})

    users = relationship("User", back_populates="tenant")
    posts = relationship("Post", back_populates="tenant")
    connected_platforms = relationship("ConnectedPlatform", back_populates="tenant")
    subscriptions = relationship("Subscription", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="member")  # owner, admin, member
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")
    posts = relationship("Post", back_populates="author")


class ConnectedPlatform(Base):
    __tablename__ = "connected_platforms"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    platform = Column(Enum(PlatformEnum), nullable=False)
    account_name = Column(String(255))
    account_id = Column(String(255))  # Platform's native ID
    access_token_encrypted = Column(Text)  # Encrypted
    refresh_token_encrypted = Column(Text)
    token_expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="connected_platforms")
    posts = relationship("Post", back_populates="platform_account")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    platform_account_id = Column(Integer, ForeignKey("connected_platforms.id"), nullable=True)

    content = Column(Text, nullable=False)
    image_urls = Column(JSON, default=[])  # List of image URLs
    media_type = Column(String(50), default="text")  # text, image, video, carousel

    platform = Column(Enum(PlatformEnum), nullable=False)
    status = Column(Enum(PostStatus), default=PostStatus.DRAFT)

    # AI generation metadata
    ai_prompt = Column(Text)  # Original user prompt
    ai_model = Column(String(100))  # gpt-4o, claude-3.5-sonnet, etc.
    ai_variants = Column(JSON, default=[])  # AI-generated variations

    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # Platform-specific results
    platform_post_id = Column(String(255))  # ID assigned by the platform
    platform_url = Column(String(512))  # URL to the published post
    platform_response = Column(JSON)  # Raw API response from platform

    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="posts")
    author = relationship("User", back_populates="posts")
    platform_account = relationship("ConnectedPlatform", back_populates="posts")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255))
    plan = Column(Enum(PlanEnum), nullable=False)
    status = Column(String(50), default="active")  # active, cancelled, past_due
    current_period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="subscriptions")


class PostAnalytics(Base):
    __tablename__ = "post_analytics"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)

    impressions = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    clicks = Column(Integer, default=0)

    fetched_at = Column(DateTime, default=datetime.utcnow)
