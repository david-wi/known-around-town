"""Regression tests for network-wide nav/copy consistency fixes.

Covers three visual-consistency bugs found during a live new-visitor
self-check of the site:

  1. The Delray Beach city name carried a stray ", FL" state suffix that no
     other city had (it read "Delray Beach, FL Beauty" on the network home).
  2. Beauty city subdomains that don't override the owners-CTA copy showed the
     shorter "For Owners" instead of the standardized "For Salon Owners".
  3. The Miami (flagship) header nav labelled the lash/brow category "Lashes"
     while every other city and the category page itself use the canonical
     "Lash & Brow".
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Keep this file runnable on its own: ensure backend/ is importable.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

ADMIN_HEADERS = {"X-API-Key": "test-admin-key"}


@pytest.fixture
def client(seeded_db):
    """TestClient over the seeded app (mirrors the fixture in test_smoke.py)."""
    from app.main import app

    return TestClient(app)


def test_no_city_display_name_carries_a_state_suffix():
    """Bug #1: no city's display name may end in a ", XX" state suffix. Delray
    Beach read "Delray Beach, FL" on the network home while every other city was
    bare. This guards the whole network against reintroducing a state suffix on
    any city, now or in future."""
    seed_dir = _BACKEND / "seed"
    offenders = []
    for path in sorted(seed_dir.glob("seed_*.py")):
        mod = importlib.import_module(f"seed.{path.stem}")
        name = getattr(mod, "CITY_NAME", None)
        if isinstance(name, str) and re.search(r",\s*[A-Z]{2}$", name.strip()):
            offenders.append((path.name, name))
    assert not offenders, f"City names with a stray state suffix: {offenders}"


def test_miami_beauty_nav_uses_canonical_lash_brow_label():
    """Bug #3: the Miami beauty header nav must label the lash/brow category
    with the canonical "Lash & Brow" (matching the network category name and the
    category page it links to), not the divergent "Lashes"."""
    from seed.seed_miami import NETWORK_CITY_CONFIG

    labels = dict(NETWORK_CITY_CONFIG["beauty"]["header_nav"])
    assert labels.get("lash-brow") == "Lash & Brow", labels.get("lash-brow")


def test_owners_cta_default_is_for_salon_owners(client, seeded_db):
    """Bug #2: a beauty city that does NOT override the owners-CTA copy must fall
    through to the standardized "For Salon Owners" default (previously the
    shorter "For Owners"). We clear Miami beauty's seeded value to exercise the
    route's default directly.

    The assertion matches the rendered anchor text exactly because "For Owners"
    is a substring of "For Salon Owners" — a bare substring check would pass even
    if the bug were present.
    """
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )

    # Remove the seeded explicit value so the route falls through to its default.
    deleted = asyncio.run(
        seeded_db.copy_blocks.delete_many({"key": "header.owners_cta"})
    )
    assert deleted.deleted_count >= 1

    # Belt-and-suspenders: drop the in-process nav TTL cache so the render reads
    # the now-empty DB (editable copy is read per-request, but this is cheap).
    from app.services import content as _content

    _content.clear_nav_cache()

    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    assert ">For Salon Owners</a>" in r.text
    assert ">For Owners</a>" not in r.text
