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
        """lookup_rating without existing_place_id uses Text Search then Place Details.

        WHY both endpoints are mocked: _search_and_fetch finds the place_id via
        text search (POST), then calls _fetch_by_place_id (GET) to get the full
        rating and hours. The test verifies the full two-call flow.

        WHY Places API (New) format: the key is created with the new API, which
        uses POST /v1/places:searchText (not GET textsearch/json) and returns
        {places: [{id, displayName.text, ...}]} (not {results: [{place_id, name}]}).
        """
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).return_value = httpx.Response(
                200,
                json={
                    "places": [
                        {
                            "id": "ChIJ_place_123",
                            "displayName": {"text": "Test Salon", "languageCode": "en"},
                        }
                    ],
                },
            )
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_place_123"
            ).return_value = httpx.Response(
                200,
                json={
                    "id": "ChIJ_place_123",
                    "rating": 4.7,
                    "userRatingCount": 312,
                    "regularOpeningHours": {
                        "periods": [
                            {
                                "open": {"day": 1, "hour": 9, "minute": 0},
                                "close": {"day": 1, "hour": 18, "minute": 0},
                            },
                        ]
                    },
                },
            )

            result = await google_places.lookup_rating("Test Salon", "Miami")

        assert result is not None
        assert result.place_id == "ChIJ_place_123"
        assert result.rating == 4.7
        assert result.review_count == 312
        assert len(result.hours) == 7
        monday = next(h for h in result.hours if h.day == "mon")
        assert monday.opens_at == "09:00"
        assert monday.closes_at == "18:00"
        assert monday.closed is False

    @pytest.mark.asyncio
    async def test_returns_none_on_no_results(self, respx_mock):
        """lookup_rating returns None when Places API finds no match."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).return_value = httpx.Response(200, json={})

            result = await google_places.lookup_rating("Nonexistent Salon", "Miami")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self, respx_mock):
        """lookup_rating returns None on a network failure (never raises)."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).side_effect = httpx.NetworkError("connection refused")

            result = await google_places.lookup_rating("Test Salon", "Miami")

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_place_details_when_place_id_known(self, respx_mock):
        """lookup_rating with existing_place_id uses Place Details, not Text Search."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_existing_place"
            ).return_value = httpx.Response(
                200,
                json={"id": "ChIJ_existing_place", "rating": 4.9, "userRatingCount": 800},
            )
            # Text Search should NOT be called — would 400 if it were
            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).return_value = httpx.Response(400, json={"error": "should not call this"})

            result = await google_places.lookup_rating(
                "Test Salon", "Miami", existing_place_id="ChIJ_existing_place"
            )

        assert result is not None
        assert result.place_id == "ChIJ_existing_place"
        assert result.rating == 4.9
        assert result.review_count == 800

    @pytest.mark.asyncio
    async def test_returns_none_when_place_details_has_no_rating(self, respx_mock):
        """lookup_rating returns None when Place Details has no rating (brand-new business)."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).return_value = httpx.Response(
                200,
                json={
                    "places": [{"id": "ChIJ_no_rating", "displayName": {"text": "New Salon"}}],
                },
            )
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_no_rating"
            ).return_value = httpx.Response(200, json={"id": "ChIJ_no_rating"})

            result = await google_places.lookup_rating("New Salon", "Miami")

        assert result is None

    @pytest.mark.asyncio
    async def test_hours_populated_when_place_has_opening_hours(self, respx_mock):
        """Hours are returned as a full 7-day list when Place Details includes regularOpeningHours.

        WHY integer hour/minute: Places API (New) uses {day, hour, minute} integers
        not the legacy "time": "0900" string.
        """
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_known"
            ).return_value = httpx.Response(
                200,
                json={
                    "id": "ChIJ_known",
                    "rating": 4.5,
                    "userRatingCount": 200,
                    "regularOpeningHours": {
                        "periods": [
                            {"open": {"day": 1, "hour": 9, "minute": 0}, "close": {"day": 1, "hour": 18, "minute": 0}},
                            {"open": {"day": 2, "hour": 9, "minute": 0}, "close": {"day": 2, "hour": 18, "minute": 0}},
                            {"open": {"day": 5, "hour": 10, "minute": 0}, "close": {"day": 5, "hour": 20, "minute": 0}},
                            {"open": {"day": 6, "hour": 10, "minute": 0}, "close": {"day": 6, "hour": 18, "minute": 0}},
                        ]
                    },
                },
            )

            result = await google_places.lookup_rating(
                "Any Salon", "Miami", existing_place_id="ChIJ_known"
            )

        assert result is not None
        assert len(result.hours) == 7
        open_days = sorted(h.day for h in result.hours if not h.closed)
        assert open_days == ["fri", "mon", "sat", "tue"]
        closed_days = sorted(h.day for h in result.hours if h.closed)
        assert closed_days == ["sun", "thu", "wed"]
        fri = next(h for h in result.hours if h.day == "fri")
        assert fri.opens_at == "10:00"
        assert fri.closes_at == "20:00"

    @pytest.mark.asyncio
    async def test_hours_empty_when_opening_hours_has_empty_periods(self, respx_mock):
        """Hours list is [] when regularOpeningHours.periods is empty (Google has no data).

        WHY: empty periods means Google doesn't know the hours, not that the
        business is always closed. Returning [] tells the sync to leave any
        manually-entered hours alone rather than overwriting them with 7 closed days.
        """
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_empty_periods"
            ).return_value = httpx.Response(
                200,
                json={
                    "id": "ChIJ_empty_periods",
                    "rating": 4.0,
                    "userRatingCount": 50,
                    "regularOpeningHours": {"periods": []},
                },
            )

            result = await google_places.lookup_rating(
                "Any Salon", "Miami", existing_place_id="ChIJ_empty_periods"
            )

        assert result is not None
        assert result.hours == []

    @pytest.mark.asyncio
    async def test_hours_empty_when_place_has_no_opening_hours(self, respx_mock):
        """Hours list is [] when Place Details has no regularOpeningHours field at all."""
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_no_hours"
            ).return_value = httpx.Response(
                200,
                json={"id": "ChIJ_no_hours", "rating": 4.0, "userRatingCount": 50},
            )

            result = await google_places.lookup_rating(
                "Any Salon", "Miami", existing_place_id="ChIJ_no_hours"
            )

        assert result is not None
        assert result.hours == []

    @pytest.mark.asyncio
    async def test_retries_on_429_and_succeeds(self, respx_mock):
        """lookup_rating retries after a 429 and returns the result on the second attempt.

        WHY this test exists: before the retry fix, a single 429 would permanently
        fail the business — the sync counted it as 'failed' and never retried.
        After the fix, the client backs off and tries again up to _MAX_RETRY_ATTEMPTS times.
        """
        from app.services import google_places
        from unittest.mock import AsyncMock

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # First call returns 429; second call returns valid data
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_rate_limited"
            ).side_effect = [
                httpx.Response(429, json={"error": "RESOURCE_EXHAUSTED"}),
                httpx.Response(200, json={"id": "ChIJ_rate_limited", "rating": 4.2, "userRatingCount": 150}),
            ]

            result = await google_places.lookup_rating(
                "Test Salon", "Miami", existing_place_id="ChIJ_rate_limited"
            )

        assert result is not None, "should have succeeded on the second attempt"
        assert result.rating == 4.2
        assert result.review_count == 150
        # Confirm sleep was called once (one retry)
        assert mock_sleep.call_count == 1
        # Confirm backoff delay: attempt 0 → 2.0 * 2^0 = 2.0s
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries_on_429(self, respx_mock):
        """lookup_rating returns None after exhausting all retry attempts on 429.

        WHY: verifies the retry limit is actually enforced and the function
        doesn't loop forever. With _MAX_RETRY_ATTEMPTS = 3, we expect 4 total
        attempts (original + 3 retries), all returning 429, then None.
        """
        from app.services import google_places
        from app.services.google_places import _MAX_RETRY_ATTEMPTS
        from unittest.mock import AsyncMock

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # All attempts return 429
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_always_rate_limited"
            ).return_value = httpx.Response(429, json={"error": "RESOURCE_EXHAUSTED"})

            result = await google_places.lookup_rating(
                "Test Salon", "Miami", existing_place_id="ChIJ_always_rate_limited"
            )

        assert result is None, "should give up after max retries"
        # sleep was called _MAX_RETRY_ATTEMPTS times (once per retry, not on the final give-up)
        assert mock_sleep.call_count == _MAX_RETRY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_text_search_retries_on_429(self, respx_mock):
        """429 on text search (no existing place_id) also triggers retry.

        WHY: the retry fix applies to BOTH API calls — text search (POST) and
        place details (GET). Without this, businesses without a cached place_id
        would be counted as 'no_match' on any rate-limited text search.
        """
        from app.services import google_places
        from unittest.mock import AsyncMock

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # Text search: first 429, then success
            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).side_effect = [
                httpx.Response(429, json={"error": "RESOURCE_EXHAUSTED"}),
                httpx.Response(200, json={
                    "places": [{"id": "ChIJ_found", "displayName": {"text": "Test Salon"}}]
                }),
            ]
            # Details fetch succeeds immediately
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_found"
            ).return_value = httpx.Response(
                200,
                json={"id": "ChIJ_found", "rating": 4.5, "userRatingCount": 200},
            )

            result = await google_places.lookup_rating("Test Salon", "Miami")

        assert result is not None, "should succeed after retrying the text search"
        assert result.place_id == "ChIJ_found"
        assert result.rating == 4.5
        assert mock_sleep.call_count == 1


# ── admin sync endpoint tests ────────────────────────────────────────────────

@pytest.fixture
def admin_client(seeded_db):
    from app.main import app
    from fastapi.testclient import TestClient
    import os

    client = TestClient(app)
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

        monkeypatch.setenv("ADMIN_API_KEY", "test-secret")
        get_settings.cache_clear()

        try:
            client = TestClient(app, follow_redirects=False)
            r = client.get("/admin/sync")
            assert r.status_code == 401
        finally:
            monkeypatch.delenv("ADMIN_API_KEY", raising=False)
            get_settings.cache_clear()

    def test_sync_page_loads_with_auth(self, seeded_db, monkeypatch):
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module

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
        assert r.status_code == 303
        assert "/admin/sync" in r.headers["location"]
        assert "updated=" in r.headers["location"]


# ── Business model hide_ratings field ────────────────────────────────────────

class TestBusinessHideRatings:
    def test_hide_ratings_defaults_to_false(self):
        """New business records default to showing ratings (hide_ratings=False).

        WHY: False default means a freshly synced rating appears on the listing
        automatically without the admin having to opt in for every business.
        The admin opts OUT on a per-business basis, which is the rare case.
        """
        from app.models import Business
        b = Business(
            network_id="net1",
            city_id="city1",
            slug="test-salon",
            name="Test Salon",
        )
        assert b.hide_ratings is False

    def test_hide_ratings_can_be_set_true(self):
        """hide_ratings can be set to True to suppress rating display."""
        from app.models import Business
        b = Business(
            network_id="net1",
            city_id="city1",
            slug="test-salon",
            name="Test Salon",
            hide_ratings=True,
        )
        assert b.hide_ratings is True

    def test_hide_ratings_survives_model_round_trip(self):
        """hide_ratings is preserved when the model is serialised and re-parsed."""
        from app.models import Business
        b = Business(
            network_id="net1",
            city_id="city1",
            slug="test-salon",
            name="Test Salon",
            hide_ratings=True,
        )
        data = b.model_dump(by_alias=True)
        b2 = Business(**data)
        assert b2.hide_ratings is True


# ── Admin settings page — ratings_min_review_count ───────────────────────────

class TestAdminSettingsRatingsThreshold:
    def test_settings_page_shows_ratings_min_field(self, seeded_db, monkeypatch):
        """The admin settings page renders the ratings minimum review count field."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app)
        r = client.get("/admin/settings")
        assert r.status_code == 200
        assert "ratings_min_review_count" in r.text
        assert "Minimum reviews" in r.text

    def test_settings_page_saves_ratings_min(self, seeded_db, monkeypatch):
        """POSTing a new threshold saves it and redirects with saved=1."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        from unittest.mock import AsyncMock, patch

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app, follow_redirects=False)
        with patch(
            "app.routes.admin.settings_admin.update_site_settings",
            new_callable=AsyncMock,
        ) as mock_save:
            r = client.post(
                "/admin/settings",
                data={
                    "ratings_min_review_count": "35",
                    "marketing_ai_enabled": "on",
                },
            )

        assert r.status_code == 303
        assert "saved=1" in r.headers["location"]
        # Confirm the parsed integer (not the raw string) was sent to the DB
        call_kwargs = mock_save.call_args[0][0]
        assert call_kwargs.get("ratings_min_review_count") == 35

    def test_settings_page_treats_blank_threshold_as_none(self, seeded_db, monkeypatch):
        """Clearing the field (empty string) sends None so the DB $unsets it and the default of 20 kicks in."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        from unittest.mock import AsyncMock, patch

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app, follow_redirects=False)
        with patch(
            "app.routes.admin.settings_admin.update_site_settings",
            new_callable=AsyncMock,
        ) as mock_save:
            r = client.post(
                "/admin/settings",
                data={"ratings_min_review_count": ""},
            )

        assert r.status_code == 303
        call_kwargs = mock_save.call_args[0][0]
        # None causes $unset in the DB so the service falls back to its default of 20
        assert call_kwargs.get("ratings_min_review_count") is None

    def test_settings_page_rejects_out_of_range_threshold(self, seeded_db, monkeypatch):
        """A threshold outside the valid 1–10000 range is treated as None (no change)."""
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        from unittest.mock import AsyncMock, patch

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)

        client = TestClient(app, follow_redirects=False)
        with patch(
            "app.routes.admin.settings_admin.update_site_settings",
            new_callable=AsyncMock,
        ) as mock_save:
            r = client.post(
                "/admin/settings",
                data={"ratings_min_review_count": "0"},
            )

        assert r.status_code == 303
        call_kwargs = mock_save.call_args[0][0]
        assert call_kwargs.get("ratings_min_review_count") is None
