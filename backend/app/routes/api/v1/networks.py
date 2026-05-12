from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import Network
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/networks", tags=["networks"])


@router.get("")
async def list_networks() -> List[Dict[str, Any]]:
    cur = get_db().networks.find({}).sort("name", 1)
    return await cur.to_list(length=200)


@router.get("/{slug}")
async def get_network(slug: str) -> Dict[str, Any]:
    doc = await get_db().networks.find_one({"slug": slug})
    if not doc:
        raise HTTPException(404, "Network not found")
    return doc


@router.post("", dependencies=[Depends(require_admin)])
async def create_network(body: Network) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    existing = await db.networks.find_one({"slug": doc["slug"]})
    if existing:
        raise HTTPException(409, f"Network '{doc['slug']}' already exists")
    await db.networks.insert_one(doc)
    return doc


@router.patch("/{slug}", dependencies=[Depends(require_admin)])
async def update_network(slug: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.networks.find_one({"slug": slug})
    if not existing:
        raise HTTPException(404, "Network not found")
    merged = merge_update(existing, patch)
    await db.networks.replace_one({"_id": existing["_id"]}, merged)
    return merged


@router.delete("/{slug}", dependencies=[Depends(require_admin)])
async def archive_network(slug: str) -> Dict[str, str]:
    db = get_db()
    res = await db.networks.update_one(
        {"slug": slug}, {"$set": {"status": "archived", "updated_at": now_utc()}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Network not found")
    return {"status": "archived"}
