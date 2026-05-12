from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import ensure_indexes
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
)
from app.routes.public import pages as public_pages

settings = get_settings()
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Known Around Town", version="0.1.0")


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()
    log.info("Indexes ensured. Tenant domains: %s", settings.parse_network_domains())


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


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


public_pages.attach_templates(templates)

# Public SSR routes (last, since they catch broad URL patterns).
app.include_router(public_pages.router)


@app.exception_handler(404)
async def handle_404(request: Request, exc):
    # Render a tenant-aware 404 when we have a recognized host.
    return await public_pages.render_not_found(request, templates)
