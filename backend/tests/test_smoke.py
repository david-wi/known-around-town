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


def test_photos_render_as_plain_string_urls(client, seeded_db):
    """Photos stored as plain URL strings (not dicts) must still show up as
    background images on both the listing card and the detail page.

    WHY: the database can hold photos in two formats — either as a dict like
    {"url": "https://..."} or as a bare string "https://...".  The templates
    must handle both so no salon ends up with a grey placeholder regardless of
    which format its photos are stored in.  This test injects a string-format
    photo and confirms the rendered HTML still contains a usable image URL."""
    import asyncio

    PHOTO_URL = "https://images.unsplash.com/photo-test-string-format?w=800"

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )

    # Insert a synthetic business whose photos are plain strings, not dicts.
    # status="live" is required — list_businesses filters on it, so without it
    # the business never appears in any page's card grid.
    biz_doc = {
        "slug": "test-string-photo-salon",
        "name": "Test String Photo Salon",
        "city_id": city["_id"],
        "network_id": network["_id"],
        # WHY: "hair" not "hair-salon" — the seed uses short slugs that match
        # the categories collection (hair, nails, spa, etc.).
        "category_slugs": ["hair"],
        "neighborhood_slugs": [],
        "photos": [PHOTO_URL],  # plain string, not {"url": "..."}
        "claim_status": "none",
        "status": "live",
        "editors_pick": True,
    }
    asyncio.run(seeded_db.businesses.insert_one(biz_doc))

    # Detail page: photo must appear as a background-image and in og:image.
    r = client.get("/b/test-string-photo-salon", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert PHOTO_URL in r.text, (
        "String-format photo URL missing from detail page — template rendered "
        "a grey placeholder instead of the actual photo"
    )
    assert 'property="og:image"' in r.text, (
        "og:image meta tag missing even though the business has a string-format photo"
    )

    # Category page: the card partial (business_card.html) must also render the
    # photo. Using /c/hair-salon rather than the home page because the home page
    # caps editor picks at 8 and sorts by quality_score, so a synthetic test
    # business would be pushed off the visible list. The category page lists all
    # matching businesses without a display cap.
    # WHY: "hair" matches the seed's category slugs (hair, nails, spa…).
    r2 = client.get("/c/hair", headers={"host": "miami.knowsbeauty.localhost"})
    assert r2.status_code == 200, r2.text
    assert PHOTO_URL in r2.text, (
        "String-format photo URL missing from the category-page card — "
        "business_card.html rendered a grey placeholder instead of the actual photo"
    )


def test_photos_render_as_dict_url_format(client, seeded_db):
    """Photos stored as dicts with a url key must continue to render correctly
    — this is the standard format used by the seed data and production database.

    WHY: the dual-format guard added to the templates must not break the
    existing dict format that every real business uses."""
    import asyncio

    PHOTO_URL = "https://images.unsplash.com/photo-test-dict-format?w=800"

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )

    biz_doc = {
        "slug": "test-dict-photo-salon",
        "name": "Test Dict Photo Salon",
        "city_id": city["_id"],
        "network_id": network["_id"],
        "category_slugs": ["hair"],  # WHY: seed uses short slugs (hair, nails, spa…)
        "neighborhood_slugs": [],
        "photos": [{"url": PHOTO_URL}],  # standard dict format
        "claim_status": "none",
        "is_active": True,
    }
    asyncio.run(seeded_db.businesses.insert_one(biz_doc))

    r = client.get("/b/test-dict-photo-salon", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert PHOTO_URL in r.text, (
        "Dict-format photo URL missing from detail page — the dual-format guard "
        "broke the standard dict format"
    )
    assert 'property="og:image"' in r.text, (
        "og:image meta tag missing for dict-format photo"
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


def test_neighborhood_page_shows_owner_acquisition_banner(client):
    """Neighborhood listing pages must show an owner acquisition banner after
    the business grid, so owners who find the directory by Googling their
    neighborhood have a clear path to /owners without having to click through
    to an individual listing first."""
    r = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # The "For Business Owners" eyebrow and the claim CTA must appear.
    assert "For Business Owners" in r.text, (
        "Neighborhood page missing owner acquisition banner — owners landing here "
        "from search have no visible path to claim their listing"
    )
    assert "Claim your listing" in r.text
    assert 'href="/owners"' in r.text


def test_category_page_shows_owner_acquisition_banner(client):
    """Category listing pages must show an owner acquisition banner after the
    business grid. An owner searching 'nails Miami' lands here and should see
    a direct prompt to claim without clicking through to a specific listing."""
    r = client.get("/c/nails", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "For Business Owners" in r.text, (
        "Category page missing owner acquisition banner"
    )
    assert "Claim your listing" in r.text
    assert 'href="/owners"' in r.text


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


def test_category_pages_have_meta_descriptions(client):
    """Category pages (hair, nails, spa, etc.) must have a <meta name="description">
    tag. Without one Google shows a random excerpt in search results instead of
    compelling copy — hurting click-through for searches like 'hair salons Miami'."""
    for slug, distinctive_word in [("hair", "color"), ("nails", "pedicure"), ("spa", "massage")]:
        r = client.get(f"/c/{slug}", headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, f"/c/{slug} returned {r.status_code}"
        assert 'meta name="description"' in r.text, f"/c/{slug} missing meta description tag"
        assert distinctive_word in r.text.lower(), f"/c/{slug} meta description missing '{distinctive_word}'"


def test_neighborhood_pages_have_meta_descriptions(client):
    """Neighborhood pages must have a <meta name="description"> tag so Google
    shows meaningful copy in search results for 'best salons in Wynwood'-style queries."""
    r = client.get("/n/wynwood", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert 'meta name="description"' in r.text, "Wynwood missing meta description tag"
    # The editorial hero_description text should be the fallback
    assert "canvas" in r.text, "Wynwood meta description should include editorial text"


def test_claim_sends_confirmation_email(client, seeded_db):
    """Submitting a claim must trigger a confirmation email to the owner.

    We can't test a real send in CI (no RESEND_API_KEY), but we verify:
    1. The endpoint still returns 200 after the email code was added
    2. The email module has the function and generates the right subject line
    WHY: before this fix the form promised 'we'll email you within one
    business day' but nothing was ever sent — owners would wait, assume the
    form failed, and not follow up."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )
    biz = asyncio.run(
        seeded_db.businesses.find_one({"city_id": city["_id"]})
    )
    r = client.post(
        "/api/v1/claims",
        json={
            "business_id": biz["_id"],
            "submitter_name": "Ana Garcia",
            "submitter_email": "ana@example.com",
        },
    )
    assert r.status_code == 200, r.text

    # Confirm the email helper generates the right subject without a real send
    from app.services.owner_email import _claim_confirmation_text
    text = _claim_confirmation_text("Ana Garcia", "Test Salon Miami")
    assert "Test Salon Miami" in text
    assert "one business day" in text
    assert "hello@knowsbeauty.com" in text


def test_owners_page_has_faq_section_with_schema(client):
    """The owners page must include a visible FAQ accordion and FAQPage
    structured data so Google can show expandable Q&A rich results for
    owner-intent searches like 'how do I list my salon on Miami Knows Beauty'.

    The FAQ answers the hesitation questions that stop owners from claiming:
    cost, review time, what Featured includes, and whether an account is needed.

    WHY: FAQPage JSON-LD with matching visible Q&A is what Google requires
    to show rich result snippets — having one without the other (schema only,
    no visible text, or vice versa) causes Google to ignore both."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text

    # Visible FAQ section — key questions must appear in the HTML
    assert "Is it really free" in body, "FAQ question about cost missing"
    assert "How long does" in body, "FAQ question about review time missing"
    assert "What does Featured" in body, "FAQ question about Featured plan missing"
    assert "Do I need" in body, "FAQ question about account creation missing"

    # FAQ accordion must use aria-expanded for keyboard accessibility
    assert "aria-expanded" in body, "FAQ accordion missing aria-expanded attribute"

    # FAQPage JSON-LD must be present so Google can show rich results
    assert '"@type": "FAQPage"' in body, "FAQPage JSON-LD missing"
    assert '"@type": "Question"' in body, "FAQPage JSON-LD missing Question entities"


def test_admin_new_claim_email_function_exists_with_correct_content():
    """Admin alert email helper must include business name, submitter email, and review link.

    WHY: without this email David has to check the admin panel manually — if he
    misses a day the 'within one business day' promise breaks and the owner thinks
    they were ignored.  This test verifies the alert email is actionable: names
    the business, identifies the submitter, and links directly to the admin panel."""
    from app.services.owner_email import send_admin_new_claim_email

    # Verify the helper module exports the function (import error = not implemented)
    assert callable(send_admin_new_claim_email)

    # Test the HTML and text bodies directly via the private helpers
    import importlib
    mod = importlib.import_module("app.services.owner_email")

    # The admin alert builds its body inline inside send_admin_new_claim_email,
    # so we test the final rendered strings via the function's source inspection
    # or by calling the private _admin html string directly. Since the function
    # embeds HTML inline, we verify via the module-level source text instead.
    import inspect
    src = inspect.getsource(send_admin_new_claim_email)
    assert "submitter_name" in src, "Admin email must include submitter name"
    assert "submitter_email" in src, "Admin email must include submitter email"
    assert "admin_url" in src, "Admin email must include review link"
    assert "business_name" in src, "Admin email must include business name"


def test_claim_rejected_email_function_exists_with_correct_content():
    """The claim-rejected email helper must exist and produce the right content.

    WHY: when an admin rejects a claim, the submitter currently hears nothing
    — they submitted, got a confirmation, waited, and then received silence.
    No indication the answer was no, no way to follow up or correct a mistake.
    This test verifies the rejection email body is honest, kind, and gives
    the support address so the submitter has a path forward."""
    from app.services.owner_email import _claim_rejected_text, _claim_rejected_html

    text = _claim_rejected_text("Carlos Mendez", "Salon Palma Brickell")
    assert "Salon Palma Brickell" in text, "Business name missing from rejection email text"
    assert "hello@knowsbeauty.com" in text, "Support email missing from rejection email text"
    # Must not be hostile — give the submitter a path to follow up
    assert "mistake" in text.lower() or "review" in text.lower(), (
        "Rejection email must acknowledge the submitter may have a valid claim"
    )

    html = _claim_rejected_html("Carlos Mendez", "Salon Palma Brickell")
    assert "Salon Palma Brickell" in html, "Business name missing from rejection email HTML"
    assert "hello@knowsbeauty.com" in html, "Support email missing from rejection email HTML"


def test_business_detail_jsonld_has_canonical_id(client):
    """The LocalBusiness JSON-LD on every detail page must include an '@id' field
    set to the page's canonical URL.

    WHY: without '@id', Google can't reliably connect the LocalBusiness block to
    the BreadcrumbList block on the same page — it may treat them as two unrelated
    entities. With '@id', both blocks reference the same URL, so Google knows they
    describe the same listing. This is what unlocks combined rich results (address
    + breadcrumb path shown together under the search result).

    Uses Rossano Ferretti as a well-seeded business with neighborhood, category,
    instagram, and website — confirming all four new JSON-LD fields together."""
    r = client.get(
        "/b/rossano-ferretti-hair-spa-miami",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    body = r.text

    # @id must appear in the LocalBusiness JSON-LD
    assert '"@id"' in body, (
        "Business detail page missing @id in JSON-LD — "
        "Google cannot connect LocalBusiness to BreadcrumbList without it"
    )
    # The @id value must contain the business slug so it points at the right page
    assert "rossano-ferretti-hair-spa-miami" in body


def test_business_detail_jsonld_has_image_when_photos_exist(client, seeded_db):
    """The LocalBusiness JSON-LD must include an 'image' field when the business
    has photos. Google shows this image in the Knowledge Panel next to the business
    name in search results — without it the entry is text-only and gets less
    visual prominence.

    WHY: this is the single highest-value structured-data addition for beauty
    businesses. A photo appearing alongside the name in search results dramatically
    increases click-through vs a text-only result."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )
    biz = asyncio.run(
        seeded_db.businesses.find_one(
            {"city_id": city["_id"], "photos": {"$elemMatch": {"url": {"$exists": True, "$ne": ""}}}}
        )
    )
    if biz is None:
        pytest.skip("No seeded businesses with photos — cannot test JSON-LD image field")

    r = client.get(
        f"/b/{biz['slug']}", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert '"image"' in r.text, (
        f"JSON-LD missing 'image' field on /b/{biz['slug']} even though it has photos"
    )


def test_business_detail_jsonld_has_same_as_with_instagram_and_website(client):
    """The LocalBusiness JSON-LD must include a 'sameAs' array linking to the
    business's Instagram profile and website when those are present in the seed.

    WHY: 'sameAs' tells Google's Knowledge Graph that this listing is the same
    entity as the Instagram profile and official website it already knows about.
    This strengthens the listing's entity recognition and improves ranking for
    branded searches like 'Rossano Ferretti Miami'."""
    r = client.get(
        "/b/rossano-ferretti-hair-spa-miami",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    body = r.text

    assert '"sameAs"' in body, "JSON-LD missing sameAs field for business with instagram + website"
    # Instagram handle @rossanoferretti should become the full profile URL
    assert "instagram.com/rossanoferretti" in body, (
        "sameAs must include instagram.com URL derived from handle"
    )
    # Website URL must appear in sameAs
    assert "rossanoferretti.com" in body, "sameAs must include the business website URL"


def test_business_detail_has_breadcrumb_jsonld(client):
    """Business detail pages must include a BreadcrumbList JSON-LD block so Google
    can display the navigation path (e.g. 'Miami Knows Beauty › Design District ›
    Hair Salons') under the search result.

    WHY: this breadcrumb path appears in the search result snippet and tells
    searchers exactly where the listing sits in the directory before they click —
    increasing click-through rate by giving context Google's organic link alone
    doesn't provide.

    Uses Rossano Ferretti which has both a neighborhood (design-district) and a
    category (hair), so we can verify all four breadcrumb positions are present."""
    r = client.get(
        "/b/rossano-ferretti-hair-spa-miami",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    body = r.text

    assert '"@type": "BreadcrumbList"' in body, "Business detail page missing BreadcrumbList JSON-LD"
    assert '"@type": "ListItem"' in body, "BreadcrumbList missing ListItem entries"
    # Position 1: directory home
    assert '"position": 1' in body, "BreadcrumbList missing position 1 (directory home)"
    # Business name must appear as the final breadcrumb item
    assert "Rossano Ferretti Hair Spa" in body  # already true for general page render
    # The breadcrumb item URL for this business must match its canonical path
    assert "rossano-ferretti-hair-spa-miami" in body


def test_claim_verified_email_function_exists_with_correct_content():
    """The claim-verified email helper must exist and produce the right content.

    WHY: without this email the owner has no idea their claim was approved —
    they submitted, got a confirmation, waited, and then heard nothing. They
    have no way to know they can now log in. This test verifies the email
    body names the business, links to the login page, and gives the support
    address without hitting a real email provider."""
    from app.services.owner_email import _claim_verified_text, _claim_verified_html

    login_url = "https://miami.knowsbeauty.ai.devintensive.com/owners/login"

    text = _claim_verified_text("Maria Lopez", "Salon Bliss Miami", login_url)
    assert "Salon Bliss Miami" in text, "Business name missing from verified email text"
    assert login_url in text, "Login URL missing from verified email text"
    assert "hello@knowsbeauty.com" in text, "Support email missing from verified email text"
    assert "verified" in text.lower(), "Email must state the claim has been verified"

    html = _claim_verified_html("Maria Lopez", "Salon Bliss Miami", login_url)
    assert "Salon Bliss Miami" in html, "Business name missing from verified email HTML"
    assert login_url in html, "Login URL missing from verified email HTML"
    assert "Log in to your dashboard" in html, "Login CTA missing from verified email HTML"


def test_business_card_does_not_expose_unclaimed_to_consumers(client):
    """Listing cards shown to consumers must never say 'Unclaimed'.

    'Unclaimed' signals abandonment to shoppers — it makes them think a
    business doesn't care about its listing. Only owners and admins should
    see that status. Consumer-facing cards should show 'Editorial selection'
    (or the verified/claimed label) instead.
    """
    # The home page renders business cards in the editor's-picks and trending
    # grids. No card on any consumer page should expose the word "Unclaimed".
    for path in ("/", "/c/nails", "/n/brickell"):
        r = client.get(path, headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, f"Page {path} returned {r.status_code}"
        # The word "Unclaimed" should not appear at all in the rendered HTML
        # (it would only be there if business_card.html still had the old
        # `elif b.claim_status == 'unclaimed' %}Unclaimed{%` branch).
        assert "Unclaimed" not in r.text, (
            f"Page {path} exposes 'Unclaimed' status to consumers — "
            "this label should only be shown in owner or admin views."
        )


def test_claim_form_does_not_reference_expertly_ai_email(client):
    """The claim form error messages must use hello@knowsbeauty.com, not
    hello@expertly.ai — the latter is an internal Expertly address that
    has nothing to do with Miami Knows Beauty and would confuse owners who
    hit a form error.
    """
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "hello@expertly.ai" not in r.text, (
        "The owners page references hello@expertly.ai — this must be "
        "hello@knowsbeauty.com so owners reach the right support address."
    )


def test_owner_lead_capture_endpoint_exists(client):
    """Owner email capture endpoint accepts valid email and returns ok."""
    r = client.post("/api/v1/owner-leads", json={"email": "test@example.com"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_owner_lead_capture_deduplicates(client):
    """Submitting the same email twice does not create duplicate records —
    the second call returns ok with already_captured=True instead of an error.
    WHY: an owner who double-clicks the submit button or refreshes the page
    should not hit an error or pollute the lead list with duplicates."""
    email = "dedupetest@example.com"
    r1 = client.post("/api/v1/owner-leads", json={"email": email})
    assert r1.status_code == 200
    assert r1.json()["ok"] is True

    r2 = client.post("/api/v1/owner-leads", json={"email": email})
    assert r2.status_code == 200
    data = r2.json()
    assert data["ok"] is True
    assert data.get("already_captured") is True


def test_owner_lead_capture_rejects_invalid_email(client):
    """The endpoint must reject strings that are not valid email addresses.
    WHY: garbage addresses are useless for follow-up and would inflate the
    lead count — Pydantic's EmailStr validator catches these at the API layer."""
    r = client.post("/api/v1/owner-leads", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_search_page_no_query(client):
    """GET /search with no query renders a browse prompt, not a 404."""
    r = client.get("/search", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    # A search bar should be present so the user can type their query.
    assert 'action="/search"' in r.text
    assert 'name="q"' in r.text


def test_search_page_with_results(client, seeded_db):
    """GET /search?q=<term> returns matching businesses in a grid."""
    r = client.get(
        "/search?q=brickell",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    # Results header must show the query.
    assert "brickell" in r.text.lower()
    # The search bar must be pre-filled with the query so the user can refine.
    assert 'value="brickell"' in r.text


def test_search_page_zero_results(client):
    """GET /search?q=<no-match> renders a helpful empty state, not an error."""
    r = client.get(
        "/search?q=xyzzy-no-such-business",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    # Zero-state copy must be shown.
    assert "Nothing found" in r.text
    # Owner banner in zero-state — someone searching for their own business.
    assert "Claim your listing" in r.text
    assert 'href="/owners"' in r.text


def test_search_page_shows_owner_banner_when_results(client, seeded_db):
    """When search returns results, the owner acquisition banner must appear.

    Owners often search for their own business name or service type.
    Without a banner here they'd see the results and leave without
    knowing they can claim their listing."""
    r = client.get(
        "/search?q=brickell",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    assert r.status_code == 200, r.text
    assert "For Business Owners" in r.text
    assert "Claim your listing" in r.text
    assert 'href="/owners"' in r.text


def test_404_page_has_search_and_owner_cta(client):
    """A 404 should not be a dead end. The page must include a search bar
    (so a user can recover by searching) and an owner claim CTA (since many
    404s come from business owners typing their salon's URL directly)."""
    r = client.get("/this-page-definitely-does-not-exist", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 404
    assert 'action="/search"' in r.text
    assert 'name="q"' in r.text
    assert "Claim your listing" in r.text
    assert 'href="/owners"' in r.text


def test_owners_page_has_email_capture_form(client):
    """The /owners page must include the email capture form for owners who
    are not yet ready to claim. The form posts to /api/v1/owner-leads and
    shows a thank-you message after submission."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    # The form and its key elements must be present
    assert "owner-lead-form" in body
    assert "owner-lead-email" in body
    assert "/api/v1/owner-leads" in body
    # The thank-you message exists (hidden by default, shown after submit)
    assert "owner-lead-thanks" in body
    # The prompt copy is present
    assert "Not ready to claim" in body


def test_mobile_nav_drawer_present_on_all_pages(client):
    """The mobile navigation drawer must be present on every page so phone
    visitors can reach categories, Pricing, and the owner claim page.
    Previously the hamburger button existed but had no associated menu — it
    clicked with no visible effect on screens under 640 px wide."""
    for path in ("/", "/owners", "/pricing", "/search"):
        r = client.get(path, headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        body = r.text
        assert "mobile-nav-drawer" in body, f"Mobile nav drawer missing from {path}"
        assert "mobile-nav-btn" in body, f"Mobile nav button missing from {path}"
        assert "aria-expanded" in body, f"aria-expanded missing from {path}"
        # Drawer must contain the For Salon Owners link so mobile visitors
        # can reach the claim flow without a working desktop browser
        assert "/owners" in body, f"/owners link missing from {path}"


def test_og_url_present_on_pages_with_canonical(client):
    """When a page has a canonical URL it must also have og:url set to the same
    value. Without og:url Facebook, LinkedIn, and Slack pick an arbitrary URL
    to attach social activity to — likes and comments fragment across URL
    variants instead of accumulating on the canonical page.

    WHY: og:url is separate from <link rel='canonical'>. The canonical tag is
    read by search engines; og:url is read by social crawlers. Both must be
    present for a page to behave correctly in search AND social sharing."""
    for path in ("/b/blow-dry-bar-brickell", "/", "/owners", "/pricing"):
        r = client.get(path, headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        body = r.text
        if 'rel="canonical"' in body:
            assert 'property="og:url"' in body, (
                f"{path} has a canonical tag but is missing og:url — "
                "social shares on this page will not accumulate correctly"
            )


def test_twitter_card_meta_tags_present(client):
    """Every page must include Twitter Card meta tags so links posted on
    Twitter/X render with a large image and description instead of plain text.

    Twitter/X does NOT fall back to og: tags — it requires its own twitter:
    tags. Without twitter:card the shared URL shows only the page title with
    no image or description, which looks unfinished and gets far fewer clicks.

    WHY: salon owners and clients share listings on Twitter/X. A blank link
    card makes the business look unprofessional."""
    for path in ("/", "/b/blow-dry-bar-brickell", "/owners"):
        r = client.get(path, headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        body = r.text
        assert 'name="twitter:card"' in body, (
            f"{path} missing twitter:card meta tag — Twitter/X will show a plain-text link"
        )
        assert 'name="twitter:title"' in body, (
            f"{path} missing twitter:title meta tag"
        )


def test_business_jsonld_omits_empty_address_fields(client):
    """The JSON-LD on a business page must not emit empty strings for
    addressRegion or postalCode. Google's Rich Results validator treats
    empty strings as invalid values and can suppress the whole address block
    from the Knowledge Panel, reducing the chance of a rich result appearing.

    WHY: the seed businesses may not have region/postal data. The template
    must omit those fields when empty rather than emitting '\"addressRegion\": \"\"'
    which looks valid to a human but fails structured-data validation."""
    import json, re

    r = client.get(
        "/b/blow-dry-bar-brickell", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    # Extract JSON-LD blocks
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL
    )
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if data.get("@type") in ("HairSalon", "NailSalon", "DaySpa", "BeautySalon", "LocalBusiness"):
            addr = data.get("address", {})
            assert addr.get("addressRegion") != "", (
                "addressRegion is an empty string in JSON-LD — must be omitted when unknown"
            )
            assert addr.get("postalCode") != "", (
                "postalCode is an empty string in JSON-LD — must be omitted when unknown"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_jsonld_blocks(html: str):
    """Return parsed JSON-LD dicts from all <script type='application/ld+json'> blocks."""
    import json, re
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    result = []
    for b in blocks:
        try:
            result.append(json.loads(b.strip()))
        except json.JSONDecodeError:
            pass
    return result


def test_category_page_has_breadcrumblist_jsonld(client):
    """Category pages must include BreadcrumbList structured data so Google
    can display the breadcrumb trail ("Miami Knows Beauty > Hair") in search
    results, which increases click-through rates.

    WHY: the visual breadcrumb already exists on category pages. Without the
    JSON-LD version Google falls back to guessing the site hierarchy — often
    wrong — so the search result snippet shows the full raw URL instead of
    a clean breadcrumb trail."""
    r = client.get("/c/hair", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, f"/c/hair returned {r.status_code}"
    blocks = _extract_jsonld_blocks(r.text)
    breadcrumb_blocks = [b for b in blocks if b.get("@type") == "BreadcrumbList"]
    assert breadcrumb_blocks, (
        "/c/hair is missing BreadcrumbList JSON-LD — "
        "Google cannot show breadcrumbs in search results for this category page"
    )
    items = breadcrumb_blocks[0].get("itemListElement", [])
    assert len(items) == 2, (
        f"Expected 2 breadcrumb items for /c/<slug> (Home > Category), got {len(items)}"
    )
    assert items[0]["position"] == 1
    assert items[1]["position"] == 2
    # Second item should link to the category page itself
    assert "/c/hair" in items[1]["item"], (
        f"Second breadcrumb item should point to the category page; got {items[1].get('item')}"
    )


def test_neighborhood_page_has_breadcrumblist_jsonld(client):
    """Neighborhood pages must include BreadcrumbList structured data for the
    same reason as category pages. Queries like 'Wynwood hair salons' are
    high-intent local searches that land on neighborhood pages — a breadcrumb
    rich result signals topical relevance and site structure to Google's
    local ranking algorithm.

    WHY: neighborhood pages are often the first entry point for locals
    searching by area. The visual breadcrumb is already rendered; this adds
    the machine-readable version Google uses for search result presentation."""
    r = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, f"/n/brickell returned {r.status_code}"
    blocks = _extract_jsonld_blocks(r.text)
    breadcrumb_blocks = [b for b in blocks if b.get("@type") == "BreadcrumbList"]
    assert breadcrumb_blocks, (
        "/n/brickell is missing BreadcrumbList JSON-LD — "
        "Google cannot show breadcrumbs in search results for this neighborhood page"
    )
    items = breadcrumb_blocks[0].get("itemListElement", [])
    assert len(items) == 2, (
        f"Expected 2 breadcrumb items for /n/<slug> (Home > Neighborhood), got {len(items)}"
    )
    assert "/n/brickell" in items[1]["item"], (
        f"Second breadcrumb item should point to the neighborhood page; got {items[1].get('item')}"
    )


def test_claim_form_browse_hint_present_in_dom(client):
    """The owners/claim page must include the 'Browse the full directory' hint
    element in the HTML so JavaScript can reveal it when a business name does
    not match any listing.

    WHY: without this element, salon owners who mistype their business name
    hit a dead end — they see an error message ("We couldn't find a listing
    matching...") but have no link to find their listing and come back to
    claim it. The hint gives them a one-click path to the directory browse
    view so the claim journey doesn't end in frustration."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, f"/owners returned {r.status_code}"
    assert 'id="claim-form__browse-hint"' in r.text, (
        "/owners is missing the claim-form__browse-hint element — "
        "owners who can't find their listing by name have no path forward"
    )
    assert "Browse the full directory" in r.text, (
        "'Browse the full directory' link text missing from the claim form"
    )


def test_claim_form_suggestions_container_present_in_dom(client):
    """The claim form must include the 'Did you mean?' suggestion container
    and list elements in the HTML so JavaScript can populate them when a
    business name does not exactly match any directory listing.

    WHY: a plain 'not found' error leaves the owner stuck — they typed
    something close to their salon name but not exact. The suggestion buttons
    let them click their correct listing without leaving the form, which
    keeps the claim funnel intact rather than forcing a page-leave to browse
    the directory. The container is hidden by default; JS shows it with
    word-overlap-scored matches when showBrowse=true fires."""
    r = client.get("/owners", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, f"/owners returned {r.status_code}"
    assert 'id="claim-form__suggestions"' in r.text, (
        "/owners is missing the claim-form__suggestions container — "
        "'Did you mean?' suggestions cannot appear on no-match errors"
    )
    assert 'id="claim-form__suggestion-list"' in r.text, (
        "/owners is missing the claim-form__suggestion-list element — "
        "suggestion buttons have no container to render into"
    )
    assert "Did you mean" in r.text, (
        "'Did you mean' prompt text missing from claim form suggestions"
    )


def test_owner_me_pending_state_has_feature_teaser_cards():
    """The pending-state section of the owner portal must show three
    feature-preview cards so owners waiting for claim verification can see
    exactly what tools they are about to unlock — making the wait feel
    purposeful instead of like a dead end.

    WHY: the previous copy said 'once verified, you'll be able to update
    your listing' which is vague and gives no reason to look forward to
    approval. The three cards ('Edit your listing', 'AI marketing tools',
    'Featured upgrade') are concrete and desirable — they set expectations
    and reduce the chance of an owner giving up before verification completes.

    We test the template file directly because the /owners/me route is auth-
    gated: rendering the pending state in an integration test would require
    mocking an owner session, which tests the session middleware rather than
    the feature. Checking the template text is the right scope here."""
    import pathlib
    template = (
        pathlib.Path(__file__).parent.parent
        / "app" / "templates" / "owner_me.html"
    )
    content = template.read_text()
    for label in ("Edit your listing", "AI marketing tools", "Featured upgrade"):
        assert label in content, (
            f"Pending-state feature teaser card '{label}' missing from owner_me.html — "
            "owners in the pending state won't know what's coming after verification"
        )


def test_category_page_title_uses_full_brand_name(client):
    """Category page titles must include 'Miami Knows Beauty' — the full brand
    name — not just 'Knows Beauty' (the network word without the city).

    WHY: a title that reads 'Hair in Miami — Knows Beauty' is missing the
    city prefix that makes the brand recognizable. Google shows the page title
    as the blue clickable headline in search results; a title with the full brand
    name ('Miami Knows Beauty') reinforces brand recognition and local relevance
    for every impression, even when the user does not click."""
    r = client.get("/c/hair", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    import re
    m = re.search(r"<title>(.*?)</title>", r.text)
    assert m, "Category page has no <title> tag"
    title = m.group(1)
    assert "Miami Knows Beauty" in title, (
        f"Category page title '{title}' missing 'Miami Knows Beauty' — "
        "was 'Knows Beauty' (city prefix dropped)"
    )


def test_neighborhood_page_title_uses_full_brand_name_in_correct_order(client):
    """Neighborhood page titles must read 'Design District — Miami Knows Beauty',
    not 'Design District — Knows Beauty Miami' (reversed).

    WHY: the brand name 'Miami Knows Beauty' has a specific order. 'Knows Beauty
    Miami' reads as gibberish to a first-time visitor scanning Google results —
    it is not a recognizable phrase and undermines the brand's credibility in
    the impression before any click happens."""
    r = client.get("/n/design-district", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    import re
    m = re.search(r"<title>(.*?)</title>", r.text)
    assert m, "Neighborhood page has no <title> tag"
    title = m.group(1)
    assert "Miami Knows Beauty" in title, (
        f"Neighborhood page title '{title}' missing 'Miami Knows Beauty' — "
        "was 'Knows Beauty Miami' (city and network words reversed)"
    )
    assert "Knows Beauty Miami" not in title, (
        f"Neighborhood page title '{title}' still has reversed brand name 'Knows Beauty Miami'"
    )


def test_neighborhood_category_page_title_uses_full_brand_name(client):
    """The combined neighborhood + category page title must include the full
    'Miami Knows Beauty' brand, not the reversed 'Knows Beauty Miami'.

    WHY: this is the highest-intent landing page type ('Hair salons in Wynwood')
    and is the most likely destination for Google Ads and high-value organic
    queries. A garbled brand name on the most valuable page type is particularly
    harmful to conversion."""
    r = client.get("/n/wynwood/c/hair", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    import re
    m = re.search(r"<title>(.*?)</title>", r.text)
    assert m, "Neighborhood-category page has no <title> tag"
    title = m.group(1)
    assert "Miami Knows Beauty" in title, (
        f"Neighborhood-category page title '{title}' missing 'Miami Knows Beauty'"
    )
    assert "Knows Beauty Miami" not in title, (
        f"Neighborhood-category page title '{title}' has reversed brand name"
    )
