"""Tests for M-3: per-IP rate limiting on the public form endpoints.

Two layers:
  1. Unit tests on ``enforce_ip_rate_limit`` / ``client_ip`` (the limiter logic)
  2. Integration tests that flood each live endpoint (claims, inquiries,
     owner-leads) past its cap and confirm the next request gets HTTP 429.

# @define-test KAT-075
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services.rate_limit import (
    CLAIM_MAX_PER_WINDOW,
    INQUIRY_MAX_PER_WINDOW,
    OWNER_LEAD_MAX_PER_WINDOW,
    PUBLIC_FORM_RATE_LIMIT_WINDOW,
    client_ip,
    enforce_ip_rate_limit,
)


def _enforce(db, ip, max_events, **kw):
    asyncio.run(
        enforce_ip_rate_limit(
            db=db, collection="business_claims", ip=ip, max_events=max_events, **kw
        )
    )


def test_under_cap_is_allowed(mock_db):
    # One below the cap — must not raise.
    for _ in range(CLAIM_MAX_PER_WINDOW):
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)


def test_at_cap_raises_429_with_retry_after(mock_db):
    for _ in range(CLAIM_MAX_PER_WINDOW):
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    with pytest.raises(HTTPException) as excinfo:
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    assert excinfo.value.status_code == 429
    # A polite client needs the Retry-After header to back off automatically.
    assert excinfo.value.headers.get("Retry-After")


def test_a_different_ip_is_not_affected(mock_db):
    # One IP is fully over its budget...
    for _ in range(CLAIM_MAX_PER_WINDOW):
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    # ...but a different IP with no history sails through.
    _enforce(mock_db, "9.9.9.9", CLAIM_MAX_PER_WINDOW)


def test_events_outside_the_window_do_not_count(mock_db):
    old = datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc)
    later = old + PUBLIC_FORM_RATE_LIMIT_WINDOW + timedelta(minutes=1)
    for _ in range(CLAIM_MAX_PER_WINDOW):
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW, now=old)
    # All prior reservations are in an older fixed window, so a new window is allowed.
    _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW, now=later)


def test_owner_lead_uses_its_own_rate_limit_bucket(mock_db):
    # owner_leads uses its own bucket namespace but still shares the atomic
    # limiter behavior.
    for _ in range(OWNER_LEAD_MAX_PER_WINDOW):
        asyncio.run(
            enforce_ip_rate_limit(
                db=mock_db,
                collection="owner_leads",
                ip="1.2.3.4",
                max_events=OWNER_LEAD_MAX_PER_WINDOW,
            )
        )
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            enforce_ip_rate_limit(
                db=mock_db,
                collection="owner_leads",
                ip="1.2.3.4",
                max_events=OWNER_LEAD_MAX_PER_WINDOW,
            )
        )
    assert excinfo.value.status_code == 429


def test_client_ip_reads_host_and_falls_back():
    request = SimpleNamespace(
        client=SimpleNamespace(host="5.6.7.8"),
        headers={},
    )
    assert client_ip(request) == "5.6.7.8"
    # No client (some ASGI transports / test clients) → shared bucket, no crash.
    assert client_ip(SimpleNamespace(client=None, headers={})) == "unknown"


def test_client_ip_uses_rightmost_forwarded_for_value():
    request = SimpleNamespace(
        client=SimpleNamespace(host="9.9.9.9"),
        headers={"x-forwarded-for": "198.51.100.10, 203.0.113.55"},
    )
    assert client_ip(request) == "203.0.113.55"


def test_concurrent_reservations_allow_only_the_cap(mock_db):
    async def _go():
        results = await asyncio.gather(
            *[
                enforce_ip_rate_limit(
                    db=mock_db,
                    collection="business_claims",
                    ip="1.2.3.4",
                    max_events=CLAIM_MAX_PER_WINDOW,
                    now=datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc),
                )
                for _ in range(CLAIM_MAX_PER_WINDOW + 3)
            ],
            return_exceptions=True,
        )
        return results

    results = asyncio.run(_go())
    allowed = [result for result in results if result is None]
    blocked = [result for result in results if isinstance(result, HTTPException)]
    assert len(allowed) == CLAIM_MAX_PER_WINDOW
    assert len(blocked) == 3
    assert all(exc.status_code == 429 for exc in blocked)


# ---------------------------------------------------------------------------
# Integration tests — flood each live endpoint past its cap
# ---------------------------------------------------------------------------

@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def _unclaimed_businesses(seeded_db, n):
    async def _go():
        cur = seeded_db.businesses.find(
            {"city_id": {"$exists": True}, "claim_status": {"$nin": ["verified", "pending"]}}
        ).limit(n)
        return await cur.to_list(length=n)

    return asyncio.run(_go())


def test_claim_endpoint_is_rate_limited(client, seeded_db):
    # Distinct businesses so the per-business "already pending" 409 never fires —
    # this isolates the per-IP rate limit as the thing under test.
    businesses = _unclaimed_businesses(seeded_db, CLAIM_MAX_PER_WINDOW + 1)
    assert len(businesses) >= CLAIM_MAX_PER_WINDOW + 1, "seed needs more unclaimed businesses"

    with patch(
        "app.routes.api.v1.claims.send_claim_confirmation_email", new_callable=AsyncMock
    ) as confirmation_email, patch(
        "app.routes.api.v1.claims.send_admin_new_claim_email", new_callable=AsyncMock
    ) as admin_email:
        codes = []
        for biz in businesses:
            r = client.post(
                "/api/v1/claims",
                json={
                    "business_id": biz["_id"],
                    "submitter_name": "Owner",
                    "submitter_email": "owner@example.com",
                },
            )
            codes.append(r.status_code)

    assert all(c == 200 for c in codes[:CLAIM_MAX_PER_WINDOW]), codes
    assert codes[CLAIM_MAX_PER_WINDOW] == 429, codes
    assert confirmation_email.call_count == CLAIM_MAX_PER_WINDOW
    assert admin_email.call_count == CLAIM_MAX_PER_WINDOW
    assert asyncio.run(seeded_db.business_claims.count_documents({})) == CLAIM_MAX_PER_WINDOW


def test_inquiry_endpoint_is_rate_limited(client, seeded_db):
    biz = _unclaimed_businesses(seeded_db, 1)[0]

    with patch(
        "app.routes.api.v1.inquiries.send_owner_inquiry_email", new_callable=AsyncMock
    ) as owner_email, patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email", new_callable=AsyncMock
    ) as admin_email:
        codes = []
        for _ in range(INQUIRY_MAX_PER_WINDOW + 1):
            r = client.post(
                "/api/v1/inquiries",
                json={
                    "business_id": biz["_id"],
                    "name": "Visitor",
                    "email": "visitor@example.com",
                    "message": "Do you have Saturday availability?",
                },
            )
            codes.append(r.status_code)

    assert all(c == 200 for c in codes[:INQUIRY_MAX_PER_WINDOW]), codes
    assert codes[INQUIRY_MAX_PER_WINDOW] == 429, codes
    assert owner_email.call_count == 0
    assert admin_email.call_count == INQUIRY_MAX_PER_WINDOW
    assert asyncio.run(seeded_db.business_inquiries.count_documents({})) == INQUIRY_MAX_PER_WINDOW


def test_owner_lead_endpoint_is_rate_limited(client, seeded_db):
    # Distinct emails so the idempotency early-return never short-circuits —
    # this exercises the flood-of-junk-addresses abuse path.
    codes = []
    for i in range(OWNER_LEAD_MAX_PER_WINDOW + 1):
        r = client.post("/api/v1/owner-leads", json={"email": f"lead{i}@example.com"})
        codes.append(r.status_code)

    assert all(c == 200 for c in codes[:OWNER_LEAD_MAX_PER_WINDOW]), codes
    assert codes[OWNER_LEAD_MAX_PER_WINDOW] == 429, codes
    assert asyncio.run(seeded_db.owner_leads.count_documents({})) == OWNER_LEAD_MAX_PER_WINDOW


def test_owner_lead_repeat_existing_email_stays_idempotent_after_cap(client):
    first = client.post("/api/v1/owner-leads", json={"email": "owner-repeat@example.com"})
    assert first.status_code == 200

    for i in range(OWNER_LEAD_MAX_PER_WINDOW - 1):
        r = client.post("/api/v1/owner-leads", json={"email": f"distinct{i}@example.com"})
        assert r.status_code == 200

    over_cap = client.post("/api/v1/owner-leads", json={"email": "new-over-cap@example.com"})
    assert over_cap.status_code == 429

    repeat = client.post("/api/v1/owner-leads", json={"email": "owner-repeat@example.com"})
    assert repeat.status_code == 200
    assert repeat.json() == {"ok": True, "already_captured": True}


def test_startup_indexes_cover_public_form_rate_limit_paths(mock_db):
    from app import database

    asyncio.run(database.ensure_indexes())

    async def _indexes(collection):
        return {
            index["name"]: list(index["key"].items())
            for index in await mock_db[collection].list_indexes().to_list(None)
        }

    claim_indexes = asyncio.run(_indexes("business_claims"))
    inquiry_indexes = asyncio.run(_indexes("business_inquiries"))
    lead_indexes = asyncio.run(_indexes("owner_leads"))
    bucket_indexes = asyncio.run(_indexes("public_form_rate_limits"))

    assert claim_indexes["submit_ip_1_submitted_at_-1"] == [
        ("submit_ip", 1),
        ("submitted_at", -1),
    ]
    assert inquiry_indexes["submit_ip_1_submitted_at_-1"] == [
        ("submit_ip", 1),
        ("submitted_at", -1),
    ]
    assert lead_indexes["submit_ip_1_created_at_-1"] == [
        ("submit_ip", 1),
        ("created_at", -1),
    ]
    assert lead_indexes["email_1"] == [("email", 1)]
    assert bucket_indexes["expires_at_1"] == [("expires_at", 1)]
