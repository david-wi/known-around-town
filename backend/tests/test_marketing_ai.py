"""Tests for the Featured-tier Instagram caption generator.

Covers:

* Unit-level tests for the service helpers (style note mapping, prompt
  building, feature flag parsing) — pure functions, no I/O.
* Endpoint tests with the LLM gateway mocked via injected httpx client
  — exercises the FastAPI route, validation, and error mapping.
* Optional integration test that hits the real LLM via the gateway,
  gated by env so CI doesn't spend tokens. Set
  ``KAT_INSTAGRAM_CAPTION_LIVE=1`` to run it locally.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

import httpx
import pytest
from fastapi.testclient import TestClient


# --- Unit tests for the service module (pure helpers) ---


def test_style_note_known_category():
    from app.services.ai_caption import style_note_for_category

    note = style_note_for_category("hair")
    assert "hair" in note.lower() or "beauty" in note.lower()


def test_style_note_covers_real_production_slugs():
    """Every category slug used by live businesses must get a tailored voice.

    WHY: the per-category style note is keyed on Business.category_slugs.
    An earlier version of the table used a different naming scheme
    ("skin", "lashes-brows") and had no entry for "spa"/"waxing", so ~32%
    of the live catalog silently fell through to DEFAULT_STYLE_NOTE and
    lost its category-specific voice. This test pins the real production
    slugs so a future rename can't quietly regress coverage again.

    The list is the set of distinct primary-category slugs observed on
    live businesses in production as of 2026-06-20. If a NEW vertical is
    added to the seed data, add its slug both here and in
    CATEGORY_STYLE_NOTES.
    """
    from app.services.ai_caption import (
        DEFAULT_STYLE_NOTE,
        style_note_for_category,
    )

    production_primary_slugs = [
        "hair", "nails", "spa", "lash-brow", "barber", "waxing", "med-spa",
        "makeup", "skincare", "primary-care", "massage", "pt-recovery",
        "dental", "yoga-meditation", "recovery", "aesthetics", "holistic",
        "iv-hydration", "sleep-stress", "longevity", "retreats", "fertility",
        "nutrition",
    ]
    missing = [
        slug
        for slug in production_primary_slugs
        if style_note_for_category(slug) == DEFAULT_STYLE_NOTE
    ]
    assert not missing, (
        f"These live category slugs fall back to the generic voice "
        f"instead of a tailored one: {missing}. Add them to "
        f"CATEGORY_STYLE_NOTES in ai_caption.py."
    )


def test_style_note_unknown_category_falls_back():
    from app.services.ai_caption import (
        DEFAULT_STYLE_NOTE,
        style_note_for_category,
    )

    assert style_note_for_category("not-a-real-category") == DEFAULT_STYLE_NOTE


def test_style_note_none_category_falls_back():
    from app.services.ai_caption import (
        DEFAULT_STYLE_NOTE,
        style_note_for_category,
    )

    assert style_note_for_category(None) == DEFAULT_STYLE_NOTE


def test_build_system_prompt_includes_style_and_vertical():
    from app.services.ai_caption import CaptionContext, build_system_prompt

    ctx = CaptionContext(
        business_name="Isla Nail Society",
        neighborhood_name="Brickell",
        city_name="Miami",
        primary_category="nails",
        vertical_word="salon",
        known_for=None,
        short_description=None,
        prompt="fall promo",
    )
    out = build_system_prompt(ctx)
    assert "salon" in out
    assert "polished" in out or "craftsmanship" in out  # nails style note
    assert "EXACTLY 7" in out
    assert "ONLY the seven numbered suggestions" in out


def test_build_user_prompt_drops_optional_fields_cleanly():
    from app.services.ai_caption import CaptionContext, build_user_prompt

    ctx = CaptionContext(
        business_name="Cafe X",
        neighborhood_name=None,
        city_name="Miami",
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="grand opening",
    )
    out = build_user_prompt(ctx)
    assert "Business: Cafe X" in out
    assert "grand opening" in out
    # Missing optional fields shouldn't appear as empty "X: " lines.
    assert "Category:" not in out
    assert "Known for:" not in out
    assert "About:" not in out


def test_build_user_prompt_includes_selected_photo_url():
    from app.services.ai_caption import CaptionContext, build_user_prompt

    ctx = CaptionContext(
        business_name="Isla Nail Society",
        neighborhood_name="Brickell",
        city_name="Miami",
        primary_category="nails",
        vertical_word="salon",
        known_for=None,
        short_description=None,
        prompt="new chrome set",
        photo_url="/media/photo123",
    )
    out = build_user_prompt(ctx)
    assert "Selected listing photo URL: /media/photo123" in out
    assert "do not invent visual details" in out


# --- Geographic disambiguation: the Hollywood, FL / "#LosAngelesHair" bug ---


def test_build_user_prompt_disambiguates_hollywood_with_state_and_market():
    """Regression for the Hollywood-FL → #LosAngelesHair mis-geolocation.

    A salon in Hollywood, FL must reach the model anchored to Florida and
    the South Florida market — otherwise the model defaults the famous
    "Hollywood" to Los Angeles, CA and writes LA hashtags. We assert the
    built prompt carries BOTH anchors and the LA-readable bare "Hollywood"
    on its own is replaced by "Hollywood, FL".
    """
    from app.services.ai_caption import CaptionContext, build_user_prompt

    ctx = CaptionContext(
        business_name="Studio 1847 Hair",
        neighborhood_name="Downtown Hollywood",
        city_name="Hollywood",
        primary_category="hair",
        vertical_word="salon",
        known_for=None,
        short_description=None,
        prompt="fall color promo",
        state="FL",
        market_label="South Florida (Miami metro area)",
    )
    out = build_user_prompt(ctx)
    # The city must appear state-anchored, not as a bare "Hollywood".
    assert "Hollywood, FL" in out
    # The neighborhood is preserved alongside the state-anchored city.
    assert "Downtown Hollywood, Hollywood, FL" in out
    # The coarse regional anchor must be present too.
    assert "Market: South Florida (Miami metro area)" in out
    # And there must be no Los-Angeles / California leakage in the context.
    lowered = out.lower()
    assert "los angeles" not in lowered
    assert "california" not in lowered


def test_build_user_prompt_omits_market_line_when_absent():
    """Without a market label, no empty 'Market:' line should appear, and a
    bare city stays bare (graceful degradation for legacy contexts)."""
    from app.services.ai_caption import CaptionContext, build_user_prompt

    ctx = CaptionContext(
        business_name="Cafe X",
        neighborhood_name=None,
        city_name="Hollywood",
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="grand opening",
        state=None,
        market_label=None,
    )
    out = build_user_prompt(ctx)
    assert "Market:" not in out
    # No state → city stays as-is (we can't fabricate a state we don't have).
    assert "Location: Hollywood" in out
    assert "Hollywood," not in out  # no trailing-comma state fragment


def test_resolve_location_prefers_business_address_state():
    """The salon's own structured address state is the most precise source."""
    from app.services.ai_caption import resolve_location

    business = {"address": {"state": "FL"}}
    city = {"state": "NY", "name": "Hollywood"}  # city stub disagrees
    state, market = resolve_location(business, city)
    assert state == "FL"
    assert market == "South Florida (Miami metro area)"


def test_resolve_location_accepts_legacy_region_key():
    """Early seed data used 'region' for the same value as 'state'."""
    from app.services.ai_caption import resolve_location

    business = {"address": {"region": "FL"}}
    state, _market = resolve_location(business, city=None)
    assert state == "FL"


def test_resolve_location_falls_back_to_city_state():
    """When the business has no address state, the city record supplies it."""
    from app.services.ai_caption import resolve_location

    business = {"address": {}}
    city = {"state": "FL", "name": "Hollywood"}
    state, market = resolve_location(business, city)
    assert state == "FL"
    assert market == "South Florida (Miami metro area)"


def test_resolve_location_defaults_market_when_no_state():
    """No state anywhere → still return the regional market so there's an
    anchor, and state is None (we never invent a state)."""
    from app.services.ai_caption import resolve_location, DEFAULT_MARKET_LABEL

    state, market = resolve_location(business=None, city=None)
    assert state is None
    assert market == DEFAULT_MARKET_LABEL


def test_resolve_location_uses_city_market_label_when_present():
    """A real per-city market label wins over the South Florida default."""
    from app.services.ai_caption import resolve_location

    business = {"address": {"state": "CA"}}
    city = {"state": "CA", "market_label": "Greater Los Angeles"}
    state, market = resolve_location(business, city)
    assert state == "CA"
    assert market == "Greater Los Angeles"


def test_feature_enabled_truthy_values(monkeypatch):
    from app.services.ai_caption import feature_enabled

    for val in ["true", "TRUE", "1", "yes", "on", " true "]:
        monkeypatch.setenv("MARKETING_AI_ENABLED", val)
        assert feature_enabled() is True, val


def test_feature_disabled_default(monkeypatch):
    from app.services.ai_caption import feature_enabled

    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    assert feature_enabled() is False


def test_feature_disabled_falsy_values(monkeypatch):
    from app.services.ai_caption import feature_enabled

    for val in ["", "false", "0", "no", "off", "maybe"]:
        monkeypatch.setenv("MARKETING_AI_ENABLED", val)
        assert feature_enabled() is False, val


# --- Service-level: HTTP behaviour against a mocked gateway ---


class _MockTransport(httpx.MockTransport):
    """Lightweight per-test transport so each case picks its response."""


def _ok_transport(text: str = "Test caption 🌟\n#test"):
    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200, json={"text": text, "use_case": "marketing_caption"}
        )

    return _MockTransport(handler), captured


def _status_transport(status_code: int, body: Optional[dict] = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body or {"detail": "bang"})

    return _MockTransport(handler)


def test_generate_caption_disabled_raises(monkeypatch):
    from app.services.ai_caption import CaptionContext, CaptionFeatureDisabled, generate_caption

    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    ctx = CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )
    with pytest.raises(CaptionFeatureDisabled):
        asyncio.run(generate_caption(ctx))


def test_generate_caption_missing_key_raises(monkeypatch):
    from app.services.ai_caption import CaptionContext, CaptionGenerationError, generate_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("AI_GATEWAY_KEY", raising=False)
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    ctx = CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )
    with pytest.raises(CaptionGenerationError):
        asyncio.run(generate_caption(ctx))


def test_generate_caption_happy_path_sends_expected_body(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport, captured = _ok_transport("Caption text 💅\n#test")

    ctx = ai_caption.CaptionContext(
        business_name="Isla Nail Society",
        neighborhood_name="Brickell",
        city_name="Miami",
        primary_category="nails",
        vertical_word="salon",
        known_for="airbrush gradients",
        short_description="Tiny studio doing big nails.",
        prompt="fall hair color promo",
        state="FL",
        market_label="South Florida (Miami metro area)",
        photo_url="/media/photo123",
    )

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await ai_caption.generate_caption(ctx, http_client=client)

    out = asyncio.run(run())

    assert out == "Caption text 💅\n#test"
    assert captured["url"] == "https://admin-api.ai.devintensive.com/api/public/ai-config/call"
    # Ensure all the expected fields flowed through
    body = captured["body"]
    assert body["use_case"] == "marketing_caption"
    assert body["max_tokens_override"] == 1100
    assert body["cost_tags"]["product"] == "known-around-town"
    assert "Isla Nail Society" in body["user_content"]
    assert "Brickell, Miami, FL" in body["user_content"]
    # The regional market anchor must reach the gateway body too.
    assert "South Florida (Miami metro area)" in body["user_content"]
    assert "Selected listing photo URL: /media/photo123" in body["user_content"]
    assert "fall hair color promo" in body["user_content"]
    # System prompt should reflect the nails category style note
    assert "salon" in body["system_prompt"]
    assert "EXACTLY 7" in body["system_prompt"]
    # Auth header must be present
    assert captured["headers"]["x-api-key"] == "test-key-abc"


def test_generate_caption_502_on_gateway_error(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport = _status_transport(500, {"detail": "boom"})

    ctx = ai_caption.CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            await ai_caption.generate_caption(ctx, http_client=client)

    with pytest.raises(ai_caption.CaptionGenerationError):
        asyncio.run(go())


def test_generate_caption_empty_text_raises(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport, _ = _ok_transport(text="   ")  # whitespace-only

    ctx = ai_caption.CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            await ai_caption.generate_caption(ctx, http_client=client)

    with pytest.raises(ai_caption.CaptionGenerationError):
        asyncio.run(go())


# --- Endpoint tests through the FastAPI app ---


@pytest.fixture
def client(seeded_db, monkeypatch):
    # Feature flag on by default for endpoint tests; individual tests
    # flip it off as needed.
    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    # Make sure we don't accidentally hit the real network if a path
    # bypasses the patched generate_caption.
    monkeypatch.setenv("AI_GATEWAY_URL", "http://invalid.local/should-not-be-called")
    from app.main import app

    return TestClient(app)


def _patch_generate(monkeypatch, *, raises: Exception | None = None, returns: str | None = None):
    """Patch the service-level generator the endpoint calls.

    Endpoint tests don't exercise the gateway transport at all; they
    only need to verify the endpoint shapes the request and response
    correctly.
    """
    from app.services import ai_caption

    async def fake_generate(ctx, http_client=None):
        if raises is not None:
            raise raises
        return returns or "Mock caption from test 💫\n#mock"

    monkeypatch.setattr(ai_caption, "generate_caption", fake_generate)


_TEST_OWNER_EMAIL = "testowner@example.com"
_TEST_STRIPE_ID = "sub_test123"


def _pick_seeded_business(seeded_db):
    """Return any seeded Miami Beauty business for endpoint tests."""
    biz = asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.find_one({"slug": "isla-nail-society"})
    )
    if not biz:
        # Fall back to any business if seed data changes the slug
        biz = asyncio.get_event_loop().run_until_complete(
            seeded_db.businesses.find_one({})
        )
    return biz


def _make_pro_business(seeded_db, biz):
    """Stamp a test business with claimed_email + stripe_subscription_id so
    the auth helper recognises it as an active Featured subscriber.

    Returns the cookie value that corresponds to this owner session.
    """
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {
                "claimed_email": _TEST_OWNER_EMAIL,
                "stripe_subscription_id": _TEST_STRIPE_ID,
            }},
        )
    )
    from app.services.owner_auth import sign_session
    return sign_session(_TEST_OWNER_EMAIL)


def test_endpoint_returns_caption_on_success(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    assert biz is not None
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate(monkeypatch, returns="Hello from the mock 💅\n#mock #test")

    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "grand opening"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["caption"] == "Hello from the mock 💅\n#mock #test"
    assert data["business_id"] == biz["_id"]


def test_endpoint_builds_context_with_state_and_market(client, seeded_db, monkeypatch):
    """End-to-end wiring: the route must hand the generator a context carrying
    the state and regional market, so the model can't mis-geolocate the city.

    This is the route-layer half of the Hollywood-FL → #LosAngelesHair fix:
    the pure-function tests prove the prompt builder uses the anchors; this
    proves the endpoint actually populates them from the business + city data
    (a Florida business in the Miami seed). We capture the context the route
    builds instead of asserting on the returned text, so the test validates
    behavior (what the route passes to the model), not narration.
    """
    from app.services import ai_caption

    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)

    captured = {}

    async def fake_generate(ctx, http_client=None):
        captured["ctx"] = ctx
        return "ok 🌴\n#test"

    monkeypatch.setattr(ai_caption, "generate_caption", fake_generate)

    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "grand opening"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 200, resp.text
    ctx = captured["ctx"]
    # The seeded Miami business is in Florida → the route must anchor it.
    assert ctx.state == "FL"
    assert ctx.market_label == "South Florida (Miami metro area)"
    # And the built prompt the model would see is state-anchored, not bare.
    built = ai_caption.build_user_prompt(ctx)
    assert ", FL" in built
    assert "South Florida (Miami metro area)" in built


def test_endpoint_passes_owned_photo_url_to_caption_context(client, seeded_db, monkeypatch):
    from app.services import ai_caption

    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"photos": [{"url": "/media/owned-photo", "alt": "Front room"}]}},
        )
    )

    captured = {}

    async def fake_generate(ctx, http_client=None):
        captured["ctx"] = ctx
        return "1. Caption one\n#test\n\n2. Caption two\n#test"

    monkeypatch.setattr(ai_caption, "generate_caption", fake_generate)

    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={
            "business_id": biz["_id"],
            "prompt": "new color room",
            "photo_url": "/media/owned-photo",
        },
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 200, resp.text
    assert captured["ctx"].photo_url == "/media/owned-photo"


def test_endpoint_400_when_photo_url_is_not_on_listing(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"photos": [{"url": "/media/owned-photo", "alt": "Front room"}]}},
        )
    )
    _patch_generate(monkeypatch)

    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={
            "business_id": biz["_id"],
            "prompt": "new color room",
            "photo_url": "/media/not-this-listing",
        },
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 400
    assert "not attached" in resp.json()["detail"]


def test_endpoint_401_when_no_session_cookie(client, seeded_db, monkeypatch):
    """No cookie at all should return 401."""
    biz = _pick_seeded_business(seeded_db)
    _make_pro_business(seeded_db, biz)
    _patch_generate(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
    )
    assert resp.status_code == 401


def test_endpoint_403_when_wrong_owner(client, seeded_db, monkeypatch):
    """A session for a different email should be rejected."""
    biz = _pick_seeded_business(seeded_db)
    _make_pro_business(seeded_db, biz)
    from app.services.owner_auth import sign_session
    other_cookie = sign_session("someone-else@example.com")
    _patch_generate(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={other_cookie}"},
    )
    assert resp.status_code == 403


def test_endpoint_402_when_not_subscribed(client, seeded_db, monkeypatch):
    """A valid owner session but no Stripe subscription returns 402."""
    biz = _pick_seeded_business(seeded_db)
    # Set claimed_email but NOT stripe_subscription_id
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"claimed_email": _TEST_OWNER_EMAIL},
             "$unset": {"stripe_subscription_id": ""}},
        )
    )
    from app.services.owner_auth import sign_session
    cookie = sign_session(_TEST_OWNER_EMAIL)
    _patch_generate(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 402


def test_endpoint_404_when_feature_disabled(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 404


def test_endpoint_404_when_business_not_found(client, seeded_db, monkeypatch):
    """A nonexistent business id should 404 even with a valid session."""
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": "does-not-exist", "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 404


def test_endpoint_422_on_empty_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": ""},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 422


def test_endpoint_422_on_overlong_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x" * 601},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 422


def test_endpoint_502_on_gateway_error(client, seeded_db, monkeypatch):
    from app.services.ai_caption import CaptionGenerationError

    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate(monkeypatch, raises=CaptionGenerationError("unreachable"))
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 502
    assert "try again" in resp.json()["detail"].lower()


def test_preview_page_renders_when_flag_on(client, seeded_db):
    r = client.get(
        "/owners/preview/caption", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert "Instagram caption generator" in r.text
    # The page must include the seeded business id for the JS to call the API
    biz = _pick_seeded_business(seeded_db)
    assert biz["_id"] in r.text


def test_preview_page_404_when_flag_off(client, monkeypatch):
    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    r = client.get(
        "/owners/preview/caption", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 404


# --- Optional live integration test (skipped in CI) ---


# --- Ad copy: unit tests for service helpers ---


def test_build_ad_copy_system_prompt_includes_format_spec():
    from app.services.ai_caption import CaptionContext, build_ad_copy_system_prompt

    ctx = CaptionContext(
        business_name="Brickell Balayage",
        neighborhood_name="Brickell",
        city_name="Miami",
        primary_category="hair",
        vertical_word="salon",
        known_for=None,
        short_description=None,
        prompt="summer specials",
    )
    out = build_ad_copy_system_prompt(ctx)
    # Must describe the exact output format so the model is unambiguous.
    assert "3 variations" in out or "3" in out
    assert "headline" in out
    assert "description" in out
    # Should embed the vertical word so copy feels on-brand.
    assert "salon" in out


def test_build_ad_copy_system_prompt_fallback_vertical():
    from app.services.ai_caption import CaptionContext, build_ad_copy_system_prompt

    ctx = CaptionContext(
        business_name="No Vertical",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="sale",
    )
    out = build_ad_copy_system_prompt(ctx)
    assert "local business" in out


# --- Ad copy: service-level HTTP behaviour against a mocked gateway ---


def test_generate_ad_copy_disabled_raises(monkeypatch):
    from app.services.ai_caption import CaptionContext, CaptionFeatureDisabled, generate_ad_copy

    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    ctx = CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )
    with pytest.raises(CaptionFeatureDisabled):
        asyncio.run(generate_ad_copy(ctx))


def test_generate_ad_copy_missing_key_raises(monkeypatch):
    from app.services.ai_caption import CaptionContext, CaptionGenerationError, generate_ad_copy

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("AI_GATEWAY_KEY", raising=False)
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    ctx = CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )
    with pytest.raises(CaptionGenerationError):
        asyncio.run(generate_ad_copy(ctx))


def test_generate_ad_copy_happy_path_sends_expected_body(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    ad_text = "Get the Look\nBook your fall balayage today — limited spots.\n\nFall Into Color\nWarm tones, expert hands. New clients welcome.\n\nYear-Round Gorgeous\nBalayage that grows out beautifully. Book now."
    transport, captured = _ok_transport(ad_text)

    ctx = ai_caption.CaptionContext(
        business_name="Brickell Balayage",
        neighborhood_name="Brickell",
        city_name="Miami",
        primary_category="hair",
        vertical_word="salon",
        known_for="lived-in color",
        short_description="Balayage specialists in Brickell.",
        prompt="fall balayage promo",
        state="FL",
        market_label="South Florida (Miami metro area)",
    )

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await ai_caption.generate_ad_copy(ctx, http_client=client)

    out = asyncio.run(run())

    assert out == ad_text
    assert captured["url"] == "https://admin-api.ai.devintensive.com/api/public/ai-config/call"
    body = captured["body"]
    # Must use the ad-copy-specific cost tag, not the caption one.
    assert body["cost_tags"]["feature"] == "owners.ad_copy"
    assert "Brickell Balayage" in body["user_content"]
    # The geographic disambiguation must flow into ad copy too (shared builder).
    assert "Brickell, Miami, FL" in body["user_content"]
    assert "South Florida (Miami metro area)" in body["user_content"]
    assert "fall balayage promo" in body["user_content"]
    # Token budget must be the ad copy budget (450), not the caption budget (300).
    assert body["max_tokens_override"] == 450
    assert captured["headers"]["x-api-key"] == "test-key-abc"


def test_generate_ad_copy_gateway_error_raises(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport = _status_transport(500, {"detail": "boom"})

    ctx = ai_caption.CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            await ai_caption.generate_ad_copy(ctx, http_client=client)

    with pytest.raises(ai_caption.CaptionGenerationError):
        asyncio.run(go())


def test_generate_ad_copy_empty_text_raises(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.delenv("KAT_AI_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport, _ = _ok_transport(text="   ")  # whitespace-only

    ctx = ai_caption.CaptionContext(
        business_name="X",
        neighborhood_name=None,
        city_name=None,
        primary_category=None,
        vertical_word=None,
        known_for=None,
        short_description=None,
        prompt="hi",
    )

    async def go():
        async with httpx.AsyncClient(transport=transport) as client:
            await ai_caption.generate_ad_copy(ctx, http_client=client)

    with pytest.raises(ai_caption.CaptionGenerationError):
        asyncio.run(go())


# --- Ad copy: endpoint tests through the FastAPI app ---


def _patch_generate_ad_copy(
    monkeypatch, *, raises: Exception | None = None, returns: str | None = None
):
    """Patch the ad-copy service function the endpoint calls.

    Mirrors _patch_generate — keeps endpoint tests independent of gateway.
    """
    from app.services import ai_caption

    async def fake_generate(ctx, http_client=None):
        if raises is not None:
            raise raises
        return returns or "Mock Headline\nMock description for this ad.\n\nSecond Headline\nAnother mock description here.\n\nThird Headline\nYet another mock description text."

    monkeypatch.setattr(ai_caption, "generate_ad_copy", fake_generate)


def test_ad_copy_endpoint_returns_copy_on_success(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    assert biz is not None
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate_ad_copy(monkeypatch, returns="Headline One\nDesc one.\n\nHeadline Two\nDesc two.\n\nHeadline Three\nDesc three.")

    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "summer specials"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ad_copy"] == "Headline One\nDesc one.\n\nHeadline Two\nDesc two.\n\nHeadline Three\nDesc three."
    assert data["business_id"] == biz["_id"]


def test_ad_copy_endpoint_401_when_no_session(client, seeded_db, monkeypatch):
    """No cookie should return 401 for ad copy too."""
    biz = _pick_seeded_business(seeded_db)
    _make_pro_business(seeded_db, biz)
    _patch_generate_ad_copy(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
    )
    assert resp.status_code == 401


def test_ad_copy_endpoint_402_when_not_subscribed(client, seeded_db, monkeypatch):
    """Authenticated owner without a subscription gets 402."""
    biz = _pick_seeded_business(seeded_db)
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"claimed_email": _TEST_OWNER_EMAIL},
             "$unset": {"stripe_subscription_id": ""}},
        )
    )
    from app.services.owner_auth import sign_session
    cookie = sign_session(_TEST_OWNER_EMAIL)
    _patch_generate_ad_copy(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 402


def test_ad_copy_endpoint_403_when_wrong_owner(client, seeded_db, monkeypatch):
    """Session for a different email is rejected with 403 for ad copy too."""
    biz = _pick_seeded_business(seeded_db)
    _make_pro_business(seeded_db, biz)
    from app.services.owner_auth import sign_session
    other_cookie = sign_session("someone-else@example.com")
    _patch_generate_ad_copy(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={other_cookie}"},
    )
    assert resp.status_code == 403


def test_ad_copy_endpoint_404_when_feature_disabled(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 404


def test_ad_copy_endpoint_404_when_business_not_found(client, seeded_db, monkeypatch):
    """Nonexistent business id 404s even with a valid session."""
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate_ad_copy(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": "does-not-exist", "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 404


def test_ad_copy_endpoint_422_on_empty_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": ""},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 422


def test_ad_copy_endpoint_422_on_overlong_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x" * 601},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 422


def test_ad_copy_endpoint_502_on_gateway_error(client, seeded_db, monkeypatch):
    from app.services.ai_caption import CaptionGenerationError

    biz = _pick_seeded_business(seeded_db)
    cookie = _make_pro_business(seeded_db, biz)
    _patch_generate_ad_copy(monkeypatch, raises=CaptionGenerationError("unreachable"))
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 502
    assert "try again" in resp.json()["detail"].lower()


# --- Profile description: owner-facing "About your salon" helper ---


def test_build_profile_description_system_prompt_forbids_invention():
    from app.services.ai_caption import (
        CaptionContext,
        build_profile_description_system_prompt,
    )

    ctx = CaptionContext(
        business_name="Wynwood Color Studio",
        neighborhood_name="Wynwood",
        city_name="Miami",
        primary_category="hair",
        vertical_word="salon",
        known_for=None,
        short_description=None,
        prompt="modern color studio",
    )
    out = build_profile_description_system_prompt(ctx)
    assert "80-140 words" in out
    assert "do not invent" in out.lower()
    assert "ONLY the paragraph" in out


def test_generate_profile_description_happy_path_sends_expected_body(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    monkeypatch.setenv("AI_GATEWAY_KEY", "test-key-abc")
    transport, captured = _ok_transport(
        "Wynwood Color Studio is a relaxed Miami salon focused on lived-in color."
    )

    ctx = ai_caption.CaptionContext(
        business_name="Wynwood Color Studio",
        neighborhood_name="Wynwood",
        city_name="Miami",
        primary_category="hair",
        vertical_word="salon",
        known_for="lived-in color",
        short_description="A calm color studio.",
        prompt="calm luxury, low-maintenance hair",
        state="FL",
        market_label="South Florida (Miami metro area)",
    )

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await ai_caption.generate_profile_description(ctx, http_client=client)

    out = asyncio.run(run())

    assert out.startswith("Wynwood Color Studio")
    body = captured["body"]
    assert body["cost_tags"]["feature"] == "owners.profile_description"
    assert body["max_tokens_override"] == 500
    assert "calm luxury" in body["user_content"]
    assert "do not invent" in body["system_prompt"].lower()


def _patch_generate_profile_description(
    monkeypatch, *, raises: Exception | None = None, returns: str | None = None
):
    from app.services import ai_caption

    async def fake_generate(ctx, http_client=None):
        if raises is not None:
            raise raises
        return returns or "A polished profile paragraph from the test."

    monkeypatch.setattr(ai_caption, "generate_profile_description", fake_generate)


def _make_claimed_business(seeded_db, biz, email: str = _TEST_OWNER_EMAIL):
    asyncio.get_event_loop().run_until_complete(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"claimed_email": email}, "$unset": {"stripe_subscription_id": ""}},
        )
    )
    from app.services.owner_auth import sign_session

    return sign_session(email)


def test_profile_description_endpoint_allows_claimed_free_owner(
    client, seeded_db, monkeypatch
):
    """The profile-writing helper is useful before payment, so it only requires ownership."""
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_claimed_business(seeded_db, biz)
    _patch_generate_profile_description(
        monkeypatch,
        returns="A warm, specific paragraph the owner can paste into their listing.",
    )

    resp = client.post(
        "/api/v1/marketing-ai/profile-description",
        json={
            "business_id": biz["_id"],
            "prompt": "calm salon, lived-in color, low-maintenance clients",
        },
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "warm, specific paragraph" in data["description"]
    assert data["business_id"] == biz["_id"]


def test_profile_description_endpoint_rejects_wrong_owner(
    client, seeded_db, monkeypatch
):
    biz = _pick_seeded_business(seeded_db)
    _make_claimed_business(seeded_db, biz, email="owner@example.com")
    from app.services.owner_auth import sign_session

    _patch_generate_profile_description(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/profile-description",
        json={"business_id": biz["_id"], "prompt": "nice wording"},
        headers={"Cookie": f"kb_owner_session={sign_session('other@example.com')}"},
    )
    assert resp.status_code == 403


def test_profile_description_endpoint_422_on_overlong_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    cookie = _make_claimed_business(seeded_db, biz)
    resp = client.post(
        "/api/v1/marketing-ai/profile-description",
        json={"business_id": biz["_id"], "prompt": "x" * 801},
        headers={"Cookie": f"kb_owner_session={cookie}"},
    )
    assert resp.status_code == 422


# --- Optional live integration test (skipped in CI) ---


@pytest.mark.skipif(
    os.environ.get("KAT_INSTAGRAM_CAPTION_LIVE") != "1",
    reason="Set KAT_INSTAGRAM_CAPTION_LIVE=1 to hit the real LLM (spends tokens).",
)
def test_live_caption_generation_against_real_gateway(seeded_db, monkeypatch):
    """Hit the real Public AI Gateway with a known business.

    Skipped in CI. Run locally with:

        AI_GATEWAY_KEY=$KAT_AI_GATEWAY_KEY \\
        MARKETING_AI_ENABLED=true \\
        KAT_INSTAGRAM_CAPTION_LIVE=1 \\
            pytest backend/tests/test_marketing_ai.py -k live -s

    Verifies the full path: prompt building -> gateway -> configured provider -> text.
    """
    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
    # Caller must have set AI_GATEWAY_KEY in the env that pytest sees.
    assert os.environ.get("AI_GATEWAY_KEY"), "Set AI_GATEWAY_KEY for the live test."

    from app.main import app

    client = TestClient(app)
    biz = _pick_seeded_business(seeded_db)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "weekend balayage promo"},
    )
    assert resp.status_code == 200, resp.text
    caption = resp.json()["caption"]
    print("LIVE CAPTION:", caption)
    assert caption.strip(), "Live gateway returned empty caption"
