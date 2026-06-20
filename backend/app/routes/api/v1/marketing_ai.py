"""Marketing-AI endpoints for Featured-tier business owners.

Currently exposes two operations:

  POST /api/v1/marketing-ai/instagram-caption
    Generate an Instagram caption (2-3 sentences + hashtags + emoji)
    for a claimed business, tuned to the business's voice and category.

  POST /api/v1/marketing-ai/ad-copy
    Generate 3 short ad copy variations (headline + description each)
    ready to paste into Google Ads, Facebook, or Instagram Ads.

Auth requirements (owner sessions are live):
- Caller must present a valid ``kb_owner_session`` cookie (401 if missing
  or invalid).
- The session's ``business_id`` must match the ``business_id`` in the
  request body (403 if mismatched — prevents one owner generating content
  for another owner's business).
- The business must have an active Featured subscription, indicated by the
  presence of ``stripe_subscription_id`` on the business document (402 if
  not subscribed — the dashboard shows an upgrade prompt on 402).

Feature flag: when the feature is disabled the routes return 404, hiding
the feature entirely. The flag is read from the ``site_settings`` MongoDB
collection (set via the admin settings web page), falling back to the
``MARKETING_AI_ENABLED`` env var so behaviour is unchanged before the
admin page is first used.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.database import get_db
from app.services import ai_caption
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session
from app.services.site_settings import get_marketing_ai_enabled

log = logging.getLogger(__name__)

router = APIRouter(prefix="/marketing-ai", tags=["marketing-ai"])


class InstagramCaptionRequest(BaseModel):
    """Input shape for the caption endpoint.

    business_id is required so the model gets accurate context. The
    free-text ``prompt`` is what the owner actually typed (e.g.
    ``fall hair color promo``).
    """

    business_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The _id of the business the owner is generating a caption for.",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        # WHY: 600 chars is plenty for an owner to describe the post
        # (a promo, a new service, a holiday hours change) without
        # letting an attacker stuff the prompt with thousands of
        # tokens of cost.
        max_length=600,
        description="The owner's free-text description of what the post is about.",
    )


class InstagramCaptionResponse(BaseModel):
    """Caption returned to the dashboard panel."""

    caption: str
    # WHY: Echo the business id so a future client that fires multiple
    # requests in parallel can correlate responses. Cheap to add now,
    # expensive to retrofit later.
    business_id: str


async def _feature_required() -> None:
    """Common feature-flag gate, raised as 404 (not 403) to fully hide
    the feature in environments where it is not enabled.

    WHY: async so it can query the site_settings collection, which lets
    the admin web page toggle the flag without a server restart. Falls back
    to the MARKETING_AI_ENABLED env var when no DB value has been set.
    """
    if not await get_marketing_ai_enabled():
        raise HTTPException(status_code=404, detail="Not found")


async def _require_pro_owner(request: Request, business_id: str) -> Dict[str, Any]:
    """Authenticate the request and verify the caller is a Featured subscriber.

    Raises:
        401 -- no valid owner session cookie
        403 -- the authenticated owner's business does not match business_id
        404 -- the business doesn't exist in the database
        402 -- the business exists and is owned by the caller but has no active
               Featured subscription (stripe_subscription_id is absent)

    WHY: centralised so both caption and ad-copy endpoints share identical
    auth logic without duplication. Any future Marketing-AI endpoint should
    call this helper rather than re-implementing the checks.

    Auth design: owner sessions store the owner's email (not business_id).
    The canonical ownership link is business.claimed_email == session.email,
    mirroring the pattern in owner_profile.py. We verify ownership by loading
    the business by id and comparing claimed_email to the session email, rather
    than looking up by email and accepting whatever business comes back -- this
    prevents a session from generating content for a business whose claimed_email
    changed after the session was issued.
    """
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    session = verify_session(cookie_value) if cookie_value else None
    if not session:
        raise HTTPException(status_code=401, detail="Owner session required")

    # WHY: Businesses created before the UUID migration have ObjectId _id values.
    # The template serialises _id via str(), so the request body always contains
    # the string representation. We try ObjectId first (24-hex-char string), then
    # fall back to the raw string for UUID-keyed businesses.
    try:
        id_query: Union[ObjectId, str] = ObjectId(business_id)
    except (InvalidId, TypeError):
        id_query = business_id

    doc = await get_db().businesses.find_one({"_id": id_query})
    if not doc:
        raise HTTPException(status_code=404, detail="Business not found")

    # WHY: compare the business's claimed_email to the session email rather than
    # trusting a business_id in the cookie. Owner sessions only embed the email;
    # business_id is provided by the caller, so we must verify the two agree via
    # the database's claimed_email field.
    session_email = session.get("email", "").lower()
    if doc.get("claimed_email", "").lower() != session_email:
        raise HTTPException(status_code=403, detail="Not your business")

    # WHY: stripe_subscription_id is written by the Stripe webhook on successful
    # payment and cleared on cancellation -- it's the authoritative subscription
    # signal, more reliable than featured.tier which can be set manually by admins.
    if not doc.get("stripe_subscription_id"):
        raise HTTPException(
            status_code=402,
            detail="Featured subscription required to use AI tools",
        )

    return doc


async def _resolve_neighborhood_name(
    city_id: str, neighborhood_slugs: Optional[list]
) -> Optional[str]:
    """Return the neighborhood's display name for the prompt.

    Picks the first slug in the list (the primary neighborhood) since
    Instagram captions reference a single location. Returns None if
    the slug list is empty or the lookup fails.
    """
    if not neighborhood_slugs:
        return None
    primary_slug = neighborhood_slugs[0]
    doc = await get_db().neighborhoods.find_one(
        {"city_id": city_id, "slug": primary_slug}
    )
    if doc:
        return doc.get("name")
    return None


async def _resolve_city(city_id: str) -> Optional[Dict[str, Any]]:
    return await get_db().cities.find_one({"_id": city_id})


@router.post(
    "/instagram-caption",
    response_model=InstagramCaptionResponse,
    # WHY: no FastAPI Depends() for auth -- we call _require_pro_owner() inline
    # so the 404 feature-flag check always fires first, avoiding information
    # disclosure about whether the endpoint exists in this environment.
)
async def generate_instagram_caption(
    request: Request,
    body: InstagramCaptionRequest,
) -> InstagramCaptionResponse:
    """Generate an Instagram caption for a business.

    Returns 401 when the caller has no valid owner session.
    Returns 402 when the owner's business has no Featured subscription.
    Returns 403 when the session belongs to a different business.
    Returns 404 when the feature flag is off or the business doesn't exist.
    Returns 502 when the AI gateway is unreachable.
    """
    await _feature_required()

    business = await _require_pro_owner(request, body.business_id)
    city_id = business.get("city_id")
    if not city_id:
        # Shouldn't happen for real seeded data; defend against partial records.
        raise HTTPException(status_code=409, detail="Business has no city")

    city = await _resolve_city(city_id)

    primary_category_slug = (business.get("category_slugs") or [None])[0]
    neighborhood_name = await _resolve_neighborhood_name(
        city_id, business.get("neighborhood_slugs")
    )

    # WHY: listing_word_singular lives on the city record and is what
    # the brand calls its businesses ("salon" for Beauty, "studio" for
    # Wellness, "clinic" for Health). It's the right hint for the model.
    # Falls through to None if the city record predates the field, in
    # which case the prompt builder uses "local business".
    vertical_word = (city or {}).get("listing_word_singular")

    # WHY: pass the state + regional market so an ambiguously-named city
    # (e.g. "Hollywood", which the model otherwise reads as Hollywood, CA)
    # is pinned to South Florida and the caption/hashtags come out right.
    state, market_label = ai_caption.resolve_location(business, city)

    ctx = ai_caption.CaptionContext(
        business_name=business.get("name", ""),
        neighborhood_name=neighborhood_name,
        city_name=(city or {}).get("name"),
        state=state,
        market_label=market_label,
        primary_category=primary_category_slug,
        vertical_word=vertical_word,
        known_for=business.get("known_for"),
        short_description=business.get("short_description"),
        prompt=body.prompt.strip(),
    )

    try:
        caption = await ai_caption.generate_caption(ctx)
    except ai_caption.CaptionFeatureDisabled:
        # Defensive -- feature_required() already checked, but a race
        # between flag-check and use can happen during a config flip.
        raise HTTPException(status_code=404, detail="Not found")
    except ai_caption.CaptionGenerationError as exc:
        log.warning("Caption generation failed for business=%s: %s", body.business_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Couldn't reach the caption model right now. Please try again.",
        ) from exc

    return InstagramCaptionResponse(caption=caption, business_id=body.business_id)


class AdCopyRequest(BaseModel):
    """Input shape for the ad copy endpoint.

    Mirrors InstagramCaptionRequest -- same business_id + free-text prompt
    pattern. The prompt here describes what the owner wants to promote
    (e.g. "summer specials, 20% off color services through July").
    """

    business_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The _id of the business the owner is generating ad copy for.",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        # WHY: Same 600-char cap as captions -- enough for a promo description
        # without letting the prompt balloon into a token-cost attack.
        max_length=600,
        description="What the owner wants to advertise.",
    )


class AdCopyResponse(BaseModel):
    """Ad copy variations returned to the dashboard panel.

    ``ad_copy`` is the raw text returned by the model: 3 variations,
    each with a headline on line 1 and a description on line 2,
    separated by blank lines. The dashboard displays this verbatim.
    """

    # WHY: Named "ad_copy" not "copy" -- "copy" shadows BaseModel.copy(), a
    # Pydantic method, which causes UserWarning and subtle behaviour in v2.
    ad_copy: str
    business_id: str


@router.post(
    "/ad-copy",
    response_model=AdCopyResponse,
    # WHY: same auth-inline pattern as /instagram-caption -- feature flag
    # check fires before session/subscription checks to avoid disclosure.
)
async def generate_ad_copy(
    request: Request,
    body: AdCopyRequest,
) -> AdCopyResponse:
    """Generate 3 short ad copy variations for a business.

    Each variation includes a headline (under 30 chars) and a description
    (under 90 chars) -- ready to paste into Google Ads, Facebook, or
    Instagram Ads.

    Returns 401 when the caller has no valid owner session.
    Returns 402 when the owner's business has no Featured subscription.
    Returns 403 when the session belongs to a different business.
    Returns 404 when the feature flag is off or the business doesn't exist.
    Returns 502 when the AI gateway is unreachable.
    """
    await _feature_required()

    business = await _require_pro_owner(request, body.business_id)
    city_id = business.get("city_id")
    if not city_id:
        raise HTTPException(status_code=409, detail="Business has no city")

    city = await _resolve_city(city_id)
    primary_category_slug = (business.get("category_slugs") or [None])[0]
    neighborhood_name = await _resolve_neighborhood_name(
        city_id, business.get("neighborhood_slugs")
    )
    vertical_word = (city or {}).get("listing_word_singular")

    # WHY: same geographic disambiguation as the caption endpoint — ad copy
    # shares the location context so it never drifts to the wrong metro.
    state, market_label = ai_caption.resolve_location(business, city)

    ctx = ai_caption.CaptionContext(
        business_name=business.get("name", ""),
        neighborhood_name=neighborhood_name,
        city_name=(city or {}).get("name"),
        state=state,
        market_label=market_label,
        primary_category=primary_category_slug,
        vertical_word=vertical_word,
        known_for=business.get("known_for"),
        short_description=business.get("short_description"),
        prompt=body.prompt.strip(),
    )

    try:
        copy = await ai_caption.generate_ad_copy(ctx)
    except ai_caption.CaptionFeatureDisabled:
        raise HTTPException(status_code=404, detail="Not found")
    except ai_caption.CaptionGenerationError as exc:
        log.warning("Ad copy generation failed for business=%s: %s", body.business_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Couldn't reach the model right now. Please try again.",
        ) from exc

    return AdCopyResponse(ad_copy=copy, business_id=body.business_id)
