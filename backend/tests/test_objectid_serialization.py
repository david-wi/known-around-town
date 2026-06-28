from bson import ObjectId
from fastapi.encoders import jsonable_encoder
import app.main  # This applies the patch to ENCODERS_BY_TYPE


def test_objectid_serialization():
    # Verify that jsonable_encoder converts ObjectId to a string
    obj_id = ObjectId("6a2e6713442d35eb8a936916")
    data = {"_id": obj_id, "name": "Test MedSpa"}
    
    serialized = jsonable_encoder(data)
    
    assert serialized["_id"] == "6a2e6713442d35eb8a936916"
    assert isinstance(serialized["_id"], str)
    assert serialized["name"] == "Test MedSpa"
