"""Render (and optionally send) the monthly "your listing is working" email.

This is the retention email for Featured salon owners: once a month it tells
the owner, in plain language, how many people viewed their listing and how
many reached out — a recurring, visible reason to keep their $29/month
subscription.

WHY this module is split from ``monthly_report.py``: that module computes the
numbers; this one turns numbers into words and HTML, and is the only place
that touches the email provider. It reuses the exact Resend pattern and
from/reply-to helpers already proven in ``owner_email.py`` — no new provider
integration.

----------------------------------------------------------------------
SAFETY: this email never sends to a real owner from this module by itself.
----------------------------------------------------------------------
``render_monthly_email`` is pure (returns HTML/text, sends nothing).
``send_test_monthly_email`` sends exactly ONE copy to an explicitly-provided
TEST address and is gated by a feature flag that is OFF by default. There is
NO function in this module that bulk-sends to owners; the live monthly send is
a deliberate, separate, founder-approved step that does not exist yet (see
``operations.md`` and the WHY note on ``LIVE_SEND_FLAG`` below).
"""

from __future__ import annotations

import html
import logging
import os
from typing import Optional

import httpx

from app.services.monthly_report import MonthlyReport

logger = logging.getLogger(__name__)

# WHY: same 30s timeout as owner_email/preview_email — long enough for Resend
# latency, short enough not to pin a worker on a stuck call.
_PROVIDER_TIMEOUT_SECONDS = 30.0

# WHY: the test-send path is a real outbound email, so it is gated by its OWN
# flag, defaulting OFF, ON TOP OF the admin-key gate on the route. With the
# flag off the route still renders a preview but refuses to actually send —
# so a misconfigured deploy can never email anyone, even a test address.
TEST_SEND_FLAG = "MONTHLY_REPORT_TEST_SEND_ENABLED"

# WHY: the LIVE monthly send to all real owners is the founder's decision and
# does NOT exist as a wired sender. This flag name is reserved and documented
# so that when the founder approves, a future cron/sender checks it. Nothing in
# this codebase sends to real owners today; this constant is a breadcrumb, not
# an active switch.
LIVE_SEND_FLAG = "MONTHLY_REPORT_LIVE_SEND_ENABLED"


def test_send_enabled() -> bool:
    """True only when the test-send flag is explicitly truthy.

    Accepts the same truthy spellings the marketing-AI flag accepts so deploy
    scripts and humans both work.
    """
    raw = os.environ.get(TEST_SEND_FLAG, "").strip().lower()
    return raw in {"true", "1", "yes", "on"}


def _from_address() -> str:
    # WHY: identical to owner_email._from_address so the monthly email comes
    # from the same verified sender owners already recognise.
    name = os.environ.get("OWNER_EMAIL_FROM_NAME", "Knows Beauty").strip()
    addr = os.environ.get(
        "OWNER_EMAIL_FROM_ADDRESS", "noreply@knowsbeauty.ai.devintensive.com"
    ).strip()
    return f"{name} <{addr}>"


def _owner_reply_to() -> str:
    return os.environ.get("OWNER_EMAIL_REPLY_TO", "hello@knowsbeauty.com").strip()


def _provider_api_key() -> Optional[str]:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    return key or None


def _dashboard_url() -> str:
    """Public owner-dashboard URL used for the email's main button.

    WHY read at call time from CANONICAL_BASE_URL: the link must use the public
    hostname (miami.knowsbeauty.com), not the Docker-internal dev domain. Same
    reasoning as inquiries._dashboard_url.
    """
    base = (os.environ.get("CANONICAL_BASE_URL") or "https://miami.knowsbeauty.com").rstrip("/")
    return f"{base}/owners/me"


# =====================================================================
# FOUNDER-OWNED COPY — edit these to change the pitch and tone.
# These are the headline/subject lines David tweaks. They are plain
# Python format strings; the only placeholders are the named fields in
# braces. Keep the braces, change everything else freely.
# =====================================================================

# Subject line. {month} = "June", {name} = salon name.
SUBJECT_TEMPLATE = "Your {name} listing in {month} — here's how it did"

# Headline when this month's views are UP from last month (lead with the win).
HEADLINE_TREND_UP = "Your listing is picking up steam"

# Headline for a normal month with a healthy view count.
HEADLINE_NORMAL = "Here's how your listing did this month"

# Headline when views are thin — we don't dwell on the small number, we hand
# the owner something to post next month instead.
HEADLINE_THIN = "A little something to grow your listing"

# Headline on the very first report (we report lifetime, not a month delta).
HEADLINE_FIRST = "Your listing on Miami Knows Beauty"

# Lead sentence builders. These are the one or two human sentences under the
# headline. Keep them short; David owns the voice here.
def _action_phrase(report: MonthlyReport) -> str:
    """Human phrase for the high-intent taps, or "" when there were none.

    WHY: taps-to-call and taps-for-directions are stronger "your listing is
    working" proof than a passive view, so when any occurred the email calls
    them out. Returns "" when all three are zero so a quiet month never reads
    "0 tapped to call". Each clause is included only for the non-zero counts, in
    intent order (call, directions, website), and joined into plain English.
    """
    parts: list[str] = []
    if report.calls_this_month:
        parts.append(f"{report.calls_this_month} tapped to call")
    if report.directions_this_month:
        parts.append(f"{report.directions_this_month} tapped for directions")
    if report.website_clicks_this_month:
        parts.append(f"{report.website_clicks_this_month} clicked through to your website")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def _mkb_referral_phrase(report: MonthlyReport) -> str:
    """Human sentence crediting MKB for the visitors WE sent, or "" if none.

    WHY: this is the whole point of the report — proving we DROVE the traffic,
    not just that traffic happened (the one thing a salon's free Google Business
    Profile can't show). When we sent at least one visitor from within Miami
    Knows Beauty this period, we say so plainly: "Miami Knows Beauty sent you N
    of those visitors." Returns "" when the count is zero so a month whose
    visitors all came from Google or a typed URL never reads "we sent you 0".
    The phrase reads correctly for any count (1 or many), so no plural branch is
    needed.
    """
    n = report.mkb_referred_views_this_month
    if n <= 0:
        return ""
    # WHY "of those" ties the number back to the visitor count in the lead
    # sentence — it's a subset, not a separate metric.
    return f"Miami Knows Beauty sent you {n} of those visitors."


def _lead_sentence(report: MonthlyReport) -> str:
    """The friendly one-liner under the headline, chosen by trend.

    WHY a function (not a flat constant): the sentence changes shape with the
    numbers — up vs. first vs. normal — and pluralises "person/people" and
    "view/views" so the copy never reads "1 people viewed". Founder-facing
    wording still lives here in obvious string literals.
    """
    month = report.period_label.split()[0]  # "June 2026" -> "June"
    views = report.views_this_month
    msgs = report.messages_this_month
    person = "person" if views == 1 else "people"
    # WHY: "have viewed" reads better than "viewed" for a zero count ("0 people
    # have viewed"); a non-zero count uses the simple past ("12 people viewed").
    viewed = "viewed" if views != 0 else "have viewed"
    # WHY: "X reached out" reads correctly for any count (1 or many), so no
    # plural branch is needed for the verb itself.
    reached = "reached out"

    # WHY: when shoppers took high-intent actions this period, append a sentence
    # naming them — a tap to call is far stronger proof the listing works than a
    # view. Empty string when there were none, so it adds nothing on a quiet month.
    action = _action_phrase(report)
    action_tail = f" Of those, {action}." if action else ""

    # WHY: the MKB-referral credit comes LAST in the sentence — after the view
    # count and any taps — because it's the line that answers "did the directory
    # actually do anything for me?". Empty when we sent no one, so it never
    # reads "we sent you 0". This is what makes the report worth keeping vs. the
    # salon's free Google Business Profile.
    mkb = _mkb_referral_phrase(report)
    mkb_tail = f" {mkb}" if mkb else ""

    if report.is_first_report:
        # Lifetime framing — we don't have a month delta yet.
        return (
            f"So far, {views} {person} {viewed} your <strong>{html.escape(report.business_name)}</strong> "
            f"listing, and {msgs} {reached}.{action_tail}{mkb_tail}"
        )
    if report.trend == "up" and report.views_last_month is not None:
        return (
            f"In {month}, {views} {person} {viewed} your "
            f"<strong>{html.escape(report.business_name)}</strong> listing — "
            f"up from {report.views_last_month} last month. {msgs} {reached}.{action_tail}{mkb_tail}"
        )
    return (
        f"In {month}, {views} {person} {viewed} your "
        f"<strong>{html.escape(report.business_name)}</strong> listing, "
        f"and {msgs} {reached}.{action_tail}{mkb_tail}"
    )


def _headline(report: MonthlyReport) -> str:
    """Pick the founder-owned headline for this report's situation."""
    if report.is_first_report:
        return HEADLINE_FIRST
    if report.is_thin_views:
        return HEADLINE_THIN
    if report.trend == "up":
        return HEADLINE_TREND_UP
    return HEADLINE_NORMAL


def build_subject(report: MonthlyReport) -> str:
    """Render the email subject line from the founder-owned template."""
    month = report.period_label.split()[0]
    return SUBJECT_TEMPLATE.format(name=report.business_name, month=month)


def _text_body(report: MonthlyReport, caption: Optional[str]) -> str:
    """Plain-text fallback body — every HTML email needs one for deliverability."""
    month = report.period_label.split()[0]
    # WHY: same non-zero taps mention as the HTML body, plain-text form. Empty
    # when no taps occurred, so a quiet month's text body is unchanged.
    action = _action_phrase(report)
    action_tail = f" Of those, {action}." if action else ""
    # WHY: same MKB-referral credit as the HTML body, plain-text form — empty
    # when we sent no one, so a quiet month's text body is unchanged.
    mkb = _mkb_referral_phrase(report)
    mkb_tail = f" {mkb}" if mkb else ""
    lines = [f"Hi,", ""]
    if report.is_first_report:
        person = "person" if report.views_this_month == 1 else "people"
        lines.append(
            f"So far, {report.views_this_month} {person} have viewed your "
            f"{report.business_name} listing, and {report.messages_this_month} reached out.{action_tail}{mkb_tail}"
        )
    elif report.trend == "up" and report.views_last_month is not None:
        person = "person" if report.views_this_month == 1 else "people"
        lines.append(
            f"In {month}, {report.views_this_month} {person} viewed your "
            f"{report.business_name} listing — up from {report.views_last_month} last month. "
            f"{report.messages_this_month} reached out.{action_tail}{mkb_tail}"
        )
    else:
        person = "person" if report.views_this_month == 1 else "people"
        lines.append(
            f"In {month}, {report.views_this_month} {person} viewed your "
            f"{report.business_name} listing, and {report.messages_this_month} reached out.{action_tail}{mkb_tail}"
        )
    lines.append("")
    if caption:
        lines.append("Want more eyes on your listing? Here's a ready-to-post caption for next month:")
        lines.append("")
        lines.append(caption)
        lines.append("")
    lines.append(f"See your full dashboard: {_dashboard_url()}")
    lines.append("")
    lines.append("— The Miami Knows Beauty team")
    lines.append("")
    return "\n".join(lines)


def _caption_block_html(caption: str) -> str:
    """The ready-to-post caption card shown when views are thin.

    WHY escape + <br>: the caption is model-generated text; escape first so
    any stray angle brackets can't inject markup, then turn newlines into <br>
    so the hashtags/emoji line breaks survive in the email.
    """
    safe = html.escape(caption).replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    return f"""
    <div style="background: linear-gradient(135deg, #fff1f2 0%, #fdf4ff 100%);
                border: 1.5px solid #f9a8d4; border-radius: 12px; padding: 20px 22px;
                margin: 0 0 24px;">
      <p style="font-size: 13px; font-weight: 700; color: #1c1917; margin: 0 0 10px;">
        📲 Ready to post — a caption to bring more visitors next month
      </p>
      <div style="font-size: 14px; color: #1c1917; line-height: 1.7; white-space: pre-wrap;
                  background: #ffffff; border-radius: 8px; padding: 14px 16px;">{safe}</div>
    </div>"""


def render_monthly_email(report: MonthlyReport, caption: Optional[str] = None) -> tuple[str, str, str]:
    """Render the monthly email. Returns (subject, html_body, text_body).

    Pure function — touches no database and sends nothing. ``caption`` is the
    optional ready-to-post caption; pass it when ``report.is_thin_views`` so
    the email leans on a growth nudge instead of dwelling on a small number.
    """
    subject = build_subject(report)
    headline = _headline(report)
    lead = _lead_sentence(report)
    text_body = _text_body(report, caption)

    safe_name = html.escape(report.business_name)
    caption_html = _caption_block_html(caption) if caption else ""

    # WHY: a small stat strip is shown for non-thin months (the numbers are
    # worth showing). For thin months the lead sentence still mentions the
    # number once, but the visual emphasis shifts to the caption card above.
    if report.is_thin_views and not report.is_first_report:
        stat_strip = ""
    else:
        msgs = report.messages_this_month
        stat_strip = f"""
    <table style="width: 100%; border-collapse: collapse; margin: 0 0 24px;">
      <tr>
        <td style="width: 50%; padding: 16px; background: #fdf2f8; border-radius: 12px 0 0 12px;
                   text-align: center;">
          <div style="font-family: Georgia, serif; font-size: 34px; font-weight: 700; color: #be185d;">
            {report.views_this_month}
          </div>
          <div style="font-size: 12px; color: #78716c; text-transform: uppercase; letter-spacing: 0.08em;">
            {"views so far" if report.is_first_report else "views this month"}
          </div>
        </td>
        <td style="width: 50%; padding: 16px; background: #faf5ff; border-radius: 0 12px 12px 0;
                   text-align: center;">
          <div style="font-family: Georgia, serif; font-size: 34px; font-weight: 700; color: #9333ea;">
            {msgs}
          </div>
          <div style="font-size: 12px; color: #78716c; text-transform: uppercase; letter-spacing: 0.08em;">
            messages
          </div>
        </td>
      </tr>
    </table>"""

    html_body = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(subject)}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      {html.escape(headline)}
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      {lead}
    </p>
    {stat_strip}
    {caption_html}
    <a href="{html.escape(_dashboard_url())}"
       style="display: inline-block; background: #be185d; color: #ffffff; font-size: 15px;
              font-weight: 600; text-decoration: none; padding: 14px 28px; border-radius: 8px;
              margin: 0 0 24px;">
      See your full dashboard →
    </a>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      You're getting this because you have a Featured listing on Miami Knows Beauty.
      Reply to this email any time — a real person reads it.
    </p>
  </div>
</body></html>"""

    return subject, html_body, text_body


async def send_test_monthly_email(
    *, to: str, report: MonthlyReport, caption: Optional[str] = None
) -> bool:
    """Send ONE test copy of the monthly email to an explicit TEST address.

    SAFETY: this is the ONLY function in the codebase that sends a monthly
    report email, and it sends to exactly the one address the caller passes —
    never to a list of owners, never derived from the business document. It is
    gated by ``test_send_enabled()`` (a flag OFF by default) on top of the
    admin-key gate on its route.

    Returns True if Resend accepted the message (or it was logged in dev mode),
    False on provider error or when the flag is off.
    """
    if not test_send_enabled():
        # WHY: belt-and-suspenders. The route also checks the flag, but a
        # future caller of this function gets the same protection for free.
        logger.warning(
            "%s is not enabled — refusing to send test monthly email to %s.",
            TEST_SEND_FLAG,
            to,
        )
        return False

    subject, html_body, text_body = render_monthly_email(report, caption)

    api_key = _provider_api_key()
    if not api_key:
        # Development fallback — log instead of send so a local dev can exercise
        # the path without a mail provider. The warning reminds the operator
        # production needs real credentials.
        logger.warning(
            "RESEND_API_KEY not configured — test monthly email logged instead of sent to %s.",
            to,
        )
        logger.info("TEST MONTHLY EMAIL to %s | subject=%s", to, subject)
        return True

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": _from_address(),
                    "reply_to": _owner_reply_to(),
                    "to": to,
                    "subject": f"[TEST] {subject}",
                    "html": html_body,
                    "text": text_body,
                },
            )
        if response.status_code == 200:
            logger.info("Test monthly email sent to %s", to)
            return True
        logger.error(
            "Email provider returned status %s when sending test monthly email",
            response.status_code,
        )
        return False
    except Exception as exc:  # noqa: BLE001 — provider errors are swallowed, same as owner_email
        logger.error("Failed to send test monthly email: %s", type(exc).__name__)
        return False
