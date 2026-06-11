from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import ensure_indexes, run_startup_migrations
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
    owner_leads as api_owner_leads,
    owner_inquiries as api_owner_inquiries,
    owner_profile as api_owner_profile,
    owner_photos as api_owner_photos,
    owner_stats as api_owner_stats,
    stripe_billing as api_stripe_billing,
)
from app.routes.admin import claims_admin, analytics_admin
from app.routes.public import pages as public_pages, media as public_media

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Known Around Town", version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()
    await run_startup_migrations()
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
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "static")), name="assets")

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


public_pages.attach_templates(templates)
claims_admin.attach_templates(templates)
analytics_admin.attach_templates(templates)

# Admin HTML pages — registered BEFORE the public SSR catch-all so /admin/*
# resolves to the admin router rather than being swallowed by the public
# tenant-aware not-found handler.
app.include_router(claims_admin.router)
app.include_router(analytics_admin.router)

# WHY: media route is registered before the public SSR catch-all so /media/{id}
# is served by the GridFS streaming route and not handed to the 404 template.
app.include_router(public_media.router)

# Public SSR routes (last, since they catch broad URL patterns).
app.include_router(public_pages.router)


@app.exception_handler(404)
async def handle_404(request: Request, exc):
    # Render a tenant-aware 404 when we have a recognized host.
    return await public_pages.render_not_found(request, templates)
