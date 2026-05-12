"""Shared helpers for seed scripts."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db


async def upsert(collection_name: str, query: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db[collection_name].find_one(query)
    if existing:
        # Preserve _id and created_at on update, refresh everything else.
        doc = {**doc, "_id": existing["_id"], "created_at": existing.get("created_at", doc.get("created_at"))}
        await db[collection_name].replace_one({"_id": existing["_id"]}, doc)
        return doc
    await db[collection_name].insert_one(doc)
    return doc


def category_groups(rows: List[Dict[str, Any]], order_start: int = 0) -> List[Dict[str, Any]]:
    """Normalize the raw category map definitions into Pydantic-friendly dicts."""
    out = []
    for i, r in enumerate(rows):
        out.append(
            {
                "slug": r["slug"],
                "name": r["name"],
                "description": r.get("description"),
                "examples": r.get("examples", []),
                "order": order_start + i,
                "sub_categories": [],
            }
        )
    return out


def run(coro):
    asyncio.run(coro)
