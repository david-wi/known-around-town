"""Owner email capture endpoint.

Salon owners who visit /owners but aren't ready to claim can drop their
email address here. We store it once (idempotent on repeat submission)
and follow up with tips for getting their Miami salon found online.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.database import get_db

router = APIRouter(prefix="/owner-leads", tags=["owner-leads"])


class OwnerLeadCreate(BaseModel):
    email: EmailStr


@router.post("")
async def capture_owner_lead(body: OwnerLeadCreate) -> Dict[str, Any]:
    """Public endpoint — store an owner's email for follow-up nurture.

    Idempotent: submitting the same address twice returns ok without
    creating a duplicate record. The already_captured flag lets the
    caller distinguish a fresh capture from a repeat without an error.
    """
    db = get_db()
    existing = await db.owner_leads.find_one({"email": body.email})
    if existing:
        return {"ok": True, "already_captured": True}
    await db.owner_leads.insert_one(
        {
            "email": body.email,
            "source": "owners_page",
            # WHY: UTC timestamp so admin exports and future email tools
            # can sort / filter leads without timezone ambiguity.
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"ok": True}
