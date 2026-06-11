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
