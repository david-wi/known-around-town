"""Unit tests for owner_email template helpers.

These test the text/HTML rendering helpers directly — no HTTP call, no DB,
no email provider. The helpers are pure functions so they are straightforward
to test without any mocking.
"""

import pytest

from app.services.owner_email import (
    _claim_confirmation_html,
    _claim_rejected_html,
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

    def test_escapes_owner_controlled_html(self):
        html = _claim_verified_html(
            '<script>alert("x")</script>',
            'Salon <img src=x onerror=alert(1)>',
            'https://example.com/owners/login?email=x&next=<bad>',
            'https://example.com/pricing?x=1&y=<bad>',
        )
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;" in html
        assert "Salon &lt;img" in html
        assert "email=x&amp;next=&lt;bad&gt;" in html
        assert "x=1&amp;y=&lt;bad&gt;" in html


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

    def test_subscription_html_escapes_owner_controlled_html(self):
        html = _subscription_confirmed_html(
            '<script>alert("x")</script>',
            'Curl <img src=x onerror=alert(1)>',
            'https://example.com/owners/me?x=1&y=<bad>',
        )
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;" in html
        assert "Curl &lt;img" in html
        assert "x=1&amp;y=&lt;bad&gt;" in html


class TestClaimStatusHtmlEscaping:
    def test_confirmation_html_escapes_owner_controlled_html(self):
        html = _claim_confirmation_html(
            '<script>alert("x")</script>',
            'Salon <img src=x onerror=alert(1)>',
        )
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;" in html
        assert "Salon &lt;img" in html

    def test_rejected_html_escapes_owner_controlled_html(self):
        html = _claim_rejected_html(
            '<script>alert("x")</script>',
            'Salon <img src=x onerror=alert(1)>',
        )
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;" in html
        assert "Salon &lt;img" in html


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
async def test_admin_new_claim_email_escapes_submitter_controlled_html(monkeypatch):
    """# @define-test KAT-075"""
    import app.services.owner_email as owner_email

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, headers, json):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setattr(owner_email.httpx, "AsyncClient", FakeClient)

    ok = await owner_email.send_admin_new_claim_email(
        submitter_name='<script>alert("x")</script>',
        submitter_email='owner@example.com" onclick="steal()',
        business_name='Salon <img src=x onerror=alert(1)>',
        admin_url='https://miami.knowsbeauty.com/admin/claims?x=1&y=<bad>',
    )

    assert ok is True
    html_body = captured["json"]["html"]
    assert "<script>" not in html_body
    assert "<img" not in html_body
    assert 'onclick="steal()' not in html_body
    assert "&lt;script&gt;" in html_body
    assert "Salon &lt;img" in html_body
    assert "x=1&amp;y=&lt;bad&gt;" in html_body
    assert 'mailto:owner@example.com%22%20onclick%3D%22steal%28%29' in html_body
