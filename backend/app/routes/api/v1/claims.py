import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import quote as _url_quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import get_settings
from app.database import get_db
from app.models import BusinessClaim
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import now_utc, to_doc
from app.services.owner_email import (
    send_admin_new_claim_email,
    send_claim_confirmation_email,
    send_claim_rejected_email,
    send_claim_verified_email,
)

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("")
async def submit_claim(body: BusinessClaim, request: Request) -> Dict[str, Any]:
    """Public endpoint — anyone can submit a claim. Verification is manual."""
    doc = to_doc(body)
    db = get_db()
    business = await db.businesses.find_one({"_id": doc["business_id"]})
    if not business:
        raise HTTPException(404, "Business not found")
    # WHY: guard against overwriting a verified (paying subscriber) or
    # already-pending claim.  Without this check any visitor can submit a
    # new claim and unconditionally flip claim_status to "pending", which
    # immediately locks the verified owner out of their dashboard (the
    # dashboard checks claim_status == "verified" to grant access).
    current_status = business.get("claim_status")
    if current_status == "verified":
        raise HTTPException(
            409,
            "This listing has already been claimed. Contact hello@knowsbeauty.com if you believe this is an error.",
        )
    if current_status == "pending":
        raise HTTPException(
            409,
            "A claim for this listing is already under review.",
        )
    await db.business_claims.insert_one(doc)
    await db.businesses.update_one(
        {"_id": doc["business_id"]},
        {"$set": {"claim_status": "pending", "updated_at": now_utc()}},
    )
    # WHY: use canonical_base_url so the admin link in the notification email
    # points at the public hostname, not the Docker-internal address that
    # request.base_url returns when the app runs behind nginx.
    admin_url = (get_settings().canonical_base_url or str(request.base_url)).rstrip("/") + "/admin/claims"
    # WHY: fire-and-forget so slow or failed email sends never block the
    # API response — the claim is already saved.  Both emails swallow errors.
    asyncio.create_task(
        send_claim_confirmation_email(
            email=doc.get("submitter_email", ""),
            submitter_name=doc.get("submitter_name", ""),
            business_name=business.get("name", "your business"),
        )
    )
    asyncio.create_task(
        send_admin_new_claim_email(
            submitter_name=doc.get("submitter_name", ""),
            submitter_email=doc.get("submitter_email", ""),
            business_name=business.get("name", "your business"),
            admin_url=admin_url,
        )
    )
    return doc


@router.get("", dependencies=[Depends(require_admin)])
async def list_claims(
    business_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if business_id:
        q["business_id"] = business_id
    if status:
        q["status"] = status
    cur = get_db().business_claims.find(q).sort("submitted_at", -1)
    return await cur.to_list(length=500)


@router.post("/{claim_id}/verify", dependencies=[Depends(require_admin)])
async def verify_claim(claim_id: str, request: Request) -> Dict[str, Any]:
    db = get_db()
    claim = await db.business_claims.find_one({"_id": claim_id})
    if not claim:
        raise HTTPException(404, "Claim not found")
    now = now_utc()
    await db.business_claims.update_one(
        {"_id": claim_id},
        {"$set": {"status": "verified", "verified_at": now}},
    )

    # --- Founding Partner cap check ---
    # WHY: look up the business's network_id first so we can scope the cap
    # per vertical (beauty / wellness / health). Each vertical advertises its
    # own "X of N remaining" counter independently — a beauty network filling
    # up should not block wellness claimers from getting the badge.
    biz_for_cap = await db.businesses.find_one(
        {"_id": claim["business_id"]}, {"network_id": 1}
    )
    network_id_for_cap = (biz_for_cap or {}).get("network_id")
    settings = get_settings()
    cap = settings.founding_partner_cap
    cap_filter: dict = {"is_founding_partner": True}
    if network_id_for_cap:
        # WHY: scope to the business's own network so badge slots in one
        # vertical (beauty) don't count against a different vertical (wellness).
        cap_filter["network_id"] = network_id_for_cap
    current_fp_count = await db.businesses.count_documents(cap_filter)
    # WHY: write False explicitly rather than leaving the field absent so a
    # future cap increase doesn't require a migration — the field will be
    # present and queryable on all verified businesses regardless of badge status.
    is_founding_partner = current_fp_count < cap

    await db.businesses.update_one(
        {"_id": claim["business_id"]},
        {
            "$set": {
                "claim_status": "verified",
                "claimed_at": now,
                "verified_at": now,
                "updated_at": now,
                # WHY: stored lowercase so the owner-portal lookup
                # (`find_one({"claimed_email": email.lower()})`) matches
                # regardless of how the owner capitalises their email at
                # sign-in.
                "claimed_email": (claim["submitter_email"] or "").lower(),
                # WHY: only True when a slot is still available. The owners
                # page advertises "X of N remaining" — without this check
                # that scarcity is fake; every verified business would get
                # the badge regardless of how many slots have already been used.
                "is_founding_partner": is_founding_partner,
            }
        },
    )
    # Notify the owner that their claim was approved and they can log in.
    # WHY: without this the owner has no way to know they've been verified —
    # they submitted, got a confirmation, and then heard nothing.  Fire-and-
    # forget so a slow email never blocks the admin verification response.
    business = await db.businesses.find_one({"_id": claim["business_id"]})
    # WHY: use canonical_base_url so the login link in the verification email
    # points at the public hostname.  request.base_url is the Docker-internal
    # address when running behind nginx, producing a broken link for the owner.
    base = (settings.canonical_base_url or str(request.base_url)).rstrip("/")
    owner_email = (claim.get("submitter_email") or "").strip()
    # WHY: pre-filling the email in the login URL means the owner lands on the
    # code-entry screen immediately rather than having to re-type their address.
    # One fewer step between "verified" and "inside the dashboard".
    login_url = base + "/owners/login?email=" + _url_quote(owner_email, safe="")
    # WHY: compute founding partner spots AFTER the update so the count in the
    # email reflects the current state (the just-verified owner may have become
    # a founding partner themselves, or an earlier owner may have just taken the
    # last slot). This count is passed to the email so it shows real urgency
    # without a second DB round-trip inside the email service.
    fp_count_after = await db.businesses.count_documents(cap_filter)
    spots_left = max(0, cap - fp_count_after)
    asyncio.create_task(
        send_claim_verified_email(
            email=owner_email,
            submitter_name=claim.get("submitter_name", ""),
            business_name=(business or {}).get("name", "your business"),
            login_url=login_url,
            site_base_url=base,
            founding_partner_spots_left=spots_left,
        )
    )
    return {"status": "verified"}


@router.post("/{claim_id}/reject", dependencies=[Depends(require_admin)])
async def reject_claim(claim_id: str) -> Dict[str, Any]:
    """Mark a submitted claim as rejected and reset its business to unclaimed.

    Mirror of `verify_claim` for the negative case. Used when an admin
    decides a claim submission isn't legitimate (spam, wrong person, etc.).
    Idempotent against the same claim — re-rejecting just rewrites the
    same fields. We reset the business's claim_status to `unclaimed` so
    the business is open for a fresh submission from the real owner.
    """
    db = get_db()
    claim = await db.business_claims.find_one({"_id": claim_id})
    if not claim:
        raise HTTPException(404, "Claim not found")
    now = now_utc()
    await db.business_claims.update_one(
        {"_id": claim_id},
        {"$set": {"status": "rejected", "rejected_at": now}},
    )
    # WHY: Only flip the business back to `unclaimed` when its current
    # status is `pending` — i.e. the business is still in the "someone
    # tried to claim me" state. If the business has since been verified
    # (e.g. a different claim landed and was verified first), leave it
    # alone so we don't accidentally un-verify a legitimately-claimed
    # business.
    business = await db.businesses.find_one({"_id": claim["business_id"]})
    if business and business.get("claim_status") == "pending":
        await db.businesses.update_one(
            {"_id": claim["business_id"]},
            {"$set": {"claim_status": "unclaimed", "updated_at": now}},
        )
    # Notify the submitter that their claim wasn't approved.
    # WHY: without this they submit, wait one business day, and then hear
    # nothing — no idea the answer was no, no way to follow up or correct
    # a mistake. Fire-and-forget so a slow email never blocks the admin
    # reject response.
    asyncio.create_task(
        send_claim_rejected_email(
            email=claim.get("submitter_email", ""),
            submitter_name=claim.get("submitter_name", ""),
            business_name=(business or {}).get("name", "your business"),
        )
    )
    return {"status": "rejected"}
