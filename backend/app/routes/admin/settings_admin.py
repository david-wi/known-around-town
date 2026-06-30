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
from app.services.site_settings import (
    get_google_site_verification,
    get_marketing_ai_enabled,
    get_preview_mode_enabled,
    get_ratings_min_review_count,
    get_support_email,
    update_site_settings,
)

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
    preview_mode_enabled = await get_preview_mode_enabled()
    google_site_verification = await get_google_site_verification()
    support_email = await get_support_email()
    ratings_min_review_count = await get_ratings_min_review_count()

    return _templates.TemplateResponse(
        request,
        "admin/settings.html",
        {
            "request": request,
            "marketing_ai_enabled": marketing_ai_enabled,
            "preview_mode_enabled": preview_mode_enabled,
            "google_site_verification": google_site_verification,
            "support_email": support_email,
            "ratings_min_review_count": ratings_min_review_count,
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
    # WHY: preview_mode toggle uses the same checkbox convention — present means
    # "private (preview on)", absent means "public (preview off)".
    preview_mode_enabled = form.get("preview_mode_enabled") == "on"
    # WHY: strip whitespace so a stray space in the pasted GSC code doesn't
    # silently break verification (Google requires an exact match). Storing
    # None (not "") when blank lets update_site_settings $unset the field so
    # the env-var default kicks in — an empty string in the DB would override
    # the default and expose a broken (empty) value everywhere on the site.
    google_site_verification = str(form.get("google_site_verification") or "").strip() or None
    # WHY: same reasoning — blank input means "use the default address", not
    # "set the support email to nothing".
    support_email = str(form.get("support_email") or "").strip() or None
    # WHY: ratings_min_review_count is stored as an int. Blank input means
    # "use the default of 20", so we $unset the DB key and the service falls
    # back. Invalid (non-numeric) input is silently ignored by the int() cast
    # with a try/except, keeping the existing DB value unchanged.
    _rc_raw = str(form.get("ratings_min_review_count") or "").strip()
    try:
        ratings_min_review_count: Optional[int] = int(_rc_raw) if _rc_raw else None
        # WHY: clamp to a sensible range (1–10000) so a typo can't set the
        # threshold to 0 (shows every 1-review business) or a billion.
        if ratings_min_review_count is not None and not (1 <= ratings_min_review_count <= 10000):
            ratings_min_review_count = None
    except (ValueError, TypeError):
        ratings_min_review_count = None

    await update_site_settings({
        "marketing_ai_enabled": marketing_ai_enabled,
        "preview_mode_enabled": preview_mode_enabled,
        "google_site_verification": google_site_verification,
        "support_email": support_email,
        "ratings_min_review_count": ratings_min_review_count,
    })

    # WHY: the Jinja2 globals were set at startup from DB/env values.
    # When the admin saves new values, we update the globals in-process so
    # templates on the NEXT request immediately reflect the changes — no
    # container restart required.
    if _templates is not None:
        from app.config import get_settings as _get_settings
        _templates.env.globals["support_email"] = (
            support_email or _get_settings().support_email
        )
        # WHY: refresh the in-process Jinja2 global so the new threshold
        # takes effect immediately without a restart. Fall back to 20 if
        # the field was cleared (None = use the service default).
        _templates.env.globals["ratings_min_review_count"] = (
            ratings_min_review_count if ratings_min_review_count is not None else 20
        )

    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)
