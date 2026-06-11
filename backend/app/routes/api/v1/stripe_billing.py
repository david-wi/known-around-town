"""Stripe billing endpoints — subscription checkout and webhook processing.

Two surfaces:

1.  POST /api/v1/billing/checkout
    Owner-authenticated.  Creates a Stripe Checkout Session for the Pro
    annual subscription and returns {"url": <checkout_url>} so the browser
    can redirect.

2.  POST /api/v1/billing/webhook
    Called by Stripe.  Verifies the HMAC signature, processes
    checkout.session.completed (upgrades the listing to Pro) and
    customer.subscription.deleted (reverts to free), and records the event
    id so duplicate deliveries are ignored.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
import stripe.error
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import get_db
from app.models import FeaturedTier
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/billing/checkout")
async def create_checkout_session(request: Request) -> JSONResponse:
    """Start a Stripe Checkout Session for the Pro annual subscription.

    Returns {"url": checkout_url}.  The caller should redirect the browser
    to that URL so Stripe handles card collection securely.
    """
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_price_id_pro:
        raise HTTPException(503, "Billing is not yet configured")

    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = verify_session(cookie) if cookie else None
    if not session:
        raise HTTPException(401, "Not signed in")

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": session["email"]})
    if not business:
        raise HTTPException(404, "No verified listing found for this account")

    # WHY: block a second checkout if already subscribed so we don't
    # create duplicate subscriptions when the owner clicks the button twice.
    if business.get("stripe_subscription_id"):
        raise HTTPException(409, "Already subscribed to Pro")

    stripe.api_key = settings.stripe_secret_key

    # WHY: base_url from the request works on both HTTP staging and HTTPS
    # production without any environment flag.
    base_url = str(request.base_url).rstrip("/")

    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.stripe_price_id_pro, "quantity": 1}],
        "success_url": f"{base_url}/owners/me?subscribed=1",
        "cancel_url": f"{base_url}/owners/me",
        # WHY: business_id in metadata lets the webhook update the right
        # Business document without a separate customer→business lookup table.
        "metadata": {"business_id": str(business["_id"])},
        # WHY: promotion codes let us hand discount codes to design partners
        # and early adopters without any code change on our side.
        "allow_promotion_codes": True,
    }

    customer_id = business.get("stripe_customer_id")
    if customer_id:
        # WHY: reuse the existing Stripe Customer so all invoices and payment
        # methods stay on one customer record in the Stripe dashboard.
        params["customer"] = customer_id
    else:
        # WHY: pre-fill the Stripe checkout form with the owner's email and
        # let Stripe create the Customer automatically on completion.
        params["customer_email"] = session["email"]

    try:
        checkout = stripe.checkout.Session.create(**params)
    except stripe.error.StripeError as exc:
        log.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(502, "Could not create checkout session — please try again")

    return JSONResponse({"url": checkout.url})


@router.post("/billing/portal")
async def create_portal_session(request: Request) -> JSONResponse:
    """Open a Stripe Billing Portal session for a Pro subscriber.

    Returns {"url": portal_url}.  The browser should redirect there so the
    owner can update their payment method, view invoices, or cancel — all
    handled by Stripe's hosted portal UI.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Billing is not yet configured")

    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = verify_session(cookie) if cookie else None
    if not session:
        raise HTTPException(401, "Not signed in")

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": session["email"]})
    if not business:
        raise HTTPException(404, "No verified listing found for this account")

    customer_id = business.get("stripe_customer_id")
    # WHY: check both customer_id and subscription_id.  customer_id is set at
    # checkout and never cleared; subscription_id is cleared by the webhook
    # when a subscription is cancelled.  Checking only customer_id would let
    # a cancelled subscriber call this endpoint directly (the UI already hides
    # the button, but defence-in-depth requires server-side enforcement too).
    if not customer_id or not business.get("stripe_subscription_id"):
        raise HTTPException(409, "No active subscription found")

    stripe.api_key = settings.stripe_secret_key
    # WHY: base_url is derived from the Host header, which is set by our
    # Nginx/Traefik proxy — not the raw client.  Stripe also validates the
    # return_url against domains configured in the portal settings, which is
    # the canonical server-side guard against header injection.  This follows
    # the same pattern used by create_checkout_session.
    base_url = str(request.base_url).rstrip("/")

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            # WHY: send the owner back to their dashboard after they finish
            # managing the subscription — keeps them in the product flow
            # rather than ending up on Stripe's generic exit page.
            return_url=f"{base_url}/owners/me",
        )
    except stripe.error.StripeError as exc:
        log.error("Stripe billing portal creation failed: %s", exc)
        raise HTTPException(502, "Could not open billing portal — please try again")

    return JSONResponse({"url": portal.url})


@router.post("/billing/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Receive and process signed Stripe webhook events.

    Stripe retries on non-2xx responses and occasionally redelivers
    successful events.  The event id is written to stripe_events as _id
    before any side effect, so a duplicate delivery causes a MongoDB
    duplicate-key error which we catch and short-circuit.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Webhook secret not configured")

    stripe.api_key = settings.stripe_secret_key

    # WHY: body must be read as raw bytes — Stripe's HMAC check runs over
    # the exact transmitted bytes.  Any parsing before this point would
    # alter the byte string and invalidate the signature.
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook payload or signature")

    db = get_db()
    event_id: str = event["id"]
    event_type: str = event["type"]

    # WHY: insert the event id as _id before taking any action.  Stripe's
    # unique _id index makes a second insert for the same event_id fail
    # immediately — preventing double-processing without any explicit
    # select-then-insert check (which would have a race window).
    try:
        await db.stripe_events.insert_one({
            "_id": event_id,
            "event_type": event_type,
            "received_at": datetime.now(timezone.utc),
        })
    except Exception:
        log.info("Stripe event %s already processed, skipping", event_id)
        return JSONResponse({"status": "already_processed"})

    log.info("Processing Stripe event %s (%s)", event_id, event_type)

    if event_type == "checkout.session.completed":
        cs = event["data"]["object"]
        business_id = (cs.get("metadata") or {}).get("business_id")
        subscription_id = cs.get("subscription")
        customer_id = cs.get("customer")

        if business_id and subscription_id:
            update_fields: dict = {
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "featured.tier": FeaturedTier.premium.value,
                "featured.enabled": True,
                "updated_at": datetime.now(timezone.utc),
            }

            # WHY: auto-grant Founding Partner status to the first N subscribers
            # so the dashboard's "Founding Partner offer" copy actually delivers
            # what it promises. The badge renders on the public listing page and
            # persists even if the owner later cancels — giving early adopters
            # something genuinely permanent.  We count BEFORE the current update
            # so two simultaneous checkouts race fairly: one gets slot N and one
            # gets slot N+1 (at worst one extra badge is granted, never one
            # fewer).
            cap = get_settings().founding_partner_cap
            existing_count = await db.businesses.count_documents(
                {"is_founding_partner": True}
            )
            if existing_count < cap:
                update_fields["is_founding_partner"] = True
                log.info(
                    "Business %s granted Founding Partner status (%d/%d slots used)",
                    business_id, existing_count + 1, cap,
                )

            await db.businesses.update_one(
                {"_id": business_id},
                {"$set": update_fields},
            )
            log.info(
                "Business %s upgraded to Pro (customer %s, sub %s)",
                business_id, customer_id, subscription_id,
            )
        else:
            log.warning(
                "checkout.session.completed missing business_id or subscription (event %s): "
                "business_id=%s subscription_id=%s",
                event_id, business_id, subscription_id,
            )

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]

        # WHY: $unset removes the field entirely rather than setting it to
        # null.  The stripe_subscription_id index is unique+sparse — sparse
        # indexes *do* index null values, so storing null would cause a
        # duplicate-key error on the second cancellation across two businesses.
        # Removing the field keeps the document out of the index.
        result = await db.businesses.update_one(
            {"stripe_subscription_id": subscription_id},
            {
                "$set": {
                    "featured.tier": FeaturedTier.free.value,
                    "featured.enabled": False,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$unset": {"stripe_subscription_id": ""},
            },
        )
        if result.matched_count:
            log.info("Business Pro subscription cancelled (sub %s)", subscription_id)
        else:
            log.warning(
                "customer.subscription.deleted: no business found for sub %s", subscription_id
            )

    return JSONResponse({"status": "ok"})
