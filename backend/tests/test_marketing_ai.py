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
    assert "ONLY the caption" in out


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
    assert body["max_tokens_override"] == 300
    assert body["cost_tags"]["product"] == "known-around-town"
    assert "Isla Nail Society" in body["user_content"]
    assert "Brickell, Miami" in body["user_content"]
    assert "fall hair color promo" in body["user_content"]
    # System prompt should reflect the nails category style note
    assert "salon" in body["system_prompt"]
    # Auth header must be present
    assert captured["headers"]["x-api-key"] == "test-key-abc"


def test_generate_caption_502_on_gateway_error(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
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


def test_endpoint_returns_caption_on_success(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    assert biz is not None
    _patch_generate(monkeypatch, returns="Hello from the mock 💅\n#mock #test")

    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "grand opening"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["caption"] == "Hello from the mock 💅\n#mock #test"
    assert data["business_id"] == biz["_id"]


def test_endpoint_404_when_feature_disabled(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
    )
    assert resp.status_code == 404


def test_endpoint_404_when_business_not_found(client, monkeypatch):
    _patch_generate(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": "does-not-exist", "prompt": "x"},
    )
    assert resp.status_code == 404


def test_endpoint_422_on_empty_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": ""},
    )
    assert resp.status_code == 422


def test_endpoint_422_on_overlong_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x" * 601},
    )
    assert resp.status_code == 422


def test_endpoint_502_on_gateway_error(client, seeded_db, monkeypatch):
    from app.services.ai_caption import CaptionGenerationError

    biz = _pick_seeded_business(seeded_db)
    _patch_generate(monkeypatch, raises=CaptionGenerationError("unreachable"))
    resp = client.post(
        "/api/v1/marketing-ai/instagram-caption",
        json={"business_id": biz["_id"], "prompt": "x"},
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
    assert "fall balayage promo" in body["user_content"]
    # Token budget must be the ad copy budget (450), not the caption budget (300).
    assert body["max_tokens_override"] == 450
    assert captured["headers"]["x-api-key"] == "test-key-abc"


def test_generate_ad_copy_gateway_error_raises(monkeypatch):
    from app.services import ai_caption

    monkeypatch.setenv("MARKETING_AI_ENABLED", "true")
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
    _patch_generate_ad_copy(monkeypatch, returns="Headline One\nDesc one.\n\nHeadline Two\nDesc two.\n\nHeadline Three\nDesc three.")

    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "summer specials"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ad_copy"] == "Headline One\nDesc one.\n\nHeadline Two\nDesc two.\n\nHeadline Three\nDesc three."
    assert data["business_id"] == biz["_id"]


def test_ad_copy_endpoint_404_when_feature_disabled(client, seeded_db, monkeypatch):
    biz = _pick_seeded_business(seeded_db)
    monkeypatch.delenv("MARKETING_AI_ENABLED", raising=False)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
    )
    assert resp.status_code == 404


def test_ad_copy_endpoint_404_when_business_not_found(client, monkeypatch):
    _patch_generate_ad_copy(monkeypatch)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": "does-not-exist", "prompt": "x"},
    )
    assert resp.status_code == 404


def test_ad_copy_endpoint_422_on_empty_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": ""},
    )
    assert resp.status_code == 422


def test_ad_copy_endpoint_422_on_overlong_prompt(client, seeded_db):
    biz = _pick_seeded_business(seeded_db)
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x" * 601},
    )
    assert resp.status_code == 422


def test_ad_copy_endpoint_502_on_gateway_error(client, seeded_db, monkeypatch):
    from app.services.ai_caption import CaptionGenerationError

    biz = _pick_seeded_business(seeded_db)
    _patch_generate_ad_copy(monkeypatch, raises=CaptionGenerationError("unreachable"))
    resp = client.post(
        "/api/v1/marketing-ai/ad-copy",
        json={"business_id": biz["_id"], "prompt": "x"},
    )
    assert resp.status_code == 502
    assert "try again" in resp.json()["detail"].lower()


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
