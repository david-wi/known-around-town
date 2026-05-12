from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import EditorialGuide
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/editorial-guides", tags=["editorial"])


@router.get("")
async def list_guides(
    city_id: str = Query(...),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"city_id": city_id}
    if status:
        q["status"] = status
    cur = get_db().editorial_guides.find(q).sort("published_at", -1).limit(limit)
    return await cur.to_list(length=limit)


@router.get("/{guide_id}")
async def get_guide(guide_id: str) -> Dict[str, Any]:
    doc = await get_db().editorial_guides.find_one({"_id": guide_id})
    if not doc:
        raise HTTPException(404, "Editorial guide not found")
    return doc


@router.post("", dependencies=[Depends(require_admin)])
async def create_guide(body: EditorialGuide) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    if await db.editorial_guides.find_one(
        {"city_id": doc["city_id"], "slug": doc["slug"]}
    ):
        raise HTTPException(409, "Editorial guide slug already exists in this city")
    await db.editorial_guides.insert_one(doc)
    return doc


@router.patch("/{guide_id}", dependencies=[Depends(require_admin)])
async def update_guide(guide_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.editorial_guides.find_one({"_id": guide_id})
    if not existing:
        raise HTTPException(404, "Editorial guide not found")
    merged = merge_update(existing, patch)
    await db.editorial_guides.replace_one({"_id": guide_id}, merged)
    return merged


@router.delete("/{guide_id}", dependencies=[Depends(require_admin)])
async def archive_guide(guide_id: str) -> Dict[str, str]:
    res = await get_db().editorial_guides.update_one(
        {"_id": guide_id},
        {"$set": {"status": "archived", "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Editorial guide not found")
    return {"status": "archived"}
