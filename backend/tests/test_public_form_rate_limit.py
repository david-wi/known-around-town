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


# ---------------------------------------------------------------------------
# Unit tests — the limiter logic in isolation
# ---------------------------------------------------------------------------

def _seed_events(db, collection, ip, n, *, ts_field="submitted_at", when=None):
    """Insert n docs stamped with (submit_ip, timestamp) into the mock db."""

    async def _go():
        stamp = when or datetime.now(timezone.utc)
        for _ in range(n):
            await db[collection].insert_one({"submit_ip": ip, ts_field: stamp})

    asyncio.run(_go())


def _enforce(db, ip, max_events, **kw):
    asyncio.run(
        enforce_ip_rate_limit(
            db=db, collection="business_claims", ip=ip, max_events=max_events, **kw
        )
    )


def test_under_cap_is_allowed(mock_db):
    _seed_events(mock_db, "business_claims", "1.2.3.4", CLAIM_MAX_PER_WINDOW - 1)
    # One below the cap — must not raise.
    _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)


def test_at_cap_raises_429_with_retry_after(mock_db):
    _seed_events(mock_db, "business_claims", "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    with pytest.raises(HTTPException) as excinfo:
        _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    assert excinfo.value.status_code == 429
    # A polite client needs the Retry-After header to back off automatically.
    assert excinfo.value.headers.get("Retry-After")


def test_a_different_ip_is_not_affected(mock_db):
    # One IP is fully over its budget...
    _seed_events(mock_db, "business_claims", "1.2.3.4", CLAIM_MAX_PER_WINDOW)
    # ...but a different IP with no history sails through.
    _enforce(mock_db, "9.9.9.9", CLAIM_MAX_PER_WINDOW)


def test_events_outside_the_window_do_not_count(mock_db):
    old = datetime.now(timezone.utc) - PUBLIC_FORM_RATE_LIMIT_WINDOW - timedelta(minutes=1)
    _seed_events(mock_db, "business_claims", "1.2.3.4", CLAIM_MAX_PER_WINDOW, when=old)
    # All prior events are older than the window, so they don't count → allowed.
    _enforce(mock_db, "1.2.3.4", CLAIM_MAX_PER_WINDOW)


def test_owner_lead_counts_on_created_at_field(mock_db):
    # owner_leads stamps created_at, not submitted_at — verify the override.
    _seed_events(
        mock_db, "owner_leads", "1.2.3.4", OWNER_LEAD_MAX_PER_WINDOW, ts_field="created_at"
    )
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            enforce_ip_rate_limit(
                db=mock_db,
                collection="owner_leads",
                ip="1.2.3.4",
                max_events=OWNER_LEAD_MAX_PER_WINDOW,
                timestamp_field="created_at",
            )
        )
    assert excinfo.value.status_code == 429


def test_client_ip_reads_host_and_falls_back():
    assert client_ip(SimpleNamespace(client=SimpleNamespace(host="5.6.7.8"))) == "5.6.7.8"
    # No client (some ASGI transports / test clients) → shared bucket, no crash.
    assert client_ip(SimpleNamespace(client=None)) == "unknown"


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
    ), patch(
        "app.routes.api.v1.claims.send_admin_new_claim_email", new_callable=AsyncMock
    ):
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


def test_inquiry_endpoint_is_rate_limited(client, seeded_db):
    biz = _unclaimed_businesses(seeded_db, 1)[0]

    with patch(
        "app.routes.api.v1.inquiries.send_owner_inquiry_email", new_callable=AsyncMock
    ), patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email", new_callable=AsyncMock
    ):
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


def test_owner_lead_endpoint_is_rate_limited(client):
    # Distinct emails so the idempotency early-return never short-circuits —
    # this exercises the flood-of-junk-addresses abuse path.
    codes = []
    for i in range(OWNER_LEAD_MAX_PER_WINDOW + 1):
        r = client.post("/api/v1/owner-leads", json={"email": f"lead{i}@example.com"})
        codes.append(r.status_code)

    assert all(c == 200 for c in codes[:OWNER_LEAD_MAX_PER_WINDOW]), codes
    assert codes[OWNER_LEAD_MAX_PER_WINDOW] == 429, codes
