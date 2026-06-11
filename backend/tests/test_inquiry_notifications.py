"""Tests for the inquiry submission endpoint and owner notification logic.

Three scenarios:
  1. Claimed business (owner session exists) → owner receives email
  2. Unclaimed business (no session, no verified claim) → admin receives email
  3. Email failure → submission still succeeds (fire-and-forget)
  4. Unknown business → 404
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def _first_business(seeded_db) -> Dict[str, Any]:
    return asyncio.run(seeded_db.businesses.find_one({"city_id": {"$exists": True}}))


def _submit(client: TestClient, business_id: str, **overrides) -> Any:
    payload = {
        "business_id": business_id,
        "name": "Test Visitor",
        "email": "visitor@example.com",
        "message": "Is a blow-out available on Saturday?",
        **overrides,
    }
    return client.post("/api/v1/inquiries", json=payload)


# ---------------------------------------------------------------------------
# 1. Claimed business — owner email sent
# ---------------------------------------------------------------------------

def test_inquiry_sends_owner_email_when_session_exists(client, seeded_db):
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    # Seed an owner session bound to this business.
    asyncio.run(
        seeded_db.owner_sessions.insert_one(
            {
                "_id": "sess-test-1",
                "email": "owner@salon.com",
                "business_id": biz_id,
                "last_used_at": None,
            }
        )
    )

    with patch(
        "app.routes.api.v1.inquiries.send_owner_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_owner_email, patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_admin_email:
        r = _submit(client, biz_id)

    assert r.status_code == 200, r.text
    mock_owner_email.assert_awaited_once()
    call_kwargs = mock_owner_email.call_args.kwargs
    assert call_kwargs["owner_email"] == "owner@salon.com"
    assert call_kwargs["visitor_name"] == "Test Visitor"
    assert call_kwargs["visitor_email"] == "visitor@example.com"
    assert "blow-out" in call_kwargs["message"]
    mock_admin_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 2. Unclaimed business — admin email sent
# ---------------------------------------------------------------------------

def test_inquiry_sends_admin_email_when_no_owner(client, seeded_db):
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    # No owner session, no verified claim for this business.

    with patch(
        "app.routes.api.v1.inquiries.send_owner_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_owner_email, patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_admin_email:
        r = _submit(client, biz_id)

    assert r.status_code == 200, r.text
    mock_admin_email.assert_awaited_once()
    call_kwargs = mock_admin_email.call_args.kwargs
    assert call_kwargs["business_id"] == biz_id
    assert call_kwargs["visitor_name"] == "Test Visitor"
    mock_owner_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. Email failure does not fail the submission
# ---------------------------------------------------------------------------

def test_inquiry_succeeds_even_if_notification_raises(client, seeded_db):
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    with patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP down"),
    ):
        r = _submit(client, biz_id)

    assert r.status_code == 200, r.text
    # Inquiry was saved to DB.
    saved = asyncio.run(
        seeded_db.business_inquiries.find_one({"business_id": biz_id})
    )
    assert saved is not None
    assert saved["message"] == "Is a blow-out available on Saturday?"


# ---------------------------------------------------------------------------
# 4. Unknown business → 404
# ---------------------------------------------------------------------------

def test_inquiry_404_for_unknown_business(client, seeded_db):
    r = _submit(client, "non-existent-biz-id")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 5. Verified claim fallback (no session, but verified claim exists)
# ---------------------------------------------------------------------------

def test_inquiry_falls_back_to_claim_email(client, seeded_db):
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    # No owner session, but a verified claim exists.
    asyncio.run(
        seeded_db.business_claims.insert_one(
            {
                "_id": "claim-test-1",
                "business_id": biz_id,
                "submitter_email": "claimant@salon.com",
                "status": "verified",
                "verified_at": None,
            }
        )
    )

    with patch(
        "app.routes.api.v1.inquiries.send_owner_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_owner_email, patch(
        "app.routes.api.v1.inquiries.send_admin_inquiry_email",
        new_callable=AsyncMock,
    ) as mock_admin_email:
        r = _submit(client, biz_id)

    assert r.status_code == 200, r.text
    mock_owner_email.assert_awaited_once()
    assert mock_owner_email.call_args.kwargs["owner_email"] == "claimant@salon.com"
    mock_admin_email.assert_not_awaited()
