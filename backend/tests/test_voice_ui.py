"""Tests for the AI Receptionist UI sections added in the voice-ui PR.

Four scenarios:

  Owner dashboard (GET /owners/me):
    1. When the owner's business has a voice_phone_number, the active
       receptionist section (violet card with phone number) is shown.
    2. When the business has NO voice_phone_number, the upsell/teaser card
       is shown instead.

  Public business page (GET /b/<slug>):
    3. When the business has a voice_phone_number, the "Call Now" button
       appears with a tel: link pointing at that number.
    4. When the business has NO voice_phone_number, no "Call Now" button
       appears on the page.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client(seeded_db):
    from app.main import app
    return TestClient(app)


def _first_business(seeded_db) -> Dict[str, Any]:
    """Return the first business that has a slug (i.e. a real listing)."""
    return asyncio.run(seeded_db.businesses.find_one({"slug": {"$exists": True}}))


def _make_session_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session
    return sign_session(email)


# ── Owner dashboard tests ────────────────────────────────────────────────────

class TestOwnerDashboardVoiceSection:
    """Tests for the AI Receptionist section on the owner dashboard (/owners/me)."""

    def test_active_receptionist_section_shown_when_provisioned(self, client, seeded_db):
        """When the owner's business has a voice phone number, the dashboard
        must show the 'Your AI Receptionist' section with an 'Active' badge
        and the actual phone number — so the owner can immediately share it
        with clients.

        WHY: an owner who paid for Concierge should see their number front and
        centre on login, not have to guess where to find it."""
        biz = _first_business(seeded_db)
        email = "voice-active@example.com"
        voice_number = "(669) 232-8894"

        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$set": {
                    "claimed_email": email,
                    "voice_phone_number": voice_number,
                }},
            )
        )

        cookie = _make_session_cookie(email)
        r = client.get(
            "/owners/me",
            headers={"host": "miami.knowsbeauty.localhost"},
            cookies={"kb_owner_session": cookie},
        )
        assert r.status_code == 200, r.text
        body = r.text

        # Active section must be present
        assert "Your AI Receptionist" in body, (
            "Active receptionist section heading missing — owner can't find their number"
        )
        assert "Active" in body, (
            "'Active' badge missing — owner doesn't know the service is live"
        )
        assert voice_number in body, (
            f"Phone number '{voice_number}' not shown — owner can't share the number"
        )
        assert "Share this number" in body, (
            "Sharing instructions missing — owner doesn't know how to use the number"
        )

        # Upsell card must NOT be shown
        assert "Contact us to upgrade" not in body, (
            "Upsell card shown when voice is already active — confusing UX"
        )

    def test_upsell_section_shown_when_not_provisioned(self, client, seeded_db):
        """When the owner's business has no voice phone number, the dashboard
        must show the teaser card describing the AI Receptionist feature and
        a link to contact us for an upgrade.

        WHY: owners who don't have the feature should know it exists and have
        a clear path to get it — without this card the feature is invisible
        to non-Concierge subscribers."""
        biz = _first_business(seeded_db)
        email = "voice-inactive@example.com"

        # Ensure no voice_phone_number on this business
        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {
                    "$set": {"claimed_email": email},
                    "$unset": {"voice_phone_number": ""},
                },
            )
        )

        cookie = _make_session_cookie(email)
        r = client.get(
            "/owners/me",
            headers={"host": "miami.knowsbeauty.localhost"},
            cookies={"kb_owner_session": cookie},
        )
        assert r.status_code == 200, r.text
        body = r.text

        # Upsell card must be present
        assert "AI Receptionist" in body, (
            "AI Receptionist feature name missing from upsell card"
        )
        assert "Contact us to upgrade" in body, (
            "Upgrade CTA missing — owner has no path to get the feature"
        )
        assert "Concierge" in body, (
            "'Concierge' tier label missing — owner doesn't know which plan includes this"
        )

        # Active section heading must NOT be present
        assert "Your AI Receptionist" not in body, (
            "'Your AI Receptionist' active-state heading shown when not provisioned"
        )
        assert "Active" not in body or "Active" in body and "(669)" not in body, (
            "Active badge or phone number shown when voice is not provisioned"
        )


# ── Public business page tests ───────────────────────────────────────────────

class TestPublicPageCallNowButton:
    """Tests for the 'Call Now (24/7 AI Receptionist)' button on the public
    business detail page (/b/<slug>)."""

    def test_call_now_button_shown_when_voice_provisioned(self, client, seeded_db):
        """When a business has a voice phone number, the public listing page
        must show a 'Call Now' button with a tel: link to that number.

        WHY: the whole point of the AI Receptionist is to handle inbound calls
        from potential clients — if the button doesn't appear on the public
        listing, clients can't call the AI receptionist and the feature is wasted."""
        biz = _first_business(seeded_db)
        voice_number = "(669) 232-8894"
        # Formatted as digits for the tel: href
        voice_digits = "6692328894"

        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$set": {"voice_phone_number": voice_number}},
            )
        )

        slug = biz["slug"]
        r = client.get(
            f"/b/{slug}",
            headers={"host": "miami.knowsbeauty.localhost"},
        )
        assert r.status_code == 200, r.text
        body = r.text

        assert "Call Now" in body, (
            "Call Now button missing — clients can't reach the AI receptionist"
        )
        assert "AI Receptionist" in body, (
            "'AI Receptionist' label missing from Call Now button"
        )
        assert f"tel:{voice_digits}" in body, (
            f"tel: link for {voice_number} missing — button won't dial correctly"
        )

    def test_call_now_button_absent_when_no_voice(self, client, seeded_db):
        """When a business has no voice phone number, the 'Call Now' button
        must not appear on the public page.

        WHY: showing a 'Call Now (24/7 AI Receptionist)' button for a business
        that hasn't provisioned the feature would confuse callers when nobody
        picks up, or route them to a disconnected number."""
        biz = _first_business(seeded_db)

        # Ensure no voice_phone_number
        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$unset": {"voice_phone_number": ""}},
            )
        )

        slug = biz["slug"]
        r = client.get(
            f"/b/{slug}",
            headers={"host": "miami.knowsbeauty.localhost"},
        )
        assert r.status_code == 200, r.text
        body = r.text

        assert "Call Now (24/7 AI Receptionist)" not in body, (
            "Call Now button shown when no voice number is provisioned — "
            "clients would reach a dead number"
        )
