"""Preview gate ASGI middleware.

When PREVIEW_MODE_ENABLED is true, every incoming request is checked for a
valid preview_token cookie. Requests without a valid token are redirected to
/preview-login (with the original URL saved as `?next=` so we can send them
back after authentication).

Paths that bypass the gate:
  - /preview-login  — the login page itself (would cause an infinite redirect)
  - /api/v1/preview/*  — the login API endpoints
  - /health         — uptime checks from container orchestration
  - /api/v1/billing/*  — Stripe webhook (must reach without a cookie) AND owner
                      billing actions (checkout, portal) — those have their own
                      owner-session auth at the route level.
  - /assets/*       — static CSS/JS/images needed to render the login page
  - /favicon.*      — browser favicon probes
  - /owners         — owner claim form (exact path only); linked from outreach emails
                      sent to external salon owners who have no preview account and
                      should never need one.
  - /owners/login   — owner dashboard sign-in; verified salon owners receive a login
                      link by email after their claim is approved. They have no preview
                      account and should be able to log in without one.
  - /owners/me      — owner dashboard; has its own auth check that redirects to
                      /owners/login if no session cookie is present.
  - /api/v1/owner/* — ALL owner API endpoints (OTP login, profile, stats, photos,
                      logout, inquiries). Owners have an owner-session cookie but no
                      preview cookie; every fetch() from the dashboard would otherwise
                      receive a 302 redirect instead of JSON and the dashboard would
                      be completely non-functional.
  - /api/v1/claims  — claim form submission; salon owners post this from /owners
                      without a preview account.
  - /api/v1/owner-leads  — email lead capture on the /owners page.
  - /api/v1/marketing-ai/*  — AI caption and ad-copy generators on the owner
                      dashboard; have their own owner-session auth at the route level.
  - /admin/*         — admin panel login and management pages; each page enforces
                      admin API key auth via an HttpOnly cookie. Without this bypass
                      the browser cannot reach /admin/login to obtain the cookie.
                      Adding /admin/ to the bypass does not weaken security because
                      every admin route still requires the key-derived cookie.

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
    "/api/v1/preview/",     # preview login API endpoints (request code / verify code)
    # WHY: /api/v1/billing/ expanded from /api/v1/billing/webhook so that owner
    # billing actions (checkout + portal) are also reachable. All routes under
    # /api/v1/billing/ except the webhook enforce owner-session auth at the route
    # level, so bypassing the preview gate here does not expose any billing data.
    "/api/v1/billing/",
    "/health",              # container health checks from the load balancer
    "/assets/",             # CSS/JS/images needed by the login page itself
    "/favicon",             # browser favicon probes
    # WHY: the admin panel (/admin/login, /admin/claims, /admin/analytics) requires
    # the admin API key to authenticate — the login page sets an HttpOnly admin
    # cookie that all subsequent /admin/* routes verify. Without this bypass, the
    # browser cannot reach /admin/login to obtain the cookie, making the entire
    # admin panel inaccessible when preview mode is on. Bypassing /admin/ here is
    # safe because every admin page still enforces its own key-based auth.
    "/admin/",
    # WHY: ALL owner API endpoints are bypassed, not just /api/v1/owner/login/.
    # Authenticated owners have an owner-session cookie but no preview_token.
    # Every fetch() from the owner dashboard (profile, stats, photos, logout,
    # inquiries, billing checkout, marketing-ai) would receive a 302 redirect to
    # /preview-login instead of JSON, silently breaking the entire dashboard.
    # Each sub-route enforces owner-session auth at the route level, so bypassing
    # the preview gate here is safe.
    "/api/v1/owner/",
    # WHY: claim submission and email lead-capture come from /owners, which is
    # bypassed as a page, but the form's fetch() targets these API endpoints.
    # Without bypassing them, a salon owner who fills in the claim form gets a
    # 302 HTML redirect in the fetch() response and their claim silently fails.
    "/api/v1/claims",
    "/api/v1/owner-leads",
    # WHY: AI caption and ad-copy generators on the owner dashboard. These
    # require an active owner session at the route level; bypassing the preview
    # gate here does not allow unauthenticated access.
    "/api/v1/marketing-ai/",
    # WHY: the owner journey PDF is a shareable document sent to prospective
    # salon owners. Same logic as /walkthrough — recipients have no preview
    # account and should never hit a login wall when downloading the PDF.
    # The file contains only marketing copy; no private data is exposed.
    # Static files are mounted under /assets/ (not /static/) in main.py.
    "/assets/walkthrough/",
    # WHY: the "As Featured on Miami Knows Beauty" website badge
    # (/badge/featured.svg) is embedded on Featured salons' OWN external
    # websites. The image must load for the whole public internet even while
    # our site is still private behind the preview gate — otherwise it would
    # render as a broken image on the salon's site. This exemption is
    # deliberately scoped to the /badge/ prefix only: that path serves nothing
    # but the static brand-mark SVG (no private directory content), so exposing
    # it leaks nothing. Without this bypass, every embedded badge would 302 to
    # /preview-login (which a salon's visitor can't follow) and show broken.
    "/badge/",
)

# WHY: exact-path bypass for paths where sub-paths must stay gated. The claim
# form lives at /owners (with optional query params like ?slug=salon-name).
# /owners/login and /owners/me are the owner dashboard sign-in and portal;
# verified salon owners receive a login link by email (no preview account) and
# must be able to sign in and access their dashboard without a preview cookie.
# The owner dashboard has its own auth check that redirects to /owners/login
# when no owner session cookie is present, so bypassing the preview gate here
# is safe — an unauthenticated visitor still cannot see any owner data.
_BYPASS_EXACT = frozenset({
    "/owners",
    "/owners/login",
    "/owners/me",
    # WHY: robots.txt and sitemap.xml must reach search engine crawlers even
    # while the preview gate is active. Without this bypass, Googlebot receives
    # a 302 redirect to /preview-login instead of a valid robots.txt — so it
    # has no signal about what to crawl and wastes budget hitting gated pages.
    # Both handlers return minimal / empty responses when preview mode is enabled
    # (robots.txt returns "Disallow: /", sitemap returns an empty urlset), giving
    # crawlers an accurate "site is private" signal. Neither file exposes any
    # private content. These are exact paths — no sub-paths exist to stay gated —
    # so they belong in _BYPASS_EXACT rather than _BYPASS_PREFIXES.
    "/robots.txt",
    "/sitemap.xml",
    # WHY: /walkthrough is a shareable owner-journey explainer sent to
    # prospective salon owners during outreach. It must be publicly accessible
    # even while preview mode is active — an owner receiving David's email has
    # no preview account and should never need one just to read a product
    # overview. The page contains no private data; it only renders marketing copy
    # and links to /owners and /pricing (both also bypassed).
    "/walkthrough",
    # WHY: /pricing is linked from the /walkthrough page (Step 5: Upgrade to
    # Featured). An owner reading the walkthrough must be able to click through
    # to see the subscription tiers without hitting a preview login wall — they
    # have no preview account. /pricing renders only public marketing copy; no
    # private data is exposed. It belongs in _BYPASS_EXACT (not _BYPASS_PREFIXES)
    # so that sub-paths (none exist currently) remain gated by default.
    "/pricing",
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
        # WHY: DB value is checked first so the admin settings page can open
        # the site without an SSH restart. Falls back to the env var so the
        # existing production config works unchanged on first deploy.
        from app.services.site_settings import get_preview_mode_enabled
        preview_on = await get_preview_mode_enabled()
        if not preview_on:
            return await call_next(request)

        path = request.url.path

        if _is_bypassed(path):
            return await call_next(request)

        # WHY: requests bearing the admin API key bypass the preview gate.
        # Admin tools (scripts, internal APIs) run outside a browser and
        # cannot present a preview_token cookie; the admin key is sufficient
        # proof of identity for these callers.
        from app.config import get_settings as _get_settings
        api_key = request.headers.get("X-API-Key", "")
        if api_key and api_key == _get_settings().admin_api_key:
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
