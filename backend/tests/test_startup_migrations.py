"""Tests for one-time startup data migrations (app.database.run_startup_migrations)."""

from __future__ import annotations

import pytest

from app import database


@pytest.mark.asyncio
async def test_migration_resets_editorial_verified_to_unclaimed(mock_db):
    """Businesses seeded as 'verified' by editorial staff (no real owner claim)
    should be reset to 'unclaimed' so the Claim CTA shows on their listing page."""
    # Seed two businesses tagged verified by the seeder — no entries in business_claims.
    await mock_db.businesses.insert_many(
        [
            {"_id": "biz-a", "name": "Salon A", "claim_status": "verified"},
            {"_id": "biz-b", "name": "Salon B", "claim_status": "verified"},
        ]
    )

    await database.run_startup_migrations()

    a = await mock_db.businesses.find_one({"_id": "biz-a"})
    b = await mock_db.businesses.find_one({"_id": "biz-b"})
    assert a["claim_status"] == "unclaimed"
    assert b["claim_status"] == "unclaimed"


@pytest.mark.asyncio
async def test_migration_preserves_real_owner_claim(mock_db):
    """A business where a real owner went through the claim flow keeps 'verified'."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-real", "name": "Claimed Spa", "claim_status": "verified"}
    )
    # Real claim entry — mirrors what the claim-approval flow writes.
    await mock_db.business_claims.insert_one(
        {"_id": "claim-1", "business_id": "biz-real", "status": "verified"}
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-real"})
    assert biz["claim_status"] == "verified"


@pytest.mark.asyncio
async def test_migration_is_guarded_and_runs_only_once(mock_db):
    """Running the migration twice should not change anything on the second run."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-once", "name": "Once Salon", "claim_status": "verified"}
    )

    await database.run_startup_migrations()

    # Manually flip back to "verified" to simulate a re-insertion.
    await mock_db.businesses.update_one(
        {"_id": "biz-once"}, {"$set": {"claim_status": "verified"}}
    )

    # Second run: migration guard is in place, should not reset again.
    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-once"})
    # Still "verified" because the guard blocked the second run.
    assert biz["claim_status"] == "verified"


@pytest.mark.asyncio
async def test_migration_records_reset_count(mock_db):
    """The migration log entry should record how many businesses were reset."""
    await mock_db.businesses.insert_many(
        [
            {"_id": "biz-x", "name": "X", "claim_status": "verified"},
            {"_id": "biz-y", "name": "Y", "claim_status": "verified"},
        ]
    )

    await database.run_startup_migrations()

    record = await mock_db.app_migrations.find_one(
        {"_id": "reset-editorial-verified-to-unclaimed-20260611"}
    )
    assert record is not None
    assert record["reset_count"] == 2


# ---------------------------------------------------------------------------
# publish-all-draft-businesses-20260611
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_publishes_draft_businesses(mock_db):
    """Businesses stuck on the default 'draft' status become 'live' so they
    appear in search results, the sitemap, and the claim form directory."""
    await mock_db.businesses.insert_many(
        [
            {"_id": "biz-draft-1", "name": "Draft Salon 1", "status": "draft"},
            {"_id": "biz-draft-2", "name": "Draft Salon 2", "status": "draft"},
        ]
    )

    await database.run_startup_migrations()

    b1 = await mock_db.businesses.find_one({"_id": "biz-draft-1"})
    b2 = await mock_db.businesses.find_one({"_id": "biz-draft-2"})
    assert b1["status"] == "live"
    assert b2["status"] == "live"


@pytest.mark.asyncio
async def test_migration_does_not_touch_live_businesses(mock_db):
    """Businesses already 'live' are left unchanged."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-already-live", "name": "Live Salon", "status": "live"}
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-already-live"})
    assert biz["status"] == "live"


@pytest.mark.asyncio
async def test_migration_does_not_publish_archived_businesses(mock_db):
    """Businesses intentionally 'archived' must not be promoted to 'live'."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-archived", "name": "Closed Spa", "status": "archived"}
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-archived"})
    assert biz["status"] == "archived"


@pytest.mark.asyncio
async def test_migration_publish_draft_guard_runs_only_once(mock_db):
    """The guard record prevents the migration from running a second time."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-guard", "name": "Guard Salon", "status": "draft"}
    )

    await database.run_startup_migrations()

    # Flip back to draft to simulate a re-run scenario.
    await mock_db.businesses.update_one(
        {"_id": "biz-guard"}, {"$set": {"status": "draft"}}
    )

    # Second run — guard should block, business stays draft.
    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-guard"})
    assert biz["status"] == "draft"


@pytest.mark.asyncio
async def test_migration_publish_records_count(mock_db):
    """The migration log entry records how many businesses were promoted."""
    await mock_db.businesses.insert_many(
        [
            {"_id": "biz-p1", "name": "P1", "status": "draft"},
            {"_id": "biz-p2", "name": "P2", "status": "draft"},
            {"_id": "biz-p3", "name": "P3", "status": "live"},
        ]
    )

    await database.run_startup_migrations()

    record = await mock_db.app_migrations.find_one(
        {"_id": "publish-all-draft-businesses-20260611"}
    )
    assert record is not None
    # Only the 2 draft businesses should have been promoted.
    assert record["published_count"] == 2


# ---------------------------------------------------------------------------
# clear-seeded-founding-partner-flags-20260611
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_clears_fake_founding_partner_flags(mock_db):
    """A business flagged by seed data (no payment, no verified claim) should
    have is_founding_partner removed so the pricing page spot count is accurate."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-fake-fp", "name": "Demo Salon", "is_founding_partner": True}
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-fake-fp"})
    # The field should be unset (missing), not just False.
    assert "is_founding_partner" not in biz or not biz.get("is_founding_partner")


@pytest.mark.asyncio
async def test_migration_preserves_founding_partner_for_paying_subscriber(mock_db):
    """A business that paid via Stripe checkout (stripe_customer_id set) keeps
    the badge — even if their subscription was later cancelled."""
    await mock_db.businesses.insert_one(
        {
            "_id": "biz-paid",
            "name": "Paying Salon",
            "is_founding_partner": True,
            "stripe_customer_id": "cus_abc123",
            # stripe_subscription_id may be absent after cancellation — that is OK.
        }
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-paid"})
    assert biz.get("is_founding_partner") is True


@pytest.mark.asyncio
async def test_migration_preserves_founding_partner_for_verified_claimer(mock_db):
    """A business whose owner went through the admin claim verification flow
    legitimately earned the badge and should keep it."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-claimed", "name": "Claimed Salon", "is_founding_partner": True}
    )
    await mock_db.business_claims.insert_one(
        {"_id": "claim-fp", "business_id": "biz-claimed", "status": "verified"}
    )

    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-claimed"})
    assert biz.get("is_founding_partner") is True


@pytest.mark.asyncio
async def test_migration_clear_fp_guard_runs_only_once(mock_db):
    """The idempotency guard prevents re-clearing on a second startup."""
    await mock_db.businesses.insert_one(
        {"_id": "biz-fp-once", "name": "Once Salon", "is_founding_partner": True}
    )

    await database.run_startup_migrations()

    # Manually re-set the flag to simulate a seed accident after migration ran.
    await mock_db.businesses.update_one(
        {"_id": "biz-fp-once"}, {"$set": {"is_founding_partner": True}}
    )

    # Second run — migration guard should block; flag stays True.
    await database.run_startup_migrations()

    biz = await mock_db.businesses.find_one({"_id": "biz-fp-once"})
    assert biz.get("is_founding_partner") is True


@pytest.mark.asyncio
async def test_migration_clear_fp_records_count(mock_db):
    """The migration log entry records how many fake badges were cleared."""
    await mock_db.businesses.insert_many(
        [
            {"_id": "biz-fp-a", "name": "Fake FP 1", "is_founding_partner": True},
            {"_id": "biz-fp-b", "name": "Fake FP 2", "is_founding_partner": True},
            # This one has a customer ID — should be preserved, not counted.
            {
                "_id": "biz-fp-c",
                "name": "Real FP",
                "is_founding_partner": True,
                "stripe_customer_id": "cus_xyz",
            },
        ]
    )

    await database.run_startup_migrations()

    record = await mock_db.app_migrations.find_one(
        {"_id": "clear-seeded-founding-partner-flags-20260611"}
    )
    assert record is not None
    assert record["cleared_count"] == 2
