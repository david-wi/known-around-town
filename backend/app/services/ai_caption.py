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

# WHY: Seven caption suggestions need substantially more room than the original
# single-caption response. 1100 tokens keeps the output bounded while leaving
# enough space for seven short 2-3 sentence options plus hashtags.
MAX_OUTPUT_TOKENS = 1100

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
    # WHY: state and market_label exist purely to DISAMBIGUATE the city name
    # for the model. Many US city names are shared across states ("Hollywood"
    # is in both FL and CA; the famous one is CA, so the model defaults an
    # un-anchored "Hollywood" to Los Angeles and writes "#LosAngelesHair" for
    # a salon that is actually in Hollywood, FL). Passing the state ("FL") and
    # a regional market label ("South Florida (Miami metro area)") pins the
    # location so the caption — and any #City hashtag — comes out right.
    #
    # WHY they default to None (and sit last): older call sites and tests build
    # this context positionally/by-keyword without these fields; defaulting
    # them keeps those working and degrades gracefully (no location anchor)
    # rather than crashing. The three production call sites always pass real
    # values via resolve_location().
    state: Optional[str] = None
    market_label: Optional[str] = None
    photo_url: Optional[str] = None


# WHY: This network is the South Florida / Miami-metro directory (every seeded
# city — Hollywood, Aventura, Doral, Boca Raton, etc. — is in that market). We
# use this as the default regional anchor when a city record has no usable
# market label of its own, so an ambiguous city name like "Hollywood" reads as
# the Florida one. It is deliberately a default, NOT hardcoded into the prompt:
# if a city or business ever carries a real state/market, that real value wins
# (see resolve_location), and only the *region* defaults here — never a state
# that contradicts the data.
DEFAULT_MARKET_LABEL = "South Florida (Miami metro area)"


def resolve_location(
    business: Optional[Dict[str, Any]],
    city: Optional[Dict[str, Any]],
) -> tuple[Optional[str], str]:
    """Resolve the (state, market_label) anchor for a business.

    Returns the two-letter state and a coarse market label to feed the
    caption/ad-copy prompt so an ambiguously-named city is unambiguous.

    State source order (most specific first):
      1. The business's own structured address ``state`` (the most precise —
         it's the salon's literal address). ``region`` is checked too because
         early seed scripts used that legacy key name for the same value.
      2. The city record's ``state`` (every seeded city carries this).

    Market label: the city record's own ``market_label`` if it ever has one,
    otherwise the network-wide South Florida default. We always return a
    market label (never None) so there's a regional anchor even when no state
    is present at all.
    """
    business = business or {}
    city = city or {}

    address = business.get("address") or {}
    # WHY: dual key-name check mirrors the rest of the codebase — the Address
    # model uses ``state`` but legacy seed data sometimes used ``region``.
    state = (
        address.get("state")
        or address.get("region")
        or city.get("state")
    )
    state = state.strip() if isinstance(state, str) and state.strip() else None

    market_label = city.get("market_label")
    if not (isinstance(market_label, str) and market_label.strip()):
        market_label = DEFAULT_MARKET_LABEL

    return state, market_label


# WHY: A short style note per category keeps the model on-brand for the
# vertical. The keys are matched against Business.category_slugs (the
# city-scoped slugs in `categories.slug`). Unknown categories fall back
# to a generic warm-and-professional default so the feature still works
# for newly-added verticals.
#
# WHY both production slugs AND legacy aliases are present: the live
# `categories.slug` values use slugs like "spa", "lash-brow", "waxing",
# and "skincare". An earlier version of this table was written against a
# different naming scheme ("skin", "lashes-brows") and had no entry for
# "spa"/"waxing" at all, so roughly a third of the real catalog silently
# fell through to DEFAULT_STYLE_NOTE and lost its category-specific voice.
# We now key on the real production slugs and KEEP the legacy aliases as
# synonyms so any city still on the old scheme (or any historical data)
# keeps working. Coverage is verified against live data by the unit test
# `test_style_note_covers_real_production_slugs`.
CATEGORY_STYLE_NOTES: Dict[str, str] = {
    # Beauty
    "hair": "warm, professional, beauty-focused; speak to clients seeking expert color and cut",
    "nails": "playful but polished; emphasize craftsmanship and self-care",
    "barber": "confident and grounded; speak to men who care about how they look",
    "makeup": "celebratory and confident; lean into transformation",
    "med-spa": "trustworthy and clinical; emphasize licensed providers and visible results",
    # Brows & lashes — production slug is "lash-brow"; "lashes-brows" is a legacy alias.
    "lash-brow": "intimate and editorial; emphasize precision and natural enhancement",
    "lashes-brows": "intimate and editorial; emphasize precision and natural enhancement",
    # Spa & body — high-volume production slugs that previously had no entry.
    "spa": "serene and restorative; emphasize escape, glow, and a true reset",
    "waxing": "friendly and reassuring; emphasize smooth results, comfort, and a quick, easy visit",
    # Skin — production slug is "skincare"; "skin" is a legacy alias.
    "skincare": "calm, expert, results-focused; speak to clients investing in their skin",
    "skin": "calm, expert, results-focused; speak to clients investing in their skin",
    "aesthetics": "polished and results-focused; emphasize subtle, natural-looking enhancement",
    # Wellness
    "yoga": "grounded and intentional; emphasize practice and community",
    # Production combines these as "yoga-meditation".
    "yoga-meditation": "grounded and contemplative; emphasize practice, stillness, and community",
    "pilates": "strong, focused, intentional; emphasize control and form",
    "massage": "restorative and quiet; emphasize relief and recovery",
    "meditation": "calm and contemplative; emphasize stillness and reset",
    "fitness": "energetic and motivating; emphasize progress and community",
    "holistic": "warm and whole-person; emphasize balance, natural care, and feeling your best",
    "iv-hydration": "refreshing and revitalizing; emphasize energy, recovery, and feeling restored",
    "recovery": "restorative and motivating; emphasize bouncing back and feeling renewed",
    "sleep-stress": "calm and reassuring; emphasize rest, relief, and a clearer mind",
    "longevity": "forward-looking and expert; emphasize investing in your long-term vitality",
    "nutrition": "supportive and practical; emphasize real, sustainable habits and feeling your best",
    "retreats": "immersive and restorative; emphasize unplugging, renewal, and time away to reset",
    # Health
    "primary-care": "trustworthy and clear; speak to patients seeking a reliable provider",
    "dental": "approachable and reassuring; emphasize care and comfort",
    "physical-therapy": "expert and recovery-focused; emphasize getting patients back to life",
    # Production slug is "pt-recovery".
    "pt-recovery": "expert and recovery-focused; emphasize getting patients back to doing what they love",
    "mental-health": "compassionate and confidential; emphasize support and progress",
    "fertility": "compassionate and hopeful; emphasize expert, personalized support on the journey",
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
        "Return EXACTLY 7 distinct caption suggestions, numbered 1 through 7. "
        "Each suggestion should be 2-3 sentences, then 4-8 relevant hashtags "
        "on a new line, then 1-3 tasteful emoji. No preamble, no quotation "
        "marks around the captions. Return ONLY the seven numbered suggestions "
        "because the owner will paste one directly into Instagram."
    )


def build_user_prompt(ctx: CaptionContext) -> str:
    """Build the user-content body sent to the gateway.

    Shared by BOTH the caption and the ad-copy generators, so the
    geographic disambiguation added here (state + market label) flows
    into both surfaces from one place.
    """
    location_bits = []
    if ctx.neighborhood_name:
        location_bits.append(ctx.neighborhood_name)
    # WHY: attach the state directly to the city ("Hollywood, FL") rather than
    # as a separate field, because that is the form humans — and the model —
    # use to disambiguate a shared city name. Without the state the model reads
    # "Hollywood" as Hollywood, CA (Los Angeles) and writes LA hashtags for a
    # South Florida salon.
    if ctx.city_name:
        if ctx.state:
            location_bits.append(f"{ctx.city_name}, {ctx.state}")
        else:
            location_bits.append(ctx.city_name)
    location = ", ".join(location_bits) or "their city"

    lines = [
        f"Business: {ctx.business_name}",
        f"Location: {location}",
    ]
    # WHY: the market label is a second, coarser anchor (the metro/region) that
    # reinforces the state. Even if a city name is unfamiliar to the model,
    # "South Florida (Miami metro area)" keeps the caption from drifting to a
    # similarly-named place in another part of the country.
    if ctx.market_label:
        lines.append(f"Market: {ctx.market_label}")
    if ctx.primary_category:
        lines.append(f"Category: {ctx.primary_category}")
    if ctx.known_for:
        lines.append(f"Known for: {ctx.known_for}")
    if ctx.short_description:
        lines.append(f"About: {ctx.short_description}")
    if ctx.photo_url:
        lines.append(f"Selected listing photo URL: {ctx.photo_url}")
    lines.append("")
    lines.append(f"Owner prompt: {ctx.prompt}")
    if ctx.photo_url:
        lines.append(
            "Photo guidance: Write for the selected listing photo and owner "
            "prompt, but do not invent visual details that are not in the "
            "owner prompt or listing context."
        )
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


async def call_gateway_text(
    *,
    use_case: str,
    system_prompt: str,
    user_content: str,
    max_tokens_override: int,
    cost_tags: Dict[str, Any],
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Call the centralized AI gateway and return its text payload.

    WHY: Known Around Town has more than one LLM-backed feature now. Public
    search and owner marketing copy both need the same gateway/key/error
    handling, but public search must not be tied to MARKETING_AI_ENABLED because
    that flag only controls owner-facing marketing tools.
    """
    key = _gateway_key()
    if not key:
        log.error("Neither KAT_AI_GATEWAY_KEY nor AI_GATEWAY_KEY is set; AI gateway call cannot proceed")
        raise CaptionGenerationError("gateway not configured")

    body: Dict[str, Any] = {
        "use_case": use_case,
        "system_prompt": system_prompt,
        "user_content": user_content,
        "max_tokens_override": max_tokens_override,
        "cost_tags": cost_tags,
    }
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json",
    }

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS)
    try:
        try:
            resp = await client.post(_gateway_url(), json=body, headers=headers)
        except httpx.RequestError as exc:
            log.warning("AI gateway unreachable: %s", exc)
            raise CaptionGenerationError("gateway unreachable") from exc

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
        log.warning("AI gateway returned HTTP %s: %s", status, raw_text_snippet)
        raise CaptionGenerationError(f"gateway returned HTTP {status}")

    if json_error is not None:
        log.warning("AI gateway returned non-JSON: %s", raw_text_snippet)
        raise CaptionGenerationError("gateway returned invalid JSON") from json_error
    assert json_data is not None

    text = (json_data.get("text") or "").strip()
    if not text:
        log.warning("AI gateway returned empty text: %s", json_data)
        raise CaptionGenerationError("gateway returned empty text")
    return text


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


# WHY: Ad copy uses a separate cost tag so gateway analytics can
# show Instagram caption spend vs ad copy spend independently.
COST_TAG_FEATURE_AD_COPY = "owners.ad_copy"

# WHY: 450 tokens is ~3x the minimum needed for 3 x (headline + description) to
# leave room for the model's natural phrasing and any leading/trailing whitespace
# the format requires. Keeps per-call cost bounded while preventing truncation.
MAX_OUTPUT_TOKENS_AD_COPY = 450

# WHY: Separate use case from marketing_caption so a future Admin AI Config update
# can tune the model, token budget, or temperature for ad copy independently.
# Currently points to the same use case as captions; register "marketing_ad_copy"
# in Admin AI Config to route ad copy requests to a dedicated configuration.
USE_CASE_AD_COPY = "marketing_caption"


def build_ad_copy_system_prompt(ctx: CaptionContext) -> str:
    """System prompt for the ad copy generator.

    Produces 3 short, punchy variations — each has a headline (under 30
    chars) and a single-sentence description (under 90 chars). The format
    is plain text so the dashboard can display it verbatim; the owner can
    pick the version they like and adapt it for Google, Facebook, or
    Instagram Ads.
    """
    style = style_note_for_category(ctx.primary_category)
    vertical = ctx.vertical_word or "local business"
    return (
        f"You write short ad copy for {vertical}s. "
        f"Tone: {style}. "
        "Return EXACTLY 3 variations. "
        "Each variation is on 2 lines: line 1 is a headline (under 30 characters), "
        "line 2 is a description (under 90 characters). "
        "Separate variations with a blank line. "
        "No labels, no numbering, no preamble — just the 3 variations."
    )


async def generate_ad_copy(
    ctx: CaptionContext,
    *,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Generate short ad copy variations via the centralized AI gateway.

    Returns 3 variations as raw text (headline on line 1, description on
    line 2, blank line between them). Raises the same exception classes
    as generate_caption so the route layer handles both the same way.
    """
    if not feature_enabled():
        raise CaptionFeatureDisabled("marketing AI is disabled in this environment")

    key = _gateway_key()
    if not key:
        log.error("Neither KAT_AI_GATEWAY_KEY nor AI_GATEWAY_KEY is set; ad copy generation cannot proceed")
        raise CaptionGenerationError("gateway not configured")

    body: Dict[str, Any] = {
        "use_case": USE_CASE_AD_COPY,
        "system_prompt": build_ad_copy_system_prompt(ctx),
        "user_content": build_user_prompt(ctx),
        "max_tokens_override": MAX_OUTPUT_TOKENS_AD_COPY,
        "cost_tags": {
            "product": COST_TAG_PRODUCT,
            "feature": COST_TAG_FEATURE_AD_COPY,
            "call": f"{COST_TAG_FEATURE_AD_COPY}.generate",
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
        log.warning("AI gateway returned HTTP %s: %s", status, raw_text_snippet)
        raise CaptionGenerationError(f"gateway returned HTTP {status}")

    if json_error is not None:
        log.warning("AI gateway returned non-JSON: %s", raw_text_snippet)
        raise CaptionGenerationError("gateway returned invalid JSON") from json_error
    assert json_data is not None  # WHY: status<400 and no json_error means we have data

    text = (json_data.get("text") or "").strip()
    if not text:
        log.warning("AI gateway returned empty ad copy text: %s", json_data)
        raise CaptionGenerationError("gateway returned empty ad copy")
    return text


# WHY: Profile descriptions need more room than a caption but must still stay
# bounded because owners are waiting in the dashboard and the text must fit the
# 1000-character public listing field.
MAX_OUTPUT_TOKENS_PROFILE_DESCRIPTION = 500

# WHY: Separate cost tag so gateway reports can distinguish profile-polishing
# calls from captions and ad-copy generation.
COST_TAG_FEATURE_PROFILE_DESCRIPTION = "owners.profile_description"


def build_profile_description_system_prompt(ctx: CaptionContext) -> str:
    """System prompt for the owner profile-description helper."""
    style = style_note_for_category(ctx.primary_category)
    vertical = ctx.vertical_word or "local business"
    return (
        f"You write polished public directory descriptions for {vertical}s. "
        f"Tone: {style}. "
        "Write one warm, specific paragraph, 80-140 words. "
        "Use only the details provided; do not invent awards, services, prices, "
        "staff names, locations, or guarantees. "
        "No headline, no bullet list, no quotation marks. Return ONLY the paragraph."
    )


async def generate_profile_description(
    ctx: CaptionContext,
    *,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Generate a polished listing description via the centralized AI gateway."""
    if not feature_enabled():
        raise CaptionFeatureDisabled("marketing AI is disabled in this environment")

    key = _gateway_key()
    if not key:
        log.error("Neither KAT_AI_GATEWAY_KEY nor AI_GATEWAY_KEY is set; profile description generation cannot proceed")
        raise CaptionGenerationError("gateway not configured")

    body: Dict[str, Any] = {
        "use_case": USE_CASE,
        "system_prompt": build_profile_description_system_prompt(ctx),
        "user_content": build_user_prompt(ctx),
        "max_tokens_override": MAX_OUTPUT_TOKENS_PROFILE_DESCRIPTION,
        "cost_tags": {
            "product": COST_TAG_PRODUCT,
            "feature": COST_TAG_FEATURE_PROFILE_DESCRIPTION,
            "call": f"{COST_TAG_FEATURE_PROFILE_DESCRIPTION}.generate",
        },
    }
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json",
    }

    own_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS)
    try:
        try:
            resp = await client.post(_gateway_url(), json=body, headers=headers)
        except httpx.RequestError as exc:
            log.warning("AI gateway unreachable: %s", exc)
            raise CaptionGenerationError("gateway unreachable") from exc

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
        log.warning("AI gateway returned HTTP %s: %s", status, raw_text_snippet)
        raise CaptionGenerationError(f"gateway returned HTTP {status}")

    if json_error is not None:
        log.warning("AI gateway returned non-JSON: %s", raw_text_snippet)
        raise CaptionGenerationError("gateway returned invalid JSON") from json_error
    assert json_data is not None  # WHY: status<400 and no json_error means we have data

    text = (json_data.get("text") or "").strip()
    if not text:
        log.warning("AI gateway returned empty profile description text: %s", json_data)
        raise CaptionGenerationError("gateway returned empty profile description")
    return text
