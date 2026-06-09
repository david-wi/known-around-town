"""Instagram caption generation for Featured-tier business owners.

This module is the single integration point between Known Around Town and
the Expertly centralized LLM gateway. Everything else in the codebase
talks to *this* module; the gateway URL, auth header, and prompt shaping
all live here.

Why we use the gateway instead of a direct provider call:

  * Model choice, fallback order, and per-call cost limits are configured
    centrally in Admin AI Config under the ``marketing_caption`` use
    case. Changing the model later does NOT require a redeploy of this
    app — just an admin config update.
  * Per-tenant cost attribution (Known Around Town owners) is handled by
    the gateway via ``cost_tags``, which forwards them to the provider's
    metadata field.
  * If we ever want to switch from Claude Sonnet to a cheaper model for
    captions specifically, no code change here is needed.

Why this module exists as a thin wrapper rather than calling httpx from
the endpoint directly:

  * The endpoint stays focused on HTTP shape (body validation, status
    codes, feature flag).
  * Tests mock this single function instead of patching httpx globally.
  * Future enhancements (caching, rate limiting per business, persisting
    captions) live in one place.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger(__name__)

# WHY: Public AI Gateway URL is hardcoded because there is exactly one
# gateway across all Expertly environments (admin-api.ai.devintensive.com).
# Override via env for local development where staff might want to point
# at a fake responder during tests.
DEFAULT_GATEWAY_URL = "https://admin-api.ai.devintensive.com/api/public/ai-config/call"

# WHY: 30s is generous enough for the configured caption model to produce 2-3 sentences
# plus hashtags (typically completes in 3-8s) while still failing fast
# if the gateway is unreachable. The owner sits and watches the spinner,
# so anything longer feels broken.
DEFAULT_TIMEOUT_SECONDS = 30.0

# WHY: The use case is registered in Admin AI Config and owns the model,
# fallback sequence, and max_output_tokens (300). Changing this string
# would orphan the central config — keep them in lockstep.
USE_CASE = "marketing_caption"

# WHY: We send max_output_tokens=300 because the use case is already
# configured for that; sending the override makes the contract explicit
# in code review and survives a misconfiguration on the central side.
MAX_OUTPUT_TOKENS = 300

# WHY: Cost-tag product and feature so the central usage report can
# break out Known Around Town caption spend separately from other
# Expertly products. ``call`` is filled in per-request.
COST_TAG_PRODUCT = "known-around-town"
COST_TAG_FEATURE = "owners.instagram_caption"


class CaptionGenerationError(RuntimeError):
    """Raised when the gateway is unreachable or returns a non-2xx response.

    Wraps lower-level httpx/network exceptions so the HTTP route can
    translate this into a 502 without leaking internal detail.
    """


class CaptionFeatureDisabled(RuntimeError):
    """Raised when MARKETING_AI_ENABLED is not true.

    Distinct from CaptionGenerationError so the route can map it to a
    404 (feature does not exist for this environment) rather than 502.
    """


@dataclass(frozen=True)
class CaptionContext:
    """Inputs the LLM needs to produce a useful caption.

    Kept as a small dataclass instead of passing keyword arguments so
    the prompt-shaping logic can be unit-tested without an HTTP layer
    and so a future "preview the prompt" admin endpoint has a clean
    type to render.
    """

    business_name: str
    neighborhood_name: Optional[str]
    city_name: Optional[str]
    primary_category: Optional[str]
    vertical_word: Optional[str]
    known_for: Optional[str]
    short_description: Optional[str]
    prompt: str


# WHY: A short style note per category keeps the model on-brand for the
# vertical. The keys are matched against Business.category_slugs (the
# city-scoped slugs in `categories.slug`). Unknown categories fall back
# to a generic warm-and-professional default so the feature still works
# for newly-added verticals.
CATEGORY_STYLE_NOTES: Dict[str, str] = {
    # Beauty
    "hair": "warm, professional, beauty-focused; speak to clients seeking expert color and cut",
    "nails": "playful but polished; emphasize craftsmanship and self-care",
    "skin": "calm, expert, results-focused; speak to clients investing in their skin",
    "lashes-brows": "intimate and editorial; emphasize precision and natural enhancement",
    "barber": "confident and grounded; speak to men who care about how they look",
    "makeup": "celebratory and confident; lean into transformation",
    "med-spa": "trustworthy and clinical; emphasize licensed providers and visible results",
    # Wellness
    "yoga": "grounded and intentional; emphasize practice and community",
    "pilates": "strong, focused, intentional; emphasize control and form",
    "massage": "restorative and quiet; emphasize relief and recovery",
    "meditation": "calm and contemplative; emphasize stillness and reset",
    "fitness": "energetic and motivating; emphasize progress and community",
    # Health
    "primary-care": "trustworthy and clear; speak to patients seeking a reliable provider",
    "dental": "approachable and reassuring; emphasize care and comfort",
    "physical-therapy": "expert and recovery-focused; emphasize getting patients back to life",
    "mental-health": "compassionate and confidential; emphasize support and progress",
}

# WHY: Generic default used when the business's primary category isn't
# in the table above. Better than no guidance at all — the model still
# gets a clear tone hint.
DEFAULT_STYLE_NOTE = "warm, professional, and locally proud; speak to people in the neighborhood"


def style_note_for_category(category_slug: Optional[str]) -> str:
    """Return the style note for a category slug.

    Pure function — kept separate from prompt building so tests can
    pin the exact mapping for every vertical the seed data uses.
    """
    if not category_slug:
        return DEFAULT_STYLE_NOTE
    return CATEGORY_STYLE_NOTES.get(category_slug, DEFAULT_STYLE_NOTE)


def build_system_prompt(ctx: CaptionContext) -> str:
    """Build the system prompt sent to the gateway.

    Public so tests can lock in the exact string and so an admin
    "preview prompt" surface can render it later.
    """
    style = style_note_for_category(ctx.primary_category)
    vertical = ctx.vertical_word or "local business"
    return (
        "You write short Instagram captions for "
        f"{vertical}s in their actual neighborhood voice. "
        f"Tone: {style}. "
        "Keep it to 2-3 sentences, then 4-8 relevant hashtags on a new "
        "line, then 1-3 tasteful emoji. No preamble, no quotation marks "
        "around the caption. Return ONLY the caption text — the owner "
        "will paste it directly into Instagram."
    )


def build_user_prompt(ctx: CaptionContext) -> str:
    """Build the user-content body sent to the gateway."""
    location_bits = []
    if ctx.neighborhood_name:
        location_bits.append(ctx.neighborhood_name)
    if ctx.city_name:
        location_bits.append(ctx.city_name)
    location = ", ".join(location_bits) or "their city"

    lines = [
        f"Business: {ctx.business_name}",
        f"Location: {location}",
    ]
    if ctx.primary_category:
        lines.append(f"Category: {ctx.primary_category}")
    if ctx.known_for:
        lines.append(f"Known for: {ctx.known_for}")
    if ctx.short_description:
        lines.append(f"About: {ctx.short_description}")
    lines.append("")
    lines.append(f"Owner prompt: {ctx.prompt}")
    return "\n".join(lines)


def _gateway_url() -> str:
    return os.environ.get("AI_GATEWAY_URL", DEFAULT_GATEWAY_URL)


def _gateway_key() -> Optional[str]:
    """Read the gateway API key from env.

    Returns None when unset so the route layer can distinguish
    misconfiguration from an actual model failure.

    WHY: Checks KAT_AI_GATEWAY_KEY first (the app-scoped name used in
    the server's .env to avoid collisions with other Expertly apps on
    the same host), then falls back to the generic AI_GATEWAY_KEY so
    both naming conventions work.
    """
    return os.environ.get("KAT_AI_GATEWAY_KEY") or os.environ.get("AI_GATEWAY_KEY")


def feature_enabled() -> bool:
    """Return True when MARKETING_AI_ENABLED is set to a truthy string.

    WHY: Feature flag lives in env (not in Mongo) so the production and
    stage environments diverge cleanly without a config record to keep
    in sync. Stage sets it to "true"; production keeps it absent by
    default until we're ready to ship.
    """
    raw = os.environ.get("MARKETING_AI_ENABLED", "").strip().lower()
    # WHY: Accept "1" and "yes" too because deploy scripts and humans
    # both write env files; being strict about only "true" creates a
    # silly failure mode at 2am.
    return raw in {"true", "1", "yes", "on"}


async def generate_caption(
    ctx: CaptionContext,
    *,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Generate an Instagram caption via the centralized AI gateway.

    Args:
      ctx: Business context + owner's free-text prompt.
      http_client: Optional injected httpx client (tests use this to
        avoid touching the network).

    Returns:
      The generated caption text, stripped of leading/trailing
      whitespace. Always non-empty on success.

    Raises:
      CaptionFeatureDisabled: When MARKETING_AI_ENABLED is not truthy.
      CaptionGenerationError: When the gateway is unreachable, returns
        a non-2xx response, or returns an empty caption.
    """
    if not feature_enabled():
        raise CaptionFeatureDisabled("marketing AI is disabled in this environment")

    key = _gateway_key()
    if not key:
        # WHY: This is operator misconfiguration, not user error.
        # Surface clearly so an SRE sees it in logs immediately.
        log.error("Neither KAT_AI_GATEWAY_KEY nor AI_GATEWAY_KEY is set; caption generation cannot proceed")
        raise CaptionGenerationError("gateway not configured")

    body: Dict[str, Any] = {
        "use_case": USE_CASE,
        "system_prompt": build_system_prompt(ctx),
        "user_content": build_user_prompt(ctx),
        "max_tokens_override": MAX_OUTPUT_TOKENS,
        "cost_tags": {
            "product": COST_TAG_PRODUCT,
            "feature": COST_TAG_FEATURE,
            "call": f"{COST_TAG_FEATURE}.generate",
        },
    }
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json",
    }

    # WHY: When the caller didn't inject a client (production path),
    # we own the lifecycle and must close it. When the caller passed
    # one (test path), they manage it. Using a sentinel keeps both
    # paths in one block instead of duplicating the POST logic.
    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS)
    try:
        try:
            resp = await client.post(_gateway_url(), json=body, headers=headers)
        except httpx.RequestError as exc:
            log.warning("AI gateway unreachable: %s", exc)
            raise CaptionGenerationError("gateway unreachable") from exc

        # WHY: Buffer .text and .json now (while client is still open)
        # so the close in `finally` cannot race with response reads.
        status = resp.status_code
        raw_text_snippet = resp.text[:500]
        json_data: Optional[Dict[str, Any]] = None
        json_error: Optional[Exception] = None
        if status < 400:
            try:
                json_data = resp.json()
            except ValueError as exc:
                json_error = exc
                raw_text_snippet = resp.text[:500]
    finally:
        if own_client:
            await client.aclose()

    if status >= 400:
        # WHY: Log the full body server-side (helpful for ops) but never
        # leak the gateway's internal message to the owner; the route
        # turns CaptionGenerationError into a generic 502.
        log.warning("AI gateway returned HTTP %s: %s", status, raw_text_snippet)
        raise CaptionGenerationError(f"gateway returned HTTP {status}")

    if json_error is not None:
        log.warning("AI gateway returned non-JSON: %s", raw_text_snippet)
        raise CaptionGenerationError("gateway returned invalid JSON") from json_error
    assert json_data is not None  # WHY: status<400 and no json_error means we have data

    text = (json_data.get("text") or "").strip()
    if not text:
        log.warning("AI gateway returned empty caption text: %s", json_data)
        raise CaptionGenerationError("gateway returned empty caption")
    return text
