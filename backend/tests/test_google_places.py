"""Tests for the Google Places rating service and admin sync endpoint."""
from __future__ import annotations

import pytest
import httpx

from unittest.mock import AsyncMock, patch, MagicMock


# ── google_places service unit tests ────────────────────────────────────────

class TestIsConfigured:
    def test_false_when_no_key(self, monkeypatch):
        from app.config import Settings
        with patch("app.services.google_places.get_settings", return_value=Settings(
            google_places_api_key=""
        )):
            from app.services import google_places
            # Force reload of the function using the patched settings
            assert google_places.is_configured() is False

    def test_true_when_key_set(self):
        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"
            from app.services import google_places
            assert google_places.is_configured() is True


class TestLookupRating:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_api_key(self):
        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = ""
            from app.services import google_places
            result = await google_places.lookup_rating("Test Salon", "Miami")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_rating_from_text_search(self, respx_mock):
        """lookup_rating without existing_place_id uses Text Search."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # Mock the text search response
            search_pattern = respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
            )
            search_pattern.return_value = httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "place_id": "ChIJ_place_123",
                            "name": "Test Salon",
                            "rating": 4.7,
                            "user_ratings_total": 312,
                        }
                    ],
                    "status": "OK",
                },
            )

            result = await google_places.lookup_rating("Test Salon", "Miami")

        assert result is not None
        assert result.place_id == "ChIJ_place_123"
        assert result.rating == 4.7
        assert result.review_count == 312

    @pytest.mark.asyncio
    async def test_returns_none_on_no_results(self, respx_mock):
        """lookup_rating returns None when Places API finds no match."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
            ).return_value = httpx.Response(200, json={"results": [], "status": "ZERO_RESULTS"})

            result = await google_places.lookup_rating("Nonexistent Salon", "Miami")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self, respx_mock):
        """lookup_rating returns None on a network failure (never raises)."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
            ).side_effect = httpx.NetworkError("connection refused")

            result = await google_places.lookup_rating("Test Salon", "Miami")

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_place_details_when_place_id_known(self, respx_mock):
        """lookup_rating with existing_place_id uses Place Details, not Text Search."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # Details endpoint should be called
            respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/details/json"
            ).return_value = httpx.Response(
                200,
                json={
                    "result": {"rating": 4.9, "user_ratings_total": 800},
                    "status": "OK",
                },
            )
            # Text Search should NOT be called
            respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
            ).return_value = httpx.Response(400, json={"error": "should not call this"})

            result = await google_places.lookup_rating(
                "Test Salon", "Miami", existing_place_id="ChIJ_existing_place"
            )

        assert result is not None
        assert result.place_id == "ChIJ_existing_place"
        assert result.rating == 4.9
        assert result.review_count == 800

    @pytest.mark.asyncio
    async def test_returns_none_when_result_has_no_rating(self, respx_mock):
        """lookup_rating returns None when the matched place has no rating."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
            ).return_value = httpx.Response(
                200,
                json={
                    "results": [{"place_id": "ChIJ_no_rating", "name": "New Salon"}],
                    "status": "OK",
                },
            )

            result = await google_places.lookup_rating("New Salon", "Miami")

        assert result is None


# ── admin sync endpoint tests ────────────────────────────────────────────────

@pytest.fixture
def admin_client(seeded_db):
    from app.main import app
    from fastapi.testclient import TestClient
    import os

    client = TestClient(app)
    # Set the admin cookie so require_admin passes
    client.cookies.set(
        "mkb_admin",
        "test-admin-token",
        domain="testserver",
    )
    return client


class TestSyncPage:
    def test_sync_page_returns_401_without_auth(self, seeded_db, monkeypatch):
        """When ADMIN_API_KEY is configured, requests without the cookie get 401."""
        from app.main import app
        from fastapi.testclient import TestClient
        from app.config import get_settings

        # WHY: require_admin only gates requests when ADMIN_API_KEY is set;
        # with no key the gate is intentionally open for local dev. Setting
        # the env var here and clearing the lru_cache exercises the real
        # production code path.
        monkeypatch.setenv("ADMIN_API_KEY", "test-secret")
        get_settings.cache_clear()

        try:
            client = TestClient(app, follow_redirects=False)
            r = client.get("/admin/sync")
            assert r.status_code == 401
        finally:
            # Always restore — subsequent tests depend on the open gate
            monkeypatch.delenv("ADMIN_API_KEY", raising=False)
            get_settings.cache_clear()

    def test_sync_page_loads_with_auth(self, seeded_db, monkeypatch):
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module

        # Bypass the require_admin dependency
        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app)
        r = client.get("/admin/sync")
        assert r.status_code == 200
        assert "Google Ratings Sync" in r.text
        assert "Coverage" in r.text

    def test_sync_page_counts_live_businesses(self, seeded_db, monkeypatch):
        """Coverage stats must count 'live' businesses, not 'published' (wrong status value).

        WHY this test exists: sync_admin.py originally queried {"status": "published"}
        but the PublishStatus enum uses "live". The coverage dashboard showed 0 even
        when 55+ salons were in the directory.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import re

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app)
        r = client.get("/admin/sync")
        assert r.status_code == 200
        # The seeded_db includes live businesses (status="live"). The coverage
        # section should show a non-zero total — if it shows 0, the status filter
        # is querying the wrong value.
        #
        # Extract the number immediately before "TOTAL SALONS" in the HTML.
        # The template renders: <div ...>NN</div><div ...>TOTAL SALONS</div>
        match = re.search(r">(\d+)<[^>]+>[^<]*TOTAL SALONS", r.text, re.IGNORECASE)
        if match:
            assert int(match.group(1)) > 0, (
                "sync page shows 0 total salons even though seeded_db has live businesses. "
                "This means the status filter is using the wrong value."
            )

    def test_sync_page_shows_no_key_warning_when_not_configured(self, seeded_db, monkeypatch):
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: False)

        client = TestClient(app)
        r = client.get("/admin/sync")
        assert "GOOGLE_PLACES_API_KEY" in r.text or "API key required" in r.text


class TestSyncRatingsPost:
    def test_sync_redirects_with_error_when_no_api_key(self, seeded_db, monkeypatch):
        """Without an API key, POST redirects back to the sync page with an error flag."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: False)

        # WHY follow_redirects=False: we want to inspect the redirect itself,
        # not the page it leads to.
        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303
        assert "error:no-key" in r.headers["location"]

    def test_sync_runs_and_redirects_when_configured(self, seeded_db, monkeypatch):
        """With API key configured and mocked lookup, sync completes and redirects."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            return PlaceRating(
                place_id="ChIJ_mock",
                rating=4.5,
                review_count=100,
            )

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        # Should redirect to sync page with result summary
        assert r.status_code == 303
        assert "/admin/sync" in r.headers["location"]
        assert "updated=" in r.headers["location"]
