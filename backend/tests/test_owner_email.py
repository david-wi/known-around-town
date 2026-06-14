"""Unit tests for owner_email template helpers.

These test the text/HTML rendering helpers directly — no HTTP call, no DB,
no email provider. The helpers are pure functions so they are straightforward
to test without any mocking.
"""

import pytest

from app.services.owner_email import _claim_verified_html, _claim_verified_text


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

    def test_urgency_shown_when_spots_available(self):
        text = _claim_verified_text(
            "Maria", "Salon X", LOGIN_URL, PRICING_URL, founding_partner_spots_left=5
        )
        assert "5 spots left" in text
        assert "founding partner" in text.lower()

    def test_urgency_singular_when_one_spot(self):
        text = _claim_verified_text(
            "Maria", "Salon X", LOGIN_URL, PRICING_URL, founding_partner_spots_left=1
        )
        assert "1 spot left" in text

    def test_no_urgency_when_zero_spots(self):
        text = _claim_verified_text(
            "Maria", "Salon X", LOGIN_URL, PRICING_URL, founding_partner_spots_left=0
        )
        assert "spots left" not in text
        assert "founding partner" not in text.lower()

    def test_no_urgency_by_default(self):
        text = _claim_verified_text("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "spots left" not in text


class TestClaimVerifiedHtml:
    def test_includes_login_button(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert LOGIN_URL in html
        assert "Log in to your dashboard" in html

    def test_includes_pricing_cta_button(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert PRICING_URL in html
        assert "Get Featured" in html

    def test_shows_price(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "$29/month" in html

    def test_urgency_shown_when_spots_available(self):
        html = _claim_verified_html(
            "Maria", "Salon X", LOGIN_URL, PRICING_URL, founding_partner_spots_left=3
        )
        assert "3 founding partner spots left" in html or "3 spots" in html
        # urgency should be styled prominently (red, uppercase, etc.)
        assert "dc2626" in html  # red urgency color

    def test_no_urgency_block_when_zero_spots(self):
        html = _claim_verified_html(
            "Maria", "Salon X", LOGIN_URL, PRICING_URL, founding_partner_spots_left=0
        )
        assert "dc2626" not in html  # no red urgency color
        assert "spots left" not in html

    def test_no_urgency_by_default(self):
        html = _claim_verified_html("Maria", "Salon X", LOGIN_URL, PRICING_URL)
        assert "spots left" not in html

    def test_fallback_first_name_for_empty_name(self):
        html = _claim_verified_html("", "Salon X", LOGIN_URL, PRICING_URL)
        assert "Hi there" in html
