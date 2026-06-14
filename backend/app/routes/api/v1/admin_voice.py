"""Admin endpoints for VAPI voice provisioning — Concierge tier.

These are write operations that cost real money (buying a phone number from
Twilio via VAPI), so they are admin-gated and are never wired to any
owner-facing or automated Stripe flow. An admin must explicitly trigger
provisioning for each salon.

Routes:
  POST /api/v1/admin/businesses/{business_id}/provision-voice
    → creates the VAPI assistant + phone number and writes IDs to the DB.

  POST /api/v1/admin/businesses/{business_id}/deprovision-voice
    → deletes both VAPI resources and clears DB fields; downgrades to premium.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.routes.api.v1._auth import require_admin
from app.services.voice_provisioning import (
    deprovision_salon_receptionist,
    provision_salon_receptionist,
)

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/businesses",
    tags=["admin", "voice"],
    dependencies=[Depends(require_admin)],
)


@router.post("/{business_id}/provision-voice")
async def provision_voice(business_id: str) -> dict:
    """Buy a VAPI phone number and create an AI receptionist for this salon.

    Returns the provisioned phone number and VAPI resource IDs so the admin
    can confirm what was created and share the number with the salon owner.

    Costs money — each call buys a real Twilio phone number via VAPI.
    """
    db = get_db()
    try:
        result = await provision_salon_receptionist(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("VAPI provisioning failed for business %s", business_id)
        raise HTTPException(status_code=502, detail=f"VAPI provisioning failed: {e}")
    return {
        "ok": True,
        "phone_number": result["phone_number"],
        "assistant_id": result["assistant_id"],
        "phone_number_id": result["phone_number_id"],
    }


@router.post("/{business_id}/deprovision-voice")
async def deprovision_voice(business_id: str) -> dict:
    """Delete the VAPI receptionist and phone number for this salon.

    Clears the three voice fields from the salon record and downgrades the
    featured tier from Concierge back to Premium. Errors on the VAPI side
    (e.g. the resource was already deleted) are logged but do not fail the
    request — the DB fields are always cleared.
    """
    db = get_db()
    try:
        await deprovision_salon_receptionist(db, business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("VAPI deprovisioning failed for business %s", business_id)
        raise HTTPException(status_code=502, detail=f"VAPI deprovisioning failed: {e}")
    return {"ok": True}
