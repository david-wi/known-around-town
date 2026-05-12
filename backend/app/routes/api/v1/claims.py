from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import BusinessClaim
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import now_utc, to_doc

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("")
async def submit_claim(body: BusinessClaim) -> Dict[str, Any]:
    """Public endpoint — anyone can submit a claim. Verification is manual or
    via a separate verification step (out of scope for the initial build)."""
    doc = to_doc(body)
    db = get_db()
    business = await db.businesses.find_one({"_id": doc["business_id"]})
    if not business:
        raise HTTPException(404, "Business not found")
    await db.business_claims.insert_one(doc)
    await db.businesses.update_one(
        {"_id": doc["business_id"]},
        {"$set": {"claim_status": "pending", "updated_at": now_utc()}},
    )
    return doc


@router.get("", dependencies=[Depends(require_admin)])
async def list_claims(
    business_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if business_id:
        q["business_id"] = business_id
    if status:
        q["status"] = status
    cur = get_db().business_claims.find(q).sort("submitted_at", -1)
    return await cur.to_list(length=500)


@router.post("/{claim_id}/verify", dependencies=[Depends(require_admin)])
async def verify_claim(claim_id: str) -> Dict[str, Any]:
    db = get_db()
    claim = await db.business_claims.find_one({"_id": claim_id})
    if not claim:
        raise HTTPException(404, "Claim not found")
    now = now_utc()
    await db.business_claims.update_one(
        {"_id": claim_id},
        {"$set": {"status": "verified", "verified_at": now}},
    )
    await db.businesses.update_one(
        {"_id": claim["business_id"]},
        {
            "$set": {
                "claim_status": "verified",
                "claimed_at": now,
                "verified_at": now,
                "updated_at": now,
            }
        },
    )
    return {"status": "verified"}
