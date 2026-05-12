from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.models import CopyBlock
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import merge_update, to_doc

router = APIRouter(prefix="/copy-blocks", tags=["copy-blocks"])


@router.get("")
async def list_copy_blocks(
    scope_type: Optional[str] = Query(default=None),
    network_id: Optional[str] = Query(default=None),
    city_id: Optional[str] = Query(default=None),
    business_id: Optional[str] = Query(default=None),
    key_prefix: Optional[str] = Query(default=None),
    limit: int = Query(default=500, le=2000),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if scope_type:
        q["scope_type"] = scope_type
    if network_id:
        q["scope_ref.network_id"] = network_id
    if city_id:
        q["scope_ref.city_id"] = city_id
    if business_id:
        q["scope_ref.business_id"] = business_id
    if key_prefix:
        q["key"] = {"$regex": f"^{key_prefix}"}
    cur = get_db().copy_blocks.find(q).sort("key", 1).limit(limit)
    return await cur.to_list(length=limit)


@router.post("", dependencies=[Depends(require_admin)])
async def upsert_copy_block(body: CopyBlock) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    existing = await db.copy_blocks.find_one(
        {
            "scope_type": doc["scope_type"],
            "scope_ref": doc["scope_ref"],
            "key": doc["key"],
            "locale": doc["locale"],
        }
    )
    if existing:
        merged = merge_update(existing, {"value": doc["value"], "notes": doc.get("notes")})
        await db.copy_blocks.replace_one({"_id": existing["_id"]}, merged)
        return merged
    await db.copy_blocks.insert_one(doc)
    return doc


@router.delete("/{copy_block_id}", dependencies=[Depends(require_admin)])
async def delete_copy_block(copy_block_id: str) -> Dict[str, str]:
    res = await get_db().copy_blocks.delete_one({"_id": copy_block_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Copy block not found")
    return {"status": "deleted"}
