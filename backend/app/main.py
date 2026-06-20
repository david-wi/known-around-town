from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bson import ObjectId
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings


class _MongoJSONEncoder(json.JSONEncoder):
    """WHY: some MongoDB collections still have BSON ObjectId values in _id
    and foreign-key fields (pre-UUID-migration documents).  FastAPI's default
    Pydantic serialization can't handle ObjectId, causing 500s on any endpoint
    that returns raw cursor results."""

    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)


class MongoSafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=_MongoJSONEncoder,
        ).encode("utf-8")
from app.database import ensure_indexes, run_startup_migrations
from app.middleware.preview_gate import PreviewGateMiddleware
from app.routes.api.v1 import (
    networks as api_networks,
    cities as api_cities,
    neighborhoods as api_neighborhoods,
    categories as api_categories,
    businesses as api_businesses,
    copy_blocks as api_copy_blocks,
    editorial as api_editorial,
    claims as api_claims,
    inquiries as api_inquiries,
    marketing_ai as api_marketing_ai,
    owner_login as api_owner_login,
    preview_login as api_preview_login,
    owner_leads as api_owner_leads,
    owner_inquiries as api_owner_inquiries,
    owner_profile as api_owner_profile,
    owner_photos as api_owner_photos,
    owner_stats as api_owner_stats,
    stripe_billing as api_stripe_billing,
    admin_voice as api_admin_voice,
    owner_voice as api_owner_voice,
)
from app.routes.admin import claims_admin, analytics_admin, settings_admin, sync_admin, businesses_admin
from app.routes.public import pages as public_pages, media as public_media, badge as public_badge

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# WHY: global makes support_email available in every template without
# threading it through each individual route's context dict. A route that
# doesn't explicitly pass it still gets the right value.
templates.env.globals["support_email"] = settings.support_email
# WHY: ratings_min_review_count is injected as a global so every template
# (home, category, neighborhood, search, business detail) gets the threshold
# without each route handler needing to query the DB separately. The DB value
# is loaded at startup (below in on_startup) to override this module-load
# default of 20. The admin settings page refreshes it on save, same pattern
# as support_email.
templates.env.globals["ratings_min_review_count"] = 20


def _jinja_fmt_time(t: str) -> str:
    """Convert HH:MM to H:MM AM/PM (e.g. '09:00' -> '9:00 AM', '13:30' -> '1:30 PM').

    WHY: hours are stored in 24-hour HH:MM format (matching HTML <input type="time">
    output), but American visitors read and expect 12-hour AM/PM notation. Registering
    this as a Jinja2 filter lets every template convert times without duplicating logic.
    """
    if not t:
        return t
    try:
        h, m = map(int, t.split(":"))
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {period}"
    except (ValueError, AttributeError):
        return t


# WHY: register as a Jinja2 filter so templates can write {{ h.opens_at | fmt_time }}
# rather than calling a Python function — consistent with how other formatting
# (tojson, replace, etc.) is expressed in the template layer.
templates.env.filters["fmt_time"] = _jinja_fmt_time

app = FastAPI(title="Known Around Town", version="0.1.0", default_response_class=MongoSafeJSONResponse)

# WHY: the preview gate must be added as middleware BEFORE any routes are
# registered. FastAPI/Starlette applies middleware in reverse-registration
# order; adding it here, at the top, means it wraps the entire application
# and intercepts every request before it reaches any route handler.
app.add_middleware(
    PreviewGateMiddleware,
    enabled=settings.preview_mode_enabled,
)


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()
    await run_startup_migrations()
    # WHY: the Jinja2 global was set from the env var at module load time, before
    # the DB is available. Now that the DB is ready, load the admin-saved value
    # (if any) so a support_email change made via the admin UI survives a container
    # restart without needing to set the env var or re-save the settings page.
    from app.services.site_settings import get_support_email, get_ratings_min_review_count
    db_support_email = await get_support_email()
    templates.env.globals["support_email"] = db_support_email
    # WHY: load the DB-saved threshold (if any) at startup so a value set via
    # the admin settings page survives a container restart without needing to
    # touch the env var. Falls back to the module-load default of 20.
    templates.env.globals["ratings_min_review_count"] = await get_ratings_min_review_count()
    log.info("Indexes ensured. Tenant domains: %s", settings.parse_network_domains())


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
async def favicon() -> RedirectResponse:
    # WHY: browsers still probe these root paths even when the page points
    # at the SVG favicon; redirecting avoids noisy 404 console errors.
    return RedirectResponse(url="/assets/favicon.svg", status_code=308)


# Static assets are served at /assets so it doesn't conflict with /api or
# tenant-specific URL patterns.
# WHY: html=True enables directory-index serving — a request to /assets/walkthrough/
# returns /assets/walkthrough/index.html automatically, so the walkthrough landing
# page works at a clean URL without a separate route handler.
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="assets")

# JSON management API (tenant-agnostic — admins manage every network/city from
# any host). All write endpoints require ADMIN_API_KEY when configured.
app.include_router(api_networks.router, prefix="/api/v1")
app.include_router(api_cities.router, prefix="/api/v1")
app.include_router(api_neighborhoods.router, prefix="/api/v1")
app.include_router(api_categories.router, prefix="/api/v1")
app.include_router(api_businesses.router, prefix="/api/v1")
app.include_router(api_copy_blocks.router, prefix="/api/v1")
app.include_router(api_editorial.router, prefix="/api/v1")
app.include_router(api_claims.router, prefix="/api/v1")
app.include_router(api_inquiries.router, prefix="/api/v1")
app.include_router(api_owner_leads.router, prefix="/api/v1")
app.include_router(api_marketing_ai.router, prefix="/api/v1")
# Owner login (passwordless code-by-email). Public — no admin key required.
app.include_router(api_owner_login.router, prefix="/api/v1")
# Preview gate login API (email + 6-digit code). Public — no auth required
# because this IS the auth step for the preview gate.
app.include_router(api_preview_login.router, prefix="/api/v1")
# Owner profile editing — session-cookie-authenticated, no admin key.
# WHY: prefix omitted here because the router itself carries the full
# /api/v1/owner/profile prefix, unlike the other routers above which
# only carry the resource path and rely on the include_router prefix.
app.include_router(api_owner_profile.router)
# WHY: same full-prefix pattern as owner_profile — the router carries
# /api/v1/owner/inquiries internally so no prefix is passed here.
app.include_router(api_owner_inquiries.router)
# WHY: same full-prefix pattern — router carries /api/v1/owner/stats internally.
app.include_router(api_owner_stats.router)
# Stripe billing: checkout session creation + webhook receiver.
app.include_router(api_stripe_billing.router, prefix="/api/v1")
# Owner photo upload / delete — session-cookie-authenticated.
# WHY: same full-prefix pattern as owner_profile — the router carries
# /api/v1/owner/photos internally so no prefix is passed here.
app.include_router(api_owner_photos.router)
# Admin voice provisioning — admin-key-gated, triggers real VAPI API calls.
# WHY: prefix not passed here because the router carries /api/v1/admin/businesses
# internally (keeping all admin/businesses routes under one clear path).
app.include_router(api_admin_voice.router)
# Owner voice status — session-cookie-authenticated, read-only.
# WHY: same full-prefix pattern as owner_profile — the router carries
# /api/v1/owner/voice internally so no prefix is passed here.
app.include_router(api_owner_voice.router)


public_pages.attach_templates(templates)
claims_admin.attach_templates(templates)
analytics_admin.attach_templates(templates)
settings_admin.attach_templates(templates)
sync_admin.attach_templates(templates)
businesses_admin.attach_templates(templates)


@app.get("/preview-login", include_in_schema=False, response_class=HTMLResponse)
async def preview_login_page() -> HTMLResponse:
    """Serve the standalone preview login page.

    WHY: this page is intentionally standalone (does not extend base.html)
    because base.html requires a resolved tenant context (network/city), and
    the preview gate intercepts requests before tenant resolution happens.
    The template is a self-contained HTML document that includes reference.css
    directly so it matches the site's look without requiring tenant data.
    """
    tpl = templates.get_template("preview_login.html")
    content = tpl.render()
    return HTMLResponse(content=content)

# Admin HTML pages — registered BEFORE the public SSR catch-all so /admin/*
# resolves to the admin router rather than being swallowed by the public
# tenant-aware not-found handler.
app.include_router(claims_admin.router)
app.include_router(analytics_admin.router)
app.include_router(settings_admin.router)
app.include_router(sync_admin.router)
app.include_router(businesses_admin.router)

# WHY: media route is registered before the public SSR catch-all so /media/{id}
# is served by the GridFS streaming route and not handed to the 404 template.
app.include_router(public_media.router)

# WHY: the Featured-salon website badge (/badge/featured.svg) is registered
# before the public SSR catch-all so the explicit badge route handles it rather
# than the tenant-aware not-found handler. The preview-gate middleware exempts
# the /badge/ prefix so it loads on external salon sites even while preview mode
# is on.
app.include_router(public_badge.router)

# Public SSR routes (last, since they catch broad URL patterns).
app.include_router(public_pages.router)


@app.exception_handler(404)
async def handle_404(request: Request, exc):
    # Render a tenant-aware 404 when we have a recognized host.
    return await public_pages.render_not_found(request, templates)
