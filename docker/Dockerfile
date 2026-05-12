# PostForge AI
# Multi-tenant AI-powered social media automation platform
# © 2025 Mamu — All Rights Reserved

FROM python:3.12-slim

WORKDIR /app

# Install system deps for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]