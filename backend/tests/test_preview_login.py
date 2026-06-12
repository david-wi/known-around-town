"""Tests for the preview login gate.

Four slices are covered:

  1. Service-layer primitives — allow-list logic, code generation,
     hashing, constant-time equality, session token generation.

  2. Middleware bypass logic — paths that skip the gate, paths that
     redirect unauthenticated requests, and the disabled-gate path.

  3. Request-code API — well-formed email always returns 200; only
     allowed emails get a code stored; invalid email format gets 400.

  4. Verify-code API — correct code issues a cookie and creates a
     session; disallowed email gets 401; wrong code gets 401; expired
     or missing code gets 401; replay gets 401.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── helpers ──────────────────────────────────────────────────────────────────

def _request_and_extract_code(client: TestClient, caplog, email: str) -> str:
    """Use the dev-mode log fallback to read the cleartext preview code.

    Tests clear RESEND_API_KEY in conftest.py so the preview_email module logs
    the code instead of actually sending an email. We grep those logs here.
    """
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.services.preview_email"):
        r = client.post("/api/v1/preview/login/request", json={"email": email})
        assert r.status_code == 200, r.text
    for rec in caplog.records:
        m = re.search(r"PREVIEW CODE for \S+: (\d{6})", rec.getMessage())
        if m:
            return m.group(1)
    raise AssertionError(f"did not capture preview code from logs; records: {caplog.records}")


# ─── fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client(seeded_db, monkeypatch):
    """TestClient pointed at the app with the preview gate ENABLED.

    WHY: conftest.py sets PREVIEW_MODE_ENABLED=false so pre-gate tests are
    unaffected. This fixture overrides it to true and clears the settings
    cache so the gate middleware sees the override. After the test, monkeypatch
    restores the env and we clear the cache again so other tests are unaffected.
    """
    import os
    from app.config import get_settings

    monkeypatch.setenv("PREVIEW_MODE_ENABLED", "true")
    get_settings.cache_clear()

    from app.main import app
    tc = TestClient(app, follow_redirects=False)

    yield tc

    # Restore: clear the cache so the next test picks up the conftest default.
    get_settings.cache_clear()


# ══════════════════════════════════════════════════════════════════════════════
# 1.  Service-layer primitives
# ══════════════════════════════════════════════════════════════════════════════

class TestAllowList:
    def test_expertly_domain_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert is_allowed_email("alice@expertly.com")
        assert is_allowed_email("ALICE@EXPERTLY.COM")  # case-insensitive

    def test_webintensive_domain_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert is_allowed_email("dev@webintensive.com")

    def test_explicit_gmail_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert is_allowed_email("aggiewaggie06@gmail.com")
        assert is_allowed_email("karissa.ostoski@gmail.com")

    def test_random_gmail_not_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert not is_allowed_email("random@gmail.com")

    def test_unknown_domain_not_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert not is_allowed_email("attacker@evil.com")

    def test_empty_email_not_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert not is_allowed_email("")
        assert not is_allowed_email("   ")

    def test_no_at_sign_not_allowed(self):
        from app.services.preview_auth import is_allowed_email
        assert not is_allowed_email("notanemail")

    def test_subdomain_of_allowed_not_granted(self):
        # WHY: attacker might try attacker@sub.expertly.com to probe whether
        # any subdomain gets in. rsplit('@',1) gives them the full subdomain
        # ("sub.expertly.com") which is NOT in ALLOWED_DOMAINS, so this fails.
        from app.services.preview_auth import is_allowed_email
        assert not is_allowed_email("attacker@sub.expertly.com")


class TestCodeGeneration:
    def test_generate_code_is_six_digits(self):
        from app.services.preview_auth import generate_code
        for _ in range(50):
            code = generate_code()
            assert len(code) == 6
            assert code.isdigit()

    def test_generate_code_can_start_with_zero(self):
        from app.services.preview_auth import generate_code, CODE_LENGTH
        # Run enough iterations to ensure zero-padding is covered.
        codes = {generate_code() for _ in range(200)}
        # All generated codes must be exactly 6 chars, even small numbers.
        assert all(len(c) == CODE_LENGTH for c in codes)

    def test_hash_value_is_sha256_hex(self):
        from app.services.preview_auth import hash_value
        h = hash_value("test")
        assert len(h) == 64
        # SHA-256 of "test" — deterministic.
        assert h == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

    def test_constant_equal_same_string(self):
        from app.services.preview_auth import constant_equal
        assert constant_equal("abc", "abc")

    def test_constant_equal_different_string(self):
        from app.services.preview_auth import constant_equal
        assert not constant_equal("abc", "xyz")

    def test_generate_session_token_is_64_hex_chars(self):
        # WHY: secrets.token_hex(32) produces 64 hex characters (32 bytes × 2
        # hex chars each). This length check confirms the right byte count.
        from app.services.preview_auth import generate_session_token
        for _ in range(20):
            token = generate_session_token()
            assert len(token) == 64
            assert all(c in "0123456789abcdef" for c in token)

    def test_generate_session_token_is_unique(self):
        from app.services.preview_auth import generate_session_token
        tokens = {generate_session_token() for _ in range(50)}
        assert len(tokens) == 50


# ══════════════════════════════════════════════════════════════════════════════
# 2.  Middleware bypass logic
# ══════════════════════════════════════════════════════════════════════════════

class TestBypassPaths:
    """Verify _is_bypassed() returns True for each exempt path prefix."""

    def test_preview_login_page_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/preview-login")
        assert _is_bypassed("/preview-login?next=http%3A%2F%2F...")

    def test_preview_api_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/api/v1/preview/login/request")
        assert _is_bypassed("/api/v1/preview/login/verify")
        assert _is_bypassed("/api/v1/preview/")

    def test_stripe_webhook_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/api/v1/billing/webhook")

    def test_health_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/health")

    def test_assets_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/assets/css/reference.css")
        assert _is_bypassed("/assets/favicon.svg")

    def test_favicon_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/favicon.ico")
        assert _is_bypassed("/favicon.png")
        assert _is_bypassed("/favicon.svg")

    def test_root_not_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert not _is_bypassed("/")

    def test_api_non_preview_not_bypassed(self):
        from app.middleware.preview_gate import _is_bypassed
        assert not _is_bypassed("/api/v1/networks")
        assert not _is_bypassed("/api/v1/businesses")

    def test_owner_claim_form_bypassed(self):
        # WHY: outreach emails link salon owners directly to /owners?slug=<slug>.
        # Those owners have no preview account and must reach the claim form
        # without going through the preview login page. Query params are part of
        # the URL but NOT of request.url.path, so the path is always "/owners".
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/owners")
        assert _is_bypassed("/owners")   # same path regardless of ?slug= param

    def test_owner_login_bypassed(self):
        # WHY: verified salon owners receive a login link by email after their
        # claim is approved. They have no preview account and must be able to
        # reach /owners/login without being redirected to the preview gate.
        # The route has its own session check and redirects unauthenticated
        # visitors to /owners/login — bypassing the preview gate here does not
        # expose any owner data to the general public.
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/owners/login")

    def test_owner_login_api_bypassed(self):
        # WHY: the /owners/login page makes fetch() calls to these API endpoints
        # to send and verify the OTP code. Without bypassing them, the browser's
        # fetch() receives a 302 redirect instead of JSON and the login silently
        # fails — the form appears to do nothing.
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/api/v1/owner/login/request")
        assert _is_bypassed("/api/v1/owner/login/verify")

    def test_owner_me_bypassed(self):
        # WHY: /owners/me is the owner dashboard. It has its own auth check:
        # if the owner has no session cookie it redirects to /owners/login.
        # Bypassing the preview gate is safe — unauthenticated visitors just
        # get sent to /owners/login rather than seeing any owner data.
        # Without this bypass, an owner who just logged in is intercepted by
        # the preview gate before they can reach their dashboard.
        from app.middleware.preview_gate import _is_bypassed
        assert _is_bypassed("/owners/me")


class TestMiddlewareRedirection:
    """Integration tests that run the full app stack with the gate active."""

    def test_unauthenticated_root_redirects(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/preview-login" in r.headers["location"]

    def test_redirect_preserves_next_url(self, client):
        r = client.get("/miami/", follow_redirects=False)
        assert r.status_code == 302
        loc = r.headers["location"]
        assert "/preview-login" in loc
        assert "next=" in loc

    def test_health_passes_gate(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_preview_login_page_passes_gate(self, client):
        r = client.get("/preview-login")
        assert r.status_code == 200

    def test_assets_pass_gate(self, client):
        # The static file may not exist in the test environment, but the
        # important thing is we get 404 (or 200), not 302.
        r = client.get("/assets/css/reference.css", follow_redirects=False)
        assert r.status_code != 302

    def test_authenticated_request_passes(self, client, mock_db):
        """A request with a valid session cookie is allowed through."""
        from app.services.preview_auth import (
            generate_session_token,
            hash_value,
            session_expires_at,
        )
        token = generate_session_token()
        asyncio.run(
            mock_db.preview_sessions.insert_one(
                {
                    "_id": "test-session-001",
                    "email": "alice@expertly.com",
                    "token_hash": hash_value(token),
                    "created_at": datetime.now(timezone.utc),
                    "expires_at": session_expires_at(),
                }
            )
        )
        r = client.get("/health", cookies={"preview_token": token})
        assert r.status_code == 200

    def test_expired_session_redirects(self, client, mock_db):
        """A valid-format token whose session is past expires_at is rejected."""
        from app.services.preview_auth import generate_session_token, hash_value
        token = generate_session_token()
        asyncio.run(
            mock_db.preview_sessions.insert_one(
                {
                    "_id": "test-session-expired",
                    "email": "alice@expertly.com",
                    "token_hash": hash_value(token),
                    "created_at": datetime.now(timezone.utc) - timedelta(days=31),
                    "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
                }
            )
        )
        r = client.get("/", cookies={"preview_token": token}, follow_redirects=False)
        assert r.status_code == 302

    def test_bogus_token_redirects(self, client):
        r = client.get("/", cookies={"preview_token": "not-a-real-token"},
                       follow_redirects=False)
        assert r.status_code == 302

    def test_valid_admin_key_bypasses_gate(self, client, monkeypatch):
        """X-API-Key matching ADMIN_API_KEY must pass through the preview gate.

        WHY: admin tooling (scripts, internal APIs) runs outside a browser and
        cannot present a preview_token cookie. The gate must let these requests
        through before the cookie check so route-level admin auth can run.
        """
        from app.config import get_settings

        monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key-xyz")
        get_settings.cache_clear()
        try:
            r = client.get("/health", headers={"X-API-Key": "test-admin-key-xyz"},
                           follow_redirects=False)
            assert r.status_code == 200
        finally:
            get_settings.cache_clear()

    def test_wrong_admin_key_still_redirects(self, client, monkeypatch):
        """An unrecognised API key does NOT bypass the preview gate."""
        from app.config import get_settings

        monkeypatch.setenv("ADMIN_API_KEY", "real-key-abc")
        get_settings.cache_clear()
        try:
            r = client.get("/", headers={"X-API-Key": "wrong-key"},
                           follow_redirects=False)
            assert r.status_code == 302
        finally:
            get_settings.cache_clear()


# ══════════════════════════════════════════════════════════════════════════════
# 3.  POST /api/v1/preview/login/request
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestCode:
    def test_allowed_email_returns_ok_and_stores_hash(self, client, mock_db):
        r = client.post(
            "/api/v1/preview/login/request",
            json={"email": "alice@expertly.com"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        docs = asyncio.run(
            mock_db.preview_codes.find({"email": "alice@expertly.com"}).to_list(10)
        )
        assert len(docs) == 1
        # Cleartext code never stored — only the hash.
        assert "code" not in docs[0]
        assert isinstance(docs[0]["code_hash"], str) and len(docs[0]["code_hash"]) == 64
        assert docs[0]["used_at"] is None

    def test_disallowed_email_returns_ok_but_no_code_stored(self, client, mock_db):
        # WHY: disallowed emails must get the same 200 response as allowed ones
        # to prevent probing whether an address is on the allow-list.
        r = client.post(
            "/api/v1/preview/login/request",
            json={"email": "outsider@random.com"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        docs = asyncio.run(
            mock_db.preview_codes.find({"email": "outsider@random.com"}).to_list(10)
        )
        assert len(docs) == 0

    def test_invalid_email_format_returns_400(self, client):
        r = client.post(
            "/api/v1/preview/login/request",
            json={"email": "not-an-email"},
        )
        assert r.status_code == 400

    def test_email_normalized_to_lowercase(self, client, mock_db):
        r = client.post(
            "/api/v1/preview/login/request",
            json={"email": "  ALICE@EXPERTLY.COM  "},
        )
        assert r.status_code == 200
        docs = asyncio.run(
            mock_db.preview_codes.find({"email": "alice@expertly.com"}).to_list(10)
        )
        assert len(docs) == 1

    def test_explicit_gmail_allowed(self, client, mock_db):
        r = client.post(
            "/api/v1/preview/login/request",
            json={"email": "aggiewaggie06@gmail.com"},
        )
        assert r.status_code == 200
        docs = asyncio.run(
            mock_db.preview_codes.find({"email": "aggiewaggie06@gmail.com"}).to_list(10)
        )
        assert len(docs) == 1

    def test_code_expiry_is_roughly_fifteen_minutes(self, client, mock_db):
        client.post(
            "/api/v1/preview/login/request",
            json={"email": "alice@expertly.com"},
        )
        docs = asyncio.run(
            mock_db.preview_codes.find({"email": "alice@expertly.com"}).to_list(10)
        )
        exp = docs[0]["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta = (exp - datetime.now(timezone.utc)).total_seconds()
        # Allow a generous window to absorb slow test runners.
        assert 13 * 60 < delta < 17 * 60


# ══════════════════════════════════════════════════════════════════════════════
# 4.  POST /api/v1/preview/login/verify
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyCode:
    def test_correct_code_sets_cookie_and_creates_session(
        self, client, caplog, mock_db
    ):
        code = _request_and_extract_code(client, caplog, "alice@expertly.com")
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": code},
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # Cookie must be set.
        set_cookie = r.headers.get("set-cookie", "")
        assert "preview_token=" in set_cookie
        assert "HttpOnly" in set_cookie

        # Session document must be in the database.
        sessions = asyncio.run(
            mock_db.preview_sessions.find(
                {"email": "alice@expertly.com"}
            ).to_list(10)
        )
        assert len(sessions) == 1
        # Only the hash should be stored, not the cleartext token.
        assert len(sessions[0]["token_hash"]) == 64

        # Code must be marked used.
        codes = asyncio.run(
            mock_db.preview_codes.find({"email": "alice@expertly.com"}).to_list(10)
        )
        assert codes[0]["used_at"] is not None

    def test_wrong_code_returns_401(self, client, caplog, mock_db):
        _request_and_extract_code(client, caplog, "alice@expertly.com")
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": "000000"},
        )
        assert r.status_code == 401

    def test_replay_of_used_code_returns_401(self, client, caplog):
        code = _request_and_extract_code(client, caplog, "alice@expertly.com")
        # First use — succeeds.
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": code},
        )
        assert r.status_code == 200
        # Second use — same code — must fail.
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": code},
        )
        assert r.status_code == 401

    def test_disallowed_email_verify_returns_401(self, client):
        # WHY: disallowed addresses never had a code inserted, but the 401
        # response shape must be identical to a wrong-code 401 so callers
        # cannot distinguish between "email not on list" and "wrong code".
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "outsider@random.com", "code": "123456"},
        )
        assert r.status_code == 401
        assert r.json().get("detail") == "Invalid or expired code."

    def test_expired_code_returns_401(self, client, mock_db):
        from app.services.preview_auth import hash_value
        # Insert a code that is already past its expiry.
        asyncio.run(
            mock_db.preview_codes.insert_one(
                {
                    "_id": "expired-code-test",
                    "email": "alice@expertly.com",
                    "code_hash": hash_value("999999"),
                    "created_at": datetime.now(timezone.utc) - timedelta(minutes=20),
                    "expires_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                    "used_at": None,
                }
            )
        )
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": "999999"},
        )
        assert r.status_code == 401

    def test_no_code_at_all_returns_401(self, client):
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": "123456"},
        )
        assert r.status_code == 401

    def test_invalid_email_format_returns_400(self, client):
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "not-an-email", "code": "123456"},
        )
        assert r.status_code == 400

    def test_code_with_whitespace_stripped(self, client, caplog, mock_db):
        """A user might type spaces between digits — strip them before verify."""
        code = _request_and_extract_code(client, caplog, "alice@expertly.com")
        spaced = " ".join(code)  # e.g. "1 2 3 4 5 6"
        r = client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": spaced},
        )
        assert r.status_code == 200

    def test_session_expiry_roughly_30_days(self, client, caplog, mock_db):
        code = _request_and_extract_code(client, caplog, "alice@expertly.com")
        client.post(
            "/api/v1/preview/login/verify",
            json={"email": "alice@expertly.com", "code": code},
        )
        sessions = asyncio.run(
            mock_db.preview_sessions.find({"email": "alice@expertly.com"}).to_list(10)
        )
        exp = sessions[0]["expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta = (exp - datetime.now(timezone.utc)).total_seconds()
        # 30 days ± 1 minute tolerance for slow runners.
        expected = 30 * 24 * 3600
        assert expected - 60 < delta < expected + 60
