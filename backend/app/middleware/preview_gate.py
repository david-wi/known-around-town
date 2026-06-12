"""Preview gate ASGI middleware.

When PREVIEW_MODE_ENABLED is true, every incoming request is checked for a
valid preview_token cookie. Requests without a valid token are redirected to
/preview-login (with the original URL saved as `?next=` so we can send them
back after authentication).

Paths that bypass the gate:
  - /preview-login  — the login page itself (would cause an infinite redirect)
  - /api/v1/preview/*  — the login API endpoints
  - /health         — uptime checks from container orchestration
  - /api/v1/billing/webhook  — Stripe calls this directly; it must never be gated
  - /assets/*       — static CSS/JS/images needed to render the login page
  - /favicon.*      — browser favicon probes
  - /owners         — owner claim form (exact path only); linked from outreach emails
                      sent to external salon owners who have no preview account and
                      should never need one. /owners/login stays gated.

Design choice — middleware vs. route dependency:
  WHY middleware: a route-level dependency only protects routes we explicitly
  decorate. New routes added by other developers would be unprotected by
  default. Middleware runs before any route is matched, so every current and
  future path is gated automatically; the opt-out list is explicit and small.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp

from app.database import get_db
from app.services.preview_auth import (
    PREVIEW_COOKIE_NAME,
    hash_value,
)

logger = logging.getLogger(__name__)

# WHY: these prefixes bypass the gate entirely. The list is intentionally
# small — anything not here must present a valid preview_token cookie.
_BYPASS_PREFIXES = (
    "/preview-login",       # the login page and its form POST
    "/api/v1/preview/",     # login API endpoints (request code / verify code)
    "/api/v1/billing/webhook",  # Stripe must reach this without a browser cookie
    "/health",              # container health checks from the load balancer
    "/assets/",             # CSS/JS/images needed by the login page itself
    "/favicon",             # browser favicon probes
)

# WHY: exact-path bypass for paths where sub-paths must stay gated. The claim
# form lives at /owners (with optional query params like ?slug=salon-name).
# /owners/login is the authenticated owner dashboard sign-in and must remain
# gated — so a prefix match on "/owners" would be too broad.
_BYPASS_EXACT = frozenset({
    "/owners",
})


def _is_bypassed(path: str) -> bool:
    return path in _BYPASS_EXACT or any(path.startswith(prefix) for prefix in _BYPASS_PREFIXES)


class PreviewGateMiddleware(BaseHTTPMiddleware):
    """Block unauthenticated visitors when preview mode is active."""

    def __init__(self, app: ASGIApp, enabled: bool = True) -> None:
        super().__init__(app)
        # WHY: _initial_enabled captures the value at construction time for
        # production use. We also re-check get_settings() on each request so
        # that tests can toggle PREVIEW_MODE_ENABLED via monkeypatch and see
        # the change without restarting the app. In production the value is
        # stable across the container's lifetime, so the extra settings call
        # is a no-op (lru_cache returns instantly).
        self._initial_enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        # Re-read the current setting on every request. This is cache-backed
        # (lru_cache on get_settings) so it costs nothing in production, but
        # allows tests to toggle the flag via monkeypatch + cache_clear.
        from app.config import get_settings as _get_settings
        if not _get_settings().preview_mode_enabled:
            return await call_next(request)

        path = request.url.path

        if _is_bypassed(path):
            return await call_next(request)

        token = request.cookies.get(PREVIEW_COOKIE_NAME, "")
        if token and await _is_valid_session(token):
            return await call_next(request)

        # Unauthenticated — redirect to the login page, preserving the
        # original URL so the visitor lands where they wanted after login.
        next_url = str(request.url)
        login_url = f"/preview-login?next={quote_plus(next_url)}"
        return RedirectResponse(url=login_url, status_code=302)


async def _is_valid_session(token: str) -> bool:
    """Return True if the token corresponds to an unexpired preview session."""
    if not token:
        return False
    try:
        db = get_db()
        token_hash = hash_value(token)
        now = datetime.now(timezone.utc)
        doc = await db.preview_sessions.find_one(
            {
                "token_hash": token_hash,
                "expires_at": {"$gt": now},
            }
        )
        return doc is not None
    except Exception:
        # WHY: if the DB is momentarily unreachable, fail open rather
        # than locking everyone out of the site during an outage.
        # The gate's purpose is to keep random internet traffic out, not
        # to protect secrets — briefly skipping it during a DB hiccup is
        # the lesser harm. Log so we notice if this happens repeatedly.
        logger.exception("preview_gate: DB error during session check; failing open")
        return True
