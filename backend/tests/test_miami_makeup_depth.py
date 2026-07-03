"""Validate the Miami-core makeup studios added to deepen the thin /c/makeup page.

Miami's beauty listings live in seed/_real_businesses.json (singular
category_slug / neighborhood_slug), merged into the seed by seed_miami. Before
this batch the Makeup category showed only two listings. The real risk when
hand-adding real businesses is a typo'd neighborhood slug (which orphans the
listing / breaks its neighborhood link) or a wrong category (which drops it off
/c/makeup entirely). These tests lock in that each new studio is tagged makeup,
sits in a neighborhood that actually renders a page, and carries a complete
address — and that the seed's load step maps them onto the plural-slug shape the
rest of the app expects.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# (slug, expected neighborhood, a substring that must appear in the address)
NEW_MAKEUP = [
    ("gio-moros-miami-edgewater", "edgewater", "181 NE 22nd St"),
    ("mariely-resende-makeup-edgewater", "edgewater", "425 NE 22nd St"),
]

# WHY: only neighborhoods that render a real /n/ page — edgewater resolves 200,
# whereas downtown is allowed by the validator but have no page, so a
# listing placed there gets a broken neighborhood link. Keep new makeup studios
# on neighborhoods that resolve.
_RESOLVING_NEIGHBORHOODS = {
    "wynwood", "edgewater", "design-district", "brickell", "south-beach",
    "coral-gables", "coconut-grove", "little-havana", "aventura",
    "bal-harbour", "sunny-isles-beach", "key-biscayne", "midtown",
}


def _real_beauty():
    path = _BACKEND / "seed" / "_real_businesses.json"
    return json.loads(path.read_text())["beauty"]


@pytest.mark.parametrize("slug,nbhd,addr_part", NEW_MAKEUP)
def test_new_makeup_studio_is_well_formed(slug, nbhd, addr_part):
    beauty = _real_beauty()
    match = [b for b in beauty if b.get("slug") == slug]
    assert len(match) == 1, f"{slug}: expected exactly one entry, found {len(match)}"
    b = match[0]

    assert b.get("category_slug") == "makeup", f"{slug}: not tagged makeup"
    assert b.get("neighborhood_slug") == nbhd, f"{slug}: wrong neighborhood"
    assert nbhd in _RESOLVING_NEIGHBORHOODS, f"{slug}: neighborhood '{nbhd}' has no page"

    addr = b.get("address") or ""
    assert addr_part in addr, f"{slug}: address missing verified street '{addr_part}'"
    assert "FL 331" in addr, f"{slug}: address not a Miami-Dade ZIP"

    assert b.get("name"), f"{slug}: missing name"
    # instagram is how a siteless studio is reachable; every new entry has one
    assert b.get("instagram"), f"{slug}: missing instagram handle"


def test_makeup_category_now_has_at_least_four_listings():
    beauty = _real_beauty()
    makeup = [b for b in beauty if b.get("category_slug") == "makeup"]
    assert len(makeup) >= 4, (
        f"expected the Makeup category to be deepened to >=4 listings, "
        f"found {len(makeup)}: {[b['slug'] for b in makeup]}"
    )


def test_seed_load_maps_new_makeup_onto_plural_slugs():
    # WHY: the app consumes category_slugs / neighborhood_slugs (plural lists);
    # seed_miami._load_real_businesses is what reshapes the singular JSON into
    # that. Confirm the new studios survive that mapping tagged correctly.
    sm = importlib.import_module("seed.seed_miami")
    loaded = sm._load_real_businesses()["beauty"]
    by_slug = {b["slug"]: b for b in loaded}
    for slug, nbhd, _ in NEW_MAKEUP:
        assert slug in by_slug, f"{slug}: dropped by _load_real_businesses"
        b = by_slug[slug]
        assert b["category_slugs"] == ["makeup"], f"{slug}: category mapping wrong"
        assert b["neighborhood_slugs"] == [nbhd], f"{slug}: neighborhood mapping wrong"
        assert b["photo_url"], f"{slug}: no photo assigned (would render blank card)"
