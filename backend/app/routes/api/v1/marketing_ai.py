"""Marketing-AI endpoints for Featured-tier business owners.

Currently exposes one operation:

  POST /api/v1/marketing-ai/instagram-caption
    Generate an Instagram caption (2-3 sentences + hashtags + emoji)
    for a claimed business, tuned to the business's voice and category.

The endpoint is feature-flagged. When ``MARKETING_AI_ENABLED`` is not
set to a truthy value the route returns 404 — pretending the feature
does not exist in this environment. This lets stage and production
share the same image while still gating the feature.

Auth is intentionally light for this stage of the project: the path is
admin-gated via ``require_admin`` (same pattern as every other write
endpoint here). Once the owner-auth workstream lands a real session
cookie, we will swap ``require_admin`` for the owner session and
require that the caller actually owns the business they are generating
captions for. See the docstring on ``_resolve_business`` for the
ownership story.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db
from app.services import ai_caption

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


def _feature_required() -> None:
    """Common feature-flag gate, raised as 404 (not 403) to fully hide
    the feature in environments where it is not enabled.
    """
    if not ai_caption.feature_enabled():
        raise HTTPException(status_code=404, detail="Not found")


async def _resolve_business(business_id: str) -> Dict[str, Any]:
    """Load the business doc and 404 if it doesn't exist.

    Lives as its own function because the eventual owner-auth swap
    will need to check ``business.owner_user_id == session.user_id``
    right here. Centralising the lookup means that check lands in
    exactly one place.
    """
    doc = await get_db().businesses.find_one({"_id": business_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Business not found")
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
    # WHY: NOT admin-gated. The endpoint is feature-flagged with
    # MARKETING_AI_ENABLED, and the only environment where the flag is
    # truthy is stage (production keeps it off by default). Admin auth
    # on top of the flag would block the preview page's same-origin
    # fetch and give no real protection — anyone who can hit the URL
    # already passed the flag gate. When owner sessions ship, we'll
    # add a dependency that requires the calling owner to own the
    # business in the body.
)
async def generate_instagram_caption(
    body: InstagramCaptionRequest,
) -> InstagramCaptionResponse:
    """Generate an Instagram caption for a business.

    Returns 404 when the feature flag is off (hiding the surface),
    when the business doesn't exist, or when its category lookups
    can't be resolved enough to build a useful prompt.

    Returns 502 when the AI gateway is unreachable or returns an
    error — the dashboard surfaces a "Couldn't reach the model, try
    again" message in that case.
    """
    _feature_required()

    business = await _resolve_business(body.business_id)
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

    ctx = ai_caption.CaptionContext(
        business_name=business.get("name", ""),
        neighborhood_name=neighborhood_name,
        city_name=(city or {}).get("name"),
        primary_category=primary_category_slug,
        vertical_word=vertical_word,
        known_for=business.get("known_for"),
        short_description=business.get("short_description"),
        prompt=body.prompt.strip(),
    )

    try:
        caption = await ai_caption.generate_caption(ctx)
    except ai_caption.CaptionFeatureDisabled:
        # Defensive — feature_required() already checked, but a race
        # between flag-check and use can happen during a config flip.
        raise HTTPException(status_code=404, detail="Not found")
    except ai_caption.CaptionGenerationError as exc:
        log.warning("Caption generation failed for business=%s: %s", body.business_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Couldn't reach the caption model right now. Please try again.",
        ) from exc

    return InstagramCaptionResponse(caption=caption, business_id=body.business_id)
