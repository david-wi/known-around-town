"""Tests for voice provisioning service and admin/owner voice endpoints.

All VAPI HTTP calls are mocked — no real API calls are made.

Covers:
  - provision_salon_receptionist builds the right VAPI payload and writes
    voice_phone_number / vapi_phone_number_id / vapi_assistant_id to the DB
  - deprovision_salon_receptionist calls DELETE on both resources and clears
    the DB fields
  - POST /api/v1/admin/businesses/{id}/provision-voice returns 200 on success,
    404 when business not found
  - POST /api/v1/admin/businesses/{id}/deprovision-voice returns 200 on success,
    404 when business not found
  - GET /api/v1/owner/voice returns correct data when provisioned, {"active": false}
    when not provisioned
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Make VAPI_API_KEY available so the service module doesn't raise at import
os.environ.setdefault("VAPI_API_KEY", "test-vapi-key")


# ===== Service-layer tests (no HTTP server) =================================

class TestProvisionSalonReceptionist:
    """Unit tests for the provision_salon_receptionist service function."""

    def _make_business(self, **overrides) -> Dict[str, Any]:
        base = {
            "_id": "biz-123",
            "name": "Glam Studio Miami",
            "category_slugs": ["hair-salon"],
            "neighborhood_slugs": ["brickell"],
            "address": {"street": "100 SW 1st Ave", "city": "Miami", "state": "FL", "postal_code": "33130"},
            "phone": "(305) 555-1234",
            "hours": [
                {"day": "mon", "opens_at": "09:00", "closes_at": "18:00", "closed": False},
                {"day": "tue", "opens_at": "09:00", "closes_at": "18:00", "closed": False},
                {"day": "sun", "closed": True},
            ],
            "services": [
                {"name": "Blowout", "price_from": 45.0, "price_to": 75.0},
                {"name": "Balayage", "price_from": 150.0},
            ],
            "featured": {"tier": "premium", "enabled": True},
        }
        base.update(overrides)
        return base

    def _make_mock_db(self, business: Dict[str, Any]):
        db = MagicMock()
        db.businesses.find_one = AsyncMock(return_value=business)
        db.businesses.update_one = AsyncMock(return_value=None)
        return db

    def _mock_httpx_responses(self, *, assistant_id="asst-abc", phone_id="ph-xyz", raw_number="+16692328894"):
        """Build an httpx.AsyncClient mock that returns canned VAPI responses."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        post_assistant_resp = MagicMock()
        post_assistant_resp.raise_for_status = MagicMock()
        post_assistant_resp.json = MagicMock(return_value={"id": assistant_id})

        post_phone_resp = MagicMock()
        post_phone_resp.raise_for_status = MagicMock()
        post_phone_resp.json = MagicMock(return_value={"id": phone_id, "number": raw_number})

        patch_phone_resp = MagicMock()
        patch_phone_resp.raise_for_status = MagicMock()

        # Return different responses in order: POST /assistant, POST /phone-number, PATCH /phone-number/{id}
        mock_client.post = AsyncMock(side_effect=[post_assistant_resp, post_phone_resp])
        mock_client.patch = AsyncMock(return_value=patch_phone_resp)
        return mock_client

    def test_provision_writes_voice_fields_to_db(self):
        """provision_salon_receptionist must write voice_phone_number,
        vapi_phone_number_id, and vapi_assistant_id to the business document."""
        business = self._make_business()
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses()

        from app.services.voice_provisioning import provision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(provision_salon_receptionist(db, "biz-123"))

        # Check the return value
        assert result["phone_number"] == "(669) 232-8894"
        assert result["assistant_id"] == "asst-abc"
        assert result["phone_number_id"] == "ph-xyz"

        # Check DB was updated
        db.businesses.update_one.assert_called_once()
        call_args = db.businesses.update_one.call_args
        filter_arg = call_args[0][0]
        update_arg = call_args[0][1]
        assert filter_arg == {"_id": "biz-123"}
        assert update_arg["$set"]["voice_phone_number"] == "(669) 232-8894"
        assert update_arg["$set"]["vapi_phone_number_id"] == "ph-xyz"
        assert update_arg["$set"]["vapi_assistant_id"] == "asst-abc"
        assert update_arg["$set"]["featured.tier"] == "concierge"

    def test_provision_404_when_business_missing(self):
        """Raises ValueError when business_id is not in the DB."""
        db = MagicMock()
        db.businesses.find_one = AsyncMock(return_value=None)

        from app.services.voice_provisioning import provision_salon_receptionist

        with pytest.raises(ValueError, match="not found"):
            asyncio.run(provision_salon_receptionist(db, "nonexistent"))

    def test_provision_builds_correct_assistant_name(self):
        """The VAPI assistant name must be '{salon name} — AI Receptionist'."""
        business = self._make_business(name="Lux Nail Bar")
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses()

        from app.services.voice_provisioning import provision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(provision_salon_receptionist(db, "biz-123"))

        # Verify the assistant creation payload contained the right name
        post_calls = mock_client.post.call_args_list
        assistant_call = post_calls[0]
        payload = assistant_call.kwargs.get("json") or assistant_call[1].get("json")
        assert payload["name"] == "Lux Nail Bar — AI Receptionist"

    def test_provision_assistant_payload_has_required_fields(self):
        """The VAPI assistant payload must include model, transcriber, voice,
        firstMessage, endCallFunctionEnabled, and recordingEnabled."""
        business = self._make_business()
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses()

        from app.services.voice_provisioning import provision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(provision_salon_receptionist(db, "biz-123"))

        post_calls = mock_client.post.call_args_list
        payload = post_calls[0].kwargs.get("json") or post_calls[0][1].get("json")
        assert payload["model"]["provider"] == "openai"
        assert payload["model"]["model"] == "gpt-4o"
        assert payload["transcriber"]["provider"] == "deepgram"
        assert payload["voice"]["provider"] == "11labs"
        assert "firstMessage" in payload
        assert payload["endCallFunctionEnabled"] is True
        assert payload["recordingEnabled"] is True

    def test_provision_system_prompt_includes_salon_info(self):
        """The system prompt must mention the salon's name, address, and hours."""
        business = self._make_business(
            name="Glam Studio Miami",
            phone="(305) 555-1234",
        )
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses()

        from app.services.voice_provisioning import provision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(provision_salon_receptionist(db, "biz-123"))

        post_calls = mock_client.post.call_args_list
        payload = post_calls[0].kwargs.get("json") or post_calls[0][1].get("json")
        system_prompt = payload["model"]["messages"][0]["content"]

        assert "Glam Studio Miami" in system_prompt
        assert "(305) 555-1234" in system_prompt
        # Hours should be formatted in the prompt
        assert "Monday" in system_prompt
        assert "Sunday" in system_prompt
        assert "Closed" in system_prompt

    def test_provision_uses_configured_vapi_model(self, monkeypatch):
        """The VAPI assistant model/provider should be env-configurable."""
        monkeypatch.setenv("VAPI_ASSISTANT_MODEL_PROVIDER", "google")
        monkeypatch.setenv("VAPI_ASSISTANT_MODEL", "gemini-2.5-flash")

        from app.config import get_settings

        get_settings.cache_clear()

        business = self._make_business()
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses()

        from app.services.voice_provisioning import provision_salon_receptionist

        try:
            with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
                asyncio.run(provision_salon_receptionist(db, "biz-123"))

            payload = mock_client.post.call_args_list[0].kwargs.get("json")
            assert payload["model"]["provider"] == "google"
            assert payload["model"]["model"] == "gemini-2.5-flash"
        finally:
            get_settings.cache_clear()

    def test_provision_phone_number_formatting(self):
        """E.164 number +16692328894 must be formatted as (669) 232-8894."""
        business = self._make_business()
        db = self._make_mock_db(business)
        mock_client = self._mock_httpx_responses(raw_number="+16692328894")

        from app.services.voice_provisioning import provision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(provision_salon_receptionist(db, "biz-123"))

        assert result["phone_number"] == "(669) 232-8894"


class TestDeprovisionSalonReceptionist:
    """Unit tests for the deprovision_salon_receptionist service function."""

    def _make_business_with_voice(self, **overrides) -> Dict[str, Any]:
        base = {
            "_id": "biz-456",
            "name": "Glam Studio Miami",
            "voice_phone_number": "(669) 232-8894",
            "vapi_phone_number_id": "ph-xyz",
            "vapi_assistant_id": "asst-abc",
            "featured": {"tier": "concierge", "enabled": True},
        }
        base.update(overrides)
        return base

    def _make_mock_db(self, business: Dict[str, Any]):
        db = MagicMock()
        db.businesses.find_one = AsyncMock(return_value=business)
        db.businesses.update_one = AsyncMock(return_value=None)
        return db

    def _mock_delete_client(self):
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        delete_resp = MagicMock()
        delete_resp.raise_for_status = MagicMock()
        mock_client.delete = AsyncMock(return_value=delete_resp)
        return mock_client

    def test_deprovision_calls_delete_on_both_resources(self):
        """Must DELETE the assistant and the phone number from VAPI."""
        business = self._make_business_with_voice()
        db = self._make_mock_db(business)
        mock_client = self._mock_delete_client()

        from app.services.voice_provisioning import deprovision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(deprovision_salon_receptionist(db, "biz-456"))

        # Two DELETE calls: one for assistant, one for phone number
        assert mock_client.delete.call_count == 2
        urls_called = [call[0][0] for call in mock_client.delete.call_args_list]
        assert "/assistant/asst-abc" in urls_called
        assert "/phone-number/ph-xyz" in urls_called

    def test_deprovision_clears_voice_fields_in_db(self):
        """After deprovisioning, voice fields must be unset in the DB and
        featured tier must be reset to free — not premium.

        WHY: the salon subscribed to Concierge specifically for the AI
        receptionist. Removing that feature should return the listing to its
        baseline free state, not silently grant a paid premium tier the owner
        never purchased."""
        business = self._make_business_with_voice()
        db = self._make_mock_db(business)
        mock_client = self._mock_delete_client()

        from app.services.voice_provisioning import deprovision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(deprovision_salon_receptionist(db, "biz-456"))

        db.businesses.update_one.assert_called_once()
        call_args = db.businesses.update_one.call_args
        update_arg = call_args[0][1]
        # Must reset to "free", not "premium" — deprovisioning removes the
        # Concierge feature; it does not grant a paid premium upgrade.
        assert update_arg["$set"]["featured.tier"] == "free"
        assert "voice_phone_number" in update_arg["$unset"]
        assert "vapi_phone_number_id" in update_arg["$unset"]
        assert "vapi_assistant_id" in update_arg["$unset"]

    def test_deprovision_404_when_business_missing(self):
        """Raises ValueError when business_id is not in the DB."""
        db = MagicMock()
        db.businesses.find_one = AsyncMock(return_value=None)

        from app.services.voice_provisioning import deprovision_salon_receptionist

        with pytest.raises(ValueError, match="not found"):
            asyncio.run(deprovision_salon_receptionist(db, "nonexistent"))

    def test_deprovision_continues_when_vapi_returns_error(self):
        """If VAPI returns an error (e.g. resource already deleted), the DB
        should still be cleaned up — the function must not raise."""
        import httpx

        business = self._make_business_with_voice()
        db = self._make_mock_db(business)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Simulate 404 from VAPI (resource already gone)
        error_resp = MagicMock()
        error_resp.status_code = 404
        mock_client.delete = AsyncMock(
            side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=error_resp)
        )

        from app.services.voice_provisioning import deprovision_salon_receptionist

        with patch("app.services.voice_provisioning.httpx.AsyncClient", return_value=mock_client):
            # Should NOT raise even though VAPI returned 404
            asyncio.run(deprovision_salon_receptionist(db, "biz-456"))

        # DB cleanup must still happen
        db.businesses.update_one.assert_called_once()


# ===== Admin endpoint tests =================================================

@pytest.fixture
def client(seeded_db):
    from app.main import app
    return TestClient(app)


def _first_business(seeded_db) -> Dict[str, Any]:
    return asyncio.run(seeded_db.businesses.find_one({"city_id": {"$exists": True}}))


class TestAdminProvisionEndpoint:
    """Tests for POST /api/v1/admin/businesses/{id}/provision-voice."""

    def test_provision_voice_returns_200_on_success(self, client, seeded_db):
        """Happy path: 200 with phone_number, assistant_id, phone_number_id."""
        biz = _first_business(seeded_db)

        mock_result = {
            "phone_number": "(669) 232-8894",
            "assistant_id": "asst-abc",
            "phone_number_id": "ph-xyz",
        }
        with patch(
            "app.routes.api.v1.admin_voice.provision_salon_receptionist",
            new=AsyncMock(return_value=mock_result),
        ):
            r = client.post(f"/api/v1/admin/businesses/{biz['_id']}/provision-voice")

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["phone_number"] == "(669) 232-8894"
        assert data["assistant_id"] == "asst-abc"
        assert data["phone_number_id"] == "ph-xyz"

    def test_provision_voice_returns_404_for_unknown_business(self, client):
        """When the service raises ValueError (business not found), the
        endpoint must return 404."""
        with patch(
            "app.routes.api.v1.admin_voice.provision_salon_receptionist",
            new=AsyncMock(side_effect=ValueError("Business 'nonexistent' not found")),
        ):
            r = client.post("/api/v1/admin/businesses/nonexistent/provision-voice")

        assert r.status_code == 404, r.text

    def test_provision_voice_returns_502_on_vapi_failure(self, client, seeded_db):
        """When the VAPI call fails, the endpoint should return 502."""
        biz = _first_business(seeded_db)

        with patch(
            "app.routes.api.v1.admin_voice.provision_salon_receptionist",
            new=AsyncMock(side_effect=RuntimeError("VAPI connection failed")),
        ):
            r = client.post(f"/api/v1/admin/businesses/{biz['_id']}/provision-voice")

        assert r.status_code == 502, r.text


class TestAdminDeprovisionEndpoint:
    """Tests for POST /api/v1/admin/businesses/{id}/deprovision-voice."""

    def test_deprovision_voice_returns_200_on_success(self, client, seeded_db):
        """Happy path: 200 with ok: true."""
        biz = _first_business(seeded_db)

        with patch(
            "app.routes.api.v1.admin_voice.deprovision_salon_receptionist",
            new=AsyncMock(return_value=None),
        ):
            r = client.post(f"/api/v1/admin/businesses/{biz['_id']}/deprovision-voice")

        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

    def test_deprovision_voice_returns_404_for_unknown_business(self, client):
        """When the service raises ValueError (business not found), 404."""
        with patch(
            "app.routes.api.v1.admin_voice.deprovision_salon_receptionist",
            new=AsyncMock(side_effect=ValueError("Business 'nonexistent' not found")),
        ):
            r = client.post("/api/v1/admin/businesses/nonexistent/deprovision-voice")

        assert r.status_code == 404, r.text


# ===== Owner voice endpoint tests ===========================================

class TestOwnerVoiceEndpoint:
    """Tests for GET /api/v1/owner/voice."""

    def _make_session_cookie(self, email: str) -> str:
        """Generate a signed session cookie for the given email using the service."""
        from app.services.owner_auth import sign_session
        return sign_session(email)

    def test_owner_voice_returns_active_when_provisioned(self, client, seeded_db):
        """When the owner's business has a voice_phone_number, returns active=true."""
        biz = _first_business(seeded_db)
        email = "owner@example.com"

        # Set up the business as claimed with a voice number
        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$set": {
                    "claimed_email": email,
                    "voice_phone_number": "(669) 232-8894",
                }},
            )
        )

        cookie = self._make_session_cookie(email)
        r = client.get(
            "/api/v1/owner/voice",
            headers={"Cookie": f"kb_owner_session={cookie}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["active"] is True
        assert data["phone_number"] == "(669) 232-8894"

    def test_owner_voice_returns_inactive_when_not_provisioned(self, client, seeded_db):
        """When the owner's business has no voice number, returns active=false."""
        biz = _first_business(seeded_db)
        email = "owner2@example.com"

        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$set": {"claimed_email": email}},
                # Make sure no voice_phone_number field exists
            )
        )
        asyncio.run(
            seeded_db.businesses.update_one(
                {"_id": biz["_id"]},
                {"$unset": {"voice_phone_number": ""}},
            )
        )

        cookie = self._make_session_cookie(email)
        r = client.get(
            "/api/v1/owner/voice",
            headers={"Cookie": f"kb_owner_session={cookie}"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["active"] is False
        assert "phone_number" not in data

    def test_owner_voice_returns_401_without_session(self, client):
        """Without a session cookie, returns 401."""
        r = client.get("/api/v1/owner/voice")
        assert r.status_code == 401, r.text

    def test_owner_voice_returns_404_when_no_business(self, client, seeded_db):
        """When the owner email doesn't match any business, returns 404."""
        cookie = self._make_session_cookie("nobody@example.com")
        r = client.get(
            "/api/v1/owner/voice",
            headers={"Cookie": f"kb_owner_session={cookie}"},
        )
        assert r.status_code == 404, r.text
