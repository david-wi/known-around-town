import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.database import get_db
from app.models import BusinessInquiry
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import to_doc
from app.services.owner_email import send_admin_inquiry_email, send_owner_inquiry_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inquiries", tags=["inquiries"])


def _dashboard_url() -> str:
    # WHY: read from canonical_base_url at call time so the link in owner
    # emails uses the public hostname (miami.knowsbeauty.com) rather than
    # the Docker-internal dev domain.  A module-level constant baked the
    # dev URL into every inquiry notification sent in production.
    base = (get_settings().canonical_base_url or "https://miami.knowsbeauty.com").rstrip("/")
    return f"{base}/owners/me"


async def _notify_about_inquiry(business: Dict[str, Any], doc: Dict[str, Any]) -> None:
    """Fire email notifications after an inquiry is saved.

    For claimed businesses we email the owner directly so they can reply
    while the visitor is still engaged.  For unclaimed businesses we alert
    admin — the inquiry is evidence the salon should claim their listing.
    """
    db = get_db()
    business_id = doc["business_id"]
    business_name = business.get("name", "your business")
    visitor_name = doc.get("name", "A visitor")
    visitor_email: Optional[str] = doc.get("email")
    visitor_phone: Optional[str] = doc.get("phone")
    message = doc.get("message", "")

    # Primary: look up the most-recently-used owner session for this business.
    owner_email: Optional[str] = None
    session = await db.owner_sessions.find_one(
        {"business_id": business_id},
        sort=[("last_used_at", -1)],
    )
    if session:
        owner_email = session.get("email")

    # Fallback: the verified claim record holds the submitter's email.
    if not owner_email:
        claim = await db.business_claims.find_one(
            {"business_id": business_id, "status": "verified"},
            sort=[("verified_at", -1)],
        )
        if claim:
            owner_email = claim.get("submitter_email")

    if owner_email:
        await send_owner_inquiry_email(
            owner_email=owner_email,
            business_name=business_name,
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
            message=message,
            dashboard_url=_dashboard_url(),
        )
    else:
        await send_admin_inquiry_email(
            business_name=business_name,
            business_id=business_id,
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
            message=message,
        )


@router.post("")
async def submit_inquiry(body: BusinessInquiry) -> Dict[str, Any]:
    """Public endpoint — visitors send a lead/contact message to a business."""
    doc = to_doc(body)
    db = get_db()
    business = await db.businesses.find_one({"_id": doc["business_id"]})
    if not business:
        raise HTTPException(404, "Business not found")
    await db.business_inquiries.insert_one(doc)
    # WHY: fire-and-forget — email failure must never block the visitor's
    # submission.  The inquiry is saved to the DB; the owner will see it in
    # their dashboard even if the email doesn't arrive.
    try:
        await _notify_about_inquiry(business, doc)
    except Exception:
        logger.exception(
            "Failed to send inquiry notification for business %s", doc["business_id"]
        )
    return doc


@router.get("", dependencies=[Depends(require_admin)])
async def list_inquiries(
    business_id: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=1000),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if business_id:
        q["business_id"] = business_id
    cur = (
        get_db().business_inquiries.find(q).sort("submitted_at", -1).limit(limit)
    )
    return await cur.to_list(length=limit)
