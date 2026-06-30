"""Tests for the Stripe billing endpoints.

Coverage:
  1. POST /api/v1/billing/checkout — auth, config, already-subscribed, success, Stripe error
  2. POST /api/v1/billing/webhook  — signature, idempotency, checkout.session.completed,
                                     customer.subscription.deleted, unknown event type
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_client(seeded_db):
    # WHY: import app.main AFTER the mock_db fixture has patched the db so
    # the lru_cache-backed get_db() resolves to the mocked client.
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _signed_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session
    return sign_session(email)


def _owner_session_headers(cookie: str) -> dict[str, str]:
    return {"Cookie": f"kb_owner_session={cookie}"}


async def _insert_business(
    db,
    *,
    email: str,
    subscription_id: str | None = None,
    city_id: str | None = None,
) -> str:
    """Seed a minimal claimed business and return its _id."""
    import uuid
    biz_id = str(uuid.uuid4())
    doc: dict[str, Any] = {
        "_id": biz_id,
        "name": "Test Salon",
        "slug": "test-salon",
        "claimed_email": email,
        "featured": {"tier": "free", "enabled": False},
    }
    if city_id:
        doc["city_id"] = city_id
    if subscription_id:
        doc["stripe_subscription_id"] = subscription_id
    await db.businesses.insert_one(doc)
    return biz_id


def _make_checkout_event(business_id: str, subscription_id: str, customer_id: str) -> dict:
    return {
        "id": "evt_test_checkout",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_001",
                "subscription": subscription_id,
                "customer": customer_id,
                "metadata": {"business_id": business_id},
            }
        },
    }


def _make_cancel_event(subscription_id: str) -> dict:
    return {
        "id": "evt_test_cancel",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": subscription_id}},
    }


def _post_webhook(client, event_dict: dict, configured: bool = True):
    """POST a fake webhook event, bypassing the Stripe HMAC check."""
    raw = json.dumps(event_dict).encode()
    with patch("stripe.Webhook.construct_event", return_value=event_dict):
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"} if configured else {}):
            from app.config import get_settings
            get_settings.cache_clear()
            resp = client.post(
                "/api/v1/billing/webhook",
                content=raw,
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            get_settings.cache_clear()
            return resp


# ─── Checkout endpoint ───────────────────────────────────────────────────────

class TestCheckout:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    def test_checkout_requires_auth(self, client, seeded_db):
        """No session cookie → 401."""
        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test_key",
            "STRIPE_PRICE_ID_PRO": "price_test_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post("/api/v1/billing/checkout")
            get_settings.cache_clear()
        assert r.status_code == 401

    def test_checkout_503_when_billing_not_configured(self, client, seeded_db):
        """Missing Stripe creds → 503."""
        email = "owner@test.com"
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "",
            "STRIPE_PRICE_ID_PRO": "",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/checkout",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_checkout_404_when_no_business(self, client, seeded_db):
        """Signed in but no claimed business → 404."""
        email = "nobody@test.com"
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/checkout",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_checkout_409_when_already_subscribed(self, client, seeded_db):
        """Already has a subscription → 409."""
        email = "subscribed@test.com"
        await _insert_business(seeded_db, email=email, subscription_id="sub_existing")
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/checkout",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_checkout_success_returns_url(self, client, seeded_db):
        """Happy path: Stripe checkout session URL returned."""
        email = "fresh@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", return_value=mock_session):
                r = client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        body = r.json()
        assert body["url"] == "https://checkout.stripe.com/pay/cs_test"

    @pytest.mark.asyncio
    async def test_checkout_uses_city_specific_price_when_configured(self, client, seeded_db):
        """Knows Beauty city editions can use city-specific Stripe Products/Prices."""
        email = "miami-price@test.com"
        await seeded_db.cities.insert_one({
            "_id": "city-miami-billing",
            "name": "Miami",
            "slug": "miami",
            "status": "live",
        })
        await _insert_business(seeded_db, email=email, city_id="city-miami-billing")
        cookie = _signed_cookie(email)
        captured_params: dict = {}

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"

        def fake_create(**params):
            captured_params.update(params)
            return mock_session

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_generic_pro",
            "STRIPE_PRICE_IDS_BY_CITY": "miami:price_miami_knows_beauty,austin:price_austin_knows_beauty",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", side_effect=fake_create):
                r = client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        assert captured_params["line_items"] == [
            {"price": "price_miami_knows_beauty", "quantity": 1}
        ]

    @pytest.mark.asyncio
    async def test_checkout_falls_back_to_global_price_for_unmapped_city(
        self, client, seeded_db
    ):
        """The city map must not break existing/non-city-specific billing."""
        email = "fallback-price@test.com"
        await seeded_db.cities.insert_one({
            "_id": "city-tampa-billing",
            "name": "Tampa",
            "slug": "tampa",
            "status": "live",
        })
        await _insert_business(seeded_db, email=email, city_id="city-tampa-billing")
        cookie = _signed_cookie(email)
        captured_params: dict = {}

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"

        def fake_create(**params):
            captured_params.update(params)
            return mock_session

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_generic_pro",
            "STRIPE_PRICE_IDS_BY_CITY": "miami:price_miami_knows_beauty",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", side_effect=fake_create):
                r = client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        assert captured_params["line_items"] == [
            {"price": "price_generic_pro", "quantity": 1}
        ]

    @pytest.mark.asyncio
    async def test_checkout_passes_customer_email_for_new_customer(self, client, seeded_db):
        """No existing stripe_customer_id → customer_email passed to Stripe."""
        email = "newcustomer@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        captured_params: dict = {}

        def fake_create(**params):
            captured_params.update(params)
            return mock_session

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", side_effect=fake_create):
                client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert captured_params.get("customer_email") == email
        assert "customer" not in captured_params
        # WHY: payment_intent_data must NOT be sent in subscription mode — Stripe
        # rejects it with a 400 ("You can not pass `payment_intent_data` in
        # `subscription` mode."), which previously made every owner's upgrade
        # fail with a 502. The card-statement descriptor for a subscription is
        # configured on the Stripe Price/Product, not per checkout session.
        assert "payment_intent_data" not in captured_params

    @pytest.mark.asyncio
    async def test_checkout_never_sends_payment_intent_data_in_subscription_mode(
        self, client, seeded_db
    ):
        """Regression for the 502 upgrade bug: subscription-mode checkout must
        never include payment_intent_data, which Stripe rejects in this mode.

        Without the fix, the endpoint sent payment_intent_data and Stripe
        returned a 400, surfaced to the owner as a 502 — the "Get Featured"
        button was completely broken for every salon owner.
        """
        email = "regression@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        captured_params: dict = {}

        def fake_create(**params):
            captured_params.update(params)
            return mock_session

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", side_effect=fake_create):
                r = client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        assert captured_params.get("mode") == "subscription"
        # The exact parameter Stripe rejects in subscription mode.
        assert "payment_intent_data" not in captured_params

    @pytest.mark.asyncio
    async def test_checkout_reuses_existing_stripe_customer(self, client, seeded_db):
        """Existing stripe_customer_id → passed as `customer` not `customer_email`."""
        import uuid
        email = "returning@test.com"
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Returning Salon",
            "slug": "returning-salon",
            "claimed_email": email,
            "stripe_customer_id": "cus_existing_123",
            "featured": {"tier": "free", "enabled": False},
        })
        cookie = _signed_cookie(email)
        captured_params: dict = {}

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"

        def fake_create(**params):
            captured_params.update(params)
            return mock_session

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.checkout.Session.create", side_effect=fake_create):
                client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert captured_params.get("customer") == "cus_existing_123"
        assert "customer_email" not in captured_params

    @pytest.mark.asyncio
    async def test_checkout_502_on_stripe_error(self, client, seeded_db):
        """Stripe SDK raises → 502."""
        import stripe

        email = "stripeerr@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        with patch.dict(os.environ, {
            "STRIPE_SECRET_KEY": "sk_test",
            "STRIPE_PRICE_ID_PRO": "price_pro",
        }):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch(
                "stripe.checkout.Session.create",
                side_effect=stripe.StripeError("card declined"),
            ):
                r = client.post(
                    "/api/v1/billing/checkout",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 502


# ─── Webhook endpoint ────────────────────────────────────────────────────────

class TestWebhook:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    def test_webhook_503_when_not_configured(self, client, seeded_db):
        """No webhook secret configured → 503."""
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            get_settings.cache_clear()
        assert r.status_code == 503

    def test_webhook_400_on_invalid_signature(self, client, seeded_db):
        """Bad signature → 400."""
        import stripe

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch(
                "stripe.Webhook.construct_event",
                side_effect=stripe.SignatureVerificationError("bad", "sig"),
            ):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=b"bad payload",
                    headers={"stripe-signature": "t=1,v1=bad"},
                )
            get_settings.cache_clear()
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_completed_upgrades_business(self, client, seeded_db):
        """checkout.session.completed → business tier set to premium."""
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Upgrading Salon",
            "slug": "upgrading-salon",
            "claimed_email": "owner@salon.com",
            "featured": {"tier": "free", "enabled": False},
        })

        event = _make_checkout_event(
            business_id=biz_id,
            subscription_id="sub_new_001",
            customer_id="cus_new_001",
        )

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=event):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

        biz = await seeded_db.businesses.find_one({"_id": biz_id})
        assert biz["stripe_subscription_id"] == "sub_new_001"
        assert biz["stripe_customer_id"] == "cus_new_001"
        assert biz["featured"]["tier"] == "premium"
        assert biz["featured"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_checkout_completed_idempotent(self, client, seeded_db):
        """Delivering the same event twice returns already_processed the second time."""
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Idempotent Salon",
            "slug": "idempotent-salon",
            "claimed_email": "idem@salon.com",
            "featured": {"tier": "free", "enabled": False},
        })

        event = _make_checkout_event(biz_id, "sub_idem", "cus_idem")

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=event):
                r1 = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
                r2 = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()

        assert r1.status_code == 200
        assert r1.json() == {"status": "ok"}
        assert r2.status_code == 200
        assert r2.json() == {"status": "already_processed"}

    @pytest.mark.asyncio
    async def test_subscription_deleted_reverts_to_free(self, client, seeded_db):
        """customer.subscription.deleted → business reverts to free tier."""
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Cancelling Salon",
            "slug": "cancelling-salon",
            "claimed_email": "cancel@salon.com",
            "stripe_subscription_id": "sub_cancel_001",
            "stripe_customer_id": "cus_cancel_001",
            "featured": {"tier": "premium", "enabled": True},
        })

        event = _make_cancel_event("sub_cancel_001")

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=event):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()

        assert r.status_code == 200

        biz = await seeded_db.businesses.find_one({"_id": biz_id})
        # WHY: subscription_id should be absent (unset), not null, so the
        # unique sparse index doesn't prevent a second business from cancelling.
        assert "stripe_subscription_id" not in biz
        assert biz["featured"]["tier"] == "free"
        assert biz["featured"]["enabled"] is False

    @pytest.mark.asyncio
    async def test_two_cancellations_do_not_collide_on_index(self, client, seeded_db):
        """Cancelling two different businesses must not violate the unique sparse index.

        This is a regression test for the bug where $set stripe_subscription_id: null
        would store null in both documents, violating the unique constraint on the
        second cancellation.
        """
        import uuid

        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for i, biz_id in enumerate(ids):
            await seeded_db.businesses.insert_one({
                "_id": biz_id,
                "name": f"Salon {i}",
                "slug": f"salon-{i}",
                "claimed_email": f"owner{i}@salon.com",
                "stripe_subscription_id": f"sub_cancel_{i}",
                "featured": {"tier": "premium", "enabled": True},
            })

        for i, biz_id in enumerate(ids):
            event = {
                "id": f"evt_cancel_{i}",
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": f"sub_cancel_{i}"}},
            }
            with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
                from app.config import get_settings
                get_settings.cache_clear()
                with patch("stripe.Webhook.construct_event", return_value=event):
                    r = client.post(
                        "/api/v1/billing/webhook",
                        content=json.dumps(event).encode(),
                        headers={"stripe-signature": "t=1,v1=abc"},
                    )
                get_settings.cache_clear()
            assert r.status_code == 200, f"Cancellation {i} failed: {r.text}"

        # Both businesses should now have no stripe_subscription_id field
        for biz_id in ids:
            biz = await seeded_db.businesses.find_one({"_id": biz_id})
            assert "stripe_subscription_id" not in biz

    def test_unknown_event_type_returns_ok(self, client, seeded_db):
        """Unhandled event types must still return 200 (Stripe stops retrying on 2xx)."""
        event = {
            "id": "evt_unknown_type",
            "type": "payment_method.attached",
            "data": {"object": {}},
        }
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=event):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()
        assert r.status_code == 200


# ─── Billing portal endpoint ─────────────────────────────────────────────────

class TestBillingPortal:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    def test_portal_requires_auth(self, client, seeded_db):
        """No session cookie → 401."""
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_key"}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post("/api/v1/billing/portal")
            get_settings.cache_clear()
        assert r.status_code == 401

    def test_portal_503_when_billing_not_configured(self, client, seeded_db):
        """Missing Stripe key → 503 before auth check."""
        email = "owner@test.com"
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/portal",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 503

    @pytest.mark.asyncio
    async def test_portal_404_when_no_business(self, client, seeded_db):
        """Signed in but no claimed business → 404."""
        email = "nobody@portal.com"
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/portal",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_portal_409_when_no_customer_id(self, client, seeded_db):
        """Business has no stripe_customer_id (never subscribed) → 409."""
        email = "nosub@portal.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/portal",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_portal_409_when_subscription_cancelled(self, client, seeded_db):
        """Customer ID exists but subscription was cancelled → 409 (defence-in-depth)."""
        email = "cancelled@portal.com"
        import uuid
        biz_id = str(uuid.uuid4())
        # stripe_customer_id present, stripe_subscription_id absent (post-cancellation state)
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Cancelled Salon",
            "slug": "cancelled-salon",
            "claimed_email": email,
            "stripe_customer_id": "cus_cancelled123",
            "featured": {"tier": "free", "enabled": False},
        })
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            r = client.post(
                "/api/v1/billing/portal",
                headers=_owner_session_headers(cookie),
            )
            get_settings.cache_clear()
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_portal_502_on_stripe_error(self, client, seeded_db):
        """Stripe API failure → 502."""
        import stripe
        email = "stripe-err@portal.com"
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Error Salon",
            "slug": "error-salon",
            "claimed_email": email,
            "stripe_customer_id": "cus_err456",
            "stripe_subscription_id": "sub_err456",
            "featured": {"tier": "premium", "enabled": True},
        })
        cookie = _signed_cookie(email)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch(
                "stripe.billing_portal.Session.create",
                side_effect=stripe.StripeError("Stripe is down"),
            ):
                r = client.post(
                    "/api/v1/billing/portal",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()
        assert r.status_code == 502

    @pytest.mark.asyncio
    async def test_portal_success_returns_url(self, client, seeded_db):
        """Happy path: portal session URL returned."""
        email = "pro@portal.com"
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Pro Salon",
            "slug": "pro-salon",
            "claimed_email": email,
            "stripe_customer_id": "cus_pro789",
            "stripe_subscription_id": "sub_pro789",
            "featured": {"tier": "premium", "enabled": True},
        })
        cookie = _signed_cookie(email)

        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/session/test_portal_abc"

        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.billing_portal.Session.create", return_value=mock_portal):
                r = client.post(
                    "/api/v1/billing/portal",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        body = r.json()
        assert body["url"] == "https://billing.stripe.com/session/test_portal_abc"

    @pytest.mark.asyncio
    async def test_portal_passes_correct_customer_and_return_url(self, client, seeded_db):
        """Stripe Session.create is called with the right customer id and return_url."""
        email = "verify@portal.com"
        import uuid
        biz_id = str(uuid.uuid4())
        await seeded_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Verify Salon",
            "slug": "verify-salon",
            "claimed_email": email,
            "stripe_customer_id": "cus_verify001",
            "stripe_subscription_id": "sub_verify001",
            "featured": {"tier": "premium", "enabled": True},
        })
        cookie = _signed_cookie(email)

        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/session/verify"
        captured: dict = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return mock_portal

        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.billing_portal.Session.create", side_effect=fake_create):
                client.post(
                    "/api/v1/billing/portal",
                    headers=_owner_session_headers(cookie),
                )
            get_settings.cache_clear()

        assert captured.get("customer") == "cus_verify001"
        assert captured.get("return_url", "").endswith("/owners/me")


# ─── Founding Partner removed — checkout must NOT grant any badge ─────────────

class TestNoFoundingPartnerGrant:
    """The Founding Partner concept was removed entirely. A successful checkout
    must upgrade the salon to the paid Featured tier WITHOUT ever setting the
    legacy is_founding_partner flag, and cancellation must still downgrade the
    tier to free.

    WHY mock_db (not seeded_db): keeps the document set small and controlled so
    these assertions read cleanly.
    """

    @pytest.fixture
    def client(self, mock_db):
        return _make_client(mock_db)

    @pytest.mark.asyncio
    async def test_checkout_does_not_grant_founding_partner_flag(self, client, mock_db):
        """A first subscriber is upgraded to Featured but is NOT marked as a
        founding partner — the app no longer grants that flag."""
        import uuid
        biz_id = str(uuid.uuid4())
        await mock_db.businesses.insert_one({
            "_id": biz_id,
            "name": "First Salon",
            "slug": "first-salon",
            "claimed_email": "first@salon.com",
            "featured": {"tier": "free", "enabled": False},
        })

        event = _make_checkout_event(biz_id, "sub_first_001", "cus_first_001")
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=event):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        biz = await mock_db.businesses.find_one({"_id": biz_id})
        # WHY: the paid upgrade must still happen — the revenue path is intact.
        assert biz["featured"]["tier"] == "premium"
        assert biz["featured"]["enabled"] is True
        assert biz["stripe_subscription_id"] == "sub_first_001"
        # WHY: but the Founding Partner flag must never be set by checkout now.
        assert biz.get("is_founding_partner") is not True, (
            "Checkout must NOT grant Founding Partner status — the concept was removed"
        )

    @pytest.mark.asyncio
    async def test_cancellation_still_downgrades_tier(self, client, mock_db):
        """Cancelling a subscription must still downgrade the salon to the free
        tier and clear the subscription id — unrelated to Founding Partner."""
        import uuid
        biz_id = str(uuid.uuid4())
        await mock_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Cancel Salon",
            "slug": "cancel-salon",
            "claimed_email": "cancel@salon.com",
            "stripe_subscription_id": "sub_cancel",
            "stripe_customer_id": "cus_cancel",
            "featured": {"tier": "premium", "enabled": True},
        })

        cancel_event = _make_cancel_event("sub_cancel")
        cancel_event["id"] = "evt_cancel_unique"

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch("stripe.Webhook.construct_event", return_value=cancel_event):
                r = client.post(
                    "/api/v1/billing/webhook",
                    content=json.dumps(cancel_event).encode(),
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        biz = await mock_db.businesses.find_one({"_id": biz_id})
        assert biz["featured"]["tier"] == "free"  # subscription downgraded
        assert "stripe_subscription_id" not in biz  # subscription cleared
