"""Admin web page for managing site-wide settings.

Gives the operator (David / Posey) a point-and-click interface to toggle
feature flags and other site settings without needing SSH or command-line
access to the production server.

Auth: same ADMIN_COOKIE_NAME cookie and require_admin dependency used by
all admin routes. Log in once via /admin/login and the session lasts 8 hours.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.routes.api.v1._auth import require_admin
from app.services.site_settings import get_all_site_settings, get_marketing_ai_enabled, update_site_settings

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None


def attach_templates(t: Jinja2Templates) -> None:
    """Wire in the shared Jinja2 instance from main.py."""
    global _templates
    _templates = t


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    saved: Optional[str] = None,
    _admin=Depends(require_admin),
) -> HTMLResponse:
    """Render the settings page with current values."""
    if _templates is None:
        raise HTTPException(500, "Templates not attached")

    marketing_ai_enabled = await get_marketing_ai_enabled()

    return _templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "marketing_ai_enabled": marketing_ai_enabled,
            "saved": saved == "1",
        },
    )


@router.post("/settings")
async def update_settings(
    request: Request,
    _admin=Depends(require_admin),
) -> RedirectResponse:
    """Save updated settings and redirect back.

    WHY: reads the raw form data rather than using FastAPI Form() parameters.
    HTML checkboxes only appear in the POST body when checked — unchecked
    boxes send nothing. Checking presence in the raw form dict is the
    correct way to distinguish checked from unchecked.
    """
    form = await request.form()
    marketing_ai_enabled = form.get("marketing_ai_enabled") == "on"

    await update_site_settings({"marketing_ai_enabled": marketing_ai_enabled})

    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)
