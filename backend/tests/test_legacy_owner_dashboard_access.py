"""Access-contract tests for the internal legacy owner-dashboard mockup."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote_plus

import pytest
from fastapi.testclient import TestClient


HOST = {"host": "miami.knowsbeauty.localhost"}
ADMIN_HEADERS = {**HOST, "X-API-Key": "test-admin-key"}
PRIVATE_NO_STORE = "private, no-store"


@pytest.fixture
def client(seeded_db) -> TestClient:
    """Return a client that exposes redirects for the access assertions."""
    from app.main import app

    return TestClient(app, follow_redirects=False, raise_server_exceptions=False)


def _set_preview_mode(monkeypatch, enabled: bool) -> None:
    """Set the DB-backed launch gate state without changing persistent data."""
    from app.services import site_settings

    async def _preview_mode() -> bool:
        return enabled

    monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _preview_mode)


def _insert_preview_session(
    mock_db,
    token: str,
    *,
    expires_at: datetime | None = None,
) -> None:
    """Store a token in the same hashed format as the production login flow."""
    from app.services.preview_auth import hash_value, session_expires_at

    asyncio.run(
        mock_db.preview_sessions.insert_one(
            {
                "_id": f"legacy-dashboard-{token}",
                "email": "reviewer@expertly.com",
                "token_hash": hash_value(token),
                "created_at": datetime.now(timezone.utc),
                "expires_at": expires_at or session_expires_at(),
            }
        )
    )


def _preview_cookie(token: str) -> dict[str, str]:
    return {**HOST, "Cookie": f"preview_token={token}"}


def _deny_dashboard_context_work(monkeypatch) -> None:
    """Make any post-authorization mock data work fail this negative test."""
    import app.routes.public.pages as pages

    async def _unexpected_async(*_args, **_kwargs):
        raise AssertionError("Denied legacy dashboard request reached mock context work")

    def _unexpected_template(*_args, **_kwargs):
        raise AssertionError("Denied legacy dashboard request rendered the mock template")

    monkeypatch.setattr(pages, "_require_tenant", _unexpected_async)
    monkeypatch.setattr(pages, "_base_context", _unexpected_async)
    monkeypatch.setattr(pages.content_svc, "get_business", _unexpected_async)
    monkeypatch.setattr(pages.content_svc, "list_businesses", _unexpected_async)
    monkeypatch.setattr(pages.content_svc, "get_neighborhood", _unexpected_async)
    assert pages._templates is not None
    monkeypatch.setattr(pages._templates, "TemplateResponse", _unexpected_template)


@pytest.mark.parametrize("preview_enabled", [False, True])
@pytest.mark.parametrize("credential", ["preview", "admin"])
def test_legacy_dashboard_allows_valid_preview_session_or_admin_key(
    client, mock_db, monkeypatch, preview_enabled: bool, credential: str
):
    """@define-test KAT-079-review-credential-success"""
    # @define-test KAT-079
    _set_preview_mode(monkeypatch, preview_enabled)

    if credential == "preview":
        token = f"valid-preview-{preview_enabled}"
        _insert_preview_session(mock_db, token)
        headers = _preview_cookie(token)
    else:
        headers = ADMIN_HEADERS

    response = client.get("/owner/dashboard", headers=headers)

    assert response.status_code == 200, response.text
    assert "Preview" in response.text
    assert "mockup" in response.text
    assert "127" in response.text


@pytest.mark.parametrize("credential", ["missing", "malformed", "expired", "unknown"])
def test_legacy_dashboard_denies_missing_malformed_expired_and_invalid_credentials_before_context(
    client, mock_db, monkeypatch, credential: str
):
    """@define-test KAT-079-deny-before-context"""
    # @define-test KAT-079
    _set_preview_mode(monkeypatch, False)
    _deny_dashboard_context_work(monkeypatch)

    if credential == "missing":
        headers = {**HOST, "X-API-Key": "wrong-admin-key"}
    elif credential == "expired":
        token = "expired-preview-token"
        _insert_preview_session(
            mock_db,
            token,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        headers = {**_preview_cookie(token), "X-API-Key": "wrong-admin-key"}
    elif credential == "malformed":
        # Preview tokens are opaque; an arbitrary non-session string is malformed
        # from the route's point of view and must never gain special treatment.
        headers = {
            **_preview_cookie("not-even-a-hex-preview-token"),
            "X-API-Key": "wrong-admin-key",
        }
    else:
        headers = {
            **_preview_cookie("unknown-preview-token"),
            "X-API-Key": "wrong-admin-key",
        }

    response = client.get("/owner/dashboard", headers=headers)

    assert response.status_code == 303
    assert response.headers["location"] == "/owners/login"
    assert response.headers["cache-control"] == PRIVATE_NO_STORE
    assert "Owner Dashboard" not in response.text
    assert "127" not in response.text
    assert "482" not in response.text


@pytest.mark.parametrize("preview_enabled", [False, True])
def test_legacy_dashboard_preview_session_lookup_error_denies_before_context(
    client, monkeypatch, preview_enabled: bool
):
    """@define-test KAT-079-db-fail-closed"""
    # @define-test KAT-079
    import app.middleware.preview_gate as preview_gate
    import app.routes.public.pages as pages

    _set_preview_mode(monkeypatch, preview_enabled)
    _deny_dashboard_context_work(monkeypatch)

    async def _database_error(_token: str) -> bool:
        raise RuntimeError("preview session database unavailable")

    # WHY: while the gate is on it remains availability-first and reaches the
    # route after this error; the route's independently strict check must deny.
    monkeypatch.setattr(preview_gate, "preview_session_is_valid", _database_error)
    monkeypatch.setattr(pages, "preview_session_is_valid", _database_error)

    response = client.get(
        "/owner/dashboard",
        headers=_preview_cookie("database-error-preview-token"),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/owners/login"
    assert response.headers["cache-control"] == PRIVATE_NO_STORE


@pytest.mark.parametrize("preview_enabled", [False, True])
def test_legacy_dashboard_admin_header_short_circuits_preview_session_lookup(
    client, monkeypatch, preview_enabled: bool
):
    """@define-test KAT-079-db-fail-closed"""
    # @define-test KAT-079
    import app.routes.public.pages as pages

    _set_preview_mode(monkeypatch, preview_enabled)
    calls: list[str] = []

    async def _preview_lookup_must_not_run(_token: str) -> bool:
        calls.append("preview lookup")
        raise AssertionError("Valid admin review access should short-circuit preview lookup")

    monkeypatch.setattr(pages, "preview_session_is_valid", _preview_lookup_must_not_run)
    admin_response = client.get("/owner/dashboard", headers=ADMIN_HEADERS)

    assert admin_response.status_code == 200, admin_response.text
    assert calls == []


@pytest.mark.parametrize(
    ("preview_enabled", "expected_status", "expected_location"),
    [
        (False, 303, "/owners/login"),
        (True, 302, "/preview-login"),
    ],
)
def test_legacy_dashboard_owner_session_alone_is_denied(
    client, monkeypatch, preview_enabled: bool, expected_status: int, expected_location: str
):
    """@define-test KAT-079-owner-session-is-not-review-access"""
    # @define-test KAT-079
    from app.services.owner_auth import SESSION_COOKIE_NAME, sign_session

    _set_preview_mode(monkeypatch, preview_enabled)
    owner_cookie = sign_session("owner@example.com")
    response = client.get(
        "/owner/dashboard",
        headers={**HOST, "Cookie": f"{SESSION_COOKIE_NAME}={owner_cookie}"},
    )

    assert response.status_code == expected_status
    assert response.headers["location"].startswith(expected_location)
    assert response.headers["cache-control"] == PRIVATE_NO_STORE


@pytest.mark.parametrize("credential", ["missing", "malformed", "expired", "invalid"])
def test_legacy_dashboard_global_preview_no_credential_redirect_is_preserved(
    client, mock_db, monkeypatch, credential: str
):
    """@define-test KAT-079-preview-gate-compatibility"""
    # @define-test KAT-079
    _set_preview_mode(monkeypatch, True)

    if credential == "missing":
        headers = HOST
    elif credential == "expired":
        token = "expired-global-preview-token"
        _insert_preview_session(
            mock_db,
            token,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        headers = _preview_cookie(token)
    elif credential == "malformed":
        headers = _preview_cookie("not-even-a-hex-preview-token")
    else:
        headers = _preview_cookie("unknown-global-preview-token")

    response = client.get("/owner/dashboard", headers=headers)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/preview-login?next=")
    assert "/owner/dashboard" in unquote_plus(response.headers["location"])


def test_legacy_dashboard_review_responses_are_private_no_store(
    client, monkeypatch
):
    """@define-test KAT-079-cache-control"""
    # @define-test KAT-079
    _set_preview_mode(monkeypatch, False)
    authorized = client.get("/owner/dashboard", headers=ADMIN_HEADERS)
    route_denial = client.get("/owner/dashboard", headers=HOST)

    _set_preview_mode(monkeypatch, True)
    gate_denial = client.get("/owner/dashboard", headers=HOST)
    unrelated_gate_denial = client.get("/", headers=HOST)

    assert authorized.status_code == 200, authorized.text
    assert route_denial.status_code == 303
    assert gate_denial.status_code == 302
    assert unrelated_gate_denial.status_code == 302
    for response in (
        authorized,
        route_denial,
        gate_denial,
        unrelated_gate_denial,
    ):
        assert response.headers["cache-control"] == PRIVATE_NO_STORE
