from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import City
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, now_utc, to_doc

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("")
async def list_cities(
    network_slug: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    db = get_db()
    q: Dict[str, Any] = {}
    if network_slug:
        network = await db.networks.find_one({"slug": network_slug})
        if not network:
            return []
        q["network_id"] = network["_id"]
    cur = db.cities.find(q).sort("name", 1)
    return await cur.to_list(length=500)


@router.get("/{network_slug}/{city_slug}")
async def get_city(network_slug: str, city_slug: str) -> Dict[str, Any]:
    db = get_db()
    network = await db.networks.find_one({"slug": network_slug})
    if not network:
        raise HTTPException(404, "Network not found")
    city = await db.cities.find_one({"network_id": network["_id"], "slug": city_slug})
    if not city:
        raise HTTPException(404, "City not found")
    return city


@router.post("", dependencies=[Depends(require_admin)])
async def create_city(body: City) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    network = await db.networks.find_one({"_id": doc["network_id"]})
    if not network:
        raise HTTPException(404, "Network not found")
    existing = await db.cities.find_one(
        {"network_id": doc["network_id"], "slug": doc["slug"]}
    )
    if existing:
        raise HTTPException(409, "City already exists in this network")
    await db.cities.insert_one(doc)
    return doc


@router.patch("/{city_id}", dependencies=[Depends(require_admin)])
async def update_city(city_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db.cities.find_one({"_id": city_id})
    if not existing:
        raise HTTPException(404, "City not found")
    merged = merge_update(existing, patch)
    await db.cities.replace_one({"_id": city_id}, merged)
    return merged


@router.delete("/{city_id}", dependencies=[Depends(require_admin)])
async def archive_city(city_id: str) -> Dict[str, str]:
    res = await get_db().cities.update_one(
        {"_id": city_id}, {"$set": {"status": "archived", "updated_at": now_utc()}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "City not found")
    return {"status": "archived"}
