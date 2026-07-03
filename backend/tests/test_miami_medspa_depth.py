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
    ("miami-skin-spa-brickell", "brickell", "1501 S Miami Ave"),
    ("brickell-cosmetic-center-brickell", "brickell", "2730 SW 3rd Ave"),
    ("zeugma-medspa-edgewater", "edgewater", "501 NE 31st St"),
    ("the-plump-room-coral-gables", "coral-gables", "147 Alhambra Circle"),
    ("lavish-laser-medspa-coconut-grove", "coconut-grove", "3160 Florida Ave"),
    ("ject-medical-aesthetics-south-beach", "south-beach", "1916 Bay Rd"),
]

# Neighborhoods that render a real /n/ page (avoid orphaning a listing).
_RESOLVING = {
    "wynwood", "edgewater", "design-district", "brickell", "south-beach",
    "coral-gables", "coconut-grove", "little-havana", "aventura",
    "bal-harbour", "sunny-isles-beach", "key-biscayne",
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


def test_medspa_category_deepened_to_at_least_ten():
    medspas = [b for b in _beauty() if b.get("category_slug") == "med-spa"]
    assert len(medspas) >= 10, (
        f"expected med-spa deepened to >=10, found {len(medspas)}: "
        f"{[b['slug'] for b in medspas]}"
    )
