import pytest
from datetime import datetime
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

import app.main


@pytest.fixture
def client(mock_db):
    from app.main import app
    return TestClient(app)


def test_objectid_serialization():
    # Verify that jsonable_encoder converts ObjectId to a string
    obj_id = ObjectId("6a2e6713442d35eb8a936916")
    data = {"_id": obj_id, "name": "Test MedSpa"}
    
    serialized = jsonable_encoder(data)
    
    assert serialized["_id"] == "6a2e6713442d35eb8a936916"
    assert isinstance(serialized["_id"], str)
    assert serialized["name"] == "Test MedSpa"


async def test_businesses_api_objectid_serialization(client, mock_db):
    # Insert a business with BSON ObjectId as its _id and datetime field
    obj_id = ObjectId("6a2e6713442d35eb8a936916")
    city_id = "c9a53e0a-638c-43f9-96c0-d72a6e830c5c"
    
    await mock_db.businesses.insert_one({
        "_id": obj_id,
        "city_id": city_id,
        "name": "LUX MedSpa Brickell",
        "slug": "lux-medspa-brickell",
        "status": "live",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["brickell"],
        "updated_at": datetime(2026, 6, 28, 12, 0, 0),
    })
    
    # We must insert the city so that any references can resolve
    await mock_db.cities.insert_one({
        "_id": city_id,
        "name": "Miami",
        "slug": "miami",
    })
    
    r = client.get(f"/api/v1/businesses?city_id={city_id}&limit=10")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["_id"] == "6a2e6713442d35eb8a936916"
    assert data[0]["name"] == "LUX MedSpa Brickell"
    assert data[0]["updated_at"] == "2026-06-28T12:00:00"
