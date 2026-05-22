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


def test_unknown_city_renders_404(client):
    """Network is known but the city slug isn't in the database."""
    r = client.get("/", headers={"host": "atlantis.knowsbeauty.localhost"})
    # The tenant resolver returns no city, so the home route currently 404s on the city pages.
    # The network home template still renders 200 — verify both behaviors are not 500s.
    assert r.status_code in (200, 404)


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
