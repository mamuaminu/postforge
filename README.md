# PostForge AI — Social Media Agent

> Multi-tenant AI-powered social media automation SaaS. One prompt → platform-optimised content across X, Facebook, Instagram, Threads, and LinkedIn.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python: 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-06b6d4.svg)

---

## 🚀 What this is

PostForge AI is a portfolio project demonstrating a production-grade multi-tenant SaaS for social media automation. It shows:

- **AI content generation** via GPT-4o with platform-native variants (X: 280 chars, LinkedIn: 3000 chars, etc.)
- **Real OAuth 2.0 integrations** with Facebook (Graph API), X (v2 API), Instagram (Graph API), Threads, and LinkedIn (v2 API)
- **Multi-tenant architecture** with workspaces, role-based access, and subscription billing
- **Async FastAPI backend** with SQLite + aiosqlite, Redis queuing, and Celery workers
- **n8n workflow automation** wired up end-to-end
- **Scheduling and publishing** pipeline with retry logic

---

## 📁 Project structure

```
postforge/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── requirements.txt
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py          # SQLAlchemy async models (Tenant, User, Post, etc.)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # JWT signup/login
│   │   ├── posts.py             # Post CRUD + AI generation
│   │   ├── platforms.py         # OAuth flows + platform connections
│   │   ├── users.py             # Workspace management
│   │   ├── billing.py           # Stripe subscription
│   │   └── webhooks.py          # Stripe + n8n callbacks
│   └── services/
│       ├── __init__.py
│       ├── ai_generator.py      # GPT-4o content generation
│       ├── social_publisher.py   # Platform adapter classes
│       └── redis.py             # Redis client
├── n8n-workflows/
│   └── content-automation.json  # n8n workflow for content routing + notifications
├── frontend/
│   └── index.html               # Landing page (static HTML)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🧠 Architecture

```
User → FastAPI (auth, posts, platforms)
         ├── AI Generator (OpenAI GPT-4o)
         │     └── Returns platform-specific content variants
         ├── Platform Publishers (Facebook, X, Instagram, Threads, LinkedIn)
         │     └── OAuth → Publish → Store post_id
         ├── SQLite (async) — tenants, users, posts, platforms
         ├── Redis — job queue, rate limiting
         └── Celery worker — background publishing jobs

n8n workflow:
  Webhook (content generated) → Route by platform → Log to Sheets / Push to Redis → Notify Telegram
```

---

## 🔑 Key endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/signup` | Create tenant + user |
| `POST` | `/api/v1/auth/login` | JWT login |
| `POST` | `/api/v1/posts/generate` | Generate AI content for platforms |
| `POST` | `/api/v1/posts/thread/generate` | Generate X/Twitter thread |
| `POST` | `/api/v1/posts/{platform}` | Create + publish/schedule a post |
| `GET`  | `/api/v1/posts/` | List posts with filters |
| `GET`  | `/api/v1/platforms/connect/{platform}/url` | Get OAuth URL |
| `POST` | `/api/v1/platforms/connect/{platform}` | Complete OAuth + store token |
| `GET`  | `/api/v1/platforms/` | List connected platforms |

---

## 🔌 Platform adapters

Each social network has a dedicated adapter class in `services/social_publisher.py`:

| Platform | Adapter | API |
|----------|---------|-----|
| Facebook | `FacebookAdapter` | Meta Graph API v19.0 |
| X / Twitter | `XTwitterAdapter` | X API v2 |
| Instagram | `InstagramAdapter` | Meta Graph API (IG Business) |
| Threads | `ThreadsAdapter` | Meta Graph API |
| LinkedIn | `LinkedInAdapter` | LinkedIn v2 REST |

All adapters implement:
- `publish(content, image_urls, scheduled_at)` → `{"platform_post_id", "post_url", "success"}`
- `get_post(post_id)` → full post data + metrics
- `delete_post(post_id)` → boolean
- `refresh_token_if_needed()` → new access token

---

## 🗄️ Database schema

```
tenants ──────────┐
  │               │
users ◄───────────┤
  │               │
posts ◄───────────┤
  │               │
connected_platforms ◄───────┘
  │
subscriptions

post_analytics (per-post metrics)
```

Core models in `backend/models/database.py`:
- **Tenant** — workspace with plan limits (posts/mo, users, platforms)
- **User** — email, hashed password, role (owner/admin/member)
- **Post** — content, platform, status (draft/queued/published/failed/scheduled), AI metadata, scheduling
- **ConnectedPlatform** — OAuth tokens, account ID, active status
- **Subscription** — Stripe customer + plan tracking
- **PostAnalytics** — impressions, reach, likes, comments, shares, clicks

---

## 🧪 Quick start

### Prerequisites
- Python 3.12+
- Redis (optional, for queue)
- API keys: OpenAI, Meta, X, LinkedIn

```bash
# 1. Clone
git clone https://github.com/mamuaminu/postforge.git
cd postforge

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Environment variables
cp .env.example .env
# Fill in your API keys

# 5. Run
uvicorn backend.main:app --reload --port 8000

# API docs: http://localhost:8000/docs
```

### Docker

```bash
cd docker
docker-compose up --build
```

---

## 🔐 Environment variables

```env
# Required
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite+aiosqlite:///./postforge.db

# JWT
JWT_SECRET=change-me-in-production

# Redis
REDIS_URL=redis://localhost:6379/0

# Meta (Facebook + Instagram + Threads)
META_APP_ID=...
META_APP_SECRET=...

# X / Twitter
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_BEARER_TOKEN=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...

# LinkedIn
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...

# Stripe (optional, for billing)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 📊 AI content generation

`POST /api/v1/posts/generate` accepts:

```json
{
  "prompt": "Launching our new AI analytics dashboard — highlight time saved and ROI",
  "platforms": ["x_twitter", "linkedin", "instagram"],
  "tone": "bold",
  "num_variations": 2,
  "include_hashtags": true
}
```

Returns platform-specific variants with character counts, hashtags, and hook text:

```json
{
  "variations": [
    {
      "platform": "x_twitter",
      "content": "We just cut reporting time from 4 hours → 20 minutes...",
      "hashtags": ["#AI", "#Analytics"],
      "hook_used": "We just cut reporting time from 4 hours → 20 minutes.",
      "word_count": 38
    }
  ],
  "generated_at": "2025-04-19T17:00:00Z",
  "tokens_used": 1847,
  "model": "gpt-4o"
}
```

---

## 🌐 n8n workflow

Import `n8n-workflows/content-automation.json` into your n8n instance.

Flow:
1. **Webhook trigger** — fires when `POST /api/v1/posts/generate` completes
2. **Route by Platform** — splits content to per-platform queues
3. **Log to Google Sheets** — track all generated content
4. **Push to Redis** — enqueue for background publishing
5. **Notify Telegram** — alert the user when content is ready

---

## 📝 Post statuses

| Status | Meaning |
|--------|---------|
| `draft` | Created but not yet queued |
| `queued` | In the publishing queue |
| `scheduled` | Waiting for `scheduled_at` timestamp |
| `published` | Successfully posted to platform |
| `failed` | Platform API error (logged with `error_message`) |

Retry logic: failed posts retry up to 3 times with exponential backoff.

---

## 💳 Plans & rate limits

| Plan | Posts/mo | Users | Platforms | Price |
|------|----------|-------|-----------|-------|
| Free | 30 | 1 | 2 | $0 |
| Starter | 150 | 3 | 5 | $29 |
| Pro | 750 | 10 | 5 | $99 |
| Agency | Unlimited | Unlimited | 5 | $299 |

Monthly post counts are enforced at the router layer (`posts.py`).

---

## 🔒 Security notes

- Passwords hashed with **bcrypt** via `passlib`
- JWT tokens expire after **24 hours**
- OAuth tokens stored encrypted (use envelope encryption in production)
- All routes except `/health` require authentication
- CORS restricted to known origins
- Rate limiting via `slowapi` (100 req/min per IP)

---

## 🛠️ Extending

**Add a new platform**: implement `PlatformAdapter` in `services/social_publisher.py`, add to `get_platform_adapter()` factory.

**Add a new AI model**: swap `model="gpt-4o"` in `services/ai_generator.py` — no other changes needed.

**Add webhook events**: add route in `routers/webhooks.py`, handle in n8n workflow.

---

## 👤 Author

Muhammad Aminu Musa — [mamuaminu.github.io/portfolio](https://mamuaminu.github.io/portfolio)
<br />© 2025 — All Rights Reserved