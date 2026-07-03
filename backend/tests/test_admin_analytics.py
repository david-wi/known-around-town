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

ADMIN_HEADERS = {"X-API-Key": "test-admin-key"}


@pytest.fixture
def client(seeded_db):
    from app.main import app
    return TestClient(app)


# ── Analytics page renders with explicit admin auth ──

def test_analytics_page_loads(client):
    """The page returns 200 and renders the stat headings."""
    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert "Total page views" in r.text
    assert "Claims submitted" in r.text
    assert "Owner accounts" in r.text
    assert "Listings visited" in r.text


def test_analytics_page_zero_state(client):
    """With no data, the page should show 0s and the empty-state message."""
    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
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
    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert "Claims submitted" in r.text
    # The recent claims section should show the business name
    assert biz["name"] in r.text


def test_analytics_recent_claims_show_outreach_source(client, seeded_db):
    """Outreach-tagged claims should expose their source in the admin funnel."""
    biz = asyncio.run(seeded_db.businesses.find_one({}))
    assert biz is not None

    r = client.post("/api/v1/claims", json={
        "business_id": biz["_id"],
        "submitter_name": "Source Owner",
        "submitter_email": "source@example.com",
        "claim_source": "first-send-v3",
        "claim_ref": "trini-direct",
        "utm_source": "david-email",
        "utm_medium": "email",
        "utm_campaign": "first-send",
    })
    assert r.status_code == 200, r.text

    saved = asyncio.run(seeded_db.business_claims.find_one({"_id": r.json()["_id"]}))
    assert saved["claim_source"] == "first-send-v3"
    assert saved["claim_ref"] == "trini-direct"
    assert saved["utm_source"] == "david-email"
    assert saved["utm_medium"] == "email"
    assert saved["utm_campaign"] == "first-send"

    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert "Source:" in r.text
    assert "first-send-v3" in r.text
    assert "trini-direct" in r.text
    assert "david-email" in r.text


def test_analytics_counts_verified_claims_as_approved(client, seeded_db):
    """A verified claim should move from pending to the approved funnel count."""
    biz = asyncio.run(seeded_db.businesses.find_one({}))
    assert biz is not None

    r = client.post("/api/v1/claims", json={
        "business_id": biz["_id"],
        "submitter_name": "Verified Owner",
        "submitter_email": "verified@example.com",
        "submitter_phone": "+1 305-555-0000",
        "notes": "Analytics verified-count test",
    })
    assert r.status_code == 200, r.text
    claim = r.json()

    r = client.post(f"/api/v1/claims/{claim['_id']}/verify", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text

    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert "0 pending · 1 approved" in r.text


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

    r = client.get("/admin/analytics", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert "42" in r.text
    assert biz["name"] in r.text


def test_analytics_top_listing_links_use_listing_city_host(client, seeded_db):
    """Cross-city top listings should not link to the admin page's current city."""
    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    assert network is not None
    city = {
        "_id": "city-hollywood-admin-analytics",
        "network_id": network["_id"],
        "slug": "hollywood",
        "name": "Hollywood",
        "status": "live",
    }
    biz = {
        "_id": "biz-hollywood-admin-analytics",
        "network_id": network["_id"],
        "city_id": city["_id"],
        "name": "Hollywood Test Salon",
        "slug": "hollywood-test-salon",
        "neighborhood": "Hollywood",
        "status": "live",
        "page_view_count": 99,
    }
    asyncio.run(seeded_db.cities.insert_one(city))
    asyncio.run(seeded_db.businesses.insert_one(biz))

    r = client.get(
        "/admin/analytics",
        headers={**ADMIN_HEADERS, "host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert 'href="http://hollywood.knowsbeauty.localhost/b/hollywood-test-salon"' in r.text
    assert 'href="/b/hollywood-test-salon"' not in r.text

    r = client.get(
        "/admin/analytics",
        headers={**ADMIN_HEADERS, "host": "knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert 'href="http://hollywood.knowsbeauty.localhost/b/hollywood-test-salon"' in r.text


def test_analytics_page_listing_link_is_absolute(client, seeded_db):
    """Business listings in the top-views table should link to absolute URLs (with city subdomain)."""
    biz = asyncio.run(seeded_db.businesses.find_one({}))
    assert biz is not None

    # Inject page views to make it show up in the top listings list
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"page_view_count": 999}},
        )
    )

    r = client.get(
        "/admin/analytics",
        headers={**ADMIN_HEADERS, "host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    # Should contain the absolute URL including miami subdomain
    expected_url = f"http://miami.knowsbeauty.localhost/b/{biz['slug']}"
    assert expected_url in r.text
