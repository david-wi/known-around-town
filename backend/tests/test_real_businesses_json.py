"""Tests for _real_businesses.json data integrity.

WHY: The nightly seed re-inserts every business defined in this file. A closed
business left in the file means it reappears live every midnight. These tests
catch the two failure modes:
  1. A closed business that should be removed is still present.
  2. A newly-added business is missing required fields the seed code reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_JSON_PATH = Path(__file__).parent.parent / "seed" / "_real_businesses.json"


@pytest.fixture(scope="module")
def real_data():
    return json.loads(_JSON_PATH.read_text())


@pytest.fixture(scope="module")
def beauty_slugs(real_data):
    return {b["slug"] for b in real_data["beauty"]}


# ── Closed businesses must not reappear ──────────────────────────────────────

CLOSED_SLUGS = [
    "warren-tricomi-salon-miami-beach",   # permanently closed
    "ayesha-beauty-studio-wynwood",       # unverifiable
    "the-nail-garden-south-beach",        # wrong address (Miami Lakes, not SoBe)
    "skin-laundry-miami-beach",           # location closed
    "pfrankmd-miami-beach",               # Coral Gables, not South Beach
    "vita-aesthetics-miami",              # closed
]

STATUS_CLOSED_SLUGS = [
    "kingsmen-barbershop-wynwood",  # verified as not a safe live Miami listing
]


@pytest.mark.parametrize("slug", CLOSED_SLUGS)
def test_closed_business_removed(beauty_slugs, slug):
    """Closed businesses must be absent from the JSON so the nightly seed cannot recreate them."""
    assert slug not in beauty_slugs, (
        f"{slug!r} is a confirmed-closed business that must be removed from "
        "_real_businesses.json; leaving it in causes it to reappear live every midnight."
    )


@pytest.mark.parametrize("slug", STATUS_CLOSED_SLUGS)
def test_status_closed_business_is_explicitly_closed(real_data, slug):
    """Some reviewed records stay in the source file for audit but must not be live.

    WHY: Kingsmen was marked closed in _real_businesses.json, but seed_miami.py
    ignored the source status and wrote it as live. A reviewed-closed listing
    may remain in the source data, but only if it carries status=closed.
    """
    biz = next((b for b in real_data["beauty"] if b["slug"] == slug), None)
    assert biz is not None, f"{slug!r} should remain in source only as an audit record"
    assert biz.get("status") == "closed", (
        f"{slug!r} must be status='closed' so it cannot be surfaced as live"
    )


def test_seed_miami_honors_source_status():
    """The Miami seed must write the source status, not force every record live."""
    source = (Path(__file__).parent.parent / "seed" / "seed_miami.py").read_text()
    assert '"status": biz.get("status", "live")' in source, (
        "seed_miami.py must preserve _real_businesses.json status values; "
        "forcing status='live' resurrects reviewed-closed listings."
    )


# ── New businesses must have all required fields ──────────────────────────────

REQUIRED_FIELDS = ["name", "slug", "neighborhood_slug", "category_slug", "address", "phone"]

NEW_LITTLE_HAVANA_SLUGS = [
    "amandis-nail-spa-little-havana",
    "la-bonita-hair-salon-little-havana",
    "mancave-for-men-little-havana",
    "lash-society-miami-little-havana",
    "the-original-cuban-barbershop-little-havana",
]


@pytest.mark.parametrize("slug", NEW_LITTLE_HAVANA_SLUGS)
def test_little_havana_business_present(beauty_slugs, slug):
    """All new Little Havana businesses must be present in the beauty array."""
    assert slug in beauty_slugs, f"New business {slug!r} is missing from _real_businesses.json"


@pytest.mark.parametrize("slug", NEW_LITTLE_HAVANA_SLUGS)
def test_little_havana_business_required_fields(real_data, slug):
    """Each new business must have all fields the seed code reads."""
    biz = next((b for b in real_data["beauty"] if b["slug"] == slug), None)
    assert biz is not None, f"{slug!r} not found"
    for field in REQUIRED_FIELDS:
        assert field in biz and biz[field], (
            f"{slug!r} is missing required field {field!r}"
        )


@pytest.mark.parametrize("slug", NEW_LITTLE_HAVANA_SLUGS)
def test_little_havana_business_correct_neighborhood(real_data, slug):
    """All Little Havana businesses must have neighborhood_slug='little-havana'."""
    biz = next(b for b in real_data["beauty"] if b["slug"] == slug)
    assert biz["neighborhood_slug"] == "little-havana", (
        f"{slug!r} has neighborhood_slug={biz['neighborhood_slug']!r}, expected 'little-havana'"
    )


NEW_KEY_BISCAYNE_SLUGS = [
    "ceci-spa-hair-and-nails-key-biscayne",
    "prestige-beauty-salon-and-spa-key-biscayne",
    "b-care-salon-and-nails-spa-key-biscayne",
    "the-spot-barbershop-key-biscayne",
    "key-beauty-by-yeny-key-biscayne",
]


@pytest.mark.parametrize("slug", NEW_KEY_BISCAYNE_SLUGS)
def test_key_biscayne_business_present(beauty_slugs, slug):
    """All new Key Biscayne businesses must be present in the beauty array."""
    assert slug in beauty_slugs, f"New business {slug!r} is missing from _real_businesses.json"


@pytest.mark.parametrize("slug", NEW_KEY_BISCAYNE_SLUGS)
def test_key_biscayne_business_required_fields(real_data, slug):
    """Each new Key Biscayne business must have all fields the seed code reads."""
    biz = next((b for b in real_data["beauty"] if b["slug"] == slug), None)
    assert biz is not None, f"{slug!r} not found"
    for field in REQUIRED_FIELDS:
        assert field in biz and biz[field], (
            f"{slug!r} is missing required field {field!r}"
        )


@pytest.mark.parametrize("slug", NEW_KEY_BISCAYNE_SLUGS)
def test_key_biscayne_business_correct_neighborhood(real_data, slug):
    """All Key Biscayne businesses must have neighborhood_slug='key-biscayne'."""
    biz = next(b for b in real_data["beauty"] if b["slug"] == slug)
    assert biz["neighborhood_slug"] == "key-biscayne", (
        f"{slug!r} has neighborhood_slug={biz['neighborhood_slug']!r}, expected 'key-biscayne'"
    )


# ── seed_miami.py spotlight/trending slugs must resolve ──────────────────────

# Slugs referenced in seed_miami.py editorial placements — if they don't exist
# in the JSON the seed silently inserts nothing in those slots.
EDITORIAL_SLUGS = [
    # spotlight
    "wynwood-hair-co",
    "nue-studio-wynwood",
    "the-spot-barbershop-wynwood",
    # trending
    "rossano-ferretti-hair-spa-miami",
    "elia-spa-ritz-carlton-south-beach",
    "vanity-projects-miami-design-district",
    "igk-salon-south-beach",
    "the-spa-at-the-setai",
    # two_column south-beach
    "igk-salon-south-beach",
    "elia-spa-ritz-carlton-south-beach",
]


@pytest.mark.parametrize("slug", set(EDITORIAL_SLUGS))
def test_editorial_slug_exists(beauty_slugs, slug):
    """Slugs referenced in spotlight/trending/two-column in seed_miami.py must exist in the JSON.

    WHY: seed_miami.py references these slugs for editorial placements (homepage
    spotlight, trending row, neighborhood two-column layout). If the slug isn't in
    the JSON, the seed inserts nothing in that slot — the placement silently breaks.
    """
    assert slug in beauty_slugs, (
        f"Editorial slug {slug!r} referenced in seed_miami.py "
        "does not exist in _real_businesses.json"
    )
