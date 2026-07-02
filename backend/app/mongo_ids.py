"""Helpers for matching Mongo ``_id`` values that may be UUID strings or
legacy BSON ObjectIds.

WHY this module exists: businesses imported before the UUID migration have BSON
ObjectId ``_id`` values, while every newer record uses a UUID string. Requests
and templates always carry the *string* form (``str(_id)``), so a plain
``find_one({"_id": <str>})`` never matches the ObjectId-keyed records. That
silently broke the public claim flow, inquiries, and admin edits for those
businesses (a large share of listings in some cities). Centralising the
dual-lookup here — instead of re-inlining the try/except at every call site —
keeps every business lookup safe and consistent.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


def business_id_value(business_id: str) -> Any:
    """Return the value to match a business ``_id`` on, tolerant of legacy ids.

    A 24-hex-character string is interpreted as an ObjectId (matching the
    pre-migration records); anything else (e.g. a UUID string) is returned
    unchanged so string-keyed records still match. Mirrors the dual-lookup
    already inlined in ``marketing_ai`` and ``monthly_report_admin``.
    """
    try:
        return ObjectId(business_id)
    except (InvalidId, TypeError):
        return business_id
