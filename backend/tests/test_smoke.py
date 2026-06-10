"""Smoke tests that exercise the full request -> template path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_favicon_routes_do_not_404(client):
    for path in ("/favicon.ico", "/favicon.png"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 308
        assert r.headers["location"] == "/assets/favicon.svg"

    r = client.get("/assets/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")


def test_miami_beauty_home(client):
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    assert "Knows Beauty" in body
    assert "Miami" in body
    # Hero headline pulled from city/editorial defaults
    assert "best-kept beauty" in body.lower() or "knows beauty" in body.lower()
    # Featured Beauty businesses from the seed should appear. These two are in
    # the Miami Beauty trending list, so the home page renders them.
    # If this fails later, swap in another real Miami business currently in
    # the seed — see backend/seed/_real_businesses.json.
    assert "Rossano Ferretti Hair Spa" in body or "Warren-Tricomi Salon" in body
    # The Issue eyebrow comes from copy_blocks.
    assert "ISSUE NO. 01" in body

    # SEO — canonical tag, WebSite JSON-LD, and owner-focused title
    assert 'rel="canonical"' in body
    assert '"@type": "WebSite"' in body
    assert '"potentialAction"' in body
    assert "Directory" in body          # title block includes "Directory"
    assert "Claim Your Listing" in body  # title block includes owner-facing phrase


def test_miami_beauty_category(client):
    r = client.get("/c/nails", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # Vanity Projects Miami is a real nail studio in the seed (Design District,
    # category 'nails'), so it appears on the /c/nails category page.
    # If this fails later, swap in another real Miami business currently in
    # the seed — see backend/seed/_real_businesses.json.
    assert "Vanity Projects Miami" in r.text


def test_miami_beauty_neighborhood(client):
    r = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "Brickell" in r.text


def test_miami_beauty_business(client):
    # Blow Dry Bar Brickell is a real Brickell salon in the seed; its detail
    # page returns 200 and renders both the salon name and "Brickell".
    # If this fails later, swap in another real Miami business currently in
    # the seed — see backend/seed/_real_businesses.json.
    r = client.get(
        "/b/blow-dry-bar-brickell", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert "Blow Dry Bar Brickell" in r.text
    assert "Brickell" in r.text
    # Claim banner copy: growth-focused message for unclaimed listings
    # (Blow Dry Bar Brickell may or may not be unclaimed in seed data;
    # only check copy if the claim banner is present)
    if "Claim free to add photos" in r.text:
        assert "searching for salons in Miami" in r.text
        assert "first month free" in r.text


def test_miami_wellness_home(client):
    r = client.get("/", headers={"host": "miami.knowswellness.localhost"})
    assert r.status_code == 200, r.text
    assert "Knows Wellness" in r.text


def test_miami_health_home(client):
    r = client.get("/", headers={"host": "miami.knowshealth.localhost"})
    assert r.status_code == 200, r.text
    assert "Knows Health" in r.text
    # Health profiles are providers, not promises
    assert "doctor" in r.text.lower() or "clinic" in r.text.lower() or "provider" in r.text.lower()


def test_expertly_voice_page(client):
    r = client.get(
        "/expertly-voice.html", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert "Never miss a booking" in r.text
    assert "Expertly · Voice for Salons" in r.text
    # Trial length: the salon-facing offer is one week free.
    # If this assertion ever fails because the trial copy changed, update
    # the marketing copy and the quote at the same time — the page and the
    # sales quote must agree.
    assert "1-week free trial" in r.text or "1 week free" in r.text.lower()


def test_owners_page(client):
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "For Business Owners" in r.text
    assert "Claim your listing" in r.text
    # Three-tier explainer must mention all three tier names.
    for tier in ("Free", "Featured", "Concierge"):
        assert tier in r.text
    # Social proof + Founding Partner mention in hero section
    assert "already listed" in r.text
    assert "Founding Partner" in r.text


def test_owners_page_has_claim_form_not_mailto(client):
    """The owners page used to be two `mailto:hello@expertly.ai` links.
    Both have been replaced by a real claim form that posts to the
    existing /api/v1/claims endpoint. If this assertion ever fails, an
    edit accidentally reintroduced an email-based CTA."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # No mailto CTA anywhere on the page.
    assert "mailto:hello@expertly.ai" not in r.text
    # A real form, with the required fields, posting to the existing endpoint.
    assert 'id="claim-form__form"' in r.text
    assert "/api/v1/claims" in r.text
    for field_id in (
        "claim-form__business-name",
        "claim-form__your-name",
        "claim-form__your-email",
        "claim-form__your-phone",
        "claim-form__notes",
    ):
        assert field_id in r.text


def test_owners_page_prefills_from_slug(client, seeded_db):
    """When the visitor lands at /owners?slug=<biz>, the form shows the
    listing as a read-only confirmation and locks the business name to it.
    Without ?slug, the field is editable."""
    # With ?slug: pre-filled. Use a real seeded Miami salon (see
    # backend/seed/_real_businesses.json) so the route can resolve it.
    r = client.get(
        "/owners?slug=blow-dry-bar-brickell",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert "Blow Dry Bar Brickell" in r.text
    assert "readonly" in r.text
    assert "Claiming" in r.text

    # Without ?slug: editable, no prefill banner.
    r2 = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r2.status_code == 200, r2.text
    # The "Claiming" prefill banner is only rendered when prefilled.
    assert ">Claiming<" not in r2.text


def test_owners_page_embeds_business_directory(client, seeded_db):
    """The form needs a client-side directory of {id, name, slug} so a
    visitor who types a business name can be matched to a real listing
    record without a new endpoint. Confirm the directory is in the page."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "var DIRECTORY" in r.text
    assert "Blow Dry Bar Brickell" in r.text


def test_claim_endpoint_accepts_payload_from_form(client, seeded_db):
    """End-to-end: the JSON payload our form posts must be accepted by the
    existing POST /api/v1/claims endpoint. If the model schema ever changes
    (e.g. a field is renamed), this test breaks early."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )
    biz = asyncio.run(
        seeded_db.businesses.find_one(
            {"city_id": city["_id"], "slug": "blow-dry-bar-brickell"}
        )
    )
    assert biz is not None, "test seed missing blow-dry-bar-brickell"

    payload = {
        "business_id": biz["_id"],
        "submitter_name": "Jane Owner",
        "submitter_email": "jane@example.com",
        "submitter_phone": "(305) 555-0142",
        "notes": "I run the front desk.",
    }
    r = client.post("/api/v1/claims", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["business_id"] == biz["_id"]
    assert body["submitter_email"] == "jane@example.com"
    assert body["status"] == "pending"

    # The business itself should now show as claim_status=pending.
    updated = asyncio.run(seeded_db.businesses.find_one({"_id": biz["_id"]}))
    assert updated["claim_status"] == "pending"


def test_claim_endpoint_rejects_unknown_business(client, seeded_db):
    """Defense-in-depth: if the embedded directory drifts and the form
    submits a stale id, the server must return 404 rather than create an
    orphan claim. The form's JS handles 404 with a friendly inline error."""
    r = client.post(
        "/api/v1/claims",
        json={
            "business_id": "00000000-0000-0000-0000-000000000000",
            "submitter_name": "X",
            "submitter_email": "x@example.com",
        },
    )
    assert r.status_code == 404


def test_owner_dashboard_preview(client):
    """The owner-dashboard preview page must render with the amber preview
    banner, the Featured-tier badge, the three Marketing AI cards, the
    billing summary, and a real seeded salon name. It's a static mockup,
    so the goal here is to confirm every section the spec calls for is
    actually in the HTML — not to test live functionality, which doesn't
    exist yet."""
    r = client.get(
        "/owner/dashboard", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    body = r.text
    # Preview banner must be present so reviewers know this isn't live.
    assert "Preview" in body
    assert "mockup" in body
    # Tier badge and section headings.
    assert "Tier: Featured" in body
    assert "Owner Dashboard" in body
    assert "How your listing is doing" in body
    assert "Marketing AI" in body
    assert "Billing" in body
    # The three Marketing AI cards.
    assert "Generate caption" in body
    assert "Generate ad copy" in body
    assert "Sync Google Business" in body
    # Fake stats and billing copy.
    assert "127" in body  # weekly visits stat
    assert "$29" in body
    # A real seeded Miami salon should be the sample. The route picks the
    # first available from a short priority list — Rossano Ferretti is the
    # default, with two real-Miami fallbacks if that ever drops from the
    # seed.
    assert (
        "Rossano Ferretti" in body
        or "Warren-Tricomi" in body
        or "Eli" in body  # "Eliá Spa" without the accent
    )
    # The "Coming soon" controls must be present and disabled.
    assert "Coming soon" in body
    assert "data-coming-soon" in body


def test_owner_dashboard_links_back_to_public_listing(client):
    """The dashboard should link to the public listing of whatever sample
    salon it's showing, so reviewers can compare the owner view to the
    public view in one click."""
    r = client.get(
        "/owner/dashboard", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    # The public listing URL pattern is /b/<slug>. The route falls through
    # a short priority list of slugs, so we just check that *some* /b/
    # link exists in the rendered HTML.
    assert "/b/" in r.text


def test_pricing_page(client):
    """The dedicated /pricing page shows the three tiers side-by-side
    with prices, FAQs, and conversion CTAs. This is the page that converts
    a "thinking about it" owner into a "claim my listing" click."""
    r = client.get("/pricing", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # All three tier names appear
    for tier in ("Free", "Featured", "Concierge"):
        assert tier in r.text
    # Prices are present and unambiguous
    assert "$29" in r.text
    assert "$290" in r.text  # annual
    assert "$299" in r.text
    # Featured is positioned as the recommended tier
    assert "Most popular" in r.text
    # Trial / cancel terms appear (must align with owners.html copy)
    assert "first month free" in r.text.lower()
    # At least one FAQ question is rendered
    assert "How do I claim" in r.text
    # WHY: anchor must point to #claim-form (the actual div id), not #claim —
    # the old #claim anchor doesn't exist and silently drops visitors at the
    # top of the page instead of scrolling them to the form.
    assert "/owners#claim-form" in r.text
    assert "/owners#claim'" not in r.text  # ensure the broken anchor is gone


def test_pricing_link_in_header_nav(client):
    """The pricing page must be discoverable from the global nav so owners
    can find it without knowing the URL."""
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert 'href="/pricing"' in r.text
    assert ">Pricing<" in r.text


def test_stage_hostname_resolves_to_underlying_city(client):
    """`stage-miami.knowsbeauty.localhost` should render Miami content,
    so a reviewer can compare a preview deployment to the live miami.knows...
    URL side-by-side without needing a duplicate city record."""
    r = client.get("/", headers={"host": "stage-miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "Knows Beauty" in r.text
    assert "Miami" in r.text


def test_home_promotes_voice_page(client):
    """The home page Owners CTA and footer should link to /expertly-voice.html."""
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "/expertly-voice.html" in r.text
    assert "Voice for Salons" in r.text


def test_unknown_host_404(client):
    r = client.get("/", headers={"host": "miami.unknownsite.localhost"})
    assert r.status_code == 404


def test_bare_apex_beauty_returns_200(client):
    """The bare network host (no city subdomain) must render a real landing
    page, not a 403 / 404. Before this fix it silently fell through to a
    near-empty stub and the upstream proxy was returning 403 on HEAD probes;
    we now serve the network_landing template with a real city tile so
    visitors who land on the apex have somewhere to click."""
    r = client.get("/", headers={"host": "knowsbeauty.localhost"})
    assert r.status_code == 200, r.text


def test_bare_apex_renders_network_landing_with_city_tile(client):
    """The bare-apex landing page must list the live cities for the network
    and link each tile to its own city subdomain (not back to the apex)."""
    r = client.get("/", headers={"host": "knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    # Brand chrome present.
    assert "Knows Beauty" in body
    # City tile for the only currently-live city in the seed.
    assert "Miami Beauty" in body
    # City tile is a real link to the city subdomain — not a relative URL
    # that would route back to the apex.
    assert "miami.knowsbeauty.localhost" in body
    # The "Cities" section eyebrow shows we're on the landing page, not the
    # bare network_home stub.
    assert "CITIES" in body
    # The planned-expansion section surfaces at least one "coming soon" city.
    assert "Austin Beauty" in body
    assert "Coming 202" in body  # year prefix shared by all ETAs


def test_bare_apex_wellness_and_health_also_render(client):
    """Bare apex must work for every network, not just Beauty."""
    for host, expected_brand in [
        ("knowswellness.localhost", "Knows Wellness"),
        ("knowshealth.localhost", "Knows Health"),
    ]:
        r = client.get("/", headers={"host": host})
        assert r.status_code == 200, f"{host}: {r.text}"
        assert expected_brand in r.text
        assert "miami." in r.text  # the live Miami city tile must link out


def test_unknown_city_renders_404(client):
    """Network is known but the city slug isn't in the database."""
    r = client.get("/", headers={"host": "atlantis.knowsbeauty.localhost"})
    assert r.status_code == 404


def test_bare_network_host_renders_city_landing(client):
    r = client.get("/", headers={"host": "knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "KNOWS BEAUTY" in r.text
    assert "Miami" in r.text
    assert "http://miami.knowsbeauty.localhost/" in r.text
    assert "Austin" in r.text


def test_sitemap_includes_business(client):
    r = client.get("/sitemap.xml", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    # The sitemap lists every live business in Miami. Blow Dry Bar Brickell is
    # one of the real salons currently in the seed, so its detail URL belongs
    # in the sitemap.
    # If this fails later, swap in another real Miami business currently in
    # the seed — see backend/seed/_real_businesses.json.
    assert "blow-dry-bar-brickell" in r.text


def test_api_lists_networks(client):
    r = client.get("/api/v1/networks")
    assert r.status_code == 200
    slugs = {n["slug"] for n in r.json()}
    assert {"beauty", "wellness", "health"} <= slugs


def test_copy_block_override(client, seeded_db):
    """Override the home hero eyebrow for Miami Beauty and confirm the new
    wording appears, without restarting or touching code."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )

    r = client.post(
        "/api/v1/copy-blocks",
        json={
            "scope_type": "city",
            "scope_ref": {"city_id": city["_id"]},
            "key": "home.hero.eyebrow",
            "value": "An editors' guide for Miami",
        },
    )
    assert r.status_code == 200, r.text

    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    assert "An editors&#39; guide for Miami" in r.text or "An editors' guide for Miami" in r.text


def test_founding_partner_badge_on_business_detail(client):
    """A business that's been flagged as a Founding Partner shows the
    badge label on its detail page. Ayesha Beauty Studio in Wynwood is
    one of the five mock founding partners seeded for the design-partner
    outreach demo — if this fails, check `is_founding_partner` is still
    set on it in `_real_businesses.json`."""
    r = client.get(
        "/b/ayesha-beauty-studio-wynwood",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert "Founding Partner" in r.text
    # Tooltip should reference the publication name.
    assert "Founding member of Miami Knows Beauty" in r.text


def test_founding_partner_badge_on_trending_row(client):
    """The home page's trending row also surfaces the Founding Partner
    badge for any business that has the flag. Three of the five mock
    founding partners are in the Miami Beauty trending list
    (Ayesha, Vanity Projects, IGK), so the badge text should appear on
    the home page."""
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "Founding Partner" in r.text


def test_non_founding_partner_does_not_show_badge(client):
    """A salon NOT flagged as a Founding Partner doesn't render the
    badge on its detail page. Drybar Miami Beach is a real, non-founding
    business in the seed, so its page should NOT mention the badge."""
    r = client.get(
        "/b/drybar-miami-beach",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert "Founding Partner" not in r.text


def test_home_hero_has_owner_entry_point(client):
    """The homepage hero must contain a subtle one-line prompt for salon
    owners — "Own a salon in Miami? Claim your listing →". Without this,
    owners who land from a Google search see only the consumer search bar
    above the fold and typically bounce before reaching the Owners CTA
    section far below.

    WHY: anchor must use href="/owners" (not a #hash) so clicking
    navigates to the full owners page. The arrow character → distinguishes
    this from other "Claim your listing" CTAs that appear in other sections."""
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    # "Own a" is the start of "Own a salon in Miami?" — the owner nudge phrase
    assert "Own a" in body
    # The link arrow "→" distinguishes the hero micro-CTA from other claim
    # buttons on the page, which render without an arrow character.
    assert "Claim your listing →" in body


def test_business_detail_has_og_image_when_photos_exist(client, seeded_db):
    """When a salon's detail page has photos, the og:image meta tag must
    be present so WhatsApp/iMessage/Slack previews show the salon photo
    instead of a blank grey box. The tag is critical for owner referrals —
    owners frequently share their newly-claimed listing with friends.

    WHY: without og:image the Open Graph spec says apps may pick any image
    from the page (or show nothing). Explicitly setting it guarantees the
    hero photo appears in every social share."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )
    # Find any Miami business that has at least one photo in the seed.
    biz = asyncio.run(
        seeded_db.businesses.find_one(
            {"city_id": city["_id"], "photos": {"$elemMatch": {"url": {"$exists": True, "$ne": ""}}}}
        )
    )
    if biz is None:
        pytest.skip("No seeded businesses with photos — cannot test og:image tag")

    r = client.get(
        f"/b/{biz['slug']}", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert 'property="og:image"' in r.text, (
        f"og:image meta tag missing on /b/{biz['slug']} even though it has photos"
    )


def test_pricing_shows_monthly_equivalent_for_annual_plan(client):
    """The Featured annual price must show the per-month cost breakdown so
    owners comparing monthly subscription tools don't miscalculate the
    annual price as expensive. '$24/month' alongside '$290/year' makes the
    annual deal feel cheap rather than large."""
    r = client.get("/pricing", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # The monthly equivalent must appear near the annual price
    assert "$24/month" in r.text or "that&#39;s $24/month" in r.text or "that's $24/month" in r.text


def test_owners_page_shows_monthly_equivalent_and_support_email(client):
    """The owners page pricing strip must (a) show the monthly cost breakdown
    for the annual Featured plan, and (b) include a support email address in
    the 'what happens next' section so owners who submit and hear nothing have
    somewhere to follow up."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    # Monthly equivalent makes the annual plan feel affordable
    assert "$24/month" in body or "that's $24/month" in body or "$24" in body
    # Support email removes the silent-wait drop-off point
    assert "hello@knowsbeauty.com" in body


def test_business_detail_has_share_button(client):
    """The sticky nav on business detail pages must include a Share button so
    clients can forward a favorite salon via WhatsApp, iMessage, or any other
    native share target. Without it the impulse to share fades before the
    person finds a URL to copy."""
    r = client.get(
        "/b/blow-dry-bar-brickell",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    # The Share button must be present and labelled
    assert "share-btn" in r.text or 'id="share-btn"' in r.text
    assert ">Share<" in r.text or "> Share<" in r.text or "Share\n" in r.text


def test_unclaimed_business_detail_has_sticky_claim_bar(client):
    """An unclaimed salon page must include the sticky claim bar so owners
    who scroll past the static amber banner still see the claim prompt
    throughout their visit. Without it the conversion hook disappears after
    the first scroll and owners who read the whole page before deciding
    have no obvious call to action.

    The bar contains a 'Claim free' CTA and a dismiss button; both must be
    present. It is only shown for businesses whose claim_status is not
    'verified' or 'claimed', so we use a known unclaimed salon."""
    r = client.get(
        "/b/blow-dry-bar-brickell",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    body = r.text
    # Sticky bar container
    assert "claim-sticky-bar" in body
    # CTA and dismiss are present
    assert "Claim free" in body
    assert "claim-sticky-dismiss" in body
    # The bar links to the right destination
    assert "/owners?slug=blow-dry-bar-brickell#claim-form" in body


def test_neighborhood_pages_have_editorial_descriptions(client):
    """Each Miami beauty neighborhood page must show a unique editorial
    paragraph below the vibe quote in the hero. Without it the page has
    only a grid of salons — no unique text for Google to index, so it
    cannot rank for searches like 'best hair salon in Wynwood' or
    'nail salons Brickell Miami'.

    We test two neighborhoods to confirm the copy is distinct per page,
    not a shared fallback."""
    # Wynwood — "canvas" is a distinctive word from the Wynwood description
    r = client.get("/n/wynwood", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    assert "canvas" in body, "Wynwood editorial description missing (check hero_description seed)"
    # Brickell — "boardroom" is a distinctive word from the Brickell description
    r2 = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r2.status_code == 200, r2.text
    body2 = r2.text
    assert "boardroom" in body2, "Brickell editorial description missing"
    # The two pages must differ — different neighborhoods, different copy
    assert body != body2
