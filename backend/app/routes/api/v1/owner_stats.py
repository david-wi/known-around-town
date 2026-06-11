"""Owner listing stats endpoint.

Returns performance metrics for the signed-in salon owner's listing —
currently just page view count, designed to expand as we add more signals.

Route: GET /api/v1/owner/stats
Auth:  session cookie set by the owner login flow
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.database import get_db
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

router = APIRouter(prefix="/api/v1/owner/stats")


@router.get("")
async def get_owner_stats(request: Request) -> dict:
    """Return listing performance stats for the signed-in owner's business.

    WHY: page_view_count is the most concrete ROI signal we can give an owner —
    "your listing has been seen N times" is more convincing than any abstract
    benefit statement when they are deciding whether to renew their subscription.
    """
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        session = verify_session(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session or not session.get("email"):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    # WHY: lowercase to match how claimed_email is stored — consistent with
    # owner_profile.py and owner_inquiries.py so any capitalisation works.
    email: str = session["email"].lower()
    db = get_db()

    business = await db.businesses.find_one(
        {"claimed_email": email},
        # WHY: projection limits the fields fetched from Atlas — we only need
        # page_view_count, not the full document (photos, hours, socials, etc.)
        projection={"page_view_count": 1},
    )
    if not business:
        raise HTTPException(status_code=404, detail="No business found for this account.")

    return {
        "page_view_count": business.get("page_view_count") or 0,
    }
