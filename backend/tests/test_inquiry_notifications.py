"""Tests for the inquiry submission endpoint and owner notification logic.

Three scenarios:
  1. Claimed business (owner session exists) → owner receives email
  2. Unclaimed business (no session, no verified claim) → admin receives email
  3. Email failure → submission still succeeds (fire-and-forget)
  4. Unknown business → 404

Plus unit tests for the HTML email template (reply-button rendering).
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
# 1. Stale owner-session rows are not ownership authority
# ---------------------------------------------------------------------------

def test_inquiry_ignores_stale_owner_session_without_verified_business(client, seeded_db):
    """# @define-test KAT-075"""
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
    mock_owner_email.assert_not_awaited()
    mock_admin_email.assert_awaited_once()


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
# HTML template unit tests — reply button rendering
# ---------------------------------------------------------------------------

def _make_html(visitor_email=None, visitor_phone=None, message="Hello", business_name="Test Salon", visitor_name="Jane"):
    from app.services.owner_email import _inquiry_owner_html  # type: ignore[attr-defined]
    return _inquiry_owner_html(
        business_name=business_name,
        visitor_name=visitor_name,
        visitor_email=visitor_email,
        visitor_phone=visitor_phone,
        message=message,
        dashboard_url="https://miami.knowsbeauty.com/owners/me",
    )


def test_reply_button_present_when_email_provided():
    html_out = _make_html(visitor_email="jane@example.com")
    assert "Reply to Jane" in html_out
    assert "mailto:jane@example.com" in html_out
    assert "Re%3A%20Your%20inquiry%20about%20Test%20Salon" in html_out or "Re:" in html_out


def test_reply_button_absent_when_no_email():
    html_out = _make_html(visitor_email=None)
    assert "Reply to" not in html_out
    assert "mailto:" not in html_out


def test_reply_button_email_with_plus_sign():
    """Email addresses with + (e.g. user+tag@example.com) must be URL-encoded in href."""
    html_out = _make_html(visitor_email="user+tag@example.com")
    # The + must be encoded as %2B in the href so it is not treated as a space
    assert "user%2Btag@example.com" in html_out or "mailto:user%2Btag" in html_out


def test_dashboard_url_html_escaped():
    """dashboard_url must be HTML-escaped so & in query strings renders as &amp;."""
    from app.services.owner_email import _inquiry_owner_html  # type: ignore[attr-defined]
    html_out = _inquiry_owner_html(
        business_name="Salon",
        visitor_name="Jane",
        visitor_email=None,
        visitor_phone=None,
        message="Hi",
        dashboard_url="https://miami.knowsbeauty.com/owners/me?foo=1&bar=2",
    )
    assert "&amp;bar=2" in html_out
    assert 'href="https://miami.knowsbeauty.com/owners/me?foo=1&bar=2"' not in html_out


def test_message_newlines_rendered_as_br():
    """Multi-line visitor messages must use <br> so they render in Outlook."""
    html_out = _make_html(message="Line one\nLine two\r\nLine three")
    assert "Line one<br>Line two<br>Line three" in html_out
    assert "white-space: pre-wrap" not in html_out


def test_xss_in_visitor_name_escaped():
    html_out = _make_html(visitor_name="<script>alert(1)</script>", visitor_email="x@y.com")
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


# ---------------------------------------------------------------------------
# 5. Verified business ownership sends owner email
# ---------------------------------------------------------------------------

def test_inquiry_sends_owner_email_when_business_is_verified(client, seeded_db):
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz_id},
            {"$set": {"claim_status": "verified", "claimed_email": "owner@salon.com"}},
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
    assert mock_owner_email.call_args.kwargs["owner_email"] == "owner@salon.com"
    mock_admin_email.assert_not_awaited()


def test_inquiry_ignores_forged_verified_claim_without_business_ownership(client, seeded_db):
    """# @define-test KAT-075"""
    business = _first_business(seeded_db)
    biz_id = business["_id"]

    # No verified business owner, but an attacker-controlled verified claim row exists.
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
    mock_owner_email.assert_not_awaited()
    mock_admin_email.assert_awaited_once()
