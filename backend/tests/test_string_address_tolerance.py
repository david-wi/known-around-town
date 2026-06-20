"""Regression test: salon detail pages must tolerate a single-line string address.

The bug this guards against: ~367 imported salon records (256 of them live)
store their address as one line of text — e.g.
"2001 N Federal Hwy, Suite 208, Pompano Beach, FL 33062" — rather than the
structured {street, city, state, postal_code} object the Business model defines.
The detail route built its Google Maps query with `address.get("street")`, which
raised `AttributeError: 'str' object has no attribute 'get'` on a plain string,
so every one of those 256 live salon pages returned HTTP 500.

The fix normalises the address into a dict at render time (string -> parsed
dict, dict -> unchanged), so the page renders, shows the full address, and never
crashes. These tests fail (500 on the full-page test) if the normalisation is
removed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.routes.public.pages import _normalize_address

BEAUTY_HOST = "miami.knowsbeauty.localhost"
STRING_ADDRESS = "2001 N Federal Hwy, Suite 208, Pompano Beach, FL 33062"


# ---- unit: the normaliser ------------------------------------------------

def test_normalize_passes_dict_through_unchanged():
    structured = {
        "street": "1 A St",
        "city": "Miami",
        "state": "FL",
        "postal_code": "33101",
    }
    assert _normalize_address(structured) is structured


def test_normalize_parses_single_line_string():
    addr = _normalize_address(STRING_ADDRESS)
    # The whole original line is preserved as `street` so the Address card,
    # which renders only address.street, shows the complete address.
    assert addr["street"] == STRING_ADDRESS
    # City/state/zip are pulled out for the Maps query and JSON-LD.
    assert addr["state"] == "FL"
    assert addr["postal_code"] == "33062"
    assert addr["city"] == "Pompano Beach"


def test_normalize_handles_zip_plus_four():
    addr = _normalize_address("525 E Atlantic Ave, Delray Beach, FL 33483-1234")
    assert addr["postal_code"] == "33483-1234"
    assert addr["city"] == "Delray Beach"


def test_normalize_trailing_chunk_is_city_when_no_state_or_zip():
    # When the final comma chunk is not a state/zip, that chunk IS the city.
    addr = _normalize_address("Some Plaza, Miami Beach")
    assert addr["city"] == "Miami Beach"
    assert "state" not in addr
    assert "postal_code" not in addr


@pytest.mark.parametrize("bad", [None, 123, "", "   ", []])
def test_normalize_returns_empty_dict_for_non_address(bad):
    assert _normalize_address(bad) == {}


# ---- full request path: the detail page must not 500 --------------------

@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


@pytest.fixture
async def string_address_slug(seeded_db) -> str:
    """Insert one live beauty salon whose address is a single-line string.

    Clones an existing seeded beauty business so the network_id / city_id match
    the live tenant, then overrides the slug and address. Returns the new slug.
    """
    template = await seeded_db.businesses.find_one({"status": "live"})
    assert template is not None, "seed should contain at least one live business"

    slug = "regression-string-address-salon"
    doc = dict(template)
    doc["_id"] = "string-address-regression-id"
    doc["slug"] = slug
    doc["name"] = "String Address Salon"
    doc["address"] = STRING_ADDRESS  # the malformed single-line shape
    await seeded_db.businesses.insert_one(doc)
    return slug


@pytest.mark.asyncio
async def test_detail_page_renders_string_address_without_500(
    client, string_address_slug
):
    r = client.get(
        f"/b/{string_address_slug}", headers={"host": BEAUTY_HOST}
    )
    # Without the fix this is a 500 (AttributeError on the string address).
    assert r.status_code == 200, r.text
    body = r.text
    assert "String Address Salon" in body
    # The full address text is visible to the shopper in the Address card.
    assert STRING_ADDRESS in body
    # The "Get directions" Maps link is built from the address and points at it.
    assert "maps.google.com" in body
    assert "Pompano+Beach" in body
