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

from seed._helpers import preserve_existing_business_state, upsert
from seed import seed_miami


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


@pytest.mark.asyncio
async def test_miami_reseed_preserves_operational_state_on_custom_path(seeded_db):
    """A Miami re-seed must not erase state written after the source snapshot.

    The custom Miami business loop replaces existing documents wholesale. The
    source owns editorial fields, but claims, paid visibility, voice
    provisioning, lifecycle state, and counters belong to the live record.
    """
    # @define-test KAT-052 "Miami re-seeding preserves live operational state"
    network = await seeded_db.networks.find_one({"slug": "beauty"})
    source_row = next(
        row
        for row in seed_miami.BUSINESSES_PER_NETWORK["beauty"]
        if not row.get("premium")
    )
    existing = await seeded_db.businesses.find_one(
        {"network_id": network["_id"], "slug": source_row["slug"]}
    )
    assert existing is not None
    existing_id = existing["_id"]
    existing_created_at = existing["created_at"]

    operational = {
        "status": "archived",
        "claim_status": "verified",
        "claimed_email": "owner@example.com",
        "facebook": "https://facebook.example/owner",
        "featured": {"enabled": True, "tier": "concierge"},
        "voice_phone_number": "(669) 232-8894",
        "vapi_phone_number_id": "phone_test_123",
        "vapi_assistant_id": "assistant_test_123",
        "page_view_count": 17,
        "mkb_referred_view_count": 5,
        "call_click_count": 3,
        "directions_click_count": 2,
        "website_click_count": 4,
    }
    await seeded_db.businesses.update_one(
        {"_id": existing["_id"]},
        {"$set": operational},
    )

    await seed_miami.main()

    reseeded = await seeded_db.businesses.find_one({"_id": existing["_id"]})
    assert reseeded["_id"] == existing_id
    assert reseeded["created_at"] == existing_created_at
    for field, expected in operational.items():
        assert reseeded[field] == expected, f"re-seed erased {field}"

    # The control row must remain one stable listing across repeated Miami
    # replacement runs, just like each satellite canary row.
    await seed_miami.main()
    reseeded_again = await seeded_db.businesses.find_one({"_id": existing_id})
    assert reseeded_again["_id"] == existing_id
    assert reseeded_again["created_at"] == existing_created_at
    assert await seeded_db.businesses.count_documents(
        {"network_id": network["_id"], "slug": source_row["slug"]}
    ) == 1


def test_shared_business_preservation_policy_keeps_present_state_only():
    """The satellite boundary preserves live fields without inventing absent ones."""
    existing = {
        "_id": "stable",
        "created_at": "old-created-at",
        "status": "archived",
        "claim_status": "verified",
        "claimed_email": "owner@example.com",
        "claimed_at": "claimed-at",
        "stripe_customer_id": "cus-existing",
        "stripe_subscription_id": "sub-existing",
        "featured": {"enabled": True, "tier": "premium"},
        "voice_phone_number": "(669) 232-8894",
        "vapi_phone_number_id": "phone-existing",
        "vapi_assistant_id": "assistant-existing",
        "is_founding_partner": True,
        "google_place_id": "place-existing",
        "google_rating": 4.9,
        "google_review_count": 321,
        "page_view_count": 17,
        "mkb_referred_view_count": 5,
        "call_click_count": 3,
        "directions_click_count": 2,
        "website_click_count": 4,
        "phone": "owner-phone",
        "website": "https://owner.example",
        "instagram": "@owner",
        "socials": {"instagram": "@owner", "facebook": "https://facebook.example"},
        "hours": [{"day": "Mon", "open": "10:00", "close": "18:00"}],
        "services": [{"name": "Owner service"}],
        "photos": [
            {"url": "https://old-seed.example/photo.jpg"},
            {"url": "/media/owner-photo", "is_hero": True},
        ],
    }
    seed_doc = {
        "name": "Refreshed source name",
        "phone": "new-source-phone",
        "website": "https://new-source.example",
        "instagram": "@new-source",
        "featured": {"enabled": False, "tier": "free"},
        "status": "live",
        "photos": [{"url": "https://new-seed.example/photo.jpg"}],
        "hours": [],
        "services": [],
    }

    preserve_existing_business_state(existing, seed_doc)

    assert seed_doc["name"] == "Refreshed source name"
    assert seed_doc["status"] == "archived"
    assert seed_doc["featured"] == existing["featured"]
    for field in (
        "claim_status", "claimed_email", "claimed_at", "stripe_customer_id",
        "stripe_subscription_id", "voice_phone_number", "vapi_phone_number_id",
        "vapi_assistant_id", "is_founding_partner", "google_place_id",
        "google_rating", "google_review_count", "page_view_count",
        "mkb_referred_view_count", "call_click_count", "directions_click_count",
        "website_click_count", "phone", "website", "instagram", "socials",
        "hours", "services",
    ):
        assert seed_doc[field] == existing[field]
    assert {photo["url"] for photo in seed_doc["photos"]} == {
        "https://new-seed.example/photo.jpg",
        "/media/owner-photo",
    }
    # The source cannot manufacture state that was absent from the live record.
    assert "google_rating_synced_at" not in seed_doc
    assert "nonexistent_operational_field" not in seed_doc


def test_shared_business_preservation_does_not_replace_source_contact_with_null():
    """Null legacy contact values leave fresh source contact/social values intact."""
    existing = {
        "claim_status": "claimed",
        "phone": None,
        "website": None,
        "instagram": None,
        "socials": {"facebook": "https://facebook.example/owner"},
    }
    seed_doc = {
        "phone": "source-phone",
        "website": "https://source.example",
        "instagram": "@source",
        "socials": {"instagram": "@source"},
    }

    preserve_existing_business_state(existing, seed_doc)

    assert seed_doc["phone"] == "source-phone"
    assert seed_doc["website"] == "https://source.example"
    assert seed_doc["instagram"] == "@source"
    assert seed_doc["socials"] == {
        "instagram": "@source",
        "facebook": "https://facebook.example/owner",
    }

    # Optional source fields omitted by a later snapshot do not erase newer
    # values that are already present in the live document.
    absent_source = {"name": "Another source refresh", "photos": []}
    preserve_existing_business_state(
        {"website": "https://newer-source.example", "address": {"street": "Newer"}},
        absent_source,
    )
    assert absent_source["website"] == "https://newer-source.example"
    assert absent_source["address"] == {"street": "Newer"}


def test_shared_business_preservation_treats_claimed_boolean_as_owner_state():
    """Legacy claimed=True records keep owner-edited contact fields."""
    existing = {
        "claimed": True,
        "phone": "(305) 555-0199",
        "website": "https://owner.example/legacy",
        "instagram": "@legacy-owner",
        "socials": {"instagram": "@legacy-owner"},
    }
    seed_doc = {
        "phone": "(305) 555-0100",
        "website": "https://source.example",
        "instagram": "@source",
        "socials": {"instagram": "@source"},
    }

    preserve_existing_business_state(existing, seed_doc)

    assert seed_doc["phone"] == existing["phone"]
    assert seed_doc["website"] == existing["website"]
    assert seed_doc["instagram"] == existing["instagram"]
    assert seed_doc["socials"] == existing["socials"]


def test_shared_business_preservation_refreshes_legacy_editorial_description():
    """Legacy city source descriptions remain source-owned by default."""
    existing = {"description": "old editorial copy"}
    seed_doc = {"description": "fresh editorial copy"}

    preserve_existing_business_state(existing, seed_doc)

    assert seed_doc["description"] == "fresh editorial copy"


def test_miami_can_opt_into_existing_description_override():
    """Miami keeps its established owner/editor description override explicitly."""
    existing = {"description": "owner-approved copy"}
    seed_doc = {"description": "source copy"}

    preserve_existing_business_state(existing, seed_doc, preserve_description=True)

    assert seed_doc["description"] == "owner-approved copy"


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
