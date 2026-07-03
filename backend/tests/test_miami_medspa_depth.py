"""Validate the med-spa studios added to deepen the thin Miami med-spa category.

Med spas (injectables, laser, medical-grade skin) are premium, high-spend
businesses — good directory anchors and strong paid-listing prospects. The
category had only four listings, all in Aventura/Bal Harbour/Design District,
none in the core. These entries add verified real med spas in Brickell,
Edgewater, Coral Gables, Coconut Grove, and South Beach. Each was vetted to a
real, resolving website (the reliable signal that separates real listings from
fabricated ones), so every new entry must carry a website and sit in a
neighborhood that renders a page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# (slug, neighborhood, address substring)
NEW_MEDSPAS = [
    ("zeugma-medspa-edgewater", "edgewater", "501 NE 31st St"),
    ("the-plump-room-coral-gables", "coral-gables", "147 Alhambra Circle"),
    ("ject-medical-aesthetics-south-beach", "south-beach", "1916 Bay Rd"),
]
# NOTE: three originally-added med spas (Miami Skin Spa, Lavish Laser, Brickell
# Cosmetic Center) were removed after they turned out to duplicate businesses
# already in the live directory under different slugs. Lesson: dedupe new
# businesses against the whole live catalog (subdomain seed files + DB records),
# not just this JSON's slugs.

# Neighborhoods that render a real /n/ page (avoid orphaning a listing).
_RESOLVING = {
    "wynwood", "edgewater", "design-district", "brickell", "south-beach",
    "coral-gables", "coconut-grove", "little-havana", "aventura",
    "bal-harbour", "sunny-isles-beach", "key-biscayne", "midtown",
}


def _beauty():
    return json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())["beauty"]


@pytest.mark.parametrize("slug,nbhd,addr_part", NEW_MEDSPAS)
def test_new_medspa_is_well_formed(slug, nbhd, addr_part):
    match = [b for b in _beauty() if b.get("slug") == slug]
    assert len(match) == 1, f"{slug}: expected one entry, found {len(match)}"
    b = match[0]
    assert b.get("category_slug") == "med-spa", f"{slug}: not tagged med-spa"
    assert b.get("neighborhood_slug") == nbhd, f"{slug}: wrong neighborhood"
    assert nbhd in _RESOLVING, f"{slug}: neighborhood '{nbhd}' has no page"
    assert addr_part in (b.get("address") or ""), f"{slug}: address missing '{addr_part}'"
    # every med-spa here was vetted to a real resolving website — require one
    assert b.get("website", "").startswith("http"), f"{slug}: missing website"


def test_medspa_category_deepened():
    # 4 original + 3 genuinely-new (the 3 duplicates were removed).
    medspas = [b for b in _beauty() if b.get("category_slug") == "med-spa"]
    assert len(medspas) >= 7, (
        f"expected med-spa >=7, found {len(medspas)}: {[b['slug'] for b in medspas]}"
    )


def test_no_duplicate_business_name_within_real_businesses():
    # WHY: PR #473 added med spas that duplicated existing businesses (same name +
    # address, different slug). An address-only check false-positives on real
    # multi-tenant buildings (a mall can hold several salons), so guard on the
    # normalized business NAME instead — two listings with the same name in this
    # file is the real duplicate signal.
    # Key on (normalized name + street number). A chain repeats the name at a
    # DIFFERENT address; a mall repeats the address under a DIFFERENT name. Only a
    # true duplicate matches on BOTH, so this stays false-positive-free.
    import re

    def name_key(name):
        return re.sub(r"[^a-z0-9]+", "", re.sub(r"&", "and", (name or "").lower()))

    def street_no(addr):
        m = re.match(r"\s*(\d+)", addr or "")
        return m.group(1) if m else ""

    seen = {}
    dups = []
    for b in _beauty():
        key = (name_key(b.get("name"))[:12], street_no(b.get("address")))
        if all(key) and key in seen:
            dups.append((seen[key], b["slug"]))
        else:
            seen[key] = b["slug"]
    assert not dups, f"same business listed twice in _real_businesses.json: {dups}"
