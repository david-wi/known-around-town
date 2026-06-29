"""Unit tests for owner_email template helpers.

These test the text/HTML rendering helpers directly — no HTTP call, no DB,
no email provider. The helpers are pure functions so they are straightforward
to test without any mocking.
"""

import pytest

from app.services.owner_email import (
    _claim_verified_html,
    _claim_verified_text,
    _subscription_confirmed_html,
    _subscription_confirmed_text,
)


LOGIN_URL = "https://miami.knowsbeauty.com/owners/login?email=test%40example.com"
PRICING_URL = "https://miami.knowsbeauty.com/pricing"


class TestClaimVerifiedText:
    def test_includes_owner_first_name(self):
        text = _claim_verified_text("Maria Rodriguez", "Salon X", LOGIN_URL, PRICING_URL)
        assert "Hi Maria" in text

    def test_includes_business_name(self):
        text = _claim_verified_text("Maria", "Curl Studio", LOGIN_URL, PRICING_URL)
        assert "Curl Studio" in text

    def test_includes_login_url(self):
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert LOGIN_URL in text

    def test_includes_pricing_url(self):
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert PRICING_URL in text

    def test_no_founding_partner_mention(self):
        # WHY: the Founding Partner concept was removed entirely. The claim-
        # verified email must no longer mention founding partner status or a
        # spots-left scarcity hook.
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "founding partner" not in text.lower()
        assert "spots left" not in text.lower()

    def test_still_sells_featured(self):
        # WHY: removing Founding Partner must not remove the legitimate Featured
        # upgrade pitch — that's the revenue path and stays.
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "Featured" in text
        assert "$29/month" in text

    def test_no_top_placement_promise(self):
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        lowered = text.lower()
        assert "top of every page" not in lowered
        assert "top of category" not in lowered
        assert "appear first" not in lowered
        assert "appears first" not in lowered


class TestClaimVerifiedHtml:
    def test_includes_login_button(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert LOGIN_URL in html
        assert "Log in to your owner page" in html

    def test_includes_pricing_cta_button(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert PRICING_URL in html
        assert "Get Featured" in html

    def test_shows_price(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "$29/month" in html

    def test_no_founding_partner_block(self):
        # WHY: the Founding Partner concept was removed entirely — the email
        # must no longer carry the founding-partner scarcity block (the red
        # "spots left" urgency line) or any founding-partner wording.
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "founding partner" not in html.lower()
        assert "spots left" not in html.lower()
        assert "dc2626" not in html  # the red urgency color is gone with the block

    def test_fallback_first_name_for_empty_name(self):
        html = _claim_verified_html("", "Salon X", LOGIN_URL, PRICING_URL)
        assert "Hi there" in html

    def test_no_top_placement_promise(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        lowered = html.lower()
        assert "top of every page" not in lowered
        assert "top of category" not in lowered
        assert "appear first" not in lowered
        assert "appears first" not in lowered


DASHBOARD_URL = "https://miami.knowsbeauty.com/owners/me"


class TestSubscriptionConfirmedAdVariationCount:
    """The welcome email must promise the same number of ad variations the
    generator actually returns. The ad-copy tool is hard-coded to produce
    EXACTLY 3 variations (app/services/ai_caption.py), so the email previously
    promising "20" was an over-promise that set owners up for disappointment
    the first time they used the tool. These tests lock the email to "3" and
    guard against the inflated "20" creeping back in.
    """

    def test_text_promises_three_ad_variations(self):
        text = _subscription_confirmed_text("Maria", "Curl Studio", DASHBOARD_URL)
        assert "3 ready-to-run ad variations" in text

    def test_text_does_not_overpromise_twenty(self):
        text = _subscription_confirmed_text("Maria", "Curl Studio", DASHBOARD_URL)
        assert "20 ready-to-run ad variations" not in text

    def test_html_promises_three_variations(self):
        html = _subscription_confirmed_html("Maria", "Curl Studio", DASHBOARD_URL)
        assert "3 ready-to-run variations per campaign" in html

    def test_html_does_not_overpromise_twenty(self):
        html = _subscription_confirmed_html("Maria", "Curl Studio", DASHBOARD_URL)
        assert "20 ready-to-run variations" not in html

    def test_subscription_email_has_no_top_placement_promise(self):
        text = _subscription_confirmed_text("Maria", "Curl Studio", DASHBOARD_URL)
        html = _subscription_confirmed_html("Maria", "Curl Studio", DASHBOARD_URL)
        combined = f"{text}\n{html}".lower()
        assert "top of every page" not in combined
        assert "top of category" not in combined
        assert "appear first" not in combined
        assert "appears first" not in combined

    def test_subscription_email_uses_featured_not_pro(self):
        text = _subscription_confirmed_text("Maria", "Curl Studio", DASHBOARD_URL)
        html = _subscription_confirmed_html("Maria", "Curl Studio", DASHBOARD_URL)
        combined = f"{text}\n{html}"
        assert "Featured listing" in combined
        assert "Pro listing" not in combined
        assert "Featured Pro" not in combined
        assert "Pro Featured" not in combined


class TestNoFoundingPartnerInEmails:
    """The Founding Partner concept was removed entirely. The claim-verified
    email must carry no founding-partner wording in either the text or HTML
    body — no badge mention, no spots-left scarcity, no founding price.
    """

    def test_text_has_no_founding_partner_wording(self):
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        for phrase in ("founding partner", "founding price", "spots left"):
            assert phrase not in text.lower(), f"text must not mention {phrase!r}"

    def test_html_has_no_founding_partner_wording(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        for phrase in ("founding partner", "founding price", "spots left"):
            assert phrase not in html.lower(), f"html must not mention {phrase!r}"


@pytest.mark.asyncio
class TestDynamicSiteNameResolution:
    async def test_resolves_default_for_empty_inputs(self, seeded_db):
        from app.services.owner_email import _resolve_site_names
        site_name, net_name = await _resolve_site_names()
        assert site_name == "Miami Knows Beauty"
        assert net_name == "Knows Beauty"

    async def test_resolves_from_url_hostname(self, seeded_db):
        from app.services.owner_email import _resolve_site_names
        
        # Test with a known seeded city (Miami)
        site_name, net_name = await _resolve_site_names(url="https://miami.knowsbeauty.localhost:8000/owners/login")
        assert site_name == "Miami Knows Beauty"
        assert net_name == "Knows Beauty"
        
        db = seeded_db
        # Let's get the seeded beauty network ID
        net = await db.networks.find_one({"slug": "beauty"})
        assert net is not None
        
        # Let's seed a new city in the existing beauty network
        await db.cities.insert_one({
            "_id": "test-city-id",
            "network_id": net["_id"],
            "slug": "weston",
            "name": "Weston",
        })
        
        # Now resolve from the Weston URL hostname
        site_name, net_name = await _resolve_site_names(url="https://weston.knowsbeauty.localhost:8000/owners/login")
        assert site_name == "Weston Knows Beauty"
        assert net_name == "Knows Beauty"
        
        # Test with another network
        net_well = await db.networks.find_one({"slug": "wellness"})
        assert net_well is not None
        await db.cities.insert_one({
            "_id": "test-well-city-id",
            "network_id": net_well["_id"],
            "slug": "fort-lauderdale",
            "name": "Fort Lauderdale",
        })
        site_name, net_name = await _resolve_site_names(url="https://fort-lauderdale.knowswellness.localhost/owners/login")
        assert site_name == "Fort Lauderdale Knows Wellness"
        assert net_name == "Knows Wellness"

    async def test_resolves_from_business_id(self, seeded_db):
        from app.services.owner_email import _resolve_site_names
        db = seeded_db
        
        await db.networks.insert_one({"_id": "net-1", "slug": "beauty-net", "name": "Knows Beauty"})
        await db.cities.insert_one({"_id": "city-1", "network_id": "net-1", "slug": "doral", "name": "Doral"})
        await db.businesses.insert_one({
            "_id": "biz-1",
            "city_id": "city-1",
            "name": "Doral Nail Salon",
        })
        
        site_name, net_name = await _resolve_site_names(business_id="biz-1")
        assert site_name == "Doral Knows Beauty"
        assert net_name == "Knows Beauty"

    async def test_resolves_from_business_name(self, seeded_db):
        from app.services.owner_email import _resolve_site_names
        db = seeded_db
        
        await db.networks.insert_one({"_id": "net-2", "slug": "beauty-net-2", "name": "Knows Beauty"})
        await db.cities.insert_one({"_id": "city-2", "network_id": "net-2", "slug": "fort-lauderdale", "name": "Fort Lauderdale"})
        await db.businesses.insert_one({
            "_id": "biz-2",
            "city_id": "city-2",
            "name": "Las Olas Hair Design",
        })
        
        site_name, net_name = await _resolve_site_names(business_name="Las Olas Hair Design")
        assert site_name == "Fort Lauderdale Knows Beauty"
        assert net_name == "Knows Beauty"
