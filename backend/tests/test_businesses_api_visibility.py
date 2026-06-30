from fastapi.testclient import TestClient


def _client():
    from app.main import app

    return TestClient(app)


async def _seed_city_and_business(mock_db, *, city_status="live", business_status="live"):
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
            "name": "Test Salon",
            "slug": "test-salon",
            "status": business_status,
            "category_slugs": ["hair"],
            "neighborhood_slugs": ["downtown"],
        }
    )
    return city_id, business_id


async def test_businesses_api_lists_live_businesses_in_live_city(mock_db):
    city_id, business_id = await _seed_city_and_business(mock_db)

    response = _client().get(f"/api/v1/businesses?city_id={city_id}")

    assert response.status_code == 200
    assert [business["_id"] for business in response.json()] == [business_id]


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
