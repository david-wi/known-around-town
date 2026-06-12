"""Preview login gate — service-layer primitives.

Restricts the site to a known list of internal users before public launch.
All security-sensitive logic lives here so it can be unit-tested in isolation.

Design mirrors the existing owner_auth module:
- 6-digit numeric code stored hashed (SHA-256), expires after 15 minutes
- Random 32-byte hex token stored hashed in preview_sessions, 30-day lifetime
- No cleartext secrets ever written to the database

Cookie name:  preview_token
Gate control: PREVIEW_MODE_ENABLED env var — set to "false" (or leave unset)
              to disable the gate entirely when the site goes public.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


# WHY: allowed domains and explicit email addresses for the private preview.
# Any email at these domains gets in; specific personal accounts are listed
# individually so we don't have to create a domain-wide rule for Gmail.
ALLOWED_DOMAINS = frozenset({"expertly.com", "webintensive.com"})
ALLOWED_EMAILS = frozenset(
    {
        "aggiewaggie06@gmail.com",
        "karissa.ostoski@gmail.com",
        "david@bodnick.com",
        "david@wisdev.com",
    }
)

# WHY: 6 numeric digits gives 1,000,000 combinations in a 15-minute window.
# Numeric-only is intentional — easier to type on a phone than mixed-case,
# and the short lifetime makes brute-force infeasible even with the reduced
# alphabet.
CODE_LENGTH = 6

# WHY: 15 minutes mirrors the owner magic-code lifetime — long enough to
# switch browser tabs, short enough to limit replay on intercepted email.
CODE_TTL_SECONDS = 60 * 15  # 900 seconds

# WHY: 30 days matches the owner session lifetime. An active internal user
# should not have to re-authenticate daily.
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 2,592,000 seconds

# Cookie name — distinct from kb_owner_session so they coexist without
# confusion in DevTools.
PREVIEW_COOKIE_NAME = "preview_token"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_allowed_email(email: str) -> bool:
    """Return True if the email is permitted to access the preview.

    WHY: check both the domain list and the explicit-email list so we can
    grant access to individual accounts (e.g., personal Gmail) without
    opening the gate to all of gmail.com.
    """
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return False
    _, domain = normalized.rsplit("@", 1)
    return domain in ALLOWED_DOMAINS or normalized in ALLOWED_EMAILS


def generate_code() -> str:
    """Return a fresh 6-digit numeric verification code."""
    # WHY: secrets.randbelow is cryptographically random. The modulo
    # produces a zero-padded decimal string ("047382") that is easy to
    # type but genuinely unpredictable.
    value = secrets.randbelow(10 ** CODE_LENGTH)
    return str(value).zfill(CODE_LENGTH)


def hash_value(value: str) -> str:
    """SHA-256 hex digest used for both codes and session tokens."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_equal(a: str, b: str) -> bool:
    """Constant-time string equality to prevent timing side channels."""
    return hmac.compare_digest(
        a.encode("utf-8"),
        b.encode("utf-8"),
    )


def generate_session_token() -> str:
    """Return a fresh 32-byte hex session token."""
    # WHY: 256 bits from the CSPRNG is overkill for an internal preview
    # gate but costs nothing. Using the same approach as prod auth keeps
    # the implementation consistent.
    return secrets.token_hex(32)


def code_expires_at() -> datetime:
    return _now() + timedelta(seconds=CODE_TTL_SECONDS)


def session_expires_at() -> datetime:
    return _now() + timedelta(seconds=SESSION_TTL_SECONDS)
