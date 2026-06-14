"""Owner endpoint to check the Concierge voice receptionist status.

Route:
  GET /api/v1/owner/voice
    Auth: owner session cookie (same pattern as owner_profile, owner_stats, etc.)
    Returns: {"active": true, "phone_number": "(669) 232-8894"}
             or {"active": false} when no number is provisioned.

WHY: owners need to know their AI receptionist's phone number so they can
put it on their website, Google Business Profile, and marketing materials.
The admin provisions the number; the owner reads it here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.database import get_db
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

router = APIRouter(prefix="/api/v1/owner/voice")


@router.get("")
async def get_owner_voice(request: Request) -> dict:
    """Return the voice receptionist status for the signed-in owner's salon.

    Returns {"active": true, "phone_number": "..."} when a number has been
    provisioned, or {"active": false} when the Concierge tier is not active.
    """
    # WHY: HttpOnly session cookie — same auth pattern as owner_profile.py
    # so every owner endpoint behaves consistently.
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        session = verify_session(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session or not session.get("email"):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    # WHY: normalize to lowercase — claimed_email is stored lowercase (see
    # owner_profile.py for the same pattern).
    email: str = session["email"].lower()

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": email})
    if not business:
        raise HTTPException(status_code=404, detail="No business found for this account.")

    phone_number = business.get("voice_phone_number")
    if phone_number:
        return {"active": True, "phone_number": phone_number}
    return {"active": False}
