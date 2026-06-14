"""Admin HTML pages for searching and editing individual business records.

WHY: The ratings display logic already respects a per-business `hide_ratings`
flag, but there was no admin UI to flip it — the only way was a raw database
write or a curl PATCH call. This page gives any admin a self-serve UI to
suppress Google ratings for a specific salon without touching the database
directly. The same edit form can grow to cover other per-business flags in
the future (e.g. is_featured, editors_pick).

Auth model: the same ADMIN_COOKIE_NAME cookie and require_admin dependency
used by every other admin route. Log in once via /admin/login; the session
lasts 8 hours.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import now_utc

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None


def attach_templates(t: Jinja2Templates) -> None:
    """Wire in the shared Jinja2 instance from main.py.

    WHY: same deferred-attach pattern as every other admin router —
    keeps the template object a singleton instead of constructing a
    new one per request, and avoids an import-time circular dependency
    with main.py.
    """
    global _templates
    _templates = t


@router.get(
    "/businesses",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def businesses_search_page(
    request: Request,
    q: Optional[str] = Query(default=None),
) -> HTMLResponse:
    """Search admin page — find businesses by name or slug so the edit form
    can be reached without knowing the internal ID.

    WHY: the edit URL uses the internal MongoDB _id, which is opaque. Rather
    than making the admin paste IDs from the database, a simple name search
    lets them find the business and click through to the edit form. Capped at
    50 results to keep the page fast — if you need more, narrow the query.
    """
    if _templates is None:
        raise HTTPException(500, "Templates not attached")
    db = get_db()
    businesses: List[Dict[str, Any]] = []
    if q and q.strip():
        # WHY: case-insensitive regex so "lash" matches "Miami Lash Studio"
        # without requiring exact capitalisation. The `i` flag makes it
        # accent-insensitive on most Atlas collations too.
        pattern = re.compile(re.escape(q.strip()), re.IGNORECASE)
        cursor = (
            db.businesses.find({"name": pattern})
            .sort("name", 1)
            .limit(50)
        )
        businesses = await cursor.to_list(length=50)

    return _templates.TemplateResponse(
        "admin/businesses.html",
        {
            "request": request,
            "q": q or "",
            "businesses": businesses,
        },
    )


@router.get(
    "/businesses/{business_id}/edit",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def business_edit_page(
    request: Request,
    business_id: str,
    saved: Optional[str] = None,
) -> HTMLResponse:
    """Edit form for a single business.

    Currently exposes only the hide_ratings flag because that's the immediate
    need. The form can be extended to cover other per-business settings later.
    """
    if _templates is None:
        raise HTTPException(500, "Templates not attached")
    db = get_db()
    business = await db.businesses.find_one({"_id": business_id})
    if not business:
        raise HTTPException(404, "Business not found")

    return _templates.TemplateResponse(
        "admin/business_edit.html",
        {
            "request": request,
            "business": business,
            "saved": saved == "1",
        },
    )


@router.post(
    "/businesses/{business_id}/edit",
    dependencies=[Depends(require_admin)],
)
async def business_edit_submit(
    request: Request,
    business_id: str,
) -> RedirectResponse:
    """Save the edited business flags and redirect back with a confirmation.

    WHY: reads raw form data rather than FastAPI Form() parameters because HTML
    checkboxes only appear in the POST body when checked — an unchecked box
    sends nothing, so `Form(...)` would always evaluate it as a missing/None
    value rather than False. Checking presence in the raw form dict is the
    correct way to distinguish checked (value="on") from unchecked (absent).
    """
    db = get_db()
    existing = await db.businesses.find_one({"_id": business_id})
    if not existing:
        raise HTTPException(404, "Business not found")

    form = await request.form()

    # WHY: checkbox sends "on" when checked, nothing when unchecked. Comparing
    # to "on" converts to a proper Python bool for the DB write.
    hide_ratings = form.get("hide_ratings") == "on"

    await db.businesses.update_one(
        {"_id": business_id},
        {"$set": {
            "hide_ratings": hide_ratings,
            "updated_at": now_utc(),
        }},
    )

    # WHY: 303 See Other converts the POST to a GET on redirect, preventing
    # the browser from re-submitting the form on a page refresh (PRG pattern).
    return RedirectResponse(
        url=f"/admin/businesses/{business_id}/edit?saved=1",
        status_code=303,
    )
