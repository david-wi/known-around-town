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


async def _insert_business(db, *, email: str, subscription_id: str | None = None) -> str:
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
                cookies={"kb_owner_session": cookie},
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
                cookies={"kb_owner_session": cookie},
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
                cookies={"kb_owner_session": cookie},
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
                    cookies={"kb_owner_session": cookie},
                )
            get_settings.cache_clear()

        assert r.status_code == 200
        body = r.json()
        assert body["url"] == "https://checkout.stripe.com/pay/cs_test"

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
                    cookies={"kb_owner_session": cookie},
                )
            get_settings.cache_clear()

        assert captured_params.get("customer_email") == email
        assert "customer" not in captured_params
        # Verify the statement descriptor suffix is sent so card statements
        # show "KNOWS BEAUTY" instead of a generic account name.
        pid = captured_params.get("payment_intent_data", {})
        assert pid.get("statement_descriptor_suffix") == "KNOWS BEAUTY"

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
                    cookies={"kb_owner_session": cookie},
                )
            get_settings.cache_clear()

        assert captured_params.get("customer") == "cus_existing_123"
        assert "customer_email" not in captured_params

    @pytest.mark.asyncio
    async def test_checkout_502_on_stripe_error(self, client, seeded_db):
        """Stripe SDK raises → 502."""
        import stripe.error as se

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
                side_effect=se.StripeError("card declined"),
            ):
                r = client.post(
                    "/api/v1/billing/checkout",
                    cookies={"kb_owner_session": cookie},
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
        import stripe.error as se

        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            from app.config import get_settings
            get_settings.cache_clear()
            with patch(
                "stripe.Webhook.construct_event",
                side_effect=se.SignatureVerificationError("bad", "sig"),
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
                cookies={"kb_owner_session": cookie},
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
                cookies={"kb_owner_session": cookie},
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
                cookies={"kb_owner_session": cookie},
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
                cookies={"kb_owner_session": cookie},
            )
            get_settings.cache_clear()
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_portal_502_on_stripe_error(self, client, seeded_db):
        """Stripe API failure → 502."""
        import stripe.error
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
                side_effect=stripe.error.StripeError("Stripe is down"),
            ):
                r = client.post(
                    "/api/v1/billing/portal",
                    cookies={"kb_owner_session": cookie},
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
                    cookies={"kb_owner_session": cookie},
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
                    cookies={"kb_owner_session": cookie},
                )
            get_settings.cache_clear()

        assert captured.get("customer") == "cus_verify001"
        assert captured.get("return_url", "").endswith("/owners/me")


# ─── Founding Partner auto-grant ─────────────────────────────────────────────

class TestFoundingPartner:
    """Verify that the first N subscribers receive is_founding_partner: True
    automatically on checkout.session.completed, and that subscribers beyond
    the cap do not.

    WHY mock_db (not seeded_db): these tests count exactly how many businesses
    have is_founding_partner: True. The seeded_db fixture inserts 147 seed
    businesses; mongomock_motor's count_documents incorrectly counts documents
    that LACK the field as matching {"is_founding_partner": True}, so the
    seeded data inflates the count and makes the cap comparison wrong.
    Using the bare mock_db (no seed data) keeps the count controlled and
    tests the logic we actually care about.
    """

    @pytest.fixture
    def client(self, mock_db):
        # WHY: mock_db not seeded_db — see class docstring.
        return _make_client(mock_db)

    @pytest.mark.asyncio
    async def test_first_subscriber_receives_founding_partner_badge(self, client, mock_db):
        """When no other founding partners exist, the first subscriber is granted
        is_founding_partner: True."""
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
        # WHY: override cap to a small number so the test doesn't depend on
        # the production default and is easy to understand at a glance.
        with patch.dict(os.environ, {
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "FOUNDING_PARTNER_CAP": "5",
        }):
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
        assert biz.get("is_founding_partner") is True, (
            "First subscriber must receive the Founding Partner badge — "
            "the owner dashboard promises this as an incentive"
        )

    @pytest.mark.asyncio
    async def test_subscriber_at_cap_does_not_receive_badge(self, client, mock_db):
        """When the founding partner cap is already reached, the next subscriber
        does NOT receive is_founding_partner: True."""
        import uuid

        cap = 3
        # Seed `cap` businesses that already have the badge.
        for i in range(cap):
            await mock_db.businesses.insert_one({
                "_id": str(uuid.uuid4()),
                "name": f"Existing FP Salon {i}",
                "slug": f"fp-salon-{i}",
                "claimed_email": f"fp{i}@salon.com",
                "is_founding_partner": True,
                "featured": {"tier": "premium", "enabled": True},
                "stripe_subscription_id": f"sub_fp_{i}",
            })

        # The new subscriber — should NOT get the badge.
        new_biz_id = str(uuid.uuid4())
        await mock_db.businesses.insert_one({
            "_id": new_biz_id,
            "name": "Late Subscriber Salon",
            "slug": "late-sub-salon",
            "claimed_email": "late@salon.com",
            "featured": {"tier": "free", "enabled": False},
        })

        event = _make_checkout_event(new_biz_id, "sub_late_001", "cus_late_001")
        # Use event id different from existing tests to avoid idempotency short-circuit.
        event["id"] = "evt_late_subscriber"

        with patch.dict(os.environ, {
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "FOUNDING_PARTNER_CAP": str(cap),
        }):
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
        biz = await mock_db.businesses.find_one({"_id": new_biz_id})
        assert biz.get("is_founding_partner") is not True, (
            f"Subscriber #{cap + 1} must NOT receive Founding Partner status — "
            f"the cap of {cap} is already reached"
        )
        # The subscription upgrade should still have happened even though no badge.
        assert biz["featured"]["tier"] == "premium"
        assert biz["stripe_subscription_id"] == "sub_late_001"

    @pytest.mark.asyncio
    async def test_last_available_slot_receives_badge(self, client, mock_db):
        """The subscriber who fills the final slot (existing_count == cap - 1)
        must receive the badge."""
        import uuid

        cap = 3
        # Seed cap-1 businesses with the badge.
        for i in range(cap - 1):
            await mock_db.businesses.insert_one({
                "_id": str(uuid.uuid4()),
                "name": f"Early FP Salon {i}",
                "slug": f"early-fp-{i}",
                "claimed_email": f"earlyFP{i}@salon.com",
                "is_founding_partner": True,
                "featured": {"tier": "premium", "enabled": True},
                "stripe_subscription_id": f"sub_early_{i}",
            })

        last_biz_id = str(uuid.uuid4())
        await mock_db.businesses.insert_one({
            "_id": last_biz_id,
            "name": "Last FP Slot Salon",
            "slug": "last-fp-salon",
            "claimed_email": "lastfp@salon.com",
            "featured": {"tier": "free", "enabled": False},
        })

        event = _make_checkout_event(last_biz_id, "sub_last_fp", "cus_last_fp")
        event["id"] = "evt_last_fp_slot"

        with patch.dict(os.environ, {
            "STRIPE_WEBHOOK_SECRET": "whsec_test",
            "FOUNDING_PARTNER_CAP": str(cap),
        }):
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
        biz = await mock_db.businesses.find_one({"_id": last_biz_id})
        assert biz.get("is_founding_partner") is True, (
            f"Subscriber filling the last of {cap} slots must receive the badge"
        )

    @pytest.mark.asyncio
    async def test_founding_partner_badge_persists_after_cancellation(self, client, mock_db):
        """Cancelling the subscription must NOT revoke the founding partner badge —
        the badge is permanent as promised in the owner dashboard copy."""
        import uuid
        biz_id = str(uuid.uuid4())
        await mock_db.businesses.insert_one({
            "_id": biz_id,
            "name": "Founding Cancel Salon",
            "slug": "founding-cancel-salon",
            "claimed_email": "fpcancel@salon.com",
            "is_founding_partner": True,
            "stripe_subscription_id": "sub_fp_cancel",
            "stripe_customer_id": "cus_fp_cancel",
            "featured": {"tier": "premium", "enabled": True},
        })

        cancel_event = _make_cancel_event("sub_fp_cancel")
        cancel_event["id"] = "evt_fp_cancel_unique"

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
        assert biz.get("is_founding_partner") is True, (
            "Founding partner badge must survive cancellation — "
            "the owner dashboard explicitly promises it is permanent"
        )
        assert biz["featured"]["tier"] == "free"  # subscription downgraded
        assert "stripe_subscription_id" not in biz  # subscription cleared
