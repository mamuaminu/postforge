# © 2025 Mamu — All Rights Reserved
"""
PostForge AI — Content Generation Service
Uses GPT-4o to generate platform-optimised social media content.
Generates multiple variations, adapts tone/hashtags per platform.
"""

import os
import json
import logging
from openai import AsyncOpenAI
from datetime import datetime
from typing import Optional

logger = logging.getLogger("postforge.ai")

# ─── Platform constraints ──────────────────────────────────────────────────────

PLATFORM_LIMITS = {
    "facebook":  {"max_chars": 63206, "max_images": 1, "hashtag_limit": 30},
    "x_twitter": {"max_chars": 280,   "max_images": 4, "hashtag_limit": 0},
    "instagram": {"max_chars": 2200,   "max_images": 1, "hashtag_limit": 30},
    "threads":   {"max_chars": 500,    "max_images": 1, "hashtag_limit": 30},
    "linkedin":  {"max_chars": 3000,   "max_images": 1, "hashtag_limit": 10},
}

# ─── Tone presets ──────────────────────────────────────────────────────────────

TONES = {
    "professional": "Authoritative, data-driven, thought leadership — suitable for LinkedIn",
    "casual":       "Conversational, friendly, relatable — suitable for Twitter/X and Threads",
    "bold":         "Punchy, provocative, high-energy — suitable for Instagram and X",
    "educational":  "Informative, helpful, tutorial-style — suitable for all platforms",
    "promotional":  "Sales-oriented, benefit-focused, CTA-driven — suitable for Facebook",
}

# ─── Main generator ────────────────────────────────────────────────────────────

class ContentGenerator:
    """
    Generates platform-optimised social media content using GPT-4o.
    Single prompt → multiple platform variants, optionally with variations.
    """

    SYSTEM_PROMPT = """You are a world-class social media copywriter for a SaaS brand called PostForge AI.
Generate platform-native social media posts that feel human-written, not AI-generated.
Every post should: hook the reader in the first line, provide real value or insight,
and end with a clear action or question that drives engagement.
Never use generic filler phrases. Never use excessive emojis. Write like a smart human."""


    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))


    async def generate(
        self,
        prompt: str,
        platforms: list[str],
        tone: str = "bold",
        num_variations: int = 2,
        include_hashtags: bool = True,
        brand_voice: str = "PostForge AI helps marketers and agencies save 10+ hours/week with AI-powered social media automation.",
    ) -> dict:
        """
        Generate content for multiple platforms from a single prompt.

        Returns:
            {
              "variations": [
                {"platform": "x_twitter", "content": "...", "hashtags": [...]},
                ...
              ],
              "best_for": {...}
            }
        """

        platform_specs = "\n".join(
            f"- {p}: max {PLATFORM_LIMITS[p]['max_chars']} chars, "
            f"{PLATFORM_LIMITS[p]['max_images']} image(s), "
            f"{TONES.get(tone, TONES['bold'])}"
            for p in platforms
        )

        variation_requests = "\n".join(
            f"[VARIATION {i+1}]" for i in range(num_variations)
        )

        user_prompt = f"""Brand voice: "{brand_voice}"

Generate {num_variations} variation(s) for each of these platforms:
{platform_specs}

User's content request: "{prompt}"

For each variation:
1. Follow the character limit for that platform
2. Adapt tone to match the platform's norms
3. Use 3-7 relevant hashtags (no #{'too'} many) unless the platform discourages them
4. Include a compelling hook in the first sentence
5. End with something that drives engagement (question, stat, or bold take)
{variation_requests}

Return your response as valid JSON with this exact structure:
{{
  "variations": [
    {{
      "platform": "x_twitter",
      "variation_id": 1,
      "content": "...",
      "hashtags": ["#tag1", "#tag2"],
      "hook_used": "...",
      "word_count": 45
    }}
  ]
}}
Only output JSON. No preamble, no explanation."""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.85,
                response_format={"type": "json_object"},
            )
            result_text = response.choices[0].message.content

            # Parse and validate
            parsed = json.loads(result_text)
            variations = parsed.get("variations", [])

            # Enforce platform character limits
            for v in variations:
                platform = v.get("platform", "")
                limit = PLATFORM_LIMITS.get(platform, {}).get("max_chars", 5000)
                if len(v.get("content", "")) > limit:
                    v["content"] = v["content"][:limit - 3] + "..."

            logger.info("Generated %d content variations for %s", len(variations), platforms)
            return {
                "variations": variations,
                "generated_at": datetime.utcnow().isoformat(),
                "model": "gpt-4o",
                "tokens_used": response.usage.total_tokens,
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON: %s", e)
            raise
        except Exception as e:
            logger.error("Content generation failed: %s", e)
            raise


    async def generate_thread(
        self,
        topic: str,
        num_slides: int = 5,
        brand_voice: str = None,
    ) -> dict:
        """Generate a Twitter/X thread on a topic."""
        voice = brand_voice or "PostForge AI: AI-powered social media automation for agencies"

        user_prompt = f"""Brand: "{voice}"

Generate a {num_slides}-slide Twitter/X thread on: "{topic}"

Rules:
- Slide 1: Hook — grab attention immediately (no "Tweet 1 of N" labels)
- Slides 2-{num_slides-1}: Build the argument or insight with real value
- Final slide: Strong CTA or question that drives replies
- Each slide: max 280 chars
- Use line breaks (\\n) between slides
- No emojis or very minimal (max 1-2 per slide)
- No hashtags in thread body (move to final slide if needed)

Return as JSON:
{{"slides": ["slide 1 content", "slide 2 content", ...]}}"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content)
            return {"slides": parsed.get("slides", []), "topic": topic}
        except Exception as e:
            logger.error("Thread generation failed: %s", e)
            raise
