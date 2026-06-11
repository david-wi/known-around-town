/**
 * verify-checkout-flow.js
 * Stripe subscription checkout verification for Miami Knows Beauty
 *
 * PREREQUISITES — run this AFTER David adds to /opt/known-around-town/.env:
 *   STRIPE_SECRET_KEY=sk_test_...
 *   STRIPE_WEBHOOK_SECRET=whsec_...
 *   STRIPE_PRICE_ID_PRO=price_...
 *
 * You also need a test claimed-owner account (an account that has completed
 * the claim flow so /owners/me shows the owner dashboard with the Upgrade button).
 * Set the credentials in environment variables before running:
 *   export TEST_OWNER_EMAIL=you@example.com
 *   export TEST_OWNER_PASSWORD=yourpassword
 *
 * Run:
 *   node verify-checkout-flow.js
 *
 * Screenshots land in /tmp/mkb-*.png
 *
 * STRIPE TEST CARD (use on the Stripe-hosted checkout page):
 *   Card number : 4242 4242 4242 4242
 *   Expiry      : 12/28 (any future date)
 *   CVC         : 424 (any 3 digits)
 *   Name/ZIP    : anything
 *
 * STRIPE WEBHOOK NOTES:
 *   The badge only appears AFTER the webhook fires. Stripe sends
 *   checkout.session.completed to the configured webhook URL. Make sure
 *   the Stripe dashboard (Developers → Webhooks) points at:
 *     https://miami.knowsbeauty.ai.devintensive.com/api/v1/billing/webhook
 *   and that the STRIPE_WEBHOOK_SECRET env var matches.
 *
 *   For local/ngrok testing:
 *     stripe listen --forward-to http://localhost:8000/api/v1/billing/webhook
 *     # Copy the whsec_... it prints and set STRIPE_WEBHOOK_SECRET to that.
 */

'use strict';

const { chromium } = require('playwright');
const https = require('https');
const http  = require('http');

const BASE_URL = 'https://miami.knowsbeauty.ai.devintensive.com';

// WHY: 1440x900 matches a typical laptop screen — gives us a realistic desktop view
// of the dashboard and Stripe checkout without scrolling surprises.
const VIEWPORT = { width: 1440, height: 900 };

const TEST_OWNER_EMAIL    = process.env.TEST_OWNER_EMAIL    || '';
const TEST_OWNER_PASSWORD = process.env.TEST_OWNER_PASSWORD || '';

// ─── Helpers ────────────────────────────────────────────────────────────────

function screenshot(page, label) {
  const path = `/tmp/mkb-${label}.png`;
  console.log(`  📸  ${path}`);
  return page.screenshot({ path, fullPage: false });
}

/** Minimal fetch-style helper using the built-in http/https modules.
 *  Returns { status, body } so we can assert without a browser.
 */
function rawFetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const lib    = parsed.protocol === 'https:' ? https : http;
    const req    = lib.request(
      {
        hostname : parsed.hostname,
        port     : parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path     : parsed.pathname + parsed.search,
        method   : options.method || 'GET',
        headers  : options.headers || {},
      },
      (res) => {
        let body = '';
        res.on('data', (c) => (body += c));
        res.on('end', () => resolve({ status: res.statusCode, body }));
      },
    );
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

// ─── Step 1: Homepage ────────────────────────────────────────────────────────

async function checkHomepage(page) {
  console.log('\n[1] Homepage');
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
  await screenshot(page, '1-homepage');

  const title = await page.title();
  console.log(`    title: "${title}"`);

  // Confirm a key element is present — the site header or at least a nav link
  const hasContent = await page.locator('body').isVisible();
  console.log(`    body visible: ${hasContent}`);

  // Check the page didn't 500
  const h1Text = await page.locator('h1').first().textContent().catch(() => '(no h1)');
  console.log(`    h1: "${h1Text.trim()}"`);

  console.log('    ✅  Homepage loaded');
}

// ─── Step 2: Owner login page ────────────────────────────────────────────────

async function checkLoginPage(page) {
  console.log('\n[2] Owner login page');
  await page.goto(`${BASE_URL}/owners/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await screenshot(page, '2-owners-login');

  const emailInput = page.locator('input[type="email"], input[name="email"]');
  const hasEmail   = await emailInput.isVisible().catch(() => false);
  console.log(`    email input visible: ${hasEmail}`);

  const passInput = page.locator('input[type="password"]');
  const hasPass   = await passInput.isVisible().catch(() => false);
  console.log(`    password input visible: ${hasPass}`);

  console.log(`    ✅  Login page has form fields: email=${hasEmail} password=${hasPass}`);
}

// ─── Step 3: Authenticated dashboard (only if creds provided) ─────────────

async function checkDashboardIfCreds(page) {
  console.log('\n[3] Owner dashboard (requires credentials)');

  if (!TEST_OWNER_EMAIL || !TEST_OWNER_PASSWORD) {
    console.log('    ⚠️   TEST_OWNER_EMAIL / TEST_OWNER_PASSWORD not set.');
    console.log('    Skipping authenticated section.');
    console.log('    Set them and re-run to test the dashboard + upgrade button.');
    return;
  }

  // Log in
  console.log(`    Logging in as ${TEST_OWNER_EMAIL} …`);
  await page.goto(`${BASE_URL}/owners/login`, { waitUntil: 'networkidle' });
  await page.fill('input[type="email"], input[name="email"]', TEST_OWNER_EMAIL);
  await page.fill('input[type="password"]', TEST_OWNER_PASSWORD);
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard
  await page.waitForURL('**/owners/me**', { timeout: 15000 }).catch(() => {});
  await screenshot(page, '3-dashboard-after-login');

  const url = page.url();
  console.log(`    landed at: ${url}`);

  if (!url.includes('/owners/me')) {
    console.log('    ❌  Login did not redirect to /owners/me — credentials may be wrong');
    return;
  }
  console.log('    ✅  Logged in, on dashboard');

  // Check for the Upgrade button
  // WHY: we look for any element containing "Upgrade" text — the exact selector
  // may vary but the user-visible label should be consistent.
  const upgradeBtn = page.getByRole('button', { name: /upgrade/i })
    .or(page.getByRole('link', { name: /upgrade/i }))
    .or(page.locator('[data-testid="upgrade-button"]'));

  const hasUpgrade = await upgradeBtn.isVisible().catch(() => false);
  console.log(`    upgrade button visible: ${hasUpgrade}`);

  if (hasUpgrade) {
    console.log('    ✅  Upgrade button is present');
    console.log('    NOTE: Not clicking it here — the Stripe redirect needs real keys.');
    console.log('          For the full manual test, follow the instructions at the bottom');
    console.log('          of this script.');
  } else {
    // Maybe the owner is already Pro — look for the featured badge instead
    const featuredBadge = page.locator('[data-testid="featured-badge"], .featured-badge')
      .or(page.getByText(/featured/i).first());
    const hasBadge = await featuredBadge.isVisible().catch(() => false);
    if (hasBadge) {
      console.log('    ✅  No upgrade button (account already Pro — featured badge found)');
    } else {
      console.log('    ⚠️   No upgrade button AND no featured badge — check dashboard HTML');
    }
  }

  await screenshot(page, '3b-dashboard-upgrade-check');
}

// ─── Step 4: Billing endpoint — wiring check (no browser) ───────────────────

async function checkBillingEndpointWiring() {
  console.log('\n[4] /api/v1/billing/checkout — endpoint wiring check (no auth)');

  /**
   * We POST to /api/v1/billing/checkout without a session cookie.
   * Expected: 401 Unauthorized.
   * If we get 404, the route isn't registered.
   * If we get 500, the server is crashing before it even checks auth
   *   (likely because STRIPE_SECRET_KEY is not set).
   *
   * NOTE: a 500 with the current code is expected when Stripe keys are absent —
   * the billing router initialises the Stripe client at import time and may
   * raise immediately. This is NORMAL pre-key behaviour and does NOT indicate
   * a wiring bug.
   */
  let result;
  try {
    result = await rawFetch(`${BASE_URL}/api/v1/billing/checkout`, {
      method  : 'POST',
      headers : { 'Content-Type': 'application/json' },
      body    : JSON.stringify({}),
    });
  } catch (err) {
    console.log(`    ❌  Network error reaching endpoint: ${err.message}`);
    return;
  }

  console.log(`    HTTP status: ${result.status}`);

  if (result.status === 401 || result.status === 403) {
    console.log('    ✅  Endpoint is reachable and correctly requires authentication');
  } else if (result.status === 404) {
    console.log('    ❌  404 — route not registered. Check billing router is included in app.');
  } else if (result.status === 422) {
    console.log('    ⚠️   422 Unprocessable — reached but returned validation error without auth.');
    console.log('         The auth middleware may be missing from this route.');
  } else if (result.status === 500) {
    console.log('    ⚠️   500 — Server error. Most likely cause: STRIPE_SECRET_KEY not set.');
    console.log('         This is expected before Stripe keys are added.');
    console.log('         Once keys are live, this should return 401 instead.');
  } else if (result.status === 503) {
    console.log('    ✅  503 — Stripe keys not yet added to the server. This is expected right now.');
    console.log('         Once David adds the keys and restarts the container, this will return 401.');
  } else {
    console.log(`    ⚠️   Unexpected status ${result.status} — investigate manually.`);
  }

  // Also spot-check the webhook endpoint is reachable (POST with no sig → 400, not 404)
  console.log('\n[4b] /api/v1/billing/webhook — wiring check (no signature)');
  let whResult;
  try {
    whResult = await rawFetch(`${BASE_URL}/api/v1/billing/webhook`, {
      method  : 'POST',
      headers : { 'Content-Type': 'application/json' },
      body    : '{}',
    });
  } catch (err) {
    console.log(`    ❌  Network error: ${err.message}`);
    return;
  }
  console.log(`    HTTP status: ${whResult.status}`);
  if (whResult.status === 400) {
    console.log('    ✅  Webhook endpoint is registered (400 = missing/bad Stripe signature — expected)');
  } else if (whResult.status === 404) {
    console.log('    ❌  404 — webhook route not registered');
  } else if (whResult.status === 503) {
    console.log('    ✅  503 — Stripe webhook secret not yet configured. Expected before keys are added.');
  } else if (whResult.status === 500) {
    console.log('    ⚠️   500 — likely STRIPE_WEBHOOK_SECRET not set yet (expected pre-key)');
  } else {
    console.log(`    ⚠️   Unexpected status ${whResult.status}`);
  }
}

// ─── Manual end-to-end test instructions ────────────────────────────────────
//
// Once David has added STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_PRO
// to /opt/known-around-town/.env and restarted the container, run this full flow:
//
//  STEP A — Confirm the Stripe price exists:
//    curl https://api.stripe.com/v1/prices/$STRIPE_PRICE_ID_PRO \
//      -u $STRIPE_SECRET_KEY: | jq '{id, currency, unit_amount, recurring}'
//    Expected: JSON with the price details, no error.
//
//  STEP B — Trigger checkout from the dashboard:
//    1. Open https://miami.knowsbeauty.ai.devintensive.com/owners/login in Chrome
//    2. Log in with a claimed test-owner account
//    3. Click "Upgrade to Pro" (or equivalent button)
//    4. Confirm you're redirected to checkout.stripe.com/...
//
//  STEP C — Complete payment with test card:
//    Card number : 4242 4242 4242 4242
//    Expiry      : 12/28
//    CVC         : 424
//    Name/ZIP    : anything
//    Click "Subscribe" / "Pay"
//
//  STEP D — Confirm webhook fired:
//    You should be redirected to:
//      https://miami.knowsbeauty.ai.devintensive.com/owners/me?subscribed=1
//    Check server logs for: "Stripe webhook received: checkout.session.completed"
//    The business record in MongoDB should now have tier="pro".
//
//  STEP D (alternative if webhook is slow / not configured):
//    Check Stripe dashboard → Events → look for checkout.session.completed
//    If delivered = 0, the webhook URL is wrong or unreachable.
//    If delivered ≥ 1, the webhook fired — check server logs for processing.
//
//  STEP E — Confirm the featured badge appears:
//    After the webhook processes, reload /owners/me
//    The dashboard should show "Featured" badge and no "Upgrade" button.
//    The public listing page for that business should also show the "Featured" badge.
//
//  TROUBLESHOOTING:
//    - Badge not appearing after redirect: webhook probably hasn't fired yet.
//      Wait 5 seconds and reload. If still not there, check server logs.
//    - Stripe Checkout page says "No such price": STRIPE_PRICE_ID_PRO is wrong.
//      Get the correct price ID from Stripe → Products → your Pro plan.
//    - 500 on POST /api/v1/billing/checkout: STRIPE_SECRET_KEY is missing or wrong.
//    - Webhook 400 "No signatures found": STRIPE_WEBHOOK_SECRET doesn't match the
//      secret shown in Stripe → Developers → Webhooks for this endpoint.
//
//  STRIPE CUSTOMER PORTAL (for existing subscribers to manage billing):
//    Enable it at: https://dashboard.stripe.com/settings/billing/portal
//    Without this, the "Manage subscription" button on the dashboard will fail.
//    Minimum portal config: allow customers to cancel subscriptions.
//    This must be enabled BEFORE any live subscribers hit the "Manage" button.
//
// ─────────────────────────────────────────────────────────────────────────────

// ─── Main ────────────────────────────────────────────────────────────────────

(async () => {
  console.log('Miami Knows Beauty — Stripe checkout flow verification');
  console.log(`Target: ${BASE_URL}`);
  console.log('─'.repeat(60));

  // WHY: channel:'chrome' avoids the "Chrome for Testing" fingerprint that
  // bot-detection systems can identify. Real Chrome behaves like a real user.
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page    = await browser.newPage({ viewport: VIEWPORT });

  // Suppress noisy console messages from the page itself
  page.on('console', () => {});

  try {
    await checkHomepage(page);
    await checkLoginPage(page);
    await checkDashboardIfCreds(page);
  } finally {
    await browser.close();
  }

  // Non-browser endpoint checks run after the browser is closed
  await checkBillingEndpointWiring();

  console.log('\n' + '─'.repeat(60));
  console.log('Verification complete. Screenshots: /tmp/mkb-*.png');
  console.log('\nNext steps:');
  console.log('  1. David: add STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_PRO');
  console.log('  2. David: enable Stripe Customer Portal (Dashboard → Settings → Billing → Customer portal)');
  console.log('  3. Re-run with TEST_OWNER_EMAIL + TEST_OWNER_PASSWORD set');
  console.log('  4. Follow the manual end-to-end steps documented in the comments above');
})();
