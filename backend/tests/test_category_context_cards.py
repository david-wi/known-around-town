"""Regression tests for category-aware listing cards.

The same salon can honestly belong to more than one service category. These
tests guard the shopper-visible behavior: category pages and exact category
searches lead with the category the visitor is browsing, while neutral pages
keep the listing's default category and description.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

HOST = {"host": "miami.knowsbeauty.localhost"}

BUSINESS_ID = "category-context-test-salon"
SLUG = "category-context-test-salon"
NAILS_PHOTO = "https://cdn.example.com/category-context-nails.jpg"
HAIR_PHOTO = "https://cdn.example.com/category-context-hair.jpg"
NEUTRAL_BLURB = "Neutral category-context fallback sentence."
NAILS_BLURB = "Nails context sentence only."
HAIR_BLURB = "Hair context sentence only."


def _make_client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _insert_context_business(db) -> None:
    network = asyncio.run(db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )
    assert city, "seeded DB should include Miami beauty city"

    asyncio.run(db.businesses.insert_one({
        "_id": BUSINESS_ID,
        "network_id": network["_id"],
        "city_id": city["_id"],
        "slug": SLUG,
        "name": "Category Context Test Salon",
        "category_slugs": ["nails", "hair"],
        "neighborhood_slugs": ["brickell"],
        "short_description": NEUTRAL_BLURB,
        "category_blurbs": {
            "nails": NAILS_BLURB,
            "hair": HAIR_BLURB,
        },
        "photos": [
            {"url": NAILS_PHOTO, "category_slug": "nails", "is_hero": True},
            {"url": HAIR_PHOTO, "category_slug": "hair", "is_hero": False},
        ],
        "claim_status": "unclaimed",
        "status": "live",
        "featured": {"enabled": True, "tier": "premium"},
        "editors_pick": False,
        "quality_score": 999,
    }))


def _card_excerpt(body: str) -> str:
    marker = "Category Context Test Salon"
    index = body.rindex(marker)
    return body[max(index - 1500, 0): index + 2000]


def test_category_page_card_uses_active_category_context(seeded_db):
    _insert_context_business(seeded_db)

    body = _make_client().get("/c/hair", headers=HOST).text

    assert "Category Context Test Salon" in body
    card = _card_excerpt(body)
    assert "Hair · Brickell" in card
    assert "Nails · Brickell" not in card
    assert HAIR_BLURB in card
    assert NAILS_BLURB not in card
    assert NEUTRAL_BLURB not in card
    assert HAIR_PHOTO in card
    assert NAILS_PHOTO not in card


def test_neighborhood_category_card_uses_active_category_context(seeded_db):
    _insert_context_business(seeded_db)

    body = _make_client().get("/n/brickell/c/hair", headers=HOST).text

    assert "Category Context Test Salon" in body
    card = _card_excerpt(body)
    assert "Hair · Brickell" in card
    assert HAIR_BLURB in card
    assert HAIR_PHOTO in card


def test_exact_category_search_card_uses_active_category_context(
    seeded_db, monkeypatch
):
    _insert_context_business(seeded_db)

    from app.services import content as content_svc

    async def _select_test_business(*, query, businesses):
        return [BUSINESS_ID]

    monkeypatch.setattr(
        content_svc, "_select_matching_business_ids", _select_test_business
    )

    body = _make_client().get("/search?q=hair", headers=HOST).text

    assert "Category Context Test Salon" in body
    card = _card_excerpt(body)
    assert "Hair · Brickell" in card
    assert HAIR_BLURB in card
    assert HAIR_PHOTO in card
    assert NAILS_BLURB not in card


def test_neutral_directory_card_uses_default_context(seeded_db):
    _insert_context_business(seeded_db)

    body = _make_client().get("/all", headers=HOST).text

    assert "Category Context Test Salon" in body
    card = _card_excerpt(body)
    assert "Nails · Brickell" in card
    assert NEUTRAL_BLURB in card
    assert NAILS_PHOTO in card
    assert HAIR_BLURB not in card
    assert HAIR_PHOTO not in card
