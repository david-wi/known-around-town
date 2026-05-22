"""Helpers for the owner-login flow.

The login route is intentionally thin — it deals only with HTTP shape
(request body, response, cookies). All the security-sensitive primitives —
generating codes, hashing codes, signing cookies, verifying cookies — live
in this module so they can be unit-tested in isolation and reviewed in
one place.

Design notes:

- The one-time code is a six-character draw from a 32-character alphabet
  with the visually ambiguous characters removed (no 0, O, 1, I). At
  ~10^9 combinations it is infeasible to brute-force within the
  15-minute window, and easy to read off a phone screen.
- Codes are never stored as cleartext. We persist sha256(code) so that
  read access to the database cannot impersonate the owner.
- Cookie payloads are signed with HMAC-SHA256 over a stdlib-only base64
  format so we do not pull in a new dependency for one cookie.
- All comparisons of secrets use hmac.compare_digest (constant-time) to
  remove timing-leak side channels.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional


# WHY: a 32-character alphabet with visually ambiguous characters
# removed (no 0/O, no 1/I). At 32^6 ~= 1.07 billion combinations a
# brute-force attempt has a vanishing chance of guessing the code
# inside the 15-minute window, and the code is still easy to read
# off a screen and type into a form.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6

# WHY: 15 minutes is the same window most password-reset flows use.
# Short enough to limit replay if the email is intercepted, long
# enough that the owner has time to switch from their inbox back to
# the browser tab on the first try.
CODE_LIFETIME = timedelta(minutes=15)

# WHY: 30 days matches the "stay signed in for a month" pattern used
# by most consumer SaaS. We refresh the issued_at timestamp on every
# request the cookie is presented on, so an active owner never has
# to sign in again unless they go dark for a full month.
SESSION_LIFETIME = timedelta(days=30)

# WHY: per-email rate limit. Three codes in ten minutes is plenty for
# an owner who fat-fingered their email and tried again — and well
# below the rate at which a scraper could fish for live accounts.
RATE_LIMIT_MAX_CODES = 3
RATE_LIMIT_WINDOW = timedelta(minutes=10)

# WHY: five attempts on a single code before we lock the row. A real
# user with a typo gets several chances; a guesser sweeping the
# keyspace gets nowhere on a 32^6 alphabet.
MAX_VERIFY_ATTEMPTS = 5

# Cookie name and signing key.
# WHY: name is short, prefixed so it's clear in a cookie listing that
# this belongs to the "knows beauty" owner side, not the visitor side.
SESSION_COOKIE_NAME = "kb_owner_session"

# WHY: in development the signing key can come from an env var. In
# production it MUST be set explicitly — the warning at startup is the
# operator's reminder that without it cookies cannot survive a restart.
_SESSION_SECRET_ENV = "OWNER_SESSION_SECRET"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- code generation and hashing ----------

def generate_code() -> str:
    """Return a fresh six-character verification code."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def hash_code(code: str) -> str:
    """SHA-256 hex digest of a code (case-folded to upper).

    Hashing is intentional: we want a fast, deterministic lookup token
    so verification stays cheap. The code itself carries enough entropy
    from secrets.choice — this is not a password, so we do not need a
    slow KDF.
    """
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def codes_match(submitted: str, expected_hash: str) -> bool:
    """Constant-time comparison of sha256(submitted) against the stored hash."""
    return hmac.compare_digest(hash_code(submitted), expected_hash)


def code_expires_at(start: Optional[datetime] = None) -> datetime:
    return (start or _now()) + CODE_LIFETIME


# ---------- session cookie signing ----------

def _signing_key() -> bytes:
    """The HMAC key used to sign session cookies.

    Reads from the OWNER_SESSION_SECRET environment variable. If the
    variable is not set we fall back to a freshly generated random key
    held in memory for the lifetime of the process — that way local
    development still works without manual setup, but a server restart
    invalidates every existing session (which is the correct behavior
    when a production operator has not configured a stable key).
    """
    env_value = os.environ.get(_SESSION_SECRET_ENV, "").strip()
    if env_value:
        return env_value.encode("utf-8")
    # Process-lifetime fallback. Cached on the function via attribute so
    # repeated calls return the same key within a single process.
    cached = getattr(_signing_key, "_fallback", None)
    if cached is None:
        cached = secrets.token_bytes(32)
        _signing_key._fallback = cached
    return cached


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_session(email: str, issued_at: Optional[datetime] = None) -> str:
    """Pack and sign a session cookie payload.

    The wire format is `<payload>.<signature>` where `payload` is a
    base64url-encoded JSON object holding the owner's email and the
    issue timestamp. The signature is HMAC-SHA256 of the payload using
    the server signing key.
    """
    issued = issued_at or _now()
    body = {
        "email": email.lower(),
        "issued_at": issued.isoformat(),
    }
    payload = _b64encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_b64encode(signature)}"


def verify_session(cookie_value: str) -> Optional[dict]:
    """Verify a signed cookie and return the payload dict, or None.

    Returns None if the cookie is malformed, the signature does not
    match, or the cookie is older than SESSION_LIFETIME. The 30-day
    age check is enforced here so a leaked cookie eventually self-revokes
    even if the operator never rotates the signing key.
    """
    if not cookie_value or "." not in cookie_value:
        return None
    payload, sig = cookie_value.rsplit(".", 1)
    expected = hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64decode(sig)
    except Exception:
        return None
    if not hmac.compare_digest(expected, provided):
        return None
    try:
        body = json.loads(_b64decode(payload))
    except Exception:
        return None
    email = body.get("email")
    issued_iso = body.get("issued_at")
    if not isinstance(email, str) or not isinstance(issued_iso, str):
        return None
    try:
        issued = datetime.fromisoformat(issued_iso)
    except ValueError:
        return None
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    if _now() - issued > SESSION_LIFETIME:
        return None
    return {"email": email, "issued_at": issued}


# ---------- email format validation ----------

# WHY: we don't pull in the email-validator package for one feature.
# This regex is the standard "looks like an email" check — it rejects
# obvious garbage (no @, no dot in the domain, control characters)
# without trying to be RFC 5321 perfect.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def looks_like_email(value: str) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    if len(value) > 320 or len(value) < 3:
        return False
    return bool(_EMAIL_RE.match(value))
