"""Owner profile update endpoint.

Lets a signed-in salon owner update the public-facing fields of their
own business listing. Only the editable fields are accepted; name,
slug, network membership, and admin-only fields are never touched by
this endpoint.

Route: PATCH /api/v1/owner/profile
Auth:  session cookie set by the owner login flow
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

router = APIRouter(prefix="/api/v1/owner/profile")

# WHY: a sparse regular expression rather than a full RFC-5322 parser.
# We only want to catch obvious non-emails (missing @, missing dot after @)
# before writing to the DB. Strict validation is done at the application
# layer when the email is displayed or used for communication.
_SIMPLE_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# WHY: 24-hour HH:MM format mirrors what HTML <input type="time"> always
# emits ("09:00", "17:30") and what schema.org OpeningHoursSpecification
# expects — no conversion layer needed between form, DB, and JSON-LD.
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})


class HoursEntry(BaseModel):
    # WHY: three-letter lowercase code (mon–sun) matches the schema.org
    # day abbreviations in the JSON-LD template so no mapping layer is
    # needed between the stored value and the structured-data renderer.
    day: str = Field(max_length=10)
    opens_at: Optional[str] = Field(None, max_length=5)   # "09:00"
    closes_at: Optional[str] = Field(None, max_length=5)  # "18:00"
    closed: bool = False

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        if v not in _VALID_DAYS:
            raise ValueError("Day must be one of: mon, tue, wed, thu, fri, sat, sun")
        return v

    @field_validator("opens_at", "closes_at", mode="before")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v and not _TIME_RE.match(v):
            raise ValueError("Time must be in HH:MM 24-hour format, e.g. 09:00")
        return v or None


class ServiceEntry(BaseModel):
    name: str = Field(max_length=100)
    # WHY: free-text price display (e.g. "$45+" or "From $80") rather than
    # a numeric float so owners can express ranges and minimums the natural
    # way they communicate pricing. Stored in `price` — the field the public
    # business template already renders as `s.price`.
    price: Optional[str] = Field(None, max_length=50)


class OwnerProfileUpdate(BaseModel):
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = Field(None, max_length=254)
    description: Optional[str] = Field(None, max_length=1000)
    # WHY: capped at 7 — one entry per day of the week. The form renders a
    # fixed 7-row grid so there can never be more than one entry per day.
    hours: Optional[list[HoursEntry]] = Field(None, max_length=7)
    # WHY: capped at 30 — a reasonable upper bound for a salon's service
    # menu that prevents a malformed client from bloating the document.
    services: Optional[list[ServiceEntry]] = Field(None, max_length=30)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        # Empty string means "clear the field" — pass it through.
        if v and not _SIMPLE_EMAIL_RE.match(v):
            raise ValueError("Invalid email address.")
        return v

    @field_validator("website")
    @classmethod
    def validate_website_format(cls, v: Optional[str]) -> Optional[str]:
        # Empty string means "clear the field" — pass it through.
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Website must start with http:// or https://")
        return v


# Fields that owners may update. All other fields (name, slug, admin flags,
# Stripe ids, etc.) are never touched by this endpoint.
_OWNER_SAFE_FIELDS = {"phone", "website", "email", "description", "hours", "services"}


def _safe_response(doc: dict) -> dict:
    """Return only the owner-visible subset of a business document.

    WHY: The raw business document contains internal fields (claimed_email,
    admin notes, Stripe ids) that must not be exposed to the browser. We
    return only what the owner's edit form needs.
    """
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "slug": doc.get("slug"),
        "phone": doc.get("phone"),
        "website": doc.get("website"),
        "email": doc.get("email"),
        "description": doc.get("description"),
        "hours": doc.get("hours"),
        "services": doc.get("services"),
        "updated_at": doc.get("updated_at"),
    }


@router.patch("")
async def update_owner_profile(payload: OwnerProfileUpdate, request: Request) -> dict:
    """Update the signed-in owner's business listing.

    Only fields explicitly provided in the request body are written;
    omitted (None) fields are left unchanged. Empty strings are written
    as-is so owners can clear a field they previously set.
    """
    # WHY: Read from cookie rather than a Bearer token so the endpoint
    # is consistent with the rest of the owner-portal auth model, which
    # uses an HttpOnly cookie to prevent JavaScript access.
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        session = verify_session(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    if not session or not session.get("email"):
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    # WHY: normalize to lowercase so owners can log in with any capitalisation
    # of their email and still find their salon (claimed_email is written
    # lowercase at claim-approval time in claims.py).
    email: str = session["email"].lower()

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": email})
    if not business:
        raise HTTPException(status_code=404, detail="No business found for this account.")

    # Build update dict from only the fields the caller actually supplied.
    # WHY: exclude_none=True means a PATCH that only sends {"phone": "555"}
    # will not overwrite the other fields. Empty strings are NOT excluded —
    # they represent an explicit "clear this field" intent from the owner.
    updates: dict = {
        k: v
        for k, v in payload.model_dump(exclude_none=True).items()
        if k in _OWNER_SAFE_FIELDS
    }

    if not updates:
        return _safe_response(business)

    updates["updated_at"] = datetime.now(timezone.utc)

    await db.businesses.update_one(
        {"_id": business["_id"]},
        {"$set": updates},
    )

    # Re-fetch so the response reflects exactly what is now in the DB.
    updated = await db.businesses.find_one({"_id": business["_id"]})
    if updated is None:
        # Should never happen immediately after a successful update.
        raise HTTPException(status_code=500, detail="Failed to retrieve updated business.")

    return _safe_response(updated)
