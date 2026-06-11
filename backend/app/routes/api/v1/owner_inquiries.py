"""Owner inquiry list endpoint.

Lets a signed-in salon owner see the contact messages that visitors have
submitted through their public listing page (via the "Contact this salon"
form on the business detail page).

Route: GET /api/v1/owner/inquiries
Auth:  session cookie set by the owner login flow
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from app.database import get_db
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

router = APIRouter(prefix="/api/v1/owner/inquiries")

# WHY: cap at 100 — owners rarely have more than a handful of leads; this
# avoids unbounded queries without needing pagination on the first version.
_INQUIRY_LIMIT = 100


@router.get("")
async def list_owner_inquiries(request: Request) -> List[Dict[str, Any]]:
    """Return contact inquiries submitted for the signed-in owner's business.

    Returns them newest-first so the owner immediately sees the most recent
    leads without scrolling.
    """
    # WHY: same cookie-based auth as owner_profile.py — HttpOnly cookie
    # prevents JavaScript from reading the token directly, consistent with
    # the rest of the owner-portal auth model.
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        session = verify_session(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session or not session.get("email"):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    # WHY: lowercase to match how claimed_email is stored at claim-approval
    # time — same normalisation as owner_profile.py so any capitalisation
    # the owner used when logging in still finds their salon.
    email: str = session["email"].lower()
    db = get_db()

    business = await db.businesses.find_one({"claimed_email": email})
    if not business:
        raise HTTPException(status_code=404, detail="No business found for this account.")

    cur = (
        db.business_inquiries
        .find({"business_id": str(business["_id"])})
        .sort("submitted_at", -1)
        .limit(_INQUIRY_LIMIT)
    )
    return await cur.to_list(length=_INQUIRY_LIMIT)
