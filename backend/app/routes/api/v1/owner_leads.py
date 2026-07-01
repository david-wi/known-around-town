"""Owner email capture endpoint.

Salon owners who visit /owners but aren't ready to claim can drop their
email address here. We store it once (idempotent on repeat submission)
and follow up with tips for getting their Miami salon found online.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.services.rate_limit import (
    OWNER_LEAD_MAX_PER_WINDOW,
    client_ip,
    enforce_ip_rate_limit,
)

router = APIRouter(prefix="/owner-leads", tags=["owner-leads"])


class OwnerLeadCreate(BaseModel):
    email: EmailStr


@router.post("")
async def capture_owner_lead(body: OwnerLeadCreate, request: Request) -> Dict[str, Any]:
    """Public endpoint — store an owner's email for follow-up nurture.

    Idempotent: submitting the same address twice returns ok without
    creating a duplicate record. The already_captured flag lets the
    caller distinguish a fresh capture from a repeat without an error.
    """
    db = get_db()
    existing = await db.owner_leads.find_one({"email": body.email})
    if existing:
        return {"ok": True, "already_captured": True}

    # WHY: cap how many distinct owner-lead emails one client IP can drop in the
    # recent window so a script can't pack the nurture list with junk addresses.
    # The idempotent repeat check above stays first because a repeat creates no
    # new side effect and should not block a genuine owner who refreshes or
    # retries after their address was already captured.
    ip = client_ip(request)
    await enforce_ip_rate_limit(
        db=db,
        collection="owner_leads",
        ip=ip,
        max_events=OWNER_LEAD_MAX_PER_WINDOW,
    )
    await db.owner_leads.insert_one(
        {
            "email": body.email,
            "source": "owners_page",
            "submit_ip": ip,
            # WHY: UTC timestamp so admin exports and future email tools
            # can sort / filter leads without timezone ambiguity.
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"ok": True}
