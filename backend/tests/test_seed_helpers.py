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
