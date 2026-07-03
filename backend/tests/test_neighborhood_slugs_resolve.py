"""Guard against salons pointing at a neighborhood that has no page.

Each Miami salon in seed/_real_businesses.json carries a neighborhood_slug. The
site only builds a neighborhood page for the slugs in seed_miami.NEIGHBORHOODS.
If a salon's slug isn't one of those, the salon silently drops off neighborhood
browse and its neighborhood label doesn't render — it looks half-listed. This
bit the four Sunny Isles salons, which were tagged "sunny-isles" while the page
lives at "sunny-isles-beach" (same place, two spellings), so none of them showed
up on the Sunny Isles page.

This test locks the fix in and stops a new mismatch from creeping in.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _featured_beauty_slugs() -> set[str]:
    sm = importlib.import_module("seed.seed_miami")
    return {t[0] for t in sm.NEIGHBORHOODS["beauty"]}


def _real_beauty():
    return json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())["beauty"]


# WHY: neighborhoods that real salons point at but that have no page yet. Adding
# them is a product/curation call (they'd become featured on the city home), so
# they're surfaced to the team rather than silently tolerated. Remove a slug from
# here once its page is created — the test will then require it to resolve.
KNOWN_UNFEATURED_PENDING: set[str] = set()


def test_sunny_isles_salons_use_the_slug_that_has_a_page():
    beauty = _real_beauty()
    sunny = [b for b in beauty if "sunny-isles" in (b.get("neighborhood_slug") or "")]
    assert sunny, "expected Sunny Isles salons in the seed"
    for b in sunny:
        assert b["neighborhood_slug"] == "sunny-isles-beach", (
            f"{b['slug']}: tagged '{b['neighborhood_slug']}' but the page is 'sunny-isles-beach'"
        )


def test_no_new_orphaned_neighborhood_slugs():
    featured = _featured_beauty_slugs()
    allowed = featured | KNOWN_UNFEATURED_PENDING
    orphans = {
        b["slug"]: b["neighborhood_slug"]
        for b in _real_beauty()
        if b.get("neighborhood_slug") not in allowed
    }
    assert not orphans, (
        "these salons point at a neighborhood with no page and no pending decision "
        f"(fix the slug or add the neighborhood): {orphans}"
    )
