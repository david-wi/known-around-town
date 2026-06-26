"""Send the owner sign-in email.

This module is the only place that touches the email provider. It looks
for the same environment variables Expertly Identity uses (RESEND_API_KEY
plus a from-name/from-address pair), and falls back to logging the code
when those are not present. In development that fallback is what lets a
local laptop run the flow end-to-end without configuring a real mail
provider; in production the absence of credentials means codes will
silently never reach owners, so the operator MUST configure them before
this feature is announced.
"""

from __future__ import annotations

import html
import logging
import os
import urllib.parse
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# WHY: 30 seconds is the same timeout Expertly Identity uses for Resend.
# Long enough for typical provider latency, short enough that a stuck
# call doesn't pin a worker.
_PROVIDER_TIMEOUT_SECONDS = 30.0


def _from_address() -> str:
    name = os.environ.get("OWNER_EMAIL_FROM_NAME", "Knows Beauty").strip()
    addr = os.environ.get("OWNER_EMAIL_FROM_ADDRESS", "noreply@knowsbeauty.ai.devintensive.com").strip()
    return f"{name} <{addr}>"


def _owner_reply_to() -> str:
    # WHY: Reply-To lets owners reply directly to a monitored inbox
    # (hello@knowsbeauty.com) without requiring Resend domain verification for
    # the FROM address.  The FROM stays on expertly.com (already verified); the
    # Reply-To tells email clients to route replies to the knowsbeauty.com inbox.
    return os.environ.get("OWNER_EMAIL_REPLY_TO", "hello@knowsbeauty.com").strip()


def _provider_api_key() -> Optional[str]:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    return key or None


def _admin_notify_address() -> str:
    # WHY: ADMIN_NOTIFY_EMAIL lets the operator route claim alerts to a
    # dedicated admin inbox without a code change.  Falls back to the
    # configurable support_email setting so both use the same monitored
    # address by default rather than a separate hardcoded value.
    return os.environ.get("ADMIN_NOTIFY_EMAIL", get_settings().support_email).strip()


async def send_admin_new_claim_email(
    *, submitter_name: str, submitter_email: str, business_name: str, admin_url: str
) -> bool:
    """Alert the admin team when a new ownership claim is submitted.

    WHY: without this David has to check the admin panel daily to notice new
    claims — if he misses a day the "within one business day" promise breaks
    and the owner assumes they were ignored.  This makes claims zero-latency.
    """
    recipient = _admin_notify_address()
    subject = f"New claim: {business_name}"
    text_body = (
        f"A new ownership claim was submitted on Miami Knows Beauty.\n\n"
        f"Business: {business_name}\n"
        f"Submitted by: {submitter_name} <{submitter_email}>\n\n"
        f"Review and approve or reject at:\n{admin_url}\n\n"
        "— Miami Knows Beauty notifications\n"
    )
    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty · Admin
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      New claim submitted
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 8px;">
      <strong>{business_name}</strong>
    </p>
    <p style="font-size: 14px; color: #78716c; margin: 0 0 24px;">
      Submitted by {submitter_name}
      &lt;<a href="mailto:{submitter_email}" style="color: #be185d;">{submitter_email}</a>&gt;
    </p>
    <a href="{admin_url}"
       style="display: inline-block; background: #be185d; color: #ffffff; font-size: 14px;
              font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 8px;">
      Review claim →
    </a>
  </div>
</body></html>"""

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — admin claim alert logged instead of emailed "
            "for %s (%s).",
            business_name,
            submitter_email,
        )
        return True

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": _from_address(),
                    "to": [recipient],
                    "subject": subject,
                    "text": text_body,
                    "html": html_body,
                },
            )
            resp.raise_for_status()
            return True
    except Exception:
        logger.exception(
            "Failed to send admin new-claim alert for %s (%s).",
            business_name,
            submitter_email,
        )
        return False


async def send_claim_confirmation_email(
    *, email: str, submitter_name: str, business_name: str
) -> bool:
    """Send an immediate confirmation to an owner who just submitted a claim.

    WHY: the claim form promises "We'll email you within one business day" but
    without this call nothing was actually sent — owners would wait, assume the
    form broke, and not follow up.  Sending instantly removes that doubt and
    sets a clear expectation for the manual review step.

    Returns True if accepted by the provider or logged in dev mode; False on
    provider error.  Callers treat False as a no-op so a delivery failure does
    not surface as an API error.
    """
    subject = f"We received your claim for {business_name}"
    text_body = _claim_confirmation_text(submitter_name, business_name)
    html_body = _claim_confirmation_html(submitter_name, business_name)

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — claim confirmation logged instead of emailed "
            "for %s (%s).",
            email,
            business_name,
        )
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
                    "to": email,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if response.status_code == 200:
            logger.info("Claim confirmation sent to %s for %s", email, business_name)
            return True
        logger.error(
            "Email provider returned status %s for claim confirmation",
            response.status_code,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send claim confirmation email: %s", type(exc).__name__)
        return False


async def send_owner_code_email(*, email: str, code: str) -> bool:
    """Send the verification code to the owner.

    Returns True if the message was either accepted by the provider or
    intentionally logged in development mode; False if a real send was
    attempted but failed. The caller treats False as a no-op rather than
    a hard error — a delivery failure should look identical to a wrong
    email address from the owner's perspective, so we do not let it
    leak through the API response.
    """
    subject = f"Your Knows Beauty code: {code}"
    text_body = _text_body(code)
    html_body = _html_body(code)

    api_key = _provider_api_key()
    if not api_key:
        # Development fallback — codes go to the log so a local dev can
        # complete the flow without configuring a mail provider. The
        # warning is the operator's reminder that production needs real
        # credentials.
        logger.warning(
            "RESEND_API_KEY not configured — owner code logged instead of emailed. "
            "Set RESEND_API_KEY in the environment before announcing this feature."
        )
        logger.info("OWNER LOGIN CODE for %s: %s", email, code)
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
                    "to": email,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if response.status_code == 200:
            logger.info("Owner login code sent to %s", email)
            return True
        # WHY: we deliberately do NOT log the response body — it can echo
        # the recipient address and we want operational logs free of PII.
        logger.error("Email provider returned status %s when sending owner code", response.status_code)
        return False
    except Exception as exc:  # noqa: BLE001 — provider errors are intentionally swallowed
        # Same reasoning as above: never let provider details escape to
        # callers; just log and return False.
        logger.error("Failed to send owner code email: %s", type(exc).__name__)
        return False


def _text_body(code: str) -> str:
    return (
        "Hi,\n\n"
        f"Here's the code to sign in to Knows Beauty: {code}\n\n"
        "It expires in 15 minutes. If you didn't ask to sign in, you can ignore this email.\n\n"
        "— The Knows Beauty team\n"
    )


def _html_body(code: str) -> str:
    # Plain inline-styled HTML — no external CSS, friendly on every mail
    # client, mirrors the Expertly Identity magic-code email template.
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      Your sign-in code
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Enter this code in the Knows Beauty sign-in screen to finish logging in.
    </p>
    <div style="font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 32px;
                letter-spacing: 12px; text-align: center; padding: 20px;
                background: #fdf2f8; border-radius: 12px; color: #1c1917;
                font-weight: 600; margin: 0 0 24px;">
      {code}
    </div>
    <p style="font-size: 13px; color: #78716c; margin: 0 0 8px;">
      The code expires in 15 minutes.
    </p>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      If you didn't ask to sign in, you can safely ignore this email.
    </p>
  </div>
</body></html>"""


async def send_claim_verified_email(
    *, email: str, submitter_name: str, business_name: str, login_url: str,
    site_base_url: str = "https://miami.knowsbeauty.com",
) -> bool:
    """Notify the owner that their claim has been verified and they can now log in.

    WHY: without this email the owner has no way to know their claim was
    approved — they submitted, got a confirmation, and then heard nothing.
    The only way in is to guess that they should go back to the site and
    try logging in.  This email closes the loop and gives them a direct
    link to the login page.
    """
    subject = f"Your listing for {business_name} is verified — log in now"
    pricing_url = site_base_url.rstrip("/") + "/pricing"
    text_body = _claim_verified_text(
        submitter_name, business_name, login_url, pricing_url
    )
    html_body = _claim_verified_html(
        submitter_name, business_name, login_url, pricing_url
    )

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — claim verified notification logged instead "
            "of emailed for %s (%s).",
            email,
            business_name,
        )
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
                    "to": email,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if response.status_code == 200:
            logger.info("Claim verified notification sent to %s for %s", email, business_name)
            return True
        logger.error(
            "Email provider returned status %s for claim verified notification",
            response.status_code,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send claim verified email: %s", type(exc).__name__)
        return False


def _claim_confirmation_text(submitter_name: str, business_name: str) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return (
        f"Hi {first},\n\n"
        f"We received your claim for {business_name} and will review it within one business day.\n\n"
        "Once verified, we'll email you a login link. Click it, request your 6-digit code, and you're in — no password to set.\n\n"
        f"Questions while you wait? Email {get_settings().support_email}.\n\n"
        "— The Miami Knows Beauty team\n"
    )


def _claim_verified_text(
    submitter_name: str, business_name: str, login_url: str, pricing_url: str,
) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return (
        f"Hi {first},\n\n"
        f"Great news — your claim for {business_name} has been verified.\n\n"
        f"Log in here — your email is already filled in. Click to request your 6-digit code and you're in:\n{login_url}\n\n"
        "Three things that take 5 minutes:\n"
        "1. Add a cover photo — listings with photos get far more clicks\n"
        "2. Set your hours — visitors decide whether to visit based on this\n"
        "3. Write two sentences about what makes your salon special\n\n"
        "─────────────────────────────────\n"
        "Stand out with Featured — $29/month\n"
        "• Priority placement at the top of every page\n"
        "• Verified Pro badge on your listing\n"
        "• AI Instagram caption generator (50/month)\n"
        f"See pricing and sign up: {pricing_url}\n"
        "─────────────────────────────────\n\n"
        f"Questions? Email {get_settings().support_email}.\n\n"
        "— The Miami Knows Beauty team\n"
    )


def _claim_verified_html(
    submitter_name: str, business_name: str, login_url: str, pricing_url: str,
) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      Your listing is verified
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Hi {first} — your claim for <strong>{business_name}</strong> has been approved.
      Your owner dashboard is ready.
    </p>
    <p style="font-size: 13px; color: #78716c; line-height: 1.5; margin: 0 0 20px;">
      Click the button below — your email is already filled in. Request your 6-digit code,
      enter it, and you're in. No password to set.
    </p>
    <a href="{login_url}"
       style="display: inline-block; background: #be185d; color: #ffffff; font-size: 15px;
              font-weight: 600; text-decoration: none; padding: 14px 28px;
              border-radius: 8px; margin: 0 0 24px;">
      Log in to your owner page →
    </a>
    <div style="background: #fafaf9; border: 1px solid #e7e5e4; border-radius: 12px;
                padding: 18px 20px; margin: 0 0 24px;">
      <p style="font-size: 13px; font-weight: 600; color: #292524; margin: 0 0 10px;">
        Three things that take 5 minutes:
      </p>
      <p style="font-size: 13px; color: #57534e; line-height: 1.5; margin: 0 0 7px;">
        📸 <strong>Add a cover photo</strong> — listings with photos get far more clicks than text-only ones
      </p>
      <p style="font-size: 13px; color: #57534e; line-height: 1.5; margin: 0 0 7px;">
        🕐 <strong>Set your hours</strong> — visitors decide whether to stop by based on this
      </p>
      <p style="font-size: 13px; color: #57534e; line-height: 1.5; margin: 0;">
        ✏️ <strong>Write two sentences</strong> about what makes your salon special
      </p>
    </div>
    <div style="background: linear-gradient(135deg, #fff1f2 0%, #fdf4ff 100%);
                border: 1.5px solid #f43f5e; border-radius: 12px; padding: 20px 22px;
                margin: 0 0 24px;">
      <p style="font-size: 15px; font-weight: 700; color: #1c1917; margin: 0 0 4px;">
        ⭐ Stand out with Featured — $29/month
      </p>
      <p style="font-size: 13px; color: #57534e; line-height: 1.6; margin: 0 0 14px;">
        Priority placement at the top of every page, a verified Pro badge, and our
        AI Instagram caption generator (50 captions/month).
      </p>
      <a href="{pricing_url}"
         style="display: inline-block; background: #f43f5e; color: #ffffff; font-size: 14px;
                font-weight: 600; text-decoration: none; padding: 11px 22px;
                border-radius: 7px;">
        Get Featured →
      </a>
    </div>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      Questions? Email <a href="mailto:{get_settings().support_email}" style="color: #be185d;">{get_settings().support_email}</a>.
    </p>
  </div>
</body></html>"""


async def send_claim_rejected_email(
    *, email: str, submitter_name: str, business_name: str
) -> bool:
    """Notify the submitter that their claim could not be verified.

    WHY: without this email the submitter has no idea what happened —
    they get the initial confirmation, wait, and then simply never hear
    back. No indication that the answer was no, no way to follow up or
    correct a mistake. This closes the loop on the rejection path the
    same way send_claim_verified_email closes the approval path.
    """
    subject = f"Update on your claim for {business_name}"
    text_body = _claim_rejected_text(submitter_name, business_name)
    html_body = _claim_rejected_html(submitter_name, business_name)

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — claim rejection notification logged instead "
            "of emailed for %s (%s).",
            email,
            business_name,
        )
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
                    "to": email,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if response.status_code == 200:
            logger.info("Claim rejection notification sent to %s for %s", email, business_name)
            return True
        logger.error(
            "Email provider returned status %s for claim rejection notification",
            response.status_code,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send claim rejection email: %s", type(exc).__name__)
        return False


def _claim_rejected_text(submitter_name: str, business_name: str) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return (
        f"Hi {first},\n\n"
        f"Thank you for claiming {business_name} on Miami Knows Beauty.\n\n"
        "After reviewing your submission we weren't able to verify the claim at this time. "
        "This sometimes happens when we can't confirm the connection between the submitter "
        "and the business — it doesn't necessarily mean your claim is wrong.\n\n"
        "If you think this is a mistake or want to provide more information, please email "
        f"{get_settings().support_email} and we'll take another look.\n\n"
        "— The Miami Knows Beauty team\n"
    )


def _claim_rejected_html(submitter_name: str, business_name: str) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      Update on your claim
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 16px;">
      Hi {first} — thank you for submitting a claim for <strong>{business_name}</strong>.
    </p>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 16px;">
      After reviewing your submission, we weren't able to verify the claim at this time.
      This sometimes happens when we can't confirm the connection between the submitter
      and the business — it doesn't necessarily mean your claim is incorrect.
    </p>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      If you believe this is a mistake or can provide more information, we'd be happy to
      take another look.
    </p>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      Email us at <a href="mailto:{get_settings().support_email}" style="color: #be185d;">{get_settings().support_email}</a>
      and we'll review it together.
    </p>
  </div>
</body></html>"""


def _claim_confirmation_html(submitter_name: str, business_name: str) -> str:
    first = submitter_name.split()[0] if submitter_name else "there"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 16px; color: #1c1917;">
      We received your claim
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Hi {first} — we'll review your claim for <strong>{business_name}</strong>
      within one business day.
    </p>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Once verified, we'll email you a login link. Click it, request your 6-digit code, and you're in — no password to set.
    </p>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      Questions while you wait?
      Email <a href="mailto:{get_settings().support_email}" style="color: #be185d;">{get_settings().support_email}</a>.
    </p>
  </div>
</body></html>"""


# ---------------------------------------------------------------------------
# Subscription confirmation — sent when an owner's Pro upgrade goes through
# ---------------------------------------------------------------------------

async def send_subscription_confirmed_email(
    *,
    email: str,
    business_name: str,
    dashboard_url: str,
) -> bool:
    """Congratulate the owner after a successful Pro subscription payment.

    WHY: without this, an owner pays on Stripe, gets redirected back to the
    dashboard, and hears nothing in their inbox.  That's a trust gap — a
    'welcome aboard' email confirms the charge was legitimate and tells them
    exactly what they just unlocked.  Fire-and-forget from the webhook so
    a slow email provider never delays the Stripe 200 response.
    """
    subject = f"Welcome to Featured — {business_name} is now a Pro listing"
    first = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    text_body = _subscription_confirmed_text(first, business_name, dashboard_url)
    html_body = _subscription_confirmed_html(first, business_name, dashboard_url)

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — subscription confirmation logged instead "
            "of emailed for %s (%s).",
            email,
            business_name,
        )
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
                    "to": email,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        response.raise_for_status()
        logger.info("Subscription confirmation sent to %s for %s", email, business_name)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send subscription confirmed email: %s", type(exc).__name__)
        return False


def _subscription_confirmed_text(first: str, business_name: str, dashboard_url: str) -> str:
    return (
        f"Hi {first},\n\n"
        f"You're in — {business_name} is now a Featured Pro listing on Miami Knows Beauty.\n\n"
        "What just unlocked:\n"
        "• Featured placement — your listing appears at the top of category and neighborhood pages\n"
        "• Pro badge — signals quality and helps visitors choose you over unverified listings\n"
        "• Instagram caption generator — describe your post, get a polished caption with hashtags\n"
        "• Google, Facebook, and Instagram ad copy — describe what you're promoting, get 3 ready-to-run ad variations\n\n"
        f"Head to your dashboard to see your listing and start using these features:\n{dashboard_url}\n\n"
        f"Questions? Email {get_settings().support_email} and we'll get back to you same day.\n\n"
        "— The Miami Knows Beauty team\n"
    )


def _subscription_confirmed_html(first: str, business_name: str, dashboard_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 28px; line-height: 1.2; margin: 0 0 8px; color: #1c1917;">
      You&rsquo;re now Featured
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Hi {first} — <strong>{business_name}</strong> has been upgraded to a Pro Featured listing.
      Here&rsquo;s what just unlocked:
    </p>
    <ul style="padding: 0; margin: 0 0 24px; list-style: none;">
      <li style="padding: 8px 0; border-bottom: 1px solid #f5f0eb; font-size: 14px; color: #1c1917;">
        <span style="color: #be185d; font-weight: 700;">&#10003;</span>&nbsp;
        <strong>Featured placement</strong> &mdash; top of category and neighborhood pages
      </li>
      <li style="padding: 8px 0; border-bottom: 1px solid #f5f0eb; font-size: 14px; color: #1c1917;">
        <span style="color: #be185d; font-weight: 700;">&#10003;</span>&nbsp;
        <strong>Pro badge</strong> &mdash; instantly recognisable mark of quality
      </li>
      <li style="padding: 8px 0; border-bottom: 1px solid #f5f0eb; font-size: 14px; color: #1c1917;">
        <span style="color: #be185d; font-weight: 700;">&#10003;</span>&nbsp;
        <strong>Instagram caption generator</strong> &mdash; polished captions in seconds
      </li>
      <li style="padding: 8px 0; font-size: 14px; color: #1c1917;">
        <span style="color: #be185d; font-weight: 700;">&#10003;</span>&nbsp;
        <strong>Google, Facebook, and Instagram ad copy</strong> &mdash; 3 ready-to-run variations per campaign
      </li>
    </ul>
    <a href="{dashboard_url}"
       style="display: inline-block; background: #be185d; color: #ffffff; font-size: 15px;
              font-weight: 600; text-decoration: none; padding: 14px 28px; border-radius: 8px;
              margin-bottom: 24px;">
      Go to your dashboard &rarr;
    </a>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      Questions? Email
      <a href="mailto:{get_settings().support_email}" style="color: #be185d;">{get_settings().support_email}</a>
      &mdash; we reply same day.
    </p>
  </div>
</body></html>"""


# ---------------------------------------------------------------------------
# Inquiry notifications — sent when a visitor contacts a business listing
# ---------------------------------------------------------------------------

async def send_owner_inquiry_email(
    *,
    owner_email: str,
    business_name: str,
    visitor_name: str,
    visitor_email: Optional[str],
    visitor_phone: Optional[str],
    message: str,
    dashboard_url: str,
) -> bool:
    """Notify a claimed-business owner that a visitor has sent them a message.

    WHY: the owner dashboard shows all inquiries, but only if the owner
    actively logs in. Without this email the owner may never see a hot lead.
    Setting Reply-To lets the owner reply directly from their email client —
    removing all friction from following up with the visitor.
    """
    subject = f"New message for {business_name} on Miami Knows Beauty"
    text_body = _inquiry_owner_text(
        business_name, visitor_name, visitor_email, visitor_phone, message, dashboard_url
    )
    html_body = _inquiry_owner_html(
        business_name, visitor_name, visitor_email, visitor_phone, message, dashboard_url
    )

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — inquiry notification logged instead of emailed "
            "for %s (owner %s).",
            business_name,
            owner_email,
        )
        return True

    payload: dict = {
        "from": _from_address(),
        "to": [owner_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    # WHY: Reply-To lets the owner reply from their email client directly
    # to the visitor without opening the dashboard — reduces friction for
    # a time-sensitive response window.
    if visitor_email:
        payload["reply_to"] = visitor_email

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            logger.info(
                "Inquiry notification sent to owner %s for %s", owner_email, business_name
            )
            return True
    except Exception:
        logger.exception(
            "Failed to send inquiry notification to owner %s for %s",
            owner_email,
            business_name,
        )
        return False


async def send_admin_inquiry_email(
    *,
    business_name: str,
    business_id: str,
    visitor_name: str,
    visitor_email: Optional[str],
    visitor_phone: Optional[str],
    message: str,
) -> bool:
    """Alert admin when a visitor messages an unclaimed business.

    WHY: an unclaimed business getting inquiries is strong evidence the owner
    would benefit from claiming it. Alerting admin immediately lets us follow
    up with the owner while the lead is fresh, and ensures the visitor message
    isn't silently dropped.
    """
    recipient = _admin_notify_address()
    subject = f"Inquiry for unclaimed listing: {business_name}"
    safe_name = html.escape(visitor_name)
    safe_email = html.escape(visitor_email or "")
    safe_phone = html.escape(visitor_phone or "")
    safe_msg = html.escape(message)

    text_body = (
        f"A visitor sent a message to {business_name} — this listing is unclaimed.\n\n"
        f"Visitor: {visitor_name}\n"
        + (f"Email: {visitor_email}\n" if visitor_email else "")
        + (f"Phone: {visitor_phone}\n" if visitor_phone else "")
        + f"\nMessage:\n{message}\n\n"
        f"Business ID: {business_id}\n\n"
        "Consider reaching out to this salon to encourage them to claim their listing.\n\n"
        "— Miami Knows Beauty notifications\n"
    )
    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty · Admin
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 26px; line-height: 1.2; margin: 0 0 8px; color: #1c1917;">
      Inquiry for unclaimed listing
    </h1>
    <p style="font-size: 15px; color: #78716c; margin: 0 0 24px;">
      <strong style="color: #1c1917;">{html.escape(business_name)}</strong> has not been claimed yet.
    </p>
    <table style="width: 100%; border-collapse: collapse; margin: 0 0 20px; font-size: 14px;">
      <tr><td style="padding: 6px 0; color: #78716c; width: 80px;">From</td>
          <td style="padding: 6px 0; color: #1c1917;">{safe_name}</td></tr>
      {"<tr><td style='padding: 6px 0; color: #78716c;'>Email</td>" +
       f"<td style='padding: 6px 0;'><a href='mailto:{safe_email}' style='color: #be185d;'>{safe_email}</a></td></tr>"
       if visitor_email else ""}
      {"<tr><td style='padding: 6px 0; color: #78716c;'>Phone</td>" +
       f"<td style='padding: 6px 0; color: #1c1917;'>{safe_phone}</td></tr>"
       if visitor_phone else ""}
    </table>
    <div style="background: #f8f5f2; border-radius: 8px; padding: 16px; margin: 0 0 24px;
                font-size: 14px; color: #1c1917; line-height: 1.7; white-space: pre-wrap;">{safe_msg}</div>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      Business ID: <code>{business_id}</code>
    </p>
  </div>
</body></html>"""

    api_key = _provider_api_key()
    if not api_key:
        logger.warning(
            "RESEND_API_KEY not configured — admin inquiry alert logged instead of emailed "
            "for unclaimed business %s.",
            business_name,
        )
        return True

    try:
        async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": _from_address(),
                    "to": [recipient],
                    "subject": subject,
                    "text": text_body,
                    "html": html_body,
                },
            )
            resp.raise_for_status()
            return True
    except Exception:
        logger.exception(
            "Failed to send admin inquiry alert for unclaimed business %s", business_name
        )
        return False


def _inquiry_owner_text(
    business_name: str,
    visitor_name: str,
    visitor_email: Optional[str],
    visitor_phone: Optional[str],
    message: str,
    dashboard_url: str,
) -> str:
    contact_lines = ""
    if visitor_email:
        contact_lines += f"Email: {visitor_email}\n"
    if visitor_phone:
        contact_lines += f"Phone: {visitor_phone}\n"
    return (
        f"Hi,\n\n"
        f"A visitor sent a message to {business_name} on Miami Knows Beauty.\n\n"
        f"From: {visitor_name}\n"
        + contact_lines
        + f"\nMessage:\n{message}\n\n"
        "You can reply directly to this email, or view the full message in your dashboard:\n"
        f"{dashboard_url}\n\n"
        "— Miami Knows Beauty\n"
    )


def _inquiry_owner_html(
    business_name: str,
    visitor_name: str,
    visitor_email: Optional[str],
    visitor_phone: Optional[str],
    message: str,
    dashboard_url: str,
) -> str:
    safe_business = html.escape(business_name)
    safe_name = html.escape(visitor_name)
    safe_email = html.escape(visitor_email or "")
    safe_phone = html.escape(visitor_phone or "")
    # WHY: escape first, then replace newlines with <br> — reversing the order would
    # escape the injected tags. Handle \r\n (Windows), \r (old Mac), and \n (Unix).
    safe_msg = html.escape(message).replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    safe_dashboard_url = html.escape(dashboard_url)

    contact_rows = ""
    # WHY: pre-build the reply button outside the main f-string to avoid nested
    # f-string quoting issues. The mailto subject is URL-encoded so business
    # names with spaces or special chars don't break the URI.
    reply_button_html = ""
    if visitor_email:
        subject = urllib.parse.quote(f"Re: Your inquiry about {business_name}", safe="")
        # WHY: URL-encode email before HTML-escaping for href — safe="@" preserves
        # the required @ sign while encoding chars that would break the mailto URI
        # (e.g. + in user+tag@example.com would otherwise be treated as a space).
        safe_email_href = html.escape(urllib.parse.quote(visitor_email, safe="@"))
        reply_button_html = (
            f'<a href="mailto:{safe_email_href}?subject={subject}"'
            f' style="display: inline-block; background: #be185d; color: #ffffff; font-size: 14px;'
            f' font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 8px;'
            f' margin-right: 12px;">'
            f"Reply to {safe_name} &rarr;"
            f"</a>"
        )
        contact_rows += (
            f"<tr><td style='padding: 6px 0; color: #78716c; width: 80px;'>Email</td>"
            f"<td style='padding: 6px 0;'>"
            f"<a href='mailto:{safe_email_href}' style='color: #be185d;'>{safe_email}</a>"
            f"</td></tr>"
        )
    if visitor_phone:
        contact_rows += (
            f"<tr><td style='padding: 6px 0; color: #78716c;'>Phone</td>"
            f"<td style='padding: 6px 0; color: #1c1917;'>{safe_phone}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>New inquiry for {safe_business}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
              background: #f8f5f2; padding: 32px; color: #1c1917;">
  <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px;
              padding: 40px 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <p style="font-size: 11px; letter-spacing: 0.3em; color: #be185d; font-weight: 600;
              text-transform: uppercase; margin: 0 0 16px;">
      Miami Knows Beauty
    </p>
    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-weight: 300;
               font-size: 26px; line-height: 1.2; margin: 0 0 8px; color: #1c1917;">
      New message for {safe_business}
    </h1>
    <p style="font-size: 14px; color: #78716c; margin: 0 0 24px;">
      A visitor sent you a message through the directory.
    </p>
    <table style="width: 100%; border-collapse: collapse; margin: 0 0 20px; font-size: 14px;">
      <tr><td style="padding: 6px 0; color: #78716c; width: 80px;">From</td>
          <td style="padding: 6px 0; color: #1c1917;"><strong>{safe_name}</strong></td></tr>
      {contact_rows}
    </table>
    <div style="background: #f8f5f2; border-radius: 8px; padding: 16px; margin: 0 0 24px;
                font-size: 15px; color: #1c1917; line-height: 1.7;">{safe_msg}</div>
    <div>
      {reply_button_html}<a href="{safe_dashboard_url}"
         style="display: inline-block; background: #ffffff; color: #1c1917; font-size: 14px;
                font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 8px;
                border: 1.5px solid #e7e5e4;">
        View in dashboard &rarr;
      </a>
    </div>
  </div>
</body></html>"""
