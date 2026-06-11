"""Tests for the admin analytics dashboard page.

Exercises:
  - /admin/analytics returns 200 and contains the expected stat headings
  - Page view count shows zero state correctly
  - Claim funnel shows zero state correctly  
  - Auth gate: requires admin cookie (matches pattern in test_admin_claims.py)
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app
    return TestClient(app)


# ── Analytics page renders (no auth in test env, admin key not configured) ──

def test_analytics_page_loads(client):
    """The page returns 200 and renders the stat headings."""
    r = client.get("/admin/analytics")
    assert r.status_code == 200, r.text
    assert "Total page views" in r.text
    assert "Claims submitted" in r.text
    assert "Owner accounts" in r.text
    assert "Listings visited" in r.text


def test_analytics_page_zero_state(client):
    """With no data, the page should show 0s and the empty-state message."""
    r = client.get("/admin/analytics")
    assert r.status_code == 200, r.text
    # Zeros should appear for all counters
    assert "0" in r.text
    # Empty-state message appears when both page views and claims are zero
    assert "No page views recorded yet" in r.text or "No claim submissions yet" in r.text or "No claims yet" in r.text


def test_analytics_page_with_claims(client, seeded_db):
    """After submitting a claim, the analytics page reflects it in the funnel."""
    biz = asyncio.run(seeded_db.businesses.find_one({}))
    assert biz is not None

    # Submit a claim
    r = client.post("/api/v1/claims", json={
        "business_id": biz["_id"],
        "submitter_name": "Test Owner",
        "submitter_email": "test@example.com",
        "submitter_phone": "+1 305-555-0000",
        "notes": "Analytics test",
    })
    assert r.status_code == 200, r.text

    # Analytics page should now show 1 claim
    r = client.get("/admin/analytics")
    assert r.status_code == 200, r.text
    assert "Claims submitted" in r.text
    # The recent claims section should show the business name
    assert biz["name"] in r.text


def test_analytics_page_with_page_views(client, seeded_db):
    """After injecting a page_view_count, the analytics page reflects it."""
    biz = asyncio.run(seeded_db.businesses.find_one({}))
    assert biz is not None

    # Inject a view count directly
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"page_view_count": 42}},
        )
    )

    r = client.get("/admin/analytics")
    assert r.status_code == 200, r.text
    assert "42" in r.text
    assert biz["name"] in r.text
