import asyncio

from app.models import Business, OwnerSession, StripeEvent
from app.routes.api.v1._crud import to_doc


def test_business_preserves_stripe_identifiers():
    business = Business(
        network_id="network-1",
        city_id="city-1",
        slug="sample-salon",
        name="Sample Salon",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_456",
    )

    doc = to_doc(business)

    assert doc["stripe_customer_id"] == "cus_123"
    assert doc["stripe_subscription_id"] == "sub_456"


def test_claim_pay_models_serialize_with_mongo_ids():
    session = OwnerSession(email="owner@example.com", business_id="business-1")
    event = StripeEvent(_id="evt_123", event_type="customer.subscription.updated")

    session_doc = to_doc(session)
    event_doc = to_doc(event)

    assert session_doc["_id"]
    assert session_doc["email"] == "owner@example.com"
    assert session_doc["business_id"] == "business-1"
    assert event_doc["_id"] == "evt_123"
    assert event_doc["event_type"] == "customer.subscription.updated"


def test_new_business_omits_unset_optional_fields():
    """Regression: to_doc must not write None values to the document.

    A sparse-unique index (e.g. stripe_customer_id_1) allows only ONE
    document with the field explicitly set to null.  If to_doc serializes
    Optional fields as null rather than omitting them, the second new
    business inserted raises DuplicateKeyError even though neither has a
    real Stripe customer ID yet.
    """
    business = Business(
        network_id="network-1",
        city_id="city-1",
        slug="new-salon",
        name="New Salon",
    )

    doc = to_doc(business)

    # Fields that aren't set must be ABSENT, not present-and-null.
    assert "stripe_customer_id" not in doc
    assert "stripe_subscription_id" not in doc
    assert "website" not in doc


def test_claim_pay_indexes_include_stripe_identifiers(mock_db):
    from app import database

    asyncio.run(database.ensure_indexes())

    indexes = {
        index["name"]: index
        for index in asyncio.run(mock_db.businesses.list_indexes().to_list(None))
    }

    assert indexes["stripe_customer_id_1"]["unique"] is True
    assert indexes["stripe_customer_id_1"]["sparse"] is True
    assert indexes["stripe_subscription_id_1"]["unique"] is True
    assert indexes["stripe_subscription_id_1"]["sparse"] is True
