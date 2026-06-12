"""Admin page for syncing Google Business ratings.

Gives the operator (David / Posey) a one-click way to pull Google star ratings
and review counts for every business in the directory and store them in the
database. Once stored, ratings appear on salon detail pages and in directory
cards without any live API calls on page load.

Auth: same ADMIN_COOKIE_NAME cookie and require_admin dependency used by all
admin routes. Log in once via /admin/login and the session lasts 8 hours.

WHY a separate admin page rather than a cron: the sync costs money per API call
(Google Places API charges per request). Manual on-demand sync gives the
operator control over timing and cost — run it weekly or after adding new
businesses, not automatically on every deploy.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.routes.api.v1._auth import require_admin
from app.services import google_places

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None


def attach_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t


@router.get("/sync")
async def sync_page(
    request: Request,
    result: Optional[str] = None,
    updated: Optional[int] = None,
    no_match: Optional[int] = None,
    failed: Optional[int] = None,
    _admin=Depends(require_admin),
):
    """Show the sync dashboard: how many businesses have ratings vs. need sync."""
    if _templates is None:
        raise RuntimeError("Templates not attached — call attach_templates() at startup")

    db = get_db()
    # WHY: the PublishStatus enum uses "live" not "published" — querying for
    # "published" returns 0 results even when businesses exist.
    total = await db.businesses.count_documents({"status": "live"})
    with_rating = await db.businesses.count_documents(
        {"status": "live", "google_rating": {"$ne": None}}
    )
    without_rating = total - with_rating

    return _templates.TemplateResponse(
        "admin/sync.html",
        {
            "request": request,
            "total": total,
            "with_rating": with_rating,
            "without_rating": without_rating,
            "api_configured": google_places.is_configured(),
            "result": result,
            "sync_updated": updated,
            "sync_no_match": no_match,
            "sync_failed": failed,
        },
    )


@router.post("/sync/ratings")
async def sync_ratings(
    request: Request,
    _admin=Depends(require_admin),
):
    """Trigger a Google Places sync for all published businesses.

    Fetches ratings in parallel (5 at a time) and writes updates directly to
    the business documents. Redirects back to the sync page with a summary.
    """
    if not google_places.is_configured():
        # WHY: redirect-then-GET so browser back/refresh doesn't re-POST the form
        return RedirectResponse(url="/admin/sync?result=error:no-key", status_code=303)

    db = get_db()

    # WHY: load city names once for lookup in the sync loop — avoids N
    # separate city queries when building the Places search query per business.
    # Limit is generous (1000) because city counts are small in practice.
    city_docs = await db.cities.find({}, {"_id": 1, "name": 1}).to_list(1000)
    city_names: Dict[str, str] = {c["_id"]: c.get("name", "") for c in city_docs}

    # WHY: cap at 5000 to avoid runaway memory usage. Log a warning if we hit
    # it so the operator knows they need to re-run or implement pagination.
    businesses = await db.businesses.find(
        {"status": "live"},
        {"_id": 1, "name": 1, "city_id": 1, "google_place_id": 1},
    ).to_list(5000)

    if len(businesses) == 5000:
        log.warning(
            "sync_ratings hit the 5000-business cap — some businesses were not synced"
        )

    log.info("Starting Google ratings sync for %d businesses", len(businesses))

    # WHY: semaphore of 5 to avoid hammering the Places API with dozens of
    # simultaneous requests, which can trigger rate-limit errors even under
    # the per-second quota. Sequential-enough to stay under 10 QPS.
    sem = asyncio.Semaphore(5)
    updated = 0
    failed = 0
    no_match = 0

    async def _sync_one(biz: dict) -> None:
        nonlocal updated, failed, no_match
        city_id = biz.get("city_id", "")
        if city_id and city_id not in city_names:
            log.warning(
                "Business %r has unknown city_id %r — falling back to Miami",
                biz.get("name"), city_id,
            )
        city_name = city_names.get(city_id, "Miami")
        async with sem:
            rating_result = await google_places.lookup_rating(
                business_name=biz.get("name", ""),
                city=city_name,
                existing_place_id=biz.get("google_place_id"),
            )
        if rating_result is None:
            if biz.get("google_place_id"):
                # Had a place_id but fetch failed — transient error; keep old data
                failed += 1
            else:
                no_match += 1
            return

        await db.businesses.update_one(
            {"_id": biz["_id"]},
            {
                "$set": {
                    "google_place_id": rating_result.place_id,
                    "google_rating": rating_result.rating,
                    "google_review_count": rating_result.review_count,
                    "google_rating_synced_at": datetime.now(timezone.utc),
                }
            },
        )
        updated += 1

    await asyncio.gather(*[_sync_one(b) for b in businesses])

    log.info(
        "Google ratings sync complete: updated=%d no_match=%d failed=%d",
        updated, no_match, failed,
    )

    return RedirectResponse(
        url=f"/admin/sync?result=ok&updated={updated}&no_match={no_match}&failed={failed}",
        status_code=303,
    )
