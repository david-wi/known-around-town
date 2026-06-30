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
