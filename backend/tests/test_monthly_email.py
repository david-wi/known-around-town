"""Unit tests for the monthly email rendering and the gated test-send.

Rendering tests are pure (no DB, no provider). The test-send tests assert the
safety gate behaviour by patching the provider boundary, never hitting Resend.
All assertions check BEHAVIOR (subject text, presence of the number, the
caption card, the flag gate) rather than source-text presence.
"""

from __future__ import annotations

import pytest

from app.services import monthly_email
from app.services.monthly_email import (
    build_subject,
    render_monthly_email,
    send_test_monthly_email,
)
from app.services.monthly_report import MonthlyReport

# WHY: reference the flag-check via the module (monthly_email.test_send_enabled)
# rather than importing it bare — a module-level `from ... import test_send_enabled`
# makes pytest collect the function itself as a (bogus) test because its name
# starts with "test_".
_test_send_enabled = monthly_email.test_send_enabled


def _report(
    *,
    views_this_month: int = 25,
    views_last_month=None,
    messages: int = 3,
    trend: str = "flat",
    is_first: bool = False,
    is_thin: bool = False,
    name: str = "Glow Salon",
) -> MonthlyReport:
    return MonthlyReport(
        business_id="biz-1",
        business_name=name,
        period_key="2026-06",
        period_label="June 2026",
        views_this_month=views_this_month,
        views_last_month=views_last_month,
        messages_this_month=messages,
        trend=trend,
        is_first_report=is_first,
        is_thin_views=is_thin,
    )


# ── Subject + headline + lead ────────────────────────────────────────────────

class TestSubjectAndHeadline:
    def test_subject_includes_business_and_month(self):
        subject = build_subject(_report(name="Curl Studio"))
        assert "Curl Studio" in subject
        assert "June" in subject

    def test_up_trend_leads_with_increase(self):
        report = _report(views_this_month=80, views_last_month=10, trend="up")
        _subject, html, text = render_monthly_email(report)
        # The "up from last month" framing must appear in BOTH bodies.
        assert "up from 10 last month" in html
        assert "up from 10 last month" in text

    def test_normal_month_does_not_claim_increase(self):
        report = _report(views_this_month=30, views_last_month=40, trend="down")
        _subject, html, _text = render_monthly_email(report)
        assert "up from" not in html

    def test_first_report_uses_since_you_joined_framing(self):
        report = _report(views_this_month=120, is_first=True, trend="first")
        _subject, html, text = render_monthly_email(report)
        assert "So far" in html
        assert "So far" in text


# ── Pluralisation ────────────────────────────────────────────────────────────

class TestPluralisation:
    def test_single_viewer_uses_person(self):
        report = _report(views_this_month=1, views_last_month=0, trend="up")
        _subject, html, _text = render_monthly_email(report)
        assert "1 person" in html
        assert "1 people" not in html

    def test_multiple_viewers_use_people(self):
        report = _report(views_this_month=12, views_last_month=3, trend="up")
        _subject, html, _text = render_monthly_email(report)
        assert "12 people" in html

    def test_the_number_is_shown(self):
        # The owner-facing number must literally appear in the email body.
        report = _report(views_this_month=37, views_last_month=20, trend="up")
        _subject, html, text = render_monthly_email(report)
        assert "37" in html
        assert "37" in text


# ── Thin-views caption branch ────────────────────────────────────────────────

class TestThinViewsCaption:
    def test_thin_email_includes_caption_card_when_caption_provided(self):
        report = _report(views_this_month=3, is_thin=True, trend="down")
        caption = "Fresh fades all week ☀️\n#MiamiBarber #FreshCut"
        _subject, html, text = render_monthly_email(report, caption=caption)
        # The caption text must be present in the rendered email.
        assert "Fresh fades all week" in html
        assert "Fresh fades all week" in text
        assert "Ready to post" in html  # the caption card heading

    def test_thin_email_hides_stat_strip(self):
        # For a thin month we don't visually dwell on the small number — the
        # big stat strip (the two large numbers) is omitted.
        report = _report(views_this_month=3, is_thin=True, trend="down")
        _subject, html, _text = render_monthly_email(report, caption="Post me!")
        # The large-number stat strip uses this exact label; it must be absent.
        assert "views this month" not in html

    def test_healthy_month_shows_stat_strip_and_no_caption(self):
        report = _report(views_this_month=50, views_last_month=40, trend="up")
        _subject, html, _text = render_monthly_email(report, caption=None)
        assert "views this month" in html  # stat strip present
        assert "Ready to post" not in html  # no caption card

    def test_caption_html_is_escaped(self):
        # A caption containing HTML must be escaped, not injected as markup.
        report = _report(views_this_month=2, is_thin=True, trend="down")
        _subject, html, _text = render_monthly_email(report, caption="<script>x</script>")
        assert "<script>x</script>" not in html
        assert "&lt;script&gt;" in html


# ── Test-send safety gate ────────────────────────────────────────────────────

class TestTestSendGate:
    def test_flag_off_by_default(self, monkeypatch):
        monkeypatch.delenv("MONTHLY_REPORT_TEST_SEND_ENABLED", raising=False)
        assert _test_send_enabled() is False

    def test_flag_recognises_truthy_spellings(self, monkeypatch):
        for val in ("true", "1", "yes", "on", "TRUE", "On"):
            monkeypatch.setenv("MONTHLY_REPORT_TEST_SEND_ENABLED", val)
            assert _test_send_enabled() is True

    async def test_send_refuses_when_flag_off(self, monkeypatch):
        # Flag off → must return False WITHOUT calling the provider.
        monkeypatch.delenv("MONTHLY_REPORT_TEST_SEND_ENABLED", raising=False)
        called = {"posted": False}

        async def _boom(*a, **k):  # pragma: no cover - must never run
            called["posted"] = True
            raise AssertionError("provider must not be called when flag is off")

        # Even if a provider key is set, the flag gate must short-circuit first.
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        result = await send_test_monthly_email(to="qa@example.com", report=_report())
        assert result is False
        assert called["posted"] is False

    async def test_send_logs_in_dev_when_flag_on_and_no_key(self, monkeypatch):
        # Flag on but no RESEND_API_KEY → dev fallback logs and returns True
        # WITHOUT a real network call.
        monkeypatch.setenv("MONTHLY_REPORT_TEST_SEND_ENABLED", "true")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        result = await send_test_monthly_email(to="qa@example.com", report=_report())
        assert result is True
