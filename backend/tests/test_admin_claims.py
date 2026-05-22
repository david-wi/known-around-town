"""Tests for the admin claims page and the new /reject endpoint.

We exercise:
  - the new /api/v1/claims/{id}/reject endpoint (happy path, 404, business state)
  - the new /admin/claims HTML page (lists pending only, auth required, empty state)
  - the new /admin/login + cookie auth (right key sets cookie, wrong key rejected)
  - that the existing /verify endpoint still works
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def _first_business(seeded_db) -> Dict[str, Any]:
    return asyncio.run(seeded_db.businesses.find_one({"city_id": {"$exists": True}}))


def _submit_claim(client: TestClient, business_id: str, **overrides) -> Dict[str, Any]:
    payload = {
        "business_id": business_id,
        "submitter_name": overrides.get("submitter_name", "Alex Owner"),
        "submitter_email": overrides.get("submitter_email", "alex@example.com"),
        "submitter_phone": overrides.get("submitter_phone", "+1 305-555-0100"),
        "notes": overrides.get("notes", "I'm the owner; please verify."),
    }
    r = client.post("/api/v1/claims", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---- /admin/claims page -------------------------------------------------

def test_admin_claims_page_lists_pending(client, seeded_db):
    business = _first_business(seeded_db)
    claim = _submit_claim(client, business["_id"])

    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    # The business name shows in the table.
    assert business["name"] in r.text
    # The submitter's name and email show.
    assert "Alex Owner" in r.text
    assert "alex@example.com" in r.text
    # Both action buttons render (the Jinja template wraps them with
    # whitespace, so look for the visible label only).
    assert "Verify" in r.text
    assert "Reject" in r.text
    assert 'data-action="verify"' in r.text
    assert 'data-action="reject"' in r.text
    # The row carries the claim id so the JS handler can target the right endpoint.
    assert f'data-claim-id="{claim["_id"]}"' in r.text


def test_admin_claims_page_empty_state(client):
    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    assert "No pending claims" in r.text
    assert "Nothing to review right now" in r.text


def test_admin_claims_page_hides_verified_and_rejected(client, seeded_db):
    business = _first_business(seeded_db)
    pending = _submit_claim(client, business["_id"], submitter_name="Pending Person")

    # Insert a verified and a rejected claim directly so we can confirm they
    # are filtered out of the page.
    asyncio.run(
        seeded_db.business_claims.insert_one(
            {
                "_id": "verified-claim-id",
                "business_id": business["_id"],
                "submitter_name": "Already Verified",
                "submitter_email": "verified@example.com",
                "status": "verified",
            }
        )
    )
    asyncio.run(
        seeded_db.business_claims.insert_one(
            {
                "_id": "rejected-claim-id",
                "business_id": business["_id"],
                "submitter_name": "Already Rejected",
                "submitter_email": "rejected@example.com",
                "status": "rejected",
            }
        )
    )

    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    assert "Pending Person" in r.text
    assert "Already Verified" not in r.text
    assert "Already Rejected" not in r.text


def test_admin_claims_page_blocked_without_key(seeded_db, monkeypatch):
    """When ADMIN_API_KEY is set, requests without a key (header or cookie)
    must be rejected with 401."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "super-secret")
    try:
        from app.main import app

        c = TestClient(app)
        r = c.get("/admin/claims")
        assert r.status_code == 401, r.text
    finally:
        get_settings.cache_clear()


def test_admin_claims_page_allowed_with_cookie(seeded_db, monkeypatch):
    """With the cookie set to the right key, /admin/claims renders."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "super-secret")
    try:
        from app.main import app

        c = TestClient(app)
        # No cookie -> 401
        assert c.get("/admin/claims").status_code == 401
        # Cookie -> 200
        c.cookies.set("kbt_admin_key", "super-secret")
        r = c.get("/admin/claims")
        assert r.status_code == 200, r.text
    finally:
        get_settings.cache_clear()


def test_admin_claims_page_allowed_with_header(seeded_db, monkeypatch):
    """With the header set to the right key, /admin/claims renders too —
    same dependency, so this covers script callers."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "super-secret")
    try:
        from app.main import app

        c = TestClient(app)
        r = c.get("/admin/claims", headers={"X-API-Key": "super-secret"})
        assert r.status_code == 200, r.text
    finally:
        get_settings.cache_clear()


# ---- /admin/login -------------------------------------------------------

def test_admin_login_get_renders_form(client):
    r = client.get("/admin/login")
    assert r.status_code == 200
    assert "Admin key" in r.text
    assert 'name="api_key"' in r.text


def test_admin_login_wrong_key_redirects_with_error(seeded_db, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "real-key")
    try:
        from app.main import app

        c = TestClient(app)
        r = c.post(
            "/admin/login",
            data={"api_key": "wrong-key"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/admin/login" in r.headers["location"]
        assert "error" in r.headers["location"]
    finally:
        get_settings.cache_clear()


def test_admin_login_right_key_sets_cookie_and_redirects(seeded_db, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "real-key")
    try:
        from app.main import app

        c = TestClient(app)
        r = c.post(
            "/admin/login",
            data={"api_key": "real-key"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/admin/claims"
        # Cookie set on the client.
        assert c.cookies.get("kbt_admin_key") == "real-key"
    finally:
        get_settings.cache_clear()


def test_admin_logout_clears_cookie(client):
    client.cookies.set("kbt_admin_key", "anything")
    r = client.post("/admin/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


# ---- /api/v1/claims/{id}/reject ----------------------------------------

def test_reject_claim_flips_status_and_unclaims_business(client, seeded_db):
    business = _first_business(seeded_db)
    claim = _submit_claim(client, business["_id"])

    # Sanity: the business is `pending` after a claim is submitted.
    b_before = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_before["claim_status"] == "pending"

    r = client.post(f"/api/v1/claims/{claim['_id']}/reject")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "rejected"}

    # The claim is rejected.
    claim_after = asyncio.run(
        seeded_db.business_claims.find_one({"_id": claim["_id"]})
    )
    assert claim_after["status"] == "rejected"
    assert claim_after.get("rejected_at") is not None

    # The business is back to `unclaimed` so it's open for a real owner.
    b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_after["claim_status"] == "unclaimed"


def test_reject_claim_does_not_unverify_already_verified_business(client, seeded_db):
    """If the business is already verified by another claim, rejecting a
    different (stale) pending claim must NOT down-grade it."""
    business = _first_business(seeded_db)
    stale_claim = _submit_claim(client, business["_id"], submitter_email="stale@example.com")

    # Simulate another claim getting verified first.
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": business["_id"]},
            {"$set": {"claim_status": "verified"}},
        )
    )

    r = client.post(f"/api/v1/claims/{stale_claim['_id']}/reject")
    assert r.status_code == 200

    b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_after["claim_status"] == "verified", (
        "Rejecting a stale claim must not un-verify a business someone else "
        "has already legitimately claimed."
    )


def test_reject_claim_404(client):
    r = client.post("/api/v1/claims/does-not-exist/reject")
    assert r.status_code == 404


def test_reject_claim_requires_admin_when_key_set(seeded_db, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    try:
        from app.main import app

        c = TestClient(app)
        # Create a claim with admin auth so we have something to reject.
        business = _first_business(seeded_db)
        c.post(
            "/api/v1/claims",
            json={
                "_id": "claim-for-reject-auth",
                "business_id": business["_id"],
                "submitter_name": "X",
                "submitter_email": "x@example.com",
            },
        )
        # Without the key, reject is blocked.
        r = c.post("/api/v1/claims/claim-for-reject-auth/reject")
        assert r.status_code == 401
        # With the key, it works.
        r = c.post(
            "/api/v1/claims/claim-for-reject-auth/reject",
            headers={"X-API-Key": "secret"},
        )
        assert r.status_code == 200
    finally:
        get_settings.cache_clear()


# ---- existing verify still works ---------------------------------------

def test_verify_claim_still_works(client, seeded_db):
    business = _first_business(seeded_db)
    claim = _submit_claim(client, business["_id"])
    r = client.post(f"/api/v1/claims/{claim['_id']}/verify")
    assert r.status_code == 200
    assert r.json() == {"status": "verified"}
    b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_after["claim_status"] == "verified"
