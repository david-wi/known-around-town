import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError


# WHY: business lifecycle writes fail closed without the configured admin key;
# one shared value keeps every step in the cache regression explicitly authorized.
ADMIN_HEADERS = {"X-API-Key": "test-admin-key"}

# WHY: mongomock-only event handoffs complete immediately; one second catches
# a broken synchronization path promptly without making the full suite hang.
_ASYNC_TEST_TIMEOUT_SECONDS = 1


def _client():
    from app.main import app

    return TestClient(app)


async def _seed_city_and_business(
    mock_db, *, city_status="live", business_status="live"
):
    city_id = "test-city"
    business_id = "test-business"
    await mock_db.cities.insert_one(
        {
            "_id": city_id,
            "name": "Test City",
            "slug": "test-city",
            "status": city_status,
        }
    )
    await mock_db.businesses.insert_one(
        {
            "_id": business_id,
            "city_id": city_id,
            "network_id": "beauty",
            "name": "Test Salon",
            "slug": "test-salon",
            "status": business_status,
            "category_slugs": ["hair"],
            "neighborhood_slugs": ["downtown"],
            "description": "Full profile copy for shoppers.",
            "short_description": "Short public summary.",
            "editorial_blurb": "Editorial profile note.",
            "schema_org_type": "HairSalon",
            "meta_title_override": "Test Salon in Test City",
            "meta_description_override": "A public SEO summary.",
            "google_rating": 4.8,
            "google_review_count": 120,
            "hide_ratings": False,
            "voice_phone_number": "(305) 555-0101",
            "is_founding_partner": True,
            "claimed_email": "owner@example.com",
            "stripe_customer_id": "cus_secret",
            "stripe_subscription_id": "sub_secret",
            "vapi_phone_number_id": "vapi-phone-secret",
            "vapi_assistant_id": "vapi-assistant-secret",
            "import_data": {"source": "private"},
            "quality_score": 97,
            "page_view_count": 123,
        }
    )
    return city_id, business_id


async def test_businesses_api_lists_live_businesses_in_live_city(mock_db):
    city_id, business_id = await _seed_city_and_business(mock_db)

    response = _client().get(f"/api/v1/businesses?city_id={city_id}")

    assert response.status_code == 200
    assert [business["_id"] for business in response.json()] == [business_id]


async def test_businesses_api_omits_sensitive_internal_fields(mock_db):
    """# @define-test KAT-075"""
    city_id, business_id = await _seed_city_and_business(mock_db)
    client = _client()
    sensitive_fields = {
        "claimed_email",
        "stripe_customer_id",
        "stripe_subscription_id",
        "vapi_phone_number_id",
        "vapi_assistant_id",
        "import_data",
        "quality_score",
        "page_view_count",
        "is_founding_partner",
    }

    list_response = client.get(f"/api/v1/businesses?city_id={city_id}")
    by_slug_response = client.get(f"/api/v1/businesses/by-slug/{city_id}/test-salon")
    by_id_response = client.get(f"/api/v1/businesses/{business_id}")

    assert list_response.status_code == 200
    docs = [
        list_response.json()[0],
        by_slug_response.json(),
        by_id_response.json(),
    ]
    for doc in docs:
        assert doc["_id"] == business_id
        assert doc["google_rating"] == 4.8
        assert doc["google_review_count"] == 120
        assert doc["hide_ratings"] is False
        assert doc["voice_phone_number"] == "(305) 555-0101"
        assert doc["description"] == "Full profile copy for shoppers."
        assert doc["short_description"] == "Short public summary."
        assert doc["editorial_blurb"] == "Editorial profile note."
        assert doc["schema_org_type"] == "HairSalon"
        assert doc["meta_title_override"] == "Test Salon in Test City"
        assert doc["meta_description_override"] == "A public SEO summary."
        assert not (sensitive_fields & set(doc)), doc


async def test_businesses_api_hides_rating_values_when_admin_suppresses_them(mock_db):
    """# @define-test KAT-075"""
    city_id, business_id = await _seed_city_and_business(mock_db)
    await mock_db.businesses.update_one(
        {"_id": business_id},
        {"$set": {"hide_ratings": True}},
    )

    response = _client().get(f"/api/v1/businesses/{business_id}")

    assert response.status_code == 200
    doc = response.json()
    assert doc["hide_ratings"] is True
    assert "google_rating" not in doc
    assert "google_review_count" not in doc


async def test_businesses_api_hides_live_businesses_in_archived_city(mock_db):
    city_id, business_id = await _seed_city_and_business(
        mock_db, city_status="archived"
    )
    client = _client()

    list_response = client.get(f"/api/v1/businesses?city_id={city_id}&status=live")
    by_slug_response = client.get(f"/api/v1/businesses/by-slug/{city_id}/test-salon")
    by_id_response = client.get(f"/api/v1/businesses/{business_id}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert by_slug_response.status_code == 404
    assert by_id_response.status_code == 404


async def test_businesses_api_hides_archived_businesses_in_live_city(mock_db):
    city_id, business_id = await _seed_city_and_business(
        mock_db, business_status="archived"
    )
    client = _client()

    list_response = client.get(f"/api/v1/businesses?city_id={city_id}&status=archived")
    by_slug_response = client.get(f"/api/v1/businesses/by-slug/{city_id}/test-salon")
    by_id_response = client.get(f"/api/v1/businesses/{business_id}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert by_slug_response.status_code == 404
    assert by_id_response.status_code == 404


async def test_business_lifecycle_writes_refresh_neighborhood_navigation(mock_db):
    """@define-test KAT-010-business-lifecycle-cache"""
    from app.services import content as content_svc

    city_id = "lifecycle-city"
    await mock_db.cities.insert_one(
        {
            "_id": city_id,
            "name": "Lifecycle City",
            "slug": "lifecycle-city",
            "status": "live",
        }
    )
    await mock_db.neighborhoods.insert_many(
        [
            {
                "_id": "n-downtown",
                "city_id": city_id,
                "slug": "downtown",
                "name": "Downtown",
                "status": "live",
                "order": 1,
            },
            {
                "_id": "n-midtown",
                "city_id": city_id,
                "slug": "midtown",
                "name": "Midtown",
                "status": "live",
                "order": 2,
            },
        ]
    )
    second_city_id = "second-lifecycle-city"
    await mock_db.cities.insert_one(
        {
            "_id": second_city_id,
            "name": "Second Lifecycle City",
            "slug": "second-lifecycle-city",
            "status": "live",
        }
    )
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "n-second-midtown",
            "city_id": second_city_id,
            "slug": "midtown",
            "name": "Midtown",
            "status": "live",
            "order": 1,
        }
    )
    client = _client()

    assert await content_svc.list_neighborhoods(city_id) == []

    create_response = client.post(
        "/api/v1/businesses",
        headers=ADMIN_HEADERS,
        json={
            "network_id": "beauty",
            "city_id": city_id,
            "slug": "lifecycle-salon",
            "name": "Lifecycle Salon",
            "status": "live",
            "neighborhood_slugs": ["downtown"],
        },
    )
    assert create_response.status_code == 200, create_response.text
    business_id = create_response.json()["_id"]
    assert [item["slug"] for item in await content_svc.list_neighborhoods(city_id)] == [
        "downtown"
    ]

    draft_response = client.patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"status": "draft"},
    )
    assert draft_response.status_code == 200, draft_response.text
    assert await content_svc.list_neighborhoods(city_id) == []

    republish_response = client.patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"status": "live"},
    )
    assert republish_response.status_code == 200, republish_response.text
    assert [item["slug"] for item in await content_svc.list_neighborhoods(city_id)] == [
        "downtown"
    ]

    reassign_response = client.patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"neighborhood_slugs": ["midtown"]},
    )
    assert reassign_response.status_code == 200, reassign_response.text
    assert [item["slug"] for item in await content_svc.list_neighborhoods(city_id)] == [
        "midtown"
    ]

    assert await content_svc.list_neighborhoods(second_city_id) == []
    city_reassign_response = client.patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"city_id": second_city_id},
    )
    assert city_reassign_response.status_code == 200, city_reassign_response.text
    assert await content_svc.list_neighborhoods(city_id) == []
    assert [
        item["slug"] for item in await content_svc.list_neighborhoods(second_city_id)
    ] == ["midtown"]

    archive_response = client.delete(
        f"/api/v1/businesses/{business_id}", headers=ADMIN_HEADERS
    )
    assert archive_response.status_code == 200, archive_response.text
    assert await content_svc.list_neighborhoods(second_city_id) == []


async def test_unrelated_business_patch_preserves_navigation_cache(mock_db):
    from app.services import content as content_svc

    city_id, business_id = await _seed_city_and_business(mock_db)
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "n-downtown",
            "city_id": city_id,
            "slug": "downtown",
            "name": "Downtown",
            "status": "live",
        }
    )
    expected = await content_svc.list_neighborhoods(city_id)
    generation_before = content_svc._nav_cache_generation

    response = _client().patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"name": "Renamed Test Salon"},
    )

    assert response.status_code == 200, response.text
    assert content_svc._nav_cache_generation == generation_before
    assert await content_svc.list_neighborhoods(city_id) == expected


async def test_unrelated_patch_cannot_restore_concurrent_draft(mock_db, monkeypatch):
    """@define-test KAT-010-atomic-business-update"""
    from app.routes.api.v1 import businesses as businesses_api

    _, business_id = await _seed_city_and_business(mock_db)
    update_started = asyncio.Event()
    release_update = asyncio.Event()
    real_collection = mock_db.businesses

    class _BlockingBusinesses:
        async def find_one(self, *args, **kwargs):
            snapshot = await real_collection.find_one(*args, **kwargs)
            update_started.set()
            await release_update.wait()
            return snapshot

        async def replace_one(self, *args, **kwargs):
            return await real_collection.replace_one(*args, **kwargs)

        async def find_one_and_update(self, *args, **kwargs):
            update_started.set()
            await release_update.wait()
            return await real_collection.find_one_and_update(*args, **kwargs)

    class _BlockingDb:
        businesses = _BlockingBusinesses()

    monkeypatch.setattr(businesses_api, "get_db", lambda: _BlockingDb())
    patch_task = asyncio.create_task(
        businesses_api.update_business(
            business_id, businesses_api.BusinessPatch(name="Renamed Test Salon")
        )
    )
    try:
        await asyncio.wait_for(
            update_started.wait(), timeout=_ASYNC_TEST_TIMEOUT_SECONDS
        )
        await real_collection.update_one(
            {"_id": business_id}, {"$set": {"status": "draft"}}
        )
        release_update.set()
        await asyncio.wait_for(patch_task, timeout=_ASYNC_TEST_TIMEOUT_SECONDS)
    finally:
        release_update.set()
        if not patch_task.done():
            patch_task.cancel()
        await asyncio.gather(patch_task, return_exceptions=True)

    updated = await real_collection.find_one({"_id": business_id})
    assert updated["name"] == "Renamed Test Salon"
    assert updated["status"] == "draft"


async def test_city_patch_rejects_concurrent_neighborhood_reassignment(
    mock_db, monkeypatch
):
    """@define-test KAT-010-atomic-business-assignment"""
    from app.routes.api.v1 import businesses as businesses_api

    source_city_id, business_id = await _seed_city_and_business(mock_db)
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "source-concurrent-neighborhood",
            "city_id": source_city_id,
            "slug": "concurrent-neighborhood",
            "name": "Concurrent Neighborhood",
            "status": "live",
        }
    )
    destination_city_id = "destination-city"
    await mock_db.cities.insert_one(
        {
            "_id": destination_city_id,
            "name": "Destination City",
            "slug": "destination-city",
            "status": "live",
        }
    )
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "destination-downtown",
            "city_id": destination_city_id,
            "slug": "downtown",
            "name": "Downtown",
            "status": "live",
        }
    )
    update_started = asyncio.Event()
    release_update = asyncio.Event()
    real_collection = mock_db.businesses

    class _BlockingBusinesses:
        async def find_one(self, *args, **kwargs):
            snapshot = await real_collection.find_one(*args, **kwargs)
            update_started.set()
            await release_update.wait()
            return snapshot

        async def find_one_and_update(self, *args, **kwargs):
            return await real_collection.find_one_and_update(*args, **kwargs)

    class _BlockingDb:
        businesses = _BlockingBusinesses()
        cities = mock_db.cities
        neighborhoods = mock_db.neighborhoods

    monkeypatch.setattr(businesses_api, "get_db", lambda: _BlockingDb())
    patch_task = asyncio.create_task(
        businesses_api.update_business(
            business_id, businesses_api.BusinessPatch(city_id=destination_city_id)
        )
    )
    try:
        await asyncio.wait_for(
            update_started.wait(), timeout=_ASYNC_TEST_TIMEOUT_SECONDS
        )
        await real_collection.update_one(
            {"_id": business_id},
            {"$set": {"neighborhood_slugs": ["concurrent-neighborhood"]}},
        )
        release_update.set()
        with pytest.raises(HTTPException) as exc_info:
            await asyncio.wait_for(patch_task, timeout=_ASYNC_TEST_TIMEOUT_SECONDS)
        assert exc_info.value.status_code == 409
    finally:
        release_update.set()
        if not patch_task.done():
            patch_task.cancel()
        await asyncio.gather(patch_task, return_exceptions=True)

    updated = await real_collection.find_one({"_id": business_id})
    assert updated["city_id"] == source_city_id
    assert updated["neighborhood_slugs"] == ["concurrent-neighborhood"]


async def test_business_patch_reports_disappearing_record(mock_db, monkeypatch):
    from app.routes.api.v1 import businesses as businesses_api

    _, business_id = await _seed_city_and_business(mock_db)
    real_collection = mock_db.businesses

    class _DisappearingBusinesses:
        async def find_one(self, *args, **kwargs):
            return await real_collection.find_one(*args, **kwargs)

        async def replace_one(self, *args, **kwargs):
            await real_collection.delete_one({"_id": business_id})
            return await real_collection.replace_one(*args, **kwargs)

        async def find_one_and_update(self, *args, **kwargs):
            await real_collection.delete_one({"_id": business_id})
            return await real_collection.find_one_and_update(*args, **kwargs)

    class _DisappearingDb:
        businesses = _DisappearingBusinesses()

    monkeypatch.setattr(businesses_api, "get_db", lambda: _DisappearingDb())

    with pytest.raises(HTTPException) as exc_info:
        await businesses_api.update_business(
            business_id, businesses_api.BusinessPatch(status="draft")
        )
    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"status": "not-a-status"}, 422),
        ({"neighborhood_slugs": ["Not Canonical"]}, 422),
        ({"slug": "Not Canonical"}, 422),
        ({"slug": "-edge-hyphen"}, 422),
        ({"slug": "repeated--hyphen"}, 422),
        ({"slug": "hyphen-edge-"}, 422),
        ({"slug": "---"}, 422),
        ({"status": None}, 422),
        ({"city_id": None}, 422),
        ({"slug": None}, 422),
        ({"neighborhood_slugs": None}, 422),
        ({"_id": "replacement-id"}, 422),
        ({"city_id": "missing-city"}, 404),
    ],
)
async def test_business_patch_rejects_invalid_navigation_assignments(
    mock_db, payload, expected_status
):
    """@define-test KAT-010-valid-business-assignment"""
    _, business_id = await _seed_city_and_business(mock_db)

    response = _client().patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json=payload,
    )

    assert response.status_code == expected_status, response.text


async def test_business_patch_rejects_neighborhood_from_another_city(mock_db):
    """@define-test KAT-010-valid-business-assignment"""
    _, business_id = await _seed_city_and_business(mock_db)
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "other-neighborhood",
            "city_id": "other-city",
            "slug": "other-neighborhood",
            "name": "Other Neighborhood",
            "status": "live",
        }
    )

    response = _client().patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"neighborhood_slugs": ["other-neighborhood"]},
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    ("invalid_fields", "expected_status"),
    [
        ({"slug": "Not Canonical"}, 422),
        ({"city_id": "missing-city"}, 404),
        ({"neighborhood_slugs": ["missing-neighborhood"]}, 422),
    ],
)
async def test_business_patch_revalidates_identity_when_republishing(
    mock_db, invalid_fields, expected_status
):
    """@define-test KAT-010-valid-business-assignment"""
    _, business_id = await _seed_city_and_business(mock_db)
    await mock_db.businesses.update_one(
        {"_id": business_id}, {"$set": {"status": "draft", **invalid_fields}}
    )

    response = _client().patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"status": "live"},
    )

    assert response.status_code == expected_status, response.text
    stored = await mock_db.businesses.find_one({"_id": business_id})
    assert stored["status"] == "draft"


@pytest.mark.parametrize(
    ("collection_name", "lookup", "expected_status"),
    [
        ("cities", {"_id": "test-city"}, 404),
        ("neighborhoods", {"slug": "downtown"}, 422),
    ],
)
async def test_business_patch_rejects_archived_identity_when_republishing(
    mock_db, collection_name, lookup, expected_status
):
    """@define-test KAT-010-valid-business-assignment"""
    _, business_id = await _seed_city_and_business(mock_db)
    await mock_db.businesses.update_one(
        {"_id": business_id}, {"$set": {"status": "draft"}}
    )
    if collection_name == "neighborhoods":
        await mock_db.neighborhoods.insert_one(
            {
                "_id": "downtown",
                "city_id": "test-city",
                "slug": "downtown",
                "name": "Downtown",
                "status": "live",
            }
        )
    archive_result = await getattr(mock_db, collection_name).update_one(
        lookup, {"$set": {"status": "archived"}}
    )
    assert archive_result.matched_count == 1

    response = _client().patch(
        f"/api/v1/businesses/{business_id}",
        headers=ADMIN_HEADERS,
        json={"status": "live"},
    )

    assert response.status_code == expected_status, response.text
    stored = await mock_db.businesses.find_one({"_id": business_id})
    assert stored["status"] == "draft"


async def test_business_create_reports_duplicate_key_race_as_conflict(
    mock_db, monkeypatch
):
    """@define-test KAT-010-valid-business-assignment"""
    from app.models import Business
    from app.routes.api.v1 import businesses as businesses_api

    await mock_db.cities.insert_one(
        {"_id": "test-city", "name": "Test City", "slug": "test-city"}
    )

    class _DuplicateCreateBusinesses:
        def __getattr__(self, name):
            return getattr(mock_db.businesses, name)

        insert_one = AsyncMock(side_effect=DuplicateKeyError("duplicate city/slug"))

    class _DuplicateCreateDb:
        businesses = _DuplicateCreateBusinesses()
        cities = mock_db.cities
        neighborhoods = mock_db.neighborhoods

    monkeypatch.setattr(businesses_api, "get_db", lambda: _DuplicateCreateDb())

    with pytest.raises(HTTPException) as exc_info:
        await businesses_api.create_business(
            Business(
                network_id="beauty",
                city_id="test-city",
                slug="race-winner",
                name="Race Winner",
                status="live",
            )
        )

    assert exc_info.value.status_code == 409


async def test_business_patch_reports_duplicate_key_race_as_conflict(
    mock_db, monkeypatch
):
    """@define-test KAT-010-valid-business-assignment"""
    from app.routes.api.v1 import businesses as businesses_api

    _, business_id = await _seed_city_and_business(mock_db)

    class _DuplicateUpdateBusinesses:
        def __getattr__(self, name):
            return getattr(mock_db.businesses, name)

        find_one_and_update = AsyncMock(
            side_effect=DuplicateKeyError("duplicate city/slug")
        )

    class _DuplicateUpdateDb:
        businesses = _DuplicateUpdateBusinesses()
        cities = mock_db.cities
        neighborhoods = mock_db.neighborhoods

    monkeypatch.setattr(businesses_api, "get_db", lambda: _DuplicateUpdateDb())

    with pytest.raises(HTTPException) as exc_info:
        await businesses_api.update_business(
            business_id, businesses_api.BusinessPatch(slug="race-loser")
        )

    assert exc_info.value.status_code == 409


@pytest.mark.parametrize("move_city", [False, True])
async def test_business_patch_rejects_duplicate_slug_in_target_city(
    mock_db, move_city
):
    """@define-test KAT-010-valid-business-assignment"""
    source_city_id, business_id = await _seed_city_and_business(mock_db)
    target_city_id = "target-city" if move_city else source_city_id
    if move_city:
        await mock_db.cities.insert_one(
            {"_id": target_city_id, "name": "Target City", "slug": target_city_id}
        )
        await mock_db.businesses.update_one(
            {"_id": business_id}, {"$set": {"neighborhood_slugs": []}}
        )
    await mock_db.businesses.insert_one(
        {
            "_id": "duplicate-business",
            "network_id": "beauty",
            "city_id": target_city_id,
            "slug": "already-used",
            "name": "Duplicate Business",
            "status": "live",
            "neighborhood_slugs": [],
        }
    )
    payload = {"slug": "already-used"}
    if move_city:
        payload = {"city_id": target_city_id, "slug": "already-used"}

    response = _client().patch(
        f"/api/v1/businesses/{business_id}", headers=ADMIN_HEADERS, json=payload
    )

    assert response.status_code == 409, response.text


@pytest.mark.parametrize(
    "payload",
    [
        {
            "network_id": "beauty",
            "city_id": "test-city",
            "slug": "Not Canonical",
            "name": "Invalid Slug Salon",
            "status": "live",
        },
        {
            "network_id": "beauty",
            "city_id": "test-city",
            "slug": "wrong-neighborhood-salon",
            "name": "Wrong Neighborhood Salon",
            "status": "live",
            "neighborhood_slugs": ["other-neighborhood"],
        },
    ],
)
async def test_business_create_rejects_invalid_navigation_assignments(mock_db, payload):
    """@define-test KAT-010-valid-business-assignment"""
    await mock_db.cities.insert_one(
        {"_id": "test-city", "name": "Test City", "slug": "test-city"}
    )
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "other-neighborhood",
            "city_id": "other-city",
            "slug": "other-neighborhood",
            "name": "Other Neighborhood",
            "status": "live",
        }
    )

    response = _client().post("/api/v1/businesses", headers=ADMIN_HEADERS, json=payload)

    assert response.status_code == 422, response.text
