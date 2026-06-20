"""Admin-only preview and test-send for the monthly listing report email.

This is the SAFE way to see the monthly "your listing is working" email
before the founder approves the live monthly send. Two operations, both
behind the admin-key gate:

  GET  /admin/monthly-report/preview?business_id=...
       Renders the email HTML for one business and returns it directly in
       the browser. Sends NOTHING. This is what David uses to read the
       email and tweak the copy.

  POST /admin/monthly-report/test-send   { business_id, to }
       Sends ONE copy of the email to the explicitly-provided TEST address
       in ``to`` — and nowhere else. Gated by the MONTHLY_REPORT_TEST_SEND_ENABLED
       flag (OFF by default) ON TOP OF the admin-key gate, and it refuses to
       send to any address that belongs to a real claimed owner.

----------------------------------------------------------------------
WHY there is no bulk-send / cron here, on purpose
----------------------------------------------------------------------
The live monthly send to every Featured owner is the founder's decision and
his final call on the copy. Until he approves, this feature is DORMANT: the
only outbound path is a single test email to an address David types in, and
even that is off unless the test-send flag is set. There is deliberately no
endpoint, task, or scheduled job that emails the owner list.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field

from app.database import get_db
from app.routes.api.v1._auth import require_admin
from app.services import ai_caption
from app.services.monthly_email import (
    render_monthly_email,
    send_test_monthly_email,
    test_send_enabled,
)
from app.services.monthly_report import MonthlyReport, compute_report

log = logging.getLogger(__name__)

# WHY: /admin prefix + admin-key dependency mirrors analytics_admin so all
# admin operations live under one clearly-gated path.
router = APIRouter(prefix="/admin/monthly-report", tags=["admin"])


async def _load_business(business_id: str) -> Dict[str, Any]:
    """Load a business by id, accepting both ObjectId and UUID-string ids.

    WHY both: pre-migration businesses have ObjectId _id; newer ones are
    UUID strings. Same dual-lookup as marketing_ai._require_pro_owner.
    """
    try:
        id_query: Union[ObjectId, str] = ObjectId(business_id)
    except (InvalidId, TypeError):
        id_query = business_id
    doc = await get_db().businesses.find_one({"_id": id_query})
    if not doc:
        raise HTTPException(status_code=404, detail="Business not found")
    return doc


async def _maybe_caption(business: Dict[str, Any], report: MonthlyReport) -> Optional[str]:
    """Generate a ready-to-post caption when views are thin.

    WHY only when thin: small monthly numbers can accelerate churn, so for a
    quiet month the email leans on a growth nudge (a caption to post) rather
    than dwelling on the number. For a healthy month we skip the caption to
    keep the email focused on the win.

    Caption generation goes through the same gateway-backed ``ai_caption``
    used by the live caption tool. If the AI feature is disabled or the
    gateway is unreachable, we return None and the email simply omits the
    caption card — never fails the preview.
    """
    if not report.is_thin_views:
        return None

    db = get_db()
    city = await db.cities.find_one({"_id": business.get("city_id")})
    primary_category = (business.get("category_slugs") or [None])[0]

    neighborhood_name: Optional[str] = None
    neighborhood_slugs = business.get("neighborhood_slugs") or []
    if neighborhood_slugs:
        nb = await db.neighborhoods.find_one(
            {"city_id": business.get("city_id"), "slug": neighborhood_slugs[0]}
        )
        if nb:
            neighborhood_name = nb.get("name")

    ctx = ai_caption.CaptionContext(
        business_name=business.get("name", ""),
        neighborhood_name=neighborhood_name,
        city_name=(city or {}).get("name"),
        primary_category=primary_category,
        vertical_word=(city or {}).get("listing_word_singular"),
        known_for=business.get("known_for"),
        short_description=business.get("short_description"),
        # WHY: a generic "promote your listing next month" prompt — the owner
        # didn't type anything; this is a starter the founder can refine.
        prompt="a warm, inviting post to bring more local visitors to the salon next month",
    )
    try:
        return await ai_caption.generate_caption(ctx)
    except (ai_caption.CaptionFeatureDisabled, ai_caption.CaptionGenerationError) as exc:
        log.info("Skipping caption in monthly email (AI unavailable): %s", exc)
        return None


@router.get(
    "/preview",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def preview_monthly_email(
    business_id: str = Query(..., description="The _id of the business to preview the email for."),
) -> HTMLResponse:
    """Render the monthly email HTML for one business. Sends nothing.

    WHY this is safe to expose to admins: it only renders and returns HTML in
    the browser — no email leaves the server. It also writes/keeps this
    month's view snapshot as a side effect (so the delta math is correct), but
    that is internal bookkeeping, not an outbound message.
    """
    business = await _load_business(business_id)
    report = await compute_report(get_db(), business)
    caption = await _maybe_caption(business, report)
    _subject, html_body, _text = render_monthly_email(report, caption)
    return HTMLResponse(content=html_body)


class TestSendRequest(BaseModel):
    """Body for the admin test-send. ``to`` must be a valid email address.

    WHY EmailStr: rejects a malformed address at the door so a typo can't turn
    into a Resend error or, worse, a send to an unintended string.
    """

    business_id: str = Field(..., min_length=1, max_length=200)
    to: EmailStr


@router.post(
    "/test-send",
    dependencies=[Depends(require_admin)],
)
async def test_send_monthly_email(
    body: TestSendRequest,
) -> Dict[str, Any]:
    """Send ONE test copy of the monthly email to an explicit test address.

    SAFETY layers (all must pass):
      1. Admin-key gate (the route dependency).
      2. ``MONTHLY_REPORT_TEST_SEND_ENABLED`` flag is on (else 403). OFF by
         default, so a normal deploy cannot send anything.
      3. The target address is NOT a real claimed owner's email (else 409).
         This makes it impossible to "test-send" to an actual salon owner.

    The email goes only to ``body.to`` — never to a list, never to an address
    read from the business document.
    """
    if not test_send_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "Test send is disabled. Set MONTHLY_REPORT_TEST_SEND_ENABLED=true "
                "to allow sending a test copy to a test address."
            ),
        )

    to_address = str(body.to).strip().lower()

    # WHY: refuse to send to any address that belongs to a claimed listing.
    # This is the hard guarantee that "test send" can never reach a real owner,
    # independent of who triggers it.
    db = get_db()
    real_owner = await db.businesses.find_one(
        {"claimed_email": to_address}, projection={"_id": 1}
    )
    if real_owner is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Refusing to send: that address belongs to a real claimed owner. "
                "Use a dedicated test inbox."
            ),
        )

    business = await _load_business(body.business_id)
    report = await compute_report(db, business)
    caption = await _maybe_caption(business, report)
    sent = await send_test_monthly_email(to=to_address, report=report, caption=caption)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="The email provider did not accept the message. Check server logs.",
        )

    return {
        "sent": True,
        "to": to_address,
        "business_id": report.business_id,
        "business_name": report.business_name,
        "period": report.period_label,
        "views_this_month": report.views_this_month,
        "messages_this_month": report.messages_this_month,
        "included_caption": caption is not None,
    }
