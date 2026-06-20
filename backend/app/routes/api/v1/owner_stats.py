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
        # WHY: projection limits the fields fetched from Atlas — we only need the
        # activity counters, not the full document (photos, hours, socials, etc.)
        projection={
            "page_view_count": 1,
            "mkb_referred_view_count": 1,
            "call_click_count": 1,
            "directions_click_count": 1,
            "website_click_count": 1,
        },
    )
    if not business:
        raise HTTPException(status_code=404, detail="No business found for this account.")

    # WHY: the three shopper-action counts (taps to call / directions / website)
    # are the highest-intent "your listing is working" signals — a tap to call is
    # a far stronger renewal argument than a passive page view. Each defaults to 0
    # for listings that predate the counters or haven't been tapped yet.
    return {
        "page_view_count": business.get("page_view_count") or 0,
        # WHY: of the total page views, how many came from within Miami Knows
        # Beauty itself (a guide, on-site search, a category/neighborhood page,
        # or a sister listing). This is the number that proves WE drove the
        # traffic — the distinction a salon's free Google profile can't show.
        # Defaults to 0 for listings that predate the counter or have only had
        # external/typed visits.
        "mkb_referred_view_count": business.get("mkb_referred_view_count") or 0,
        "call_click_count": business.get("call_click_count") or 0,
        "directions_click_count": business.get("directions_click_count") or 0,
        "website_click_count": business.get("website_click_count") or 0,
    }
