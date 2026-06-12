"""Send the preview-gate verification code via Resend.

Reuses the same Resend API key and from-address pattern as owner_email.py.
Falls back to logging the code when RESEND_API_KEY is absent so local
development works without a mail provider configured.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# WHY: 30 seconds matches the owner_email module timeout — enough for typical
# Resend latency, short enough not to pin a worker on a stuck call.
_PROVIDER_TIMEOUT_SECONDS = 30.0


def _from_address() -> str:
    name = os.environ.get("OWNER_EMAIL_FROM_NAME", "Knows Beauty").strip()
    addr = os.environ.get(
        "OWNER_EMAIL_FROM_ADDRESS",
        "noreply@knowsbeauty.ai.devintensive.com",
    ).strip()
    return f"{name} <{addr}>"


def _provider_api_key() -> Optional[str]:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    return key or None


async def send_preview_code_email(*, email: str, code: str) -> bool:
    """Send the preview-access verification code to the supplied address.

    Returns True if the message was accepted by Resend or intentionally
    logged in development mode. Returns False on provider error. Callers
    treat False as a no-op — a delivery failure is silent so disallowed
    addresses cannot tell the difference from an allowed one that had a
    transient error.
    """
    subject = f"Your Miami Knows Beauty preview code: {code}"
    text_body = _text_body(code)
    html_body = _html_body(code)

    api_key = _provider_api_key()
    if not api_key:
        # Development fallback — code goes to the log. The warning
        # reminds the operator that production needs real credentials.
        logger.warning(
            "RESEND_API_KEY not configured — preview code logged instead of emailed."
        )
        logger.info("PREVIEW CODE for %s: %s", email, code)
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
            logger.info("Preview code sent to %s", email)
            return True
        # WHY: deliberately no response body in the log — it can echo
        # the recipient address and we keep operational logs PII-free.
        logger.error(
            "Email provider returned status %s when sending preview code",
            response.status_code,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send preview code email: %s", type(exc).__name__)
        return False


def _text_body(code: str) -> str:
    return (
        "Hi,\n\n"
        f"Here's your preview access code for Miami Knows Beauty: {code}\n\n"
        "It expires in 15 minutes.\n\n"
        "If you didn't request this, you can ignore this email.\n\n"
        "— The Miami Knows Beauty team\n"
    )


def _html_body(code: str) -> str:
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
      Your preview access code
    </h1>
    <p style="font-size: 15px; color: #57534e; line-height: 1.6; margin: 0 0 24px;">
      Enter this code on the Miami Knows Beauty preview page to access the site.
    </p>
    <div style="font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 40px;
                letter-spacing: 16px; text-align: center; padding: 20px;
                background: #fdf2f8; border-radius: 12px; color: #1c1917;
                font-weight: 600; margin: 0 0 24px;">
      {code}
    </div>
    <p style="font-size: 13px; color: #78716c; margin: 0 0 8px;">
      The code expires in 15 minutes.
    </p>
    <p style="font-size: 13px; color: #78716c; margin: 0;">
      If you didn't request this, you can safely ignore this email.
    </p>
  </div>
</body></html>"""
