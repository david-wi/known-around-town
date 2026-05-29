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

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# WHY: 30 seconds is the same timeout Expertly Identity uses for Resend.
# Long enough for typical provider latency, short enough that a stuck
# call doesn't pin a worker.
_PROVIDER_TIMEOUT_SECONDS = 30.0


def _from_address() -> str:
    name = os.environ.get("OWNER_EMAIL_FROM_NAME", "Knows Beauty").strip()
    addr = os.environ.get("OWNER_EMAIL_FROM_ADDRESS", "noreply@knowsbeauty.ai.devintensive.com").strip()
    return f"{name} <{addr}>"


def _provider_api_key() -> Optional[str]:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    return key or None


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
