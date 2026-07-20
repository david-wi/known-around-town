"""Regression tests: businesses with a legacy BSON ObjectId ``_id`` must be
reachable by the same string id the frontend and claim form submit.

Before the fix, ``find_one({"_id": <str>})`` never matched an ObjectId-keyed
record, so the public claim flow (and admin edits) returned 404 for ~28% of
businesses in some cities — a salon owner clicking "Claim your listing" got
"Business not found." These tests fail without app/mongo_ids.business_id_value.
"""

from datetime import datetime
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

CITY_ID = "c9a53e0a-638c-43f9-96c0-d72a6e830c5c"


@pytest.fixture
def client(mock_db):
    from app.main import app

    return TestClient(app)


async def _seed_city(db):
    await db.cities.insert_one({"_id": CITY_ID, "name": "Miami", "slug": "miami"})


async def _seed_business(db, _id):
    await db.businesses.insert_one(
        {
            "_id": _id,
            "city_id": CITY_ID,
            "name": "Legacy Lash Studio",
            "slug": f"legacy-lash-{str(_id)[-6:]}",
            "status": "live",
            "category_slugs": ["lash-brow"],
            "neighborhood_slugs": ["brickell"],
            "updated_at": datetime(2026, 7, 2, 12, 0, 0),
        }
    )


def test_helper_maps_objectid_and_passes_uuid_through():
    from app.mongo_ids import business_id_value

    oid = "6a2e6713442d35eb8a936912"
    assert business_id_value(oid) == ObjectId(oid)
    # A UUID string is not a valid ObjectId, so it must pass through unchanged.
    uuid = "11111111-2222-4333-8444-555555555555"
    assert business_id_value(uuid) == uuid


async def test_get_business_by_id_finds_objectid_record(client, mock_db):
    oid = ObjectId("6a2e6713442d35eb8a936912")
    await _seed_city(mock_db)
    await _seed_business(mock_db, oid)

    r = client.get(f"/api/v1/businesses/{str(oid)}")
    assert r.status_code == 200, r.text  # was 404 before the fix
    assert r.json()["name"] == "Legacy Lash Studio"


async def test_claim_flow_works_for_objectid_business(client, mock_db):
    """The core launch-blocker regression: claiming an ObjectId-keyed listing."""
    oid = ObjectId("6a2e6713442d35eb8a936913")
    await _seed_city(mock_db)
    await _seed_business(mock_db, oid)

    r = client.post(
        "/api/v1/claims",
        json={
            "business_id": str(oid),
            "submitter_name": "Owner Jane",
            "submitter_email": "jane@example.com",
        },
    )
    assert r.status_code == 200, r.text  # was 404 "Business not found" before the fix
    biz = await mock_db.businesses.find_one({"_id": oid})
    assert biz["claim_status"] == "pending"


async def test_claim_flow_still_works_for_uuid_business(client, mock_db):
    """Control: string-UUID businesses keep working unchanged."""
    uid = "11111111-2222-4333-8444-555555555555"
    await _seed_city(mock_db)
    await _seed_business(mock_db, uid)

    r = client.post(
        "/api/v1/claims",
        json={
            "business_id": uid,
            "submitter_name": "Owner Bob",
            "submitter_email": "bob@example.com",
        },
    )
    assert r.status_code == 200, r.text
    biz = await mock_db.businesses.find_one({"_id": uid})
    assert biz["claim_status"] == "pending"


async def test_archive_business_works_for_objectid_record(client, mock_db):
    """@define-test KAT-010-business-lifecycle-cache"""
    from app.services import content as content_svc

    oid = ObjectId("6a2e6713442d35eb8a936914")
    await _seed_city(mock_db)
    await _seed_business(mock_db, oid)
    await mock_db.neighborhoods.insert_one(
        {
            "_id": "brickell",
            "city_id": CITY_ID,
            "slug": "brickell",
            "name": "Brickell",
            "status": "live",
        }
    )
    assert [item["slug"] for item in await content_svc.list_neighborhoods(CITY_ID)] == [
        "brickell"
    ]

    response = client.delete(
        f"/api/v1/businesses/{oid}", headers={"X-API-Key": "test-admin-key"}
    )

    assert response.status_code == 200, response.text
    archived = await mock_db.businesses.find_one({"_id": oid})
    assert archived["status"] == "archived"
    assert await content_svc.list_neighborhoods(CITY_ID) == []
