# Epic: Billing — Stripe Checkout, webhooks, Founding Partner badge

### KAT-040 — Stripe Checkout integration · V1 · implemented
**Persona:** Salon Owner.
Owners can subscribe to the Founding Partner plan ($29/month) from their dashboard
via Stripe Checkout. The checkout session is created server-side via
`POST /api/v1/billing/checkout` using the restricted Stripe key.
**Acceptance:** Given a logged-in owner, when they click "Subscribe", then they are
redirected to Stripe's hosted checkout page; after payment, they are redirected to
`/owners/me?checkout=success`.

### KAT-041 — Stripe webhook processing · V1 · implemented
**Persona:** David (operator), Stripe.
The webhook endpoint at `POST /api/v1/billing/webhook` receives Stripe events.
`checkout.session.completed` sets `stripe_customer_id`, `stripe_subscription_id`,
`is_founding_partner` (if within cap), and `claim_status=verified`.
`customer.subscription.deleted` clears `stripe_subscription_id` only (badge stays).
Idempotency is enforced via the `stripe_events` collection.
**Acceptance:** Given a valid `checkout.session.completed` event, when the webhook
fires, then the business gains the Founding Partner badge within seconds; given
the same event ID sent twice, then the second delivery is a no-op.

### KAT-042 — Founding Partner badge (permanent) · V1 · implemented
**Persona:** Salon Owner, Salon Seeker.
The "Founding Partner" badge is granted to the first 25 paying subscribers and is
permanent — it stays on the listing even if the subscription is later cancelled.
Permanence is guarded by `stripe_customer_id` (set once at checkout, never cleared),
NOT by `stripe_subscription_id` (which is cleared on cancellation).
**Acceptance:** Given a founding partner who cancels their subscription, when their
business detail page is loaded, then the Founding Partner badge is still visible.

### KAT-043 — Founding Partner cap (25 slots) · V1 · implemented
**Persona:** David (operator).
The number of Founding Partner badges is capped at 25 (configurable via
`FOUNDING_PARTNER_CAP` env var). Once the cap is reached, additional subscribers
still pay $29/month but do not receive the badge.
**Acceptance:** Given 25 existing Founding Partners, when a 26th owner subscribes,
then their listing does NOT show the Founding Partner badge.

### KAT-044 — Cancellation handling · V1 · implemented
**Persona:** Salon Owner, Stripe.
When a `customer.subscription.deleted` event arrives, `stripe_subscription_id` is
cleared on the business document. The `stripe_customer_id` and `is_founding_partner`
flags remain unchanged (badge permanence).
**Acceptance:** Given an active subscriber whose subscription is cancelled, when the
webhook fires, then `stripe_subscription_id` is null but `is_founding_partner` is
still true and `stripe_customer_id` is unchanged.

### KAT-045 — Webhook secret guard · V1 · implemented
**Persona:** David (operator).
The webhook endpoint returns HTTP 503 (not 500) when `STRIPE_WEBHOOK_SECRET` is
not configured. This is intentional: 503 signals a temporary infrastructure issue,
prompting Stripe to retry rather than marking the endpoint as failed.
**Acceptance:** Given `STRIPE_WEBHOOK_SECRET` not set in production env, when Stripe
posts to the webhook, then the response is 503 and Stripe retries the delivery.

### KAT-046 — Statement descriptor · V1 · implemented
**Persona:** Salon Owner (credit card statement reader).
All charges appear on the owner's credit card statement as `EXPERTLY*KNOWSBEAUTY`
so the charge is clearly identifiable.
**Acceptance:** Given a completed checkout, when the owner views their credit card
statement, then the charge shows `EXPERTLY*KNOWSBEAUTY`.

### KAT-047 — Stripe customer portal · V1 · ready_to_build
**Persona:** Salon Owner.
Owners can access Stripe's self-service customer portal from their dashboard to
update payment methods, download invoices, or cancel their subscription without
contacting David. The portal URL is returned by `POST /api/v1/billing/portal`.
**Acceptance:** Given a logged-in subscriber, when they click "Manage Subscription",
then they are redirected to Stripe's customer portal; given a non-subscriber, then
the button is not shown.
**Blocked on:** David must enable the portal at stripe.com/settings/billing/portal.

### KAT-048 — Pricing page CTA above the fold · V1 · implemented
**Persona:** Salon Owner (considering upgrading).
The Featured pricing card ($29/month) shows a "Claim your listing" call-to-action
button immediately after the price — before the 12-item feature list — so owners
can act without scrolling. A second CTA at the bottom of the feature list is also
retained for owners who read through all the details first.
**Acceptance:** Given a visitor on `/pricing`, when the page first loads at 1440×900
viewport, then the Featured card and its "Claim your listing" button are both visible
without scrolling.
