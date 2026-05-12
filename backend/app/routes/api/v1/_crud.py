"""Shared CRUD helpers — every collection has the same shape, so we factor
the boilerplate out and let the per-resource modules just wire the bits."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException
from pydantic import BaseModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_doc(model: BaseModel) -> Dict[str, Any]:
    """Pydantic -> Mongo doc using `_id` (not `id`)."""
    doc = model.model_dump(by_alias=True)
    # Normalize enums to their string values for Mongo storage.
    for k, v in list(doc.items()):
        if hasattr(v, "value"):
            doc[k] = v.value
    return doc


def from_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the doc as-is — Mongo already has `_id` as a string UUID."""
    return doc


async def find_or_404(collection, query: Dict[str, Any]) -> Dict[str, Any]:
    doc = await collection.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


def merge_update(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow merge of patch into existing, dropping None values from patch."""
    out = dict(existing)
    for k, v in patch.items():
        if v is not None:
            out[k] = v
    out["updated_at"] = now_utc()
    return out
