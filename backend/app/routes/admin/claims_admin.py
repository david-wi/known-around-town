"""Admin HTML page for reviewing and resolving pending business claims.

Why this page exists: today, verifying a salon's claim submission means
running a database update by hand. That bottlenecks the very first
design-partner onboarding (Miami Knows Beauty), since every claim needs
a developer. This page gives the product manager a self-serve UI to
approve or reject submissions without anyone touching the database.

Auth model: the same admin API key that already guards the JSON write
endpoints (the `ADMIN_API_KEY` env var). A small `/admin/login` route
swaps the key for an HttpOnly cookie so the admin doesn't have to paste
the key on every request, and so the verify/reject fetch calls from the
page can rely on the browser sending the cookie automatically rather
than embedding the raw key in JavaScript.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_db
from app.routes.api.v1._auth import ADMIN_COOKIE_NAME, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None


def attach_templates(t: Jinja2Templates) -> None:
    """Same pattern as the public pages router — wire in the Jinja2 instance
    after FastAPI has been constructed in main.py. Keeps the template object
    a singleton instead of constructing a new one per request."""
    global _templates
    _templates = t


# WHY: Cookie lifetime is intentionally short — one workday — so a forgotten
# laptop in a coffee shop doesn't leave the admin panel logged in forever.
# An admin who comes back tomorrow can log in again in five seconds.
_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 8  # 8 hours


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None) -> HTMLResponse:
    """Minimal login form that accepts the admin key and stores it in a cookie."""
    if _templates is None:
        raise HTTPException(500, "Templates not attached")
    return _templates.TemplateResponse(
        request,
        "admin/login.html",
        {"request": request, "error": error},
    )


@router.post("/login")
async def login_submit(api_key: str = Form(...)) -> RedirectResponse:
    """Validate the submitted key against ADMIN_API_KEY, then set the cookie.

    Wrong key -> redirect back to the login form with an error flag.
    Right key (or no key configured, i.e. local dev) -> set cookie and
    redirect to the claims page.
    """
    expected = get_settings().admin_api_key
    if expected and api_key != expected:
        # WHY: 303 makes the browser issue a GET for /admin/login?error=1
        # so a refresh doesn't re-POST. Standard PRG (post/redirect/get).
        return RedirectResponse(
            url="/admin/login?error=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    resp = RedirectResponse(url="/admin/claims", status_code=status.HTTP_303_SEE_OTHER)
    # WHY: HttpOnly so client-side JavaScript can't read the key (defense in
    # depth against XSS exfiltrating it). secure=True so the cookie is only
    # ever sent over HTTPS — production (knowsbeauty.com / *.devintensive.com)
    # and stage are both HTTPS-only behind Traefik, so this is correct.
    # Browsers also allow secure cookies on `http://localhost` for dev.
    resp.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=api_key,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return resp


@router.post("/logout")
async def logout() -> RedirectResponse:
    """Clear the admin cookie. Useful when handing off a shared workstation."""
    resp = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie(ADMIN_COOKIE_NAME)
    return resp


@router.get(
    "/claims",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def pending_claims_page(request: Request) -> HTMLResponse:
    """List every pending business claim, newest first, with verify/reject buttons.

    Each row shows the business name (linking to the public listing), who
    submitted the claim, how to reach them, when they submitted, and any
    notes they left. The Verify and Reject buttons call the existing JSON
    endpoints via fetch and remove the row on success.
    """
    if _templates is None:
        raise HTTPException(500, "Templates not attached")
    db = get_db()
    # Sort newest-first so the freshest submissions are at the top.
    claims: List[Dict[str, Any]] = await (
        db.business_claims.find({"status": "pending"})
        .sort("submitted_at", -1)
        .to_list(length=500)
    )
    # Pull the businesses each claim points at in a single query so the
    # template can render the business name and a link without N+1 lookups.
    biz_ids = list({c["business_id"] for c in claims if c.get("business_id")})
    businesses_by_id: Dict[str, Dict[str, Any]] = {}
    if biz_ids:
        biz_cur = db.businesses.find({"_id": {"$in": biz_ids}})
        from app.services.tenant import build_absolute_business_url
        async for b in biz_cur:
            b["public_url"] = await build_absolute_business_url(request, b)
            businesses_by_id[b["_id"]] = b

    return _templates.TemplateResponse(
        request,
        "admin/claims.html",
        {
            "request": request,
            "claims": claims,
            "businesses_by_id": businesses_by_id,
        },
    )
