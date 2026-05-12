from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import BusinessInquiry
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import to_doc

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


@router.post("")
async def submit_inquiry(body: BusinessInquiry) -> Dict[str, Any]:
    """Public endpoint — visitors send a lead/contact message to a business."""
    doc = to_doc(body)
    db = get_db()
    if not await db.businesses.find_one({"_id": doc["business_id"]}):
        raise HTTPException(404, "Business not found")
    await db.business_inquiries.insert_one(doc)
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
