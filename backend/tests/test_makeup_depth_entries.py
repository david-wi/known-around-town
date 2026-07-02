"""Validate the makeup-depth studio entries added to city seed files.

These assert the new listings are well-formed and correctly placed — the real
risk when hand-adding businesses is a typo'd neighborhood slug (orphaning the
listing) or a wrong category. Each new studio must: be tagged makeup, sit in a
neighborhood slug that actually exists in that city, carry a complete address,
and have a unique slug within its file.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# (seed module, new slug, expected neighborhood slug)
NEW_LISTINGS = [
    ("seed.seed_brickell", "mari-d-mua-beauty-studio-brickell", "brickell-ave-mary-brickell-village"),
    ("seed.seed_coral_gables", "nova-makeup-and-hair-coral-gables", "miracle-mile"),
    ("seed.seed_south_beach", "miami-beach-glam-alton-road", "lincoln-road-alton"),
]


def _businesses(mod_name):
    mod = importlib.import_module(mod_name)
    return getattr(mod, "BUSINESSES")


@pytest.mark.parametrize("mod_name,slug,nbhd", NEW_LISTINGS)
def test_new_makeup_listing_is_well_formed(mod_name, slug, nbhd):
    businesses = _businesses(mod_name)
    match = [b for b in businesses if b.get("slug") == slug]
    assert len(match) == 1, f"{slug}: expected exactly one entry, found {len(match)}"
    b = match[0]

    # tagged makeup
    assert "makeup" in b.get("category_slugs", []), f"{slug}: not tagged makeup"

    # neighborhood exists in this city (used by at least one other real listing)
    all_nbhds = {n for x in businesses for n in x.get("neighborhood_slugs", [])}
    assert nbhd in b.get("neighborhood_slugs", []), f"{slug}: wrong neighborhood"
    assert nbhd in all_nbhds, f"{slug}: neighborhood '{nbhd}' not defined in this city"

    # complete address so the listing isn't a stub
    addr = b.get("address") or {}
    for field in ("street", "city", "state", "postal_code"):
        assert addr.get(field), f"{slug}: address missing {field}"

    assert b.get("name") and b.get("website"), f"{slug}: missing name/website"


@pytest.mark.parametrize("mod_name,slug,nbhd", NEW_LISTINGS)
def test_new_makeup_slug_is_unique_in_file(mod_name, slug, nbhd):
    businesses = _businesses(mod_name)
    slugs = [b.get("slug") for b in businesses]
    assert slugs.count(slug) == 1, f"{slug}: duplicate slug in {mod_name}"
