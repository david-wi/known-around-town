"""Tests for seed/_helpers.py — upsert behavior.

WHY a separate file: test_seed_target_guard.py covers the production guard;
these tests cover the upsert helper's data-preservation contract.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("MONGODB_URL", "mongodb://test")
os.environ.setdefault("MONGODB_DATABASE", "wkl_test")
os.environ.setdefault("NETWORK_DOMAINS", "beauty:knowsbeauty.localhost")
os.environ.setdefault("PREVIEW_MODE_ENABLED", "false")

from seed._helpers import upsert


@pytest.fixture
def db(mock_db):
    return mock_db


@pytest.mark.asyncio
async def test_upsert_preserves_archived_status(db):
    """A manually archived business must stay archived when the seed re-runs.

    WHY: the seed runs nightly. Without this guard, every confirmed-closed
    business reappeared live on the directory after midnight.
    """
    await db.businesses.insert_one({"_id": "biz-1", "slug": "closed-spa", "status": "archived", "name": "Closed Spa"})

    # Seed tries to re-insert as live
    await upsert("businesses", {"slug": "closed-spa"}, {"slug": "closed-spa", "name": "Closed Spa", "status": "live", "created_at": None})

    doc = await db.businesses.find_one({"slug": "closed-spa"})
    assert doc["status"] == "archived", "Seed must not overwrite archived status with live"


@pytest.mark.asyncio
async def test_upsert_does_not_block_other_status_transitions(db):
    """Non-archived statuses (claimed, live) are updated normally by the seed."""
    await db.businesses.insert_one({"_id": "biz-2", "slug": "open-salon", "status": "live", "name": "Open Salon"})

    await upsert("businesses", {"slug": "open-salon"}, {"slug": "open-salon", "name": "Open Salon Updated", "status": "live", "created_at": None})

    doc = await db.businesses.find_one({"slug": "open-salon"})
    assert doc["name"] == "Open Salon Updated"
    assert doc["status"] == "live"


@pytest.mark.asyncio
async def test_upsert_inserts_new_documents(db):
    """A business not yet in the database is inserted fresh."""
    await upsert("businesses", {"slug": "new-salon"}, {"slug": "new-salon", "name": "New Salon", "status": "live", "created_at": None})

    doc = await db.businesses.find_one({"slug": "new-salon"})
    assert doc is not None
    assert doc["name"] == "New Salon"
    assert doc["status"] == "live"


@pytest.mark.asyncio
async def test_upsert_preserves_id_and_created_at(db):
    """_id and created_at must not change on re-seed."""
    from datetime import datetime, timezone
    original_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await db.businesses.insert_one({"_id": "stable-id", "slug": "stable-salon", "status": "live", "created_at": original_ts})

    await upsert("businesses", {"slug": "stable-salon"}, {"slug": "stable-salon", "name": "Updated", "status": "live", "created_at": None})

    doc = await db.businesses.find_one({"slug": "stable-salon"})
    assert doc["_id"] == "stable-id"
    # WHY: mongomock strips tzinfo on roundtrip; compare naive values to
    # test the invariant that created_at is preserved, not its tz-awareness.
    stored = doc["created_at"].replace(tzinfo=None) if doc["created_at"] else None
    assert stored == original_ts.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_upsert_preserves_existing_city_hero_photo_when_seed_omits_it(db):
    """A hero photo set on a city must survive a re-seed that doesn't provide one.

    Regression: most per-city seeds don't set a city hero photo, so a hero set
    later (in the DB/admin) was wiped on every re-seed and the homepage city card
    fell back to an empty capsule. The upsert must keep the existing hero.
    """
    await db.cities.insert_one(
        {"_id": "c1", "slug": "aventura", "name": "Aventura", "status": "live",
         "hero_photo_url": "https://images.unsplash.com/photo-keep?w=1600", "created_at": None}
    )
    # Re-seed doc omits hero_photo_url entirely (the common case).
    await upsert("cities", {"slug": "aventura"},
                 {"slug": "aventura", "name": "Aventura", "status": "live", "created_at": None})

    doc = await db.cities.find_one({"slug": "aventura"})
    assert doc["hero_photo_url"] == "https://images.unsplash.com/photo-keep?w=1600"


@pytest.mark.asyncio
async def test_upsert_preserves_existing_city_hero_photo_when_seed_passes_blank(db):
    """An existing hero must NOT be overwritten by a seed that passes an empty
    string (seed_hallandale_beach passes hero_photo_url="" when it has no photo)."""
    await db.cities.insert_one(
        {"_id": "c2", "slug": "boca-raton", "name": "Boca Raton", "status": "live",
         "hero_photo_url": "https://images.unsplash.com/photo-real?w=1600", "created_at": None}
    )
    await upsert("cities", {"slug": "boca-raton"},
                 {"slug": "boca-raton", "name": "Boca Raton", "status": "live",
                  "hero_photo_url": "", "created_at": None})

    doc = await db.cities.find_one({"slug": "boca-raton"})
    assert doc["hero_photo_url"] == "https://images.unsplash.com/photo-real?w=1600"


@pytest.mark.asyncio
async def test_upsert_lets_seed_set_a_real_hero_photo(db):
    """When the seed DOES provide a real hero photo, it is used (not blocked)."""
    await db.cities.insert_one(
        {"_id": "c3", "slug": "miami", "name": "Miami", "status": "live",
         "hero_photo_url": "https://images.unsplash.com/old?w=1600", "created_at": None}
    )
    await upsert("cities", {"slug": "miami"},
                 {"slug": "miami", "name": "Miami", "status": "live",
                  "hero_photo_url": "https://images.unsplash.com/new?w=1600", "created_at": None})

    doc = await db.cities.find_one({"slug": "miami"})
    assert doc["hero_photo_url"] == "https://images.unsplash.com/new?w=1600"


def test_seeded_footer_cross_links_use_canonical_hosts():
    """Footer 'Also in <city>' cross-links must point at hosts that are actually
    served, not a bare slug that has no certificate.

    Regression: the Miami edition seeded footer_also_in_url as
    https://boca.knowsbeauty.com — a host with no valid TLS cert that dead-ends
    the visitor on a browser security warning. The live Boca edition is served at
    boca-raton.knowsbeauty.com. A broken cross-link in the footer of every page
    is a trust defect, so guard the seeded value.
    """
    from seed.seed_miami import NETWORK_CITY_CONFIG

    for network_slug, cfg in NETWORK_CITY_CONFIG.items():
        url = cfg.get("footer_also_in_url", "")
        if not url:
            continue
        # The known-broken bare-boca host must never be seeded again.
        assert "//boca.knowsbeauty" not in url, (
            f"{network_slug}: footer_also_in_url points at the broken "
            f"boca.knowsbeauty host: {url!r}"
        )
        # Sanity: any seeded cross-link must be an https knowsbeauty URL.
        assert url.startswith("https://") and "knowsbeauty" in url, (
            f"{network_slug}: footer_also_in_url is not a valid knowsbeauty "
            f"https URL: {url!r}"
        )
