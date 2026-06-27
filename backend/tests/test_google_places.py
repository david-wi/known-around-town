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

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.call_gateway_text", new_callable=AsyncMock,
                   return_value='{"same_business": true, "confidence": "high"}'):
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

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.call_gateway_text", new_callable=AsyncMock,
                   return_value='{"same_business": true, "confidence": "high"}'):
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
    async def test_hours_preserves_both_periods_when_business_closes_for_lunch(self, respx_mock):
        """When a business has two open/close periods on the same day (lunch break), both are stored.

        WHY this test exists: the original code used day_map[day_int] = (opens, closes),
        which overwrites the morning period with the afternoon one when Google returns two
        periods for Monday (e.g. 09:00-12:00 and 13:00-18:00). The business appeared to
        open in the afternoon instead of the morning. The fix accumulates all periods per
        day and emits one HoursEntry per period.
        """
        from app.services import google_places

        with patch("app.services.google_places.get_settings") as mock_settings:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_lunch_break"
            ).return_value = httpx.Response(
                200,
                json={
                    "id": "ChIJ_lunch_break",
                    "rating": 4.3,
                    "userRatingCount": 180,
                    "regularOpeningHours": {
                        "periods": [
                            # Monday: open 9am–12pm, then again 1pm–6pm (lunch break)
                            {"open": {"day": 1, "hour": 9, "minute": 0}, "close": {"day": 1, "hour": 12, "minute": 0}},
                            {"open": {"day": 1, "hour": 13, "minute": 0}, "close": {"day": 1, "hour": 18, "minute": 0}},
                            # Tuesday: normal single period
                            {"open": {"day": 2, "hour": 9, "minute": 0}, "close": {"day": 2, "hour": 18, "minute": 0}},
                        ]
                    },
                },
            )

            result = await google_places.lookup_rating(
                "Nail Salon", "Miami", existing_place_id="ChIJ_lunch_break"
            )

        assert result is not None
        # 2 Monday periods + 1 Tuesday period + 5 closed days = 8 entries total
        assert len(result.hours) == 8, (
            f"Expected 8 entries (2 Monday + 1 Tuesday + 5 closed), got {len(result.hours)}"
        )

        monday_entries = [h for h in result.hours if h.day == "mon"]
        assert len(monday_entries) == 2, (
            f"Expected 2 Monday entries for a lunch-break business, got {len(monday_entries)}. "
            "The morning period was likely overwritten by the afternoon period."
        )

        # Entries are ordered by period as Google returns them
        assert monday_entries[0].opens_at == "09:00", "morning period should be first"
        assert monday_entries[0].closes_at == "12:00", "morning period should close at noon"
        assert monday_entries[1].opens_at == "13:00", "afternoon period should be second"
        assert monday_entries[1].closes_at == "18:00", "afternoon period should close at 6pm"

        tuesday_entries = [h for h in result.hours if h.day == "tue"]
        assert len(tuesday_entries) == 1
        assert tuesday_entries[0].opens_at == "09:00"
        assert tuesday_entries[0].closes_at == "18:00"

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
        """lookup_rating raises RateLimitError after exhausting all retry attempts on 429.

        WHY: verifies the retry limit is actually enforced and the function
        doesn't loop forever. With _MAX_RETRY_ATTEMPTS = 3, we expect 4 total
        attempts (original + 3 retries), all returning 429, then RateLimitError.
        Raising an exception (rather than returning None) lets the sync loop
        distinguish "quota exhausted" from "business not on Google" so it can
        retry the business on the next sync run instead of treating it as a
        permanent no-match.
        """
        import pytest as _pytest
        from app.services import google_places
        from app.services.google_places import _MAX_RETRY_ATTEMPTS, RateLimitError
        from unittest.mock import AsyncMock

        with patch("app.services.google_places.get_settings") as mock_settings, \
             patch("app.services.google_places.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            # All attempts return 429
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_always_rate_limited"
            ).return_value = httpx.Response(429, json={"error": "RESOURCE_EXHAUSTED"})

            with _pytest.raises(RateLimitError):
                await google_places.lookup_rating(
                    "Test Salon", "Miami", existing_place_id="ChIJ_always_rate_limited"
                )

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
             patch("app.services.google_places.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("app.services.google_places.call_gateway_text", new_callable=AsyncMock,
                   return_value='{"same_business": true, "confidence": "high"}'):
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


# ── AI business-match judge ──────────────────────────────────────────────────

class TestLlmSameBusiness:
    """Unit tests for _llm_same_business — the AI judge that decides whether a
    Google Text Search result is the SAME real-world business we searched for.

    WHY this class exists: a string-overlap heuristic used to make this call and
    got it wrong — it treated "Kure Spa" and "Lux MedSpa Brickell" as the same
    business because both contained "spa" and "Brickell". The judgment now belongs
    to the model. These tests MOCK the AI gateway helper so no network call is made;
    they prove the model's verdict (and only the model's verdict) gates the result,
    and that ANY failure of the judge is treated as "not the same business".
    """

    def _patch_gateway(self, **kwargs):
        # Patches the gateway helper as the google_places module sees it.
        return patch("app.services.google_places.call_gateway_text", new_callable=AsyncMock, **kwargs)

    def _call(self, searched="Kure Spa", candidate="Lux MedSpa Brickell"):
        from app.services.google_places import _llm_same_business
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            _llm_same_business(
                searched_name=searched,
                city="Miami",
                state="FL",
                candidate_name=candidate,
                candidate_address="123 Brickell Ave, Miami, FL",
                candidate_types=["spa", "beauty_salon"],
            )
        )

    def test_returns_false_when_model_says_not_same(self):
        """Model answers same_business=false → judge returns False (reject)."""
        with self._patch_gateway(return_value='{"same_business": false, "confidence": "high"}'):
            assert self._call() is False

    def test_returns_true_when_model_says_same(self):
        """Model answers same_business=true → judge returns True (accept)."""
        with self._patch_gateway(return_value='{"same_business": true, "confidence": "high"}'):
            assert self._call("IGK Salon", "IGK Hair Salon") is True

    def test_strips_code_fence_around_json(self):
        """A model that wraps the JSON in a ``` fence is still parsed correctly."""
        fenced = '```json\n{"same_business": true, "confidence": "low"}\n```'
        with self._patch_gateway(return_value=fenced):
            assert self._call("IGK Salon", "IGK Hair Salon") is True

    def test_fail_safe_when_gateway_raises(self):
        """Gateway error (unreachable/timeout/HTTP error) → False, never accept on failure."""
        from app.services.ai_caption import CaptionGenerationError
        with self._patch_gateway(side_effect=CaptionGenerationError("gateway unreachable")):
            assert self._call() is False

    def test_fail_safe_when_response_not_json(self):
        """Unparseable answer → False (fail-safe)."""
        with self._patch_gateway(return_value="I think these are probably the same place!"):
            assert self._call() is False

    def test_fail_safe_when_response_is_json_but_not_object(self):
        """Valid JSON that isn't an object (e.g. a bare string/array) → False."""
        with self._patch_gateway(return_value='"yes"'):
            assert self._call() is False

    def test_fail_safe_when_same_business_field_missing(self):
        """Object without same_business → not confirmed → False."""
        with self._patch_gateway(return_value='{"confidence": "high"}'):
            assert self._call() is False

    def test_only_explicit_boolean_true_accepts(self):
        """A truthy non-boolean (string "true") is NOT accepted — only real True."""
        with self._patch_gateway(return_value='{"same_business": "true"}'):
            assert self._call() is False

    def test_prompt_includes_our_name_and_candidate_fields(self):
        """The judge must actually send our name + the candidate's name/address/type.

        WHY: this proves the model is given real signal to judge on (not an empty
        or wrong prompt) and documents the exact content sent to the gateway.
        """
        with self._patch_gateway(return_value='{"same_business": false}') as mock_gw:
            self._call("Kure Spa", "Lux MedSpa Brickell")

        assert mock_gw.call_count == 1
        kwargs = mock_gw.call_args.kwargs
        assert kwargs["use_case"] == "light"
        # Generous token budget so a reasoning model's answer isn't truncated.
        assert kwargs["max_tokens_override"] >= 100
        content = kwargs["user_content"]
        assert "Kure Spa" in content
        assert "Lux MedSpa Brickell" in content
        assert "123 Brickell Ave" in content
        assert "beauty_salon" in content


class TestLookupRatingNameMatch:
    """End-to-end accept/reject via lookup_rating (mocked Text Search + Details +
    AI judge). These exercise the real _search_and_fetch path: text search returns
    a candidate place; the AI judge (mocked here) decides whether to proceed to the
    details fetch. A REJECT must return None and NOT fetch details; an ACCEPT must
    return the rating from the details call.

    WHY mock the judge (not call the live gateway): these tests must be
    deterministic and offline, and they prove the GATE — that the model's verdict
    is what allows or blocks the rating. The reject/fail-safe tests fail loudly if
    the gate is ever bypassed (they assert details was NOT fetched).
    """

    def _settings_patch(self):
        return patch("app.services.google_places.get_settings")

    def _judge_patch(self, **kwargs):
        return patch("app.services.google_places.call_gateway_text", new_callable=AsyncMock, **kwargs)

    @pytest.mark.asyncio
    async def test_rejects_kure_when_google_returns_lux(self, respx_mock):
        """Searched "Kure Spa — Brickell City Centre"; Google's top result is
        "Lux MedSpa Brickell"; the AI judge says NOT the same business →
        lookup_rating returns None and never fetches the (wrong) rating.

        This is the core regression: the previous string heuristic accepted this
        look-alike pair (shared "spa"/"Brickell") and attached Lux's rating to Kure.
        """
        from app.services import google_places

        with self._settings_patch() as mock_settings, \
             self._judge_patch(return_value='{"same_business": false, "confidence": "high"}'):
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            search_route = respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).mock(return_value=httpx.Response(
                200,
                json={"places": [{
                    "id": "ChIJ_lux_brickell",
                    "displayName": {"text": "Lux MedSpa Brickell"},
                    "formattedAddress": "78 SW 7th St, Miami, FL 33130",
                    "primaryType": "medical_spa",
                }]},
            ))
            # A details fetch here would mean we wrongly accepted the match.
            details_route = respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_lux_brickell"
            ).mock(return_value=httpx.Response(
                200, json={"id": "ChIJ_lux_brickell", "rating": 4.9, "userRatingCount": 500},
            ))

            result = await google_places.lookup_rating(
                "Kure Spa — Brickell City Centre", "Miami"
            )

        assert result is None, "wrong business (Lux) must be rejected for Kure"
        assert search_route.called
        assert not details_route.called, "must NOT fetch details for a rejected match"

    @pytest.mark.asyncio
    async def test_fail_safe_leaves_unrated_when_judge_errors(self, respx_mock):
        """If the AI judge call errors, lookup_rating must return None (fail-safe).

        A wrong rating is worse than no rating, so an unavailable judge must leave
        the business unrated — and must NOT fetch the candidate's rating.
        """
        from app.services import google_places
        from app.services.ai_caption import CaptionGenerationError

        with self._settings_patch() as mock_settings, \
             self._judge_patch(side_effect=CaptionGenerationError("gateway down")):
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).mock(return_value=httpx.Response(
                200,
                json={"places": [{
                    "id": "ChIJ_lux_brickell",
                    "displayName": {"text": "Lux MedSpa Brickell"},
                    "formattedAddress": "78 SW 7th St, Miami, FL 33130",
                }]},
            ))
            details_route = respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_lux_brickell"
            ).mock(return_value=httpx.Response(
                200, json={"id": "ChIJ_lux_brickell", "rating": 4.9, "userRatingCount": 500},
            ))

            result = await google_places.lookup_rating(
                "Kure Spa — Brickell City Centre", "Miami"
            )

        assert result is None, "judge failure must leave the business unrated"
        assert not details_route.called, "must NOT fetch details when the judge failed"

    @pytest.mark.asyncio
    async def test_accepts_exact_brand_match(self, respx_mock):
        """Searched "Sana Skin Studio"; Google returns the same; judge says yes
        → returns rating."""
        from app.services import google_places

        with self._settings_patch() as mock_settings, \
             self._judge_patch(return_value='{"same_business": true, "confidence": "high"}'):
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).mock(return_value=httpx.Response(
                200,
                json={"places": [{
                    "id": "ChIJ_sana",
                    "displayName": {"text": "Sana Skin Studio"},
                    "formattedAddress": "1 Main St, Miami, FL",
                }]},
            ))
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_sana"
            ).mock(return_value=httpx.Response(
                200, json={"id": "ChIJ_sana", "rating": 4.8, "userRatingCount": 240},
            ))

            result = await google_places.lookup_rating("Sana Skin Studio", "Miami")

        assert result is not None
        assert result.place_id == "ChIJ_sana"
        assert result.rating == 4.8

    @pytest.mark.asyncio
    async def test_accepts_brand_match_with_extra_generic_words(self, respx_mock):
        """Searched "IGK Salon"; Google returns "IGK Hair Salon"; judge says yes
        → accept.

        Proves the gate does not over-reject legitimate brand matches where the
        Google listing carries an extra generic business-type word.
        """
        from app.services import google_places

        with self._settings_patch() as mock_settings, \
             self._judge_patch(return_value='{"same_business": true, "confidence": "high"}'):
            mock_settings.return_value.google_places_api_key = "AIza-test-key"

            respx_mock.post(
                "https://places.googleapis.com/v1/places:searchText"
            ).mock(return_value=httpx.Response(
                200,
                json={"places": [{
                    "id": "ChIJ_igk",
                    "displayName": {"text": "IGK Hair Salon"},
                    "formattedAddress": "2 Ocean Dr, Miami, FL",
                }]},
            ))
            respx_mock.get(
                "https://places.googleapis.com/v1/places/ChIJ_igk"
            ).mock(return_value=httpx.Response(
                200, json={"id": "ChIJ_igk", "rating": 4.6, "userRatingCount": 130},
            ))

            result = await google_places.lookup_rating("IGK Salon", "Miami")

        assert result is not None
        assert result.place_id == "ChIJ_igk"
        assert result.rating == 4.6


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


class TestNeighborhoodFallback:
    """Neighborhood-name fallback in the ratings sync.

    Fort Lauderdale businesses (e.g., in Wilton Manors) fail a "Business Name
    Fort Lauderdale FL" Places search because Google knows them by their sub-city
    name. The fix tries each business neighborhood slug (converted to title case)
    as a fallback city when the primary city search finds nothing.
    """

    @pytest.fixture
    async def ft_laud_db(self, mock_db):
        """Insert a Fort Lauderdale city and a Wilton Manors business into the mock DB."""
        city_id = "city-ft-laud"
        await mock_db.cities.insert_one({"_id": city_id, "name": "Fort Lauderdale", "slug": "fort-lauderdale", "status": "live"})
        await mock_db.networks.insert_one({"_id": "net1", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"})
        await mock_db.businesses.insert_one({
            "_id": "biz-source-salon",
            "name": "Source Salon",
            "slug": "source-salon-wilton-manors",
            "city_id": city_id,
            "network_id": "net1",
            "status": "live",
            "neighborhood_slugs": ["wilton-manors"],
        })
        return mock_db

    def test_fallback_called_with_neighborhood_name_when_city_fails(self, ft_laud_db, monkeypatch):
        """lookup_rating is called with 'Wilton Manors' as city when Fort Lauderdale search fails.

        WHY: verifies the core fix — the fallback fires on a city-search miss and
        converts the slug to the title-cased name Google recognises.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append({"name": business_name, "city": city})
            # Primary city "Fort Lauderdale" fails; neighborhood "Wilton Manors" succeeds
            if city == "Wilton Manors":
                return PlaceRating(place_id="ChIJ_source", rating=4.8, review_count=210)
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        cities_tried = [c["city"] for c in call_log]
        assert "Fort Lauderdale" in cities_tried, "primary city search was not attempted"
        assert "Wilton Manors" in cities_tried, "neighborhood fallback was not tried"

    def test_fallback_not_called_when_business_has_place_id(self, mock_db, monkeypatch):
        """When a business already has a google_place_id, the neighborhood fallback is skipped.

        WHY: existing place_id means the business was already matched — using the fast
        place details endpoint skips discovery entirely. The fallback must not run
        for these businesses or it wastes API quota.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        import asyncio
        asyncio.get_event_loop().run_until_complete(mock_db.cities.insert_one(
            {"_id": "city-ft-laud2", "name": "Fort Lauderdale", "slug": "fort-lauderdale", "status": "live"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.networks.insert_one(
            {"_id": "net2", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.businesses.insert_one({
            "_id": "biz-already-matched",
            "name": "Known Salon",
            "slug": "known-salon-wilton-manors",
            "city_id": "city-ft-laud2",
            "network_id": "net2",
            "status": "live",
            "google_place_id": "ChIJ_already_known",
            "neighborhood_slugs": ["wilton-manors", "las-olas"],
        }))

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append({"name": business_name, "city": city, "place_id": existing_place_id})
            if existing_place_id:
                return PlaceRating(place_id=existing_place_id, rating=4.5, review_count=100)
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        # Only one call: the place_id details fetch. Fallback slug calls must not appear.
        assert len(call_log) == 1
        assert call_log[0]["place_id"] == "ChIJ_already_known"
        nbhd_cities = [c["city"] for c in call_log if c["place_id"] is None]
        assert nbhd_cities == [], f"unexpected fallback calls: {nbhd_cities}"

    def test_fallback_caps_at_3_slugs(self, mock_db, monkeypatch):
        """Fallback tries at most 3 neighborhood slugs even when more are present.

        WHY: an uncapped loop holding the semaphore for many slugs would starve
        concurrent sync slots and push total API calls beyond the intended ~30 req/s.
        The cap of 3 matches the [:3] slice in the implementation.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        import asyncio
        asyncio.get_event_loop().run_until_complete(mock_db.cities.insert_one(
            {"_id": "city-ft-laud3", "name": "Fort Lauderdale", "slug": "fort-lauderdale", "status": "live"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.networks.insert_one(
            {"_id": "net3", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.businesses.insert_one({
            "_id": "biz-many-slugs",
            "name": "Multi Neighborhood Salon",
            "slug": "multi-salon-ft-laud",
            "city_id": "city-ft-laud3",
            "network_id": "net3",
            "status": "live",
            "neighborhood_slugs": ["wilton-manors", "las-olas", "flagler-village", "victoria-park", "downtown-fort-lauderdale"],
        }))

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append(city)
            return None  # Always fails to force full fallback loop

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        # 1 primary city + at most 3 neighborhood fallbacks = at most 4 total calls
        # (Fort Lauderdale == city so no same-name skip here)
        assert len(call_log) <= 4, (
            f"Expected at most 4 lookup calls (1 primary + 3 fallbacks), got {len(call_log)}: {call_log}"
        )

    def test_fallback_stops_after_first_match(self, mock_db, monkeypatch):
        """Once a neighborhood fallback finds a match, no further slugs are tried.

        WHY: if slug[0] matches, we have the place_id we need — trying slug[1]
        and slug[2] would waste API quota on a business already resolved.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        import asyncio
        asyncio.get_event_loop().run_until_complete(mock_db.cities.insert_one(
            {"_id": "city-ft-laud4", "name": "Fort Lauderdale", "slug": "fort-lauderdale", "status": "live"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.networks.insert_one(
            {"_id": "net4", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"}
        ))
        asyncio.get_event_loop().run_until_complete(mock_db.businesses.insert_one({
            "_id": "biz-early-match",
            "name": "Wilton Salon",
            "slug": "wilton-salon-ft-laud",
            "city_id": "city-ft-laud4",
            "network_id": "net4",
            "status": "live",
            "neighborhood_slugs": ["wilton-manors", "las-olas", "flagler-village"],
        }))

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append(city)
            if city == "Wilton Manors":
                return PlaceRating(place_id="ChIJ_wilton", rating=4.6, review_count=88)
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        # Calls: "Fort Lauderdale" (miss) + "Wilton Manors" (hit) → stop
        # "Las Olas" and "Flagler Village" must NOT be called
        assert "Las Olas" not in call_log, f"should have stopped after Wilton Manors match; calls: {call_log}"
        assert "Flagler Village" not in call_log, f"should have stopped after Wilton Manors match; calls: {call_log}"
        assert "Wilton Manors" in call_log


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
        """POST /admin/sync/ratings queues a background sync and redirects immediately.

        The route now returns result=started right away — the actual sync runs
        as a FastAPI BackgroundTask. TestClient executes background tasks
        synchronously, so we can verify the DB was updated after the request.
        """
        import asyncio
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.admin.sync_admin as sync_mod
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)
        # Ensure the running-flag is clear before the test (module-level state)
        monkeypatch.setattr(sync_mod, "_sync_running", False)

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            return PlaceRating(
                place_id="ChIJ_mock",
                rating=4.5,
                review_count=100,
            )

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")

        # Route redirects immediately with result=started (sync runs in background)
        assert r.status_code == 303
        assert "/admin/sync" in r.headers["location"]
        assert "result=started" in r.headers["location"]

        # TestClient runs background tasks synchronously, so the DB is updated
        # by the time we reach this assertion.
        db = seeded_db
        rated_count = asyncio.get_event_loop().run_until_complete(
            db.businesses.count_documents({"status": "live", "google_rating": {"$ne": None}})
        )
        assert rated_count > 0, "Background sync should have updated at least one business"

    def test_unrated_only_skips_already_rated_businesses(self, mock_db, monkeypatch):
        """unrated_only=True only calls lookup_rating for businesses with no google_rating.

        WHY: confirms the quota-conservation feature works — the ~880 salons that
        already have ratings must NOT be passed to lookup_rating when unrated_only
        is set. Only the businesses without a rating (or with null) should be synced.
        """
        import asyncio
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.admin.sync_admin as sync_mod
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)
        monkeypatch.setattr(sync_mod, "_sync_running", False)

        # Seed: one business WITH a rating, one WITHOUT
        asyncio.get_event_loop().run_until_complete(
            mock_db.cities.insert_one({"_id": "city-test", "name": "Miami", "slug": "miami"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.networks.insert_one({"_id": "net-test", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_many([
                {"_id": "biz-rated", "name": "Already Rated Salon", "slug": "rated", "city_id": "city-test",
                 "network_id": "net-test", "status": "live", "google_rating": 4.5, "google_place_id": "ChIJ_already"},
                {"_id": "biz-unrated", "name": "Needs Rating Salon", "slug": "unrated", "city_id": "city-test",
                 "network_id": "net-test", "status": "live"},
            ])
        )

        synced_names = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            synced_names.append(business_name)
            return PlaceRating(place_id="ChIJ_new", rating=4.2, review_count=50)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings", data={"unrated_only": "1"})

        assert r.status_code == 303
        assert "unrated_only=1" in r.headers["location"], "redirect should include unrated_only flag"

        # Only the unrated business should have been synced
        assert "Needs Rating Salon" in synced_names, "unrated business should be synced"
        assert "Already Rated Salon" not in synced_names, "already-rated business should be skipped"

    def test_unrated_only_honored_from_query_string(self, mock_db, monkeypatch):
        """A programmatic caller passing ?unrated_only=true (query string, no form body)
        must get the unrated-only filter — NOT a silently-ignored full sync.

        WHY this test exists: the endpoint originally read unrated_only only from the
        form body (Form(...)). A script that passed ?unrated_only=true as a URL query
        string had it silently ignored, defaulting to a FULL sync of every business —
        which exhausted the entire daily Google Places API quota (Text Search AND Place
        Details per-day limits) and cost real money. This actually happened. The fix
        reads the query string as a fallback so the safe, cheap request is honored.

        This test proves the unrated-only filter is applied (only the unrated business
        is fetched) when the flag arrives via the query string with NO form data.
        """
        import asyncio
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.admin.sync_admin as sync_mod
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)
        monkeypatch.setattr(sync_mod, "_sync_running", False)

        # Seed: one business WITH a rating, one WITHOUT
        asyncio.get_event_loop().run_until_complete(
            mock_db.cities.insert_one({"_id": "city-test", "name": "Miami", "slug": "miami"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.networks.insert_one({"_id": "net-test", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_many([
                {"_id": "biz-rated", "name": "Already Rated Salon", "slug": "rated", "city_id": "city-test",
                 "network_id": "net-test", "status": "live", "google_rating": 4.5, "google_place_id": "ChIJ_already"},
                {"_id": "biz-unrated", "name": "Needs Rating Salon", "slug": "unrated", "city_id": "city-test",
                 "network_id": "net-test", "status": "live"},
            ])
        )

        synced_names = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            synced_names.append(business_name)
            return PlaceRating(place_id="ChIJ_new", rating=4.2, review_count=50)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        # Flag sent ONLY as a query-string param — no form body, mimicking a curl/script caller.
        r = client.post("/admin/sync/ratings?unrated_only=true")

        assert r.status_code == 303
        assert "unrated_only=1" in r.headers["location"], (
            "redirect should reflect unrated-only mode when ?unrated_only=true is in the query string"
        )

        # The unrated-only filter must have been applied: only the unrated business is fetched.
        assert "Needs Rating Salon" in synced_names, "unrated business should be synced"
        assert "Already Rated Salon" not in synced_names, (
            "already-rated business must NOT be synced — query-string unrated_only=true was ignored, "
            "meaning a full quota-exhausting sync ran instead of the safe unrated-only sync"
        )

    def test_full_sync_logs_quota_warning(self, mock_db, monkeypatch):
        """A FULL sync (no unrated_only) must emit a WARNING naming the business count.

        WHY: an accidental full sync exhausts the daily Google Places quota and costs
        money. The warning makes such an accident visible in the logs after the fact.
        """
        import asyncio
        import logging
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.admin.sync_admin as sync_mod
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)
        monkeypatch.setattr(sync_mod, "_sync_running", False)

        asyncio.get_event_loop().run_until_complete(
            mock_db.cities.insert_one({"_id": "city-test", "name": "Miami", "slug": "miami"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.networks.insert_one({"_id": "net-test", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_one(
                {"_id": "biz-1", "name": "Some Salon", "slug": "some", "city_id": "city-test",
                 "network_id": "net-test", "status": "live"}
            )
        )

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            return PlaceRating(place_id="ChIJ_x", rating=4.0, review_count=10)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        warnings = []

        class LogCapture(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    warnings.append(record.getMessage())

        handler = LogCapture()
        sync_logger = logging.getLogger("app.routes.admin.sync_admin")
        orig_level = sync_logger.level
        sync_logger.setLevel(logging.DEBUG)
        sync_logger.addHandler(handler)
        try:
            client = TestClient(app, follow_redirects=False)
            # No unrated_only anywhere → full sync.
            r = client.post("/admin/sync/ratings")
        finally:
            sync_logger.removeHandler(handler)
            sync_logger.setLevel(orig_level)

        assert r.status_code == 303
        full_warnings = [w for w in warnings if "FULL Google ratings sync" in w]
        assert full_warnings, f"Expected a FULL-sync quota warning; got warnings: {warnings}"
        assert "ALL 1 live businesses" in full_warnings[0], (
            f"Warning should name the business count that will be fetched; got: {full_warnings[0]}"
        )

    def test_rate_limit_error_counted_as_failed_not_no_match(self, mock_db, monkeypatch):
        """RateLimitError from lookup_rating counts as failed (transient), not no_match (permanent).

        WHY: quota exhaustion resets overnight; the business still needs a sync tomorrow.
        Counting it as no_match would permanently drop it from future unrated-only syncs.

        WHY test _run_sync_background directly: it owns the failed/no_match counters and
        emits the summary log line. Going through the HTTP layer adds TestClient background-
        task scheduling complexity without covering any additional logic.
        """
        import asyncio
        import logging
        import app.services.google_places as gp
        from app.routes.admin.sync_admin import _run_sync_background

        async def mock_lookup_raises(*args, **kwargs):
            raise gp.RateLimitError("quota exhausted")

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup_raises)

        businesses = [
            {"_id": "biz-rl", "name": "Rate Limited Salon", "city_id": "city-rl", "status": "live"},
        ]
        city_names = {"city-rl": "Miami"}

        log_records = []

        class LogCapture(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        handler = LogCapture()
        handler.setLevel(logging.DEBUG)
        sync_logger = logging.getLogger("app.routes.admin.sync_admin")
        orig_level = sync_logger.level
        sync_logger.setLevel(logging.DEBUG)
        sync_logger.addHandler(handler)
        try:
            asyncio.get_event_loop().run_until_complete(
                _run_sync_background(city_names, businesses)
            )
        finally:
            sync_logger.removeHandler(handler)
            sync_logger.setLevel(orig_level)

        complete_msgs = [m for m in log_records if "sync complete" in m]
        assert complete_msgs, f"Sync complete log not found. Got: {log_records}"
        summary = complete_msgs[0]
        assert "failed=1" in summary, f"Expected failed=1 (transient); got: {summary}"
        assert "no_match=0" in summary, f"Expected no_match=0 (not permanent); got: {summary}"

    def test_recent_no_match_discovery_is_skipped(self, mock_db, monkeypatch):
        """Recent unrated discovery attempts should not call Google again.

        WHY: a manual rerun minutes after a no-match sync should not spend paid
        Google Places quota repeating the same text search and fallback searches.
        """
        import asyncio
        import logging
        from datetime import datetime, timedelta, timezone
        from app.routes.admin.sync_admin import _coerce_utc_datetime, _run_sync_background
        import app.services.google_places as gp

        recent_attempt = datetime.now(timezone.utc) - timedelta(hours=1)
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_one(
                {
                    "_id": "biz-recent-no-match",
                    "name": "Recent No Match Salon",
                    "slug": "recent-no-match",
                    "city_id": "city-cache",
                    "network_id": "net-cache",
                    "status": "live",
                    "google_lookup_attempted_at": recent_attempt,
                }
            )
        )

        calls = []

        async def mock_lookup(*args, **kwargs):
            calls.append((args, kwargs))
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        log_records = []

        class LogCapture(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        handler = LogCapture()
        sync_logger = logging.getLogger("app.routes.admin.sync_admin")
        orig_level = sync_logger.level
        sync_logger.setLevel(logging.DEBUG)
        sync_logger.addHandler(handler)
        try:
            asyncio.get_event_loop().run_until_complete(
                _run_sync_background(
                    {"city-cache": "Miami"},
                    [
                        {
                            "_id": "biz-recent-no-match",
                            "name": "Recent No Match Salon",
                            "city_id": "city-cache",
                            "status": "live",
                            "google_lookup_attempted_at": recent_attempt,
                        }
                    ],
                )
            )
        finally:
            sync_logger.removeHandler(handler)
            sync_logger.setLevel(orig_level)

        assert calls == [], "recent no-match cache should skip Google lookup entirely"
        summary = next((m for m in log_records if "sync complete" in m), "")
        assert "skipped_recent=1" in summary, f"expected skipped_recent=1; got logs: {log_records}"

    def test_no_match_records_recent_lookup_attempt(self, mock_db, monkeypatch):
        """A discovery miss stores google_lookup_attempted_at for later reruns.

        WHY: without this persistent timestamp, an unrated business that just
        returned no accepted Google match gets searched again on every sync run.
        """
        import asyncio
        from datetime import datetime, timedelta, timezone
        from app.routes.admin.sync_admin import _coerce_utc_datetime, _run_sync_background
        import app.services.google_places as gp

        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_one(
                {
                    "_id": "biz-cache-miss",
                    "name": "Cache Miss Salon",
                    "slug": "cache-miss",
                    "city_id": "city-cache",
                    "network_id": "net-cache",
                    "status": "live",
                }
            )
        )

        async def mock_lookup(*args, **kwargs):
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        before = datetime.now(timezone.utc)
        asyncio.get_event_loop().run_until_complete(
            _run_sync_background(
                {"city-cache": "Miami"},
                [
                    {
                        "_id": "biz-cache-miss",
                        "name": "Cache Miss Salon",
                        "city_id": "city-cache",
                        "status": "live",
                    }
                ],
            )
        )

        updated = asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.find_one({"_id": "biz-cache-miss"})
        )
        attempted_at = _coerce_utc_datetime(updated.get("google_lookup_attempted_at"))
        assert attempted_at is not None, "no-match discovery should persist lookup timestamp"
        assert attempted_at >= before - timedelta(seconds=1), (
            "timestamp should be from this sync run, allowing Mongo's millisecond precision"
        )
        assert updated.get("google_rating") is None

    def test_stale_lookup_attempt_is_retried_and_cleared_on_success(self, mock_db, monkeypatch):
        """A lookup older than the skip window is retried, and success clears the marker."""
        import asyncio
        from datetime import datetime, timedelta, timezone
        from app.routes.admin.sync_admin import _run_sync_background
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        stale_attempt = datetime.now(timezone.utc) - timedelta(hours=7)
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_one(
                {
                    "_id": "biz-stale-cache",
                    "name": "Stale Cache Salon",
                    "slug": "stale-cache",
                    "city_id": "city-cache",
                    "network_id": "net-cache",
                    "status": "live",
                    "google_lookup_attempted_at": stale_attempt,
                }
            )
        )

        calls = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            calls.append(business_name)
            return PlaceRating(place_id="ChIJ_stale_cache", rating=4.4, review_count=44)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        asyncio.get_event_loop().run_until_complete(
            _run_sync_background(
                {"city-cache": "Miami"},
                [
                    {
                        "_id": "biz-stale-cache",
                        "name": "Stale Cache Salon",
                        "city_id": "city-cache",
                        "status": "live",
                        "google_lookup_attempted_at": stale_attempt,
                    }
                ],
            )
        )

        updated = asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.find_one({"_id": "biz-stale-cache"})
        )
        assert calls == ["Stale Cache Salon"], "stale cache marker should not block a fresh lookup"
        assert updated.get("google_place_id") == "ChIJ_stale_cache"
        assert updated.get("google_rating") == 4.4
        assert "google_lookup_attempted_at" not in updated, (
            "successful match should clear the old no-match cache marker"
        )


class TestDuplicatePlaceIdGuard:
    """The sync must never assign one Google place_id to two different live listings.

    WHY: even with the hardened name matcher, the SAME google_place_id landing on
    multiple distinct businesses is the exact symptom that caused ~283 listings to
    show the wrong business's rating. As defense-in-depth, the sync checks — before
    storing a newly-discovered place_id — whether that place_id already belongs to a
    different live business, and if so leaves the second business unrated.
    """

    def test_second_business_skipped_when_place_id_already_used(self, mock_db, monkeypatch):
        """Two live businesses both resolve (via the mock) to the same place_id;
        only the FIRST one synced gets the rating — the second stays unrated.

        WHY run _run_sync_background directly (not via HTTP): the duplicate guard
        lives in the per-business sync coroutine. Driving it directly lets us
        process the two businesses in a deterministic order so we can assert
        exactly one ends up rated, without TestClient background-task scheduling
        in the way.
        """
        import asyncio
        from app.routes.admin.sync_admin import _run_sync_background
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        # Seed two distinct live businesses, NEITHER with a cached place_id.
        asyncio.get_event_loop().run_until_complete(
            mock_db.cities.insert_one({"_id": "city-dup", "name": "Miami", "slug": "miami"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.networks.insert_one(
                {"_id": "net-dup", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"}
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_many([
                {"_id": "biz-first", "name": "First Salon", "slug": "first", "city_id": "city-dup",
                 "network_id": "net-dup", "status": "live"},
                {"_id": "biz-second", "name": "Second Salon", "slug": "second", "city_id": "city-dup",
                 "network_id": "net-dup", "status": "live"},
            ])
        )

        # Both businesses resolve to the SAME Google place_id (the bug scenario).
        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            return PlaceRating(place_id="ChIJ_shared_place", rating=4.7, review_count=300)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        # Process in a fixed order so exactly one wins. _run_sync_background uses
        # asyncio.gather, but each business's guard runs read-then-decision inside
        # its own coroutine; serialising the list here makes the outcome
        # deterministic for the assertion (first inserted is rated).
        businesses = [
            {"_id": "biz-first", "name": "First Salon", "city_id": "city-dup", "status": "live"},
        ]
        asyncio.get_event_loop().run_until_complete(
            _run_sync_background({"city-dup": "Miami"}, businesses)
        )
        businesses = [
            {"_id": "biz-second", "name": "Second Salon", "city_id": "city-dup", "status": "live"},
        ]
        asyncio.get_event_loop().run_until_complete(
            _run_sync_background({"city-dup": "Miami"}, businesses)
        )

        first = asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.find_one({"_id": "biz-first"})
        )
        second = asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.find_one({"_id": "biz-second"})
        )

        # First business owns the place_id and rating.
        assert first.get("google_place_id") == "ChIJ_shared_place"
        assert first.get("google_rating") == 4.7
        # Second business was skipped: no place_id, no rating.
        assert second.get("google_place_id") is None, (
            "second business must NOT receive a place_id already used by another live business"
        )
        assert second.get("google_rating") is None, (
            "second business must stay unrated to avoid showing another business's rating"
        )

    def test_own_place_id_refresh_not_blocked(self, mock_db, monkeypatch):
        """Re-fetching a business's OWN cached place_id is legitimate and must
        not be blocked by the duplicate guard.

        WHY: the guard only runs on the discovery path (no existing place_id). A
        business that already owns "ChIJ_self" re-syncing through the place-details
        endpoint must update its rating normally — otherwise routine refreshes
        would all be wrongly rejected as "duplicates" of themselves.
        """
        import asyncio
        from app.routes.admin.sync_admin import _run_sync_background
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        asyncio.get_event_loop().run_until_complete(
            mock_db.cities.insert_one({"_id": "city-self", "name": "Miami", "slug": "miami"})
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.networks.insert_one(
                {"_id": "net-self", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"}
            )
        )
        asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.insert_one(
                {"_id": "biz-self", "name": "Self Salon", "slug": "self", "city_id": "city-self",
                 "network_id": "net-self", "status": "live",
                 "google_place_id": "ChIJ_self", "google_rating": 4.0}
            )
        )

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            # The refresh path passes the business's own place_id back in.
            assert existing_place_id == "ChIJ_self"
            return PlaceRating(place_id="ChIJ_self", rating=4.9, review_count=400)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        businesses = [
            {"_id": "biz-self", "name": "Self Salon", "city_id": "city-self", "status": "live",
             "google_place_id": "ChIJ_self"},
        ]
        asyncio.get_event_loop().run_until_complete(
            _run_sync_background({"city-self": "Miami"}, businesses)
        )

        updated = asyncio.get_event_loop().run_until_complete(
            mock_db.businesses.find_one({"_id": "biz-self"})
        )
        assert updated.get("google_place_id") == "ChIJ_self"
        assert updated.get("google_rating") == 4.9, "own-place refresh must update the rating"


# ── Business model hide_ratings field ────────────────────────────────────────

class TestStripCitySuffix:
    """Unit tests for _strip_city_suffix — the name-cleaning helper.

    WHY this test class exists: about 40 businesses have the city name appended
    to their stored name ("Allure Medspa Aventura") or use a pipe/dash separator
    ("DIPLOMATIC IV | Brickell"). Google's listing omits these extras, so the
    full stored name doesn't match. The helper strips them so the sync can try
    a cleaner name before giving up.
    """

    def _fn(self, name, city):
        from app.routes.admin.sync_admin import _strip_city_suffix
        return _strip_city_suffix(name, city)

    def test_strips_trailing_city_name(self):
        assert self._fn("Allure Medspa Aventura", "Aventura") == "Allure Medspa"

    def test_strips_trailing_city_name_case_insensitive(self):
        assert self._fn("Salon Del Sol WESTON", "Weston") == "Salon Del Sol"

    def test_strips_pipe_separator(self):
        assert self._fn("DIPLOMATIC IV | Brickell", "Brickell") == "DIPLOMATIC IV"

    def test_strips_em_dash_separator(self):
        assert self._fn("LaserAway — Doral", "Doral") == "LaserAway"

    def test_strips_en_dash_separator(self):
        assert self._fn("LaserAway – Doral", "Doral") == "LaserAway"

    def test_returns_empty_when_nothing_to_strip(self):
        """Names with no city suffix or separator produce no candidate — caller skips the extra call."""
        assert self._fn("Allure Medspa", "Aventura") == ""

    def test_returns_empty_when_name_is_just_city(self):
        """Guard against stripping to an empty string, which would be a useless search."""
        assert self._fn("Aventura", "Aventura") == ""

    def test_does_not_strip_city_name_in_the_middle(self):
        """Only trailing city suffix is stripped, not occurrences mid-name."""
        result = self._fn("Aventura Hair Studio", "Aventura")
        # "Aventura" is a prefix, not a suffix here — should not be stripped
        assert result == ""

    def test_pipe_takes_priority_over_city_suffix(self):
        """Separator stripping runs before city-suffix stripping; first match wins."""
        # "Salon Aventura | Brickell" — strip at the pipe, not by city name
        result = self._fn("Salon | Aventura", "Aventura")
        assert result == "Salon"


class TestNameStrippingFallback:
    """Integration test for the name-stripping fallback in the ratings sync.

    WHY: the city-suffix stripping fallback only fires when:
    1. The primary city search returns nothing
    2. The neighborhood slug fallback also returns nothing
    3. The business has no existing place_id

    This test wires all three conditions to confirm the fallback is actually tried.
    """

    @pytest.fixture
    async def city_suffix_db(self, mock_db):
        """Insert a city and a business whose name includes the city as a suffix."""
        city_id = "city-aventura"
        await mock_db.cities.insert_one({"_id": city_id, "name": "Aventura", "slug": "aventura", "status": "live"})
        await mock_db.networks.insert_one({"_id": "net-av", "name": "Beauty", "domain_suffix": "knowsbeauty.localhost"})
        await mock_db.businesses.insert_one({
            "_id": "biz-allure-aventura",
            "name": "Allure Medspa Aventura",  # city suffix in name
            "slug": "allure-medspa-aventura",
            "city_id": city_id,
            "network_id": "net-av",
            "status": "live",
            # no google_place_id — needs discovery
        })
        return mock_db

    def test_stripped_name_tried_when_full_name_fails(self, city_suffix_db, monkeypatch):
        """lookup_rating is called with the city-suffix stripped name when the full name fails.

        WHY: confirms the fallback path actually fires and passes the cleaned name.
        Without this fallback, "Allure Medspa Aventura" finds nothing on Google
        because the listing is just "Allure Medspa".
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append({"name": business_name, "city": city})
            # Full name fails; stripped name succeeds
            if business_name == "Allure Medspa":
                return PlaceRating(place_id="ChIJ_allure", rating=4.6, review_count=305)
            return None

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        names_tried = [c["name"] for c in call_log]
        assert "Allure Medspa Aventura" in names_tried, "primary name was not tried"
        assert "Allure Medspa" in names_tried, "stripped-name fallback was not tried"

    def test_stripping_fallback_not_called_when_primary_succeeds(self, city_suffix_db, monkeypatch):
        """The stripping fallback is NOT called when the primary search finds a result.

        WHY: verifies no extra API call happens for businesses that match fine as-is.
        """
        from app.main import app
        from fastapi.testclient import TestClient
        import app.routes.api.v1._auth as _auth_module
        import app.services.google_places as gp
        from app.services.google_places import PlaceRating

        monkeypatch.setattr(_auth_module, "require_admin", lambda request: True)
        monkeypatch.setattr(gp, "is_configured", lambda: True)

        call_log = []

        async def mock_lookup(business_name, city, state="FL", existing_place_id=None):
            call_log.append(business_name)
            # Always succeed (primary hit)
            return PlaceRating(place_id="ChIJ_found", rating=4.5, review_count=100)

        monkeypatch.setattr(gp, "lookup_rating", mock_lookup)

        client = TestClient(app, follow_redirects=False)
        r = client.post("/admin/sync/ratings")
        assert r.status_code == 303

        # Only one call — the primary. Stripping fallback must not add an extra call.
        assert len(call_log) == 1
        assert call_log[0] == "Allure Medspa Aventura"


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
