"""Tests for the admin monthly-report preview and test-send routes.

These exercise the FastAPI routes end-to-end against the mocked database.
The admin gate is open in the test env (no ADMIN_API_KEY configured), matching
the pattern in test_admin_analytics.py. The AI caption call is patched so the
thin-views branch runs without touching the live gateway.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_db):
    # WHY: use mock_db (not seeded_db) so we control exactly which businesses
    # exist — the seed adds hundreds of records and we want a known target.
    from app.main import app

    return TestClient(app)


def _insert_business(mock_db, business_id="biz-preview", name="Glow Salon", views=50, claimed_email=None):
    doc = {
        "_id": business_id,
        "name": name,
        "page_view_count": views,
        "city_id": "city-1",
        "category_slugs": ["hair"],
        "neighborhood_slugs": [],
    }
    if claimed_email:
        doc["claimed_email"] = claimed_email
    asyncio.run(mock_db.businesses.insert_one(doc))
    return doc


# ── Preview route ────────────────────────────────────────────────────────────

class TestPreview:
    def test_preview_renders_email_html(self, client, mock_db):
        _insert_business(mock_db, views=50)
        r = client.get("/admin/monthly-report/preview", params={"business_id": "biz-preview"})
        assert r.status_code == 200, r.text
        # It returns the rendered email HTML — the salon name and a number show.
        assert "Glow Salon" in r.text
        assert "50" in r.text
        assert "<!DOCTYPE html>" in r.text

    def test_preview_unknown_business_404(self, client, mock_db):
        r = client.get("/admin/monthly-report/preview", params={"business_id": "nope"})
        assert r.status_code == 404

    def test_preview_sends_nothing(self, client, mock_db, monkeypatch):
        # The preview must never call the email provider.
        _insert_business(mock_db, views=50)
        import app.services.monthly_email as me

        async def _boom(*a, **k):  # pragma: no cover - must never run
            raise AssertionError("preview must not send")

        monkeypatch.setattr(me, "send_test_monthly_email", _boom)
        r = client.get("/admin/monthly-report/preview", params={"business_id": "biz-preview"})
        assert r.status_code == 200

    def test_preview_thin_views_includes_caption(self, client, mock_db, monkeypatch):
        # A business with very few views triggers the caption branch.
        _insert_business(mock_db, business_id="biz-thin", name="Quiet Spa", views=2)
        import app.services.ai_caption as ai

        async def _fake_caption(ctx, **k):
            return "Come unwind with us 🌸\n#MiamiSpa"

        monkeypatch.setattr(ai, "generate_caption", _fake_caption)
        r = client.get("/admin/monthly-report/preview", params={"business_id": "biz-thin"})
        assert r.status_code == 200, r.text
        assert "Come unwind with us" in r.text
        assert "Ready to post" in r.text


# ── Test-send route ──────────────────────────────────────────────────────────

class TestTestSend:
    def test_test_send_blocked_when_flag_off(self, client, mock_db, monkeypatch):
        monkeypatch.delenv("MONTHLY_REPORT_TEST_SEND_ENABLED", raising=False)
        _insert_business(mock_db, views=50)
        r = client.post(
            "/admin/monthly-report/test-send",
            json={"business_id": "biz-preview", "to": "qa@example.com"},
        )
        assert r.status_code == 403
        assert "disabled" in r.text.lower()

    def test_test_send_refuses_real_owner_address(self, client, mock_db, monkeypatch):
        # Even with the flag ON, sending to a real claimed owner's address is
        # refused — the hard guarantee that test-send can never reach an owner.
        monkeypatch.setenv("MONTHLY_REPORT_TEST_SEND_ENABLED", "true")
        _insert_business(mock_db, business_id="biz-owned", name="Owned Salon", views=50,
                         claimed_email="realowner@salon.com")
        r = client.post(
            "/admin/monthly-report/test-send",
            json={"business_id": "biz-owned", "to": "RealOwner@Salon.com"},
        )
        assert r.status_code == 409
        assert "real claimed owner" in r.text.lower()

    def test_test_send_success_with_mocked_sender(self, client, mock_db, monkeypatch):
        monkeypatch.setenv("MONTHLY_REPORT_TEST_SEND_ENABLED", "true")
        _insert_business(mock_db, business_id="biz-ok", name="Send Salon", views=50)

        sent = {"to": None}
        import app.routes.admin.monthly_report_admin as route_mod

        async def _fake_send(*, to, report, caption=None):
            sent["to"] = to
            return True

        monkeypatch.setattr(route_mod, "send_test_monthly_email", _fake_send)
        r = client.post(
            "/admin/monthly-report/test-send",
            json={"business_id": "biz-ok", "to": "qa@example.com"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sent"] is True
        assert body["to"] == "qa@example.com"
        assert sent["to"] == "qa@example.com"  # the explicit address, nowhere else

    def test_test_send_invalid_email_rejected(self, client, mock_db, monkeypatch):
        monkeypatch.setenv("MONTHLY_REPORT_TEST_SEND_ENABLED", "true")
        _insert_business(mock_db, business_id="biz-ok", name="Send Salon", views=50)
        r = client.post(
            "/admin/monthly-report/test-send",
            json={"business_id": "biz-ok", "to": "not-an-email"},
        )
        # Pydantic EmailStr validation rejects the malformed address (422).
        assert r.status_code == 422
