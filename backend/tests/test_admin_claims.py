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


# ---- admin claims UX: Google search link + street address --------------

def test_admin_claims_page_shows_google_search_link(client, seeded_db):
    """A Google search shortcut appears in the business cell so David can
    verify a business is real with one click instead of typing the name
    into a new tab manually."""
    business = _first_business(seeded_db)
    _submit_claim(client, business["_id"])
    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    # The Google search URL must appear in the page.  We don't assert the
    # exact encoded query because encoding details are Jinja internals, but
    # google.com/search is the reliable anchor.
    assert "google.com/search" in r.text
    # The icon link must carry the accessibility title so David knows what it does.
    assert "Search Google to verify this business" in r.text


def test_admin_claims_page_shows_street_address(client, seeded_db):
    """The full street address appears under the business name so David
    can cross-reference physical location without leaving the page."""
    business = _first_business(seeded_db)
    _submit_claim(client, business["_id"])
    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    # Every seeded business has a street address (from _real_businesses.json
    # address_full).  The template renders it in a <p> below the business name.
    street = (business.get("address") or {}).get("street")
    if street:
        assert street in r.text
        # The city/state must NOT be duplicated — the street field already
        # contains the full formatted address (e.g. "900 S Miami Ave, Miami,
        # FL 33130"), so appending ", Miami, FL" again would look broken.
        city = (business.get("address") or {}).get("city", "")
        state = (business.get("address") or {}).get("state", "")
        if city and state:
            duplicate_suffix = f"{street}, {city}, {state}"
            assert duplicate_suffix not in r.text, (
                "City/state should not be appended when street already contains full address"
            )


# ---- submit_claim guard: verified and pending businesses ---------------

def test_submit_claim_blocked_when_business_already_verified(client, seeded_db):
    """Submitting a claim for a business that already has claim_status='verified'
    must return 409 so the verified owner's dashboard access is never revoked."""
    business = _first_business(seeded_db)
    # Mark the business as verified (simulates a paying subscriber owning it).
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": business["_id"]},
            {"$set": {"claim_status": "verified"}},
        )
    )
    payload = {
        "business_id": business["_id"],
        "submitter_name": "Imposter",
        "submitter_email": "imposter@example.com",
        "submitter_phone": "+1 305-555-9999",
        "notes": "Trying to steal this listing.",
    }
    r = client.post("/api/v1/claims", json=payload)
    assert r.status_code == 409, r.text
    assert "already been claimed" in r.text
    # Confirm the business status was NOT changed.
    b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_after["claim_status"] == "verified"


def test_submit_claim_blocked_when_business_claim_pending(client, seeded_db):
    """Submitting a second claim for a business that is already pending review
    must return 409.  A duplicate submission does not create a second record."""
    business = _first_business(seeded_db)
    # First submission — should succeed.
    _submit_claim(client, business["_id"])
    # Confirm the business is now pending.
    b_mid = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_mid["claim_status"] == "pending"
    # Second submission — must be rejected.
    payload = {
        "business_id": business["_id"],
        "submitter_name": "Second Claimant",
        "submitter_email": "second@example.com",
        "submitter_phone": "+1 305-555-8888",
        "notes": "Also want to claim this.",
    }
    r = client.post("/api/v1/claims", json=payload)
    assert r.status_code == 409, r.text
    assert "already under review" in r.text


# ---- existing verify still works ---------------------------------------

def test_verify_claim_still_works(client, seeded_db):
    business = _first_business(seeded_db)
    claim = _submit_claim(client, business["_id"])
    r = client.post(f"/api/v1/claims/{claim['_id']}/verify")
    assert r.status_code == 200
    assert r.json() == {"status": "verified"}
    b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
    assert b_after["claim_status"] == "verified"
    # WHY: with the default cap of 25 and only one business being verified here,
    # 0 < 25 so the badge is still granted. This asserts the happy path still
    # works after the cap-enforcement fix. Cap rejection is tested below.
    assert b_after.get("is_founding_partner") is True, (
        "First verified claimer must receive Founding Partner status — "
        "cap is 25 and this is the only verified claim in this test."
    )


# ---- founding partner cap enforcement in verify_claim ------------------

def test_verify_claim_does_not_grant_fp_badge_when_cap_full(seeded_db, monkeypatch):
    """When the founding-partner cap is already reached, a newly-verified
    claim in the same network must NOT receive the badge."""
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("FOUNDING_PARTNER_CAP", "1")
    try:
        from app.main import app
        c = TestClient(app)

        # Mark the first business as already having the badge — cap is now full.
        first_biz = _first_business(seeded_db)
        network_id = first_biz.get("network_id")
        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": first_biz["_id"]},
                {"$set": {"is_founding_partner": True}},
            )
        )

        # Find a second business in the SAME network so the scoped cap filter
        # correctly sees 1 existing badge holder (cap is per-network; a business
        # in a different network would see 0 and incorrectly receive the badge).
        same_net: dict = {"city_id": {"$exists": True}, "_id": {"$ne": first_biz["_id"]}}
        if network_id:
            same_net["network_id"] = network_id
        peers = asyncio.run(seeded_db.businesses.find(same_net).to_list(length=2))
        assert peers, "Need at least two businesses in the same network to run this test"
        second_biz = peers[0]

        claim = _submit_claim(c, second_biz["_id"], submitter_email="late@example.com")
        r = c.post(f"/api/v1/claims/{claim['_id']}/verify")
        assert r.status_code == 200, r.text

        b_after = asyncio.run(seeded_db.businesses.find_one({"_id": second_biz["_id"]}))
        assert b_after["claim_status"] == "verified"
        # WHY: cap is 1 and the slot is taken by first_biz — the second claimer
        # must receive is_founding_partner: False (written explicitly, not absent)
        # so the scarcity promised on the owners and pricing pages is real.
        assert b_after.get("is_founding_partner") is False, (
            "Founding Partner badge must not be granted when the cap is full."
        )
    finally:
        get_settings.cache_clear()


def test_verify_claim_grants_fp_badge_when_cap_not_yet_reached(seeded_db, monkeypatch):
    """When slots are still available, a verified claim must receive the badge."""
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("FOUNDING_PARTNER_CAP", "5")
    try:
        from app.main import app
        c = TestClient(app)
        business = _first_business(seeded_db)
        claim = _submit_claim(c, business["_id"])
        r = c.post(f"/api/v1/claims/{claim['_id']}/verify")
        assert r.status_code == 200, r.text
        b_after = asyncio.run(seeded_db.businesses.find_one({"_id": business["_id"]}))
        # WHY: cap is 5, no existing badge holders, 0 < 5 — badge must be granted.
        assert b_after.get("is_founding_partner") is True, (
            "Founding Partner badge must be granted when slots remain."
        )
    finally:
        get_settings.cache_clear()
