"""Tests for the owner sign-in flow.

Three slices are covered:

  1. Cookie signing — `sign_session` / `verify_session` round-trip,
     plus tamper and stale-cookie rejection.

  2. Code-by-email API — request, verify, rate limit, expiry, replay,
     wrong-code attempt cap, and the logout cookie clear.

  3. Public pages — the sign-in form, the placeholder dashboard, and
     the redirect from one to the other based on whether a valid
     session cookie is present.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


# ---------- shared fixtures ----------

@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


# ---------- cookie signing ----------

def test_session_cookie_round_trip():
    from app.services.owner_auth import sign_session, verify_session

    cookie = sign_session("owner@example.com")
    out = verify_session(cookie)
    assert out is not None
    assert out["email"] == "owner@example.com"
    assert isinstance(out["issued_at"], datetime)


def test_session_cookie_rejects_tampered_payload():
    from app.services.owner_auth import sign_session, verify_session

    cookie = sign_session("owner@example.com")
    payload, sig = cookie.rsplit(".", 1)
    # WHY: change the first base64 character, not the last. The final
    # base64 character of a non-multiple-of-3 byte sequence has unused
    # padding bits that Python's decoder silently ignores, so flipping
    # it from 'A' to 'B' can produce the same decoded bytes ~25% of
    # the time. The first character has no padding bits — a one-char
    # change there always alters the decoded bytes and breaks the MAC.
    tampered = ("B" if payload[0] != "B" else "C") + payload[1:] + "." + sig
    assert verify_session(tampered) is None


def test_session_cookie_rejects_tampered_signature():
    from app.services.owner_auth import sign_session, verify_session

    cookie = sign_session("owner@example.com")
    payload, sig = cookie.rsplit(".", 1)
    # WHY: same padding-bit hazard as test_session_cookie_rejects_tampered_payload.
    # HMAC-SHA256 is 32 bytes → 43 base64url chars where the final char
    # encodes only 4 real bits + 2 zero padding bits.  Python decodes
    # 'A' and 'B' identically for that position, making the last-char
    # flip a no-op about 25% of runs.  Changing the first character is
    # always significant — all 6 bits are real HMAC data.
    tampered = payload + "." + ("B" if sig[0] != "B" else "C") + sig[1:]
    assert verify_session(tampered) is None


def test_session_cookie_rejects_missing_dot():
    from app.services.owner_auth import verify_session

    assert verify_session("") is None
    assert verify_session("nodothere") is None


def test_session_cookie_rejects_expired_issued_at():
    from app.services.owner_auth import SESSION_LIFETIME, sign_session, verify_session

    too_old = datetime.now(timezone.utc) - SESSION_LIFETIME - timedelta(minutes=1)
    cookie = sign_session("owner@example.com", issued_at=too_old)
    assert verify_session(cookie) is None


def test_session_cookie_uses_lowercase_email():
    """We normalize the email before signing so cookies for the same
    address always compare equal regardless of input casing."""
    from app.services.owner_auth import sign_session, verify_session

    out = verify_session(sign_session("Owner@Example.COM"))
    assert out is not None
    assert out["email"] == "owner@example.com"


# ---------- code-generation primitives ----------

def test_generate_code_shape_and_alphabet():
    from app.services.owner_auth import CODE_ALPHABET, CODE_LENGTH, generate_code

    for _ in range(50):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert all(ch in CODE_ALPHABET for ch in code)


def test_hash_and_match_are_case_insensitive_and_constant_time_safe():
    from app.services.owner_auth import codes_match, hash_code

    code = "AB23CD"
    h = hash_code(code)
    assert codes_match("ab23cd", h)
    assert codes_match("AB23CD", h)
    assert not codes_match("AB23CE", h)


# ---------- API: request a code ----------

def test_request_code_persists_hash_and_returns_ok(client, seeded_db):
    r = client.post("/api/v1/owner/login/request", json={"email": "owner@example.com"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    docs = asyncio.run(seeded_db.owner_magic_codes.find({"email": "owner@example.com"}).to_list(10))
    assert len(docs) == 1
    saved = docs[0]
    # We persist a hash, never the cleartext code.
    assert "code" not in saved
    assert isinstance(saved["code_hash"], str) and len(saved["code_hash"]) == 64
    assert saved["used_at"] is None
    assert saved["attempts"] == 0
    # Expiry is roughly 15 min in the future.
    exp = saved["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    delta = (exp - datetime.now(timezone.utc)).total_seconds()
    assert 14 * 60 < delta < 16 * 60


def test_request_code_rejects_obvious_garbage(client):
    r = client.post("/api/v1/owner/login/request", json={"email": "not-an-email"})
    assert r.status_code == 400


def test_request_code_lowercases_email(client, seeded_db):
    r = client.post(
        "/api/v1/owner/login/request",
        json={"email": "  OWNER@Example.COM  "},
    )
    assert r.status_code == 200
    docs = asyncio.run(seeded_db.owner_magic_codes.find({"email": "owner@example.com"}).to_list(10))
    assert len(docs) == 1


def test_request_code_rate_limit_blocks_fourth(client):
    payload = {"email": "rate@example.com"}
    for _ in range(3):
        r = client.post("/api/v1/owner/login/request", json=payload)
        assert r.status_code == 200, r.text
    r = client.post("/api/v1/owner/login/request", json=payload)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    # The body explains the situation in human terms.
    assert "Too many" in r.json()["detail"]


def test_rate_limit_does_not_carry_across_emails(client):
    for _ in range(3):
        assert client.post(
            "/api/v1/owner/login/request", json={"email": "alice@example.com"}
        ).status_code == 200
    # Different email — still under its own limit.
    assert client.post(
        "/api/v1/owner/login/request", json={"email": "bob@example.com"}
    ).status_code == 200


# ---------- API: verify a code ----------

def _peek_code_for(seeded_db, email: str) -> Dict[str, Any]:
    """Return the most recent stored code-row for `email`. We pluck the
    cleartext out of the log capture in tests that need it; tests that
    only need to assert "the hash exists" can use this directly."""
    docs = asyncio.run(
        seeded_db.owner_magic_codes.find({"email": email}).sort("created_at", -1).to_list(1)
    )
    assert docs, f"no code stored for {email}"
    return docs[0]


def _request_and_extract_code(client, caplog, email: str) -> str:
    """Use the dev-mode log fallback to retrieve the cleartext code.

    The route is configured (in dev / tests) to log the code via the
    `app.services.owner_email` module when no RESEND_API_KEY is set.
    We grep the captured log for the line and pull the code out.
    """
    caplog.clear()
    import logging
    with caplog.at_level(logging.INFO, logger="app.services.owner_email"):
        r = client.post("/api/v1/owner/login/request", json={"email": email})
        assert r.status_code == 200, r.text
    for rec in caplog.records:
        m = re.search(r"OWNER LOGIN CODE for \S+: (\S+)", rec.getMessage())
        if m:
            return m.group(1)
    raise AssertionError("did not capture login code from logs")


def test_verify_happy_path_sets_cookie(client, caplog, seeded_db):
    code = _request_and_extract_code(client, caplog, "owner@example.com")
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "owner@example.com", "code": code},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"ok": True, "email": "owner@example.com"}
    # Cookie set on the response.
    set_cookie = r.headers.get("set-cookie", "")
    assert "kb_owner_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie

    # Code row is now marked used.
    saved = _peek_code_for(seeded_db, "owner@example.com")
    assert saved["used_at"] is not None


def test_verify_rejects_replayed_code(client, caplog):
    code = _request_and_extract_code(client, caplog, "replay@example.com")
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "replay@example.com", "code": code},
    )
    assert r.status_code == 200
    # Second use of the same code must fail — it's marked used.
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "replay@example.com", "code": code},
    )
    assert r.status_code == 401


def test_verify_rejects_wrong_code_and_increments_attempts(client, caplog, seeded_db):
    _request_and_extract_code(client, caplog, "wrong@example.com")
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "wrong@example.com", "code": "ZZZZZZ"},
    )
    assert r.status_code == 401
    saved = _peek_code_for(seeded_db, "wrong@example.com")
    assert saved["attempts"] == 1


def test_verify_locks_after_five_wrong_attempts(client, caplog):
    _request_and_extract_code(client, caplog, "lock@example.com")
    for i in range(5):
        r = client.post(
            "/api/v1/owner/login/verify",
            json={"email": "lock@example.com", "code": "AAAAAA"},
        )
        assert r.status_code == 401
    # Sixth attempt: even if the right code were used, the row is locked.
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "lock@example.com", "code": "AAAAAA"},
    )
    assert r.status_code == 401
    assert "request a new code" in r.json()["detail"].lower()


def test_verify_rejects_expired_code(client, seeded_db):
    # Insert a code-row directly with an expires_at in the past.
    from app.services.owner_auth import hash_code

    asyncio.run(
        seeded_db.owner_magic_codes.insert_one(
            {
                "_id": "test-expired",
                "email": "expired@example.com",
                "code_hash": hash_code("ABCDEF"),
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=20),
                "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                "used_at": None,
                "attempts": 0,
            }
        )
    )
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "expired@example.com", "code": "ABCDEF"},
    )
    assert r.status_code == 401


def test_verify_rejects_email_with_no_codes(client):
    r = client.post(
        "/api/v1/owner/login/verify",
        json={"email": "ghost@example.com", "code": "ABCDEF"},
    )
    assert r.status_code == 401


# ---------- logout ----------

def test_logout_clears_cookie(client):
    r = client.post("/api/v1/owner/logout")
    assert r.status_code == 200
    # delete_cookie sets Max-Age=0 or an expires-in-the-past timestamp.
    set_cookie = r.headers.get("set-cookie", "")
    assert "kb_owner_session=" in set_cookie


# ---------- public pages ----------

def test_login_page_renders(client):
    r = client.get(
        "/owners/login", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert "Sign in" in r.text
    assert 'id="owner-email-form"' in r.text
    assert 'id="owner-code-form"' in r.text


def test_me_page_redirects_without_session(client):
    r = client.get(
        "/owners/me",
        headers={"host": "miami.knowsbeauty.localhost"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/owners/login" in r.headers["location"]


def test_me_page_renders_with_valid_session(client):
    from app.services.owner_auth import SESSION_COOKIE_NAME, sign_session

    cookie_value = sign_session("owner@example.com")
    r = client.get(
        "/owners/me",
        headers={"host": "miami.knowsbeauty.localhost"},
        cookies={SESSION_COOKIE_NAME: cookie_value},
    )
    assert r.status_code == 200, r.text
    assert "owner@example.com" in r.text
    assert "signed in" in r.text.lower()


def test_login_page_redirects_when_already_signed_in(client):
    from app.services.owner_auth import SESSION_COOKIE_NAME, sign_session

    cookie_value = sign_session("owner@example.com")
    r = client.get(
        "/owners/login",
        headers={"host": "miami.knowsbeauty.localhost"},
        cookies={SESSION_COOKIE_NAME: cookie_value},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/owners/me" in r.headers["location"]
