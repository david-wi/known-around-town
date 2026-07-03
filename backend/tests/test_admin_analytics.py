"""Tests for the admin analytics dashboard page.

Exercises:
  - /admin/analytics returns 200 and contains the expected stat headings
  - Page view count shows zero state correctly
  - Claim funnel shows zero state correctly  
  - Auth gate: requires admin cookie (matches pattern in test_admin_claims.py)
"""

from __future__ import annotations

import asyncio
import re

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


def test_analytics_page_requires_admin_auth(client):
    """The admin dashboard must not expose metrics without admin auth."""
    r = client.get("/admin/analytics")
    assert r.status_code == 401

    r = client.get("/admin/analytics", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


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
    assert "bg-emerald-100 text-emerald-800" in r.text


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
        "featured": "malformed",
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


def test_analytics_first_send_targets_panel_shows_outreach_status(client, seeded_db):
    """@define-test KAT-051: David can monitor prepared outreach targets."""
    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    assert network is not None
    asyncio.run(
        seeded_db.cities.insert_many([
            {
                "_id": "city-brickell-first-send",
                "network_id": network["_id"],
                "slug": "brickell",
                "name": "Brickell",
                "status": "live",
            },
            {
                "_id": "city-coconut-grove-first-send",
                "network_id": network["_id"],
                "slug": "coconut-grove",
                "name": "Coconut Grove",
                "status": "live",
            },
            {
                "_id": "city-south-beach-first-send",
                "network_id": network["_id"],
                "slug": "south-beach",
                "name": "South Beach",
                "status": "live",
            },
        ])
    )
    asyncio.run(
        seeded_db.businesses.insert_many([
            {
                "_id": "biz-trini-first-send",
                "network_id": network["_id"],
                "city_id": "city-brickell-first-send",
                "name": "Trini Salon & Spa",
                "slug": "trini-salon-and-spa-brickell-ave",
                "status": "live",
                "claim_status": "unclaimed",
            },
            {
                "_id": "biz-sana-first-send",
                "network_id": network["_id"],
                "city_id": "city-coconut-grove-first-send",
                "name": "Sana Skin Studio",
                "slug": "sana-skin-studio-coconut-grove",
                "status": "live",
                "claim_status": None,
                "page_view_count": None,
                "mkb_referred_view_count": None,
                "call_click_count": None,
                "directions_click_count": None,
                "website_click_count": None,
            },
            {
                "_id": "biz-lux-first-send",
                "network_id": network["_id"],
                "city_id": "city-brickell-first-send",
                "name": "Lux MedSpa Brickell",
                "slug": "lux-medspa-brickell",
                "status": "live",
                "claim_status": "unclaimed",
            },
            {
                "_id": "biz-mcallister-first-send",
                "network_id": network["_id"],
                "city_id": "city-south-beach-first-send",
                "name": "McAllister Spa",
                "slug": "mcallister-spa-south-beach",
                "status": "live",
                "claim_status": "unclaimed",
            },
            {
                "_id": "biz-trini-wrong-city-first-send",
                "network_id": network["_id"],
                "city_id": "city-coconut-grove-first-send",
                "name": "Wrong City Trini",
                "slug": "trini-salon-and-spa-brickell-ave",
                "status": "live",
                "page_view_count": 0,
            },
        ])
    )
    trini = asyncio.run(
        seeded_db.businesses.find_one({"_id": "biz-trini-first-send"})
    )
    assert trini is not None
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": trini["_id"]},
            {
                "$set": {
                    "page_view_count": 7,
                    "mkb_referred_view_count": 2,
                    "call_click_count": 1,
                    "directions_click_count": 3,
                    "website_click_count": 4,
                    "claim_status": "pending",
                    "claimed_email": "owner@trini.example",
                    "stripe_subscription_id": "sub_test_trini",
                    "featured": {"enabled": True},
                }
            },
        )
    )
    asyncio.run(
        seeded_db.business_claims.insert_one(
            {
                "_id": "claim-first-send-trini",
                "business_id": trini["_id"],
                "status": "pending",
                "claim_source": "first-send-v3",
                "claim_ref": "trini-listing",
            }
        )
    )

    r = client.get(
        "/admin/analytics",
        headers={**ADMIN_HEADERS, "host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    total_biz = asyncio.run(
        seeded_db.businesses.count_documents({"network_id": network["_id"]})
    )
    unvisited = asyncio.run(
        seeded_db.businesses.count_documents({
            "network_id": network["_id"],
            "$or": [
                {"page_view_count": {"$lte": 0}},
                {"page_view_count": None},
                {"page_view_count": {"$exists": False}},
            ],
        })
    )
    visited = total_biz - unvisited
    assert (
        f'<p class="text-3xl font-semibold text-stone-900">{visited}</p>'
        in r.text
    )
    assert f"{unvisited} not yet visited" in r.text
    assert "First-send targets" in r.text
    assert 'target="_blank" rel="noopener noreferrer"' in r.text
    assert "Trini Salon &amp; Spa" in r.text
    assert "Sana Skin Studio" in r.text
    assert "Lux MedSpa Brickell" in r.text
    assert "McAllister Spa" in r.text
    assert "Wrong City Trini" not in r.text
    assert "None" not in r.text
    assert "Miami Knows Beauty views" in r.text
    assert "Active subscription" in r.text
    assert "1 claim" in r.text
    assert re.search(r">\s*7\s*<", r.text)
    assert re.search(r">\s*2\s*<", r.text)
    assert re.search(r">\s*8\s*<", r.text)
    assert (
        'href="http://brickell.knowsbeauty.localhost/b/'
        'trini-salon-and-spa-brickell-ave"'
    ) in r.text
