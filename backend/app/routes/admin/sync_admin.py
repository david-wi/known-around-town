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
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.routes.api.v1._auth import require_admin
from app.services import google_places

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None

# WHY module-level flag (not DB-backed): a simple bool avoids a round-trip on
# every GET to /admin/sync. It resets on container restart, which is acceptable
# because a restart would also abort any in-progress sync.
_sync_running: bool = False

# WHY: six hours prevents same-evening manual reruns from spending Google quota
# on businesses we just searched, but expires before the 3:12 AM daily sync after
# a normal afternoon/evening cleanup so fresh overnight quota can repopulate.
_RECENT_DISCOVERY_SKIP_WINDOW = timedelta(hours=6)


def attach_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t


def _strip_city_suffix(name: str, city_name: str) -> str:
    """Return a cleaned business name to try when the original Places search fails.

    WHY: ~40 businesses in the seed data include the city name as a suffix
    (e.g. "Allure Medspa Aventura") or a location qualifier after a separator
    (e.g. "DIPLOMATIC IV | Brickell"). Google's Places listing omits these extras,
    so searching the full stored name finds nothing. Stripping the city name or
    separator suffix produces a search-friendly name that matches the Places record.
    Returns the stripped name if stripping produced a change, or "" if unchanged
    (so the caller can skip the extra API call when nothing would differ).
    """
    stripped = name.strip()

    # Strip separators first: "DIPLOMATIC IV | Brickell" → "DIPLOMATIC IV"
    # WHY: check separators before city-name suffix because a name like
    # "LaserAway – Doral" needs the separator stripped, not just " Doral".
    for sep in (" | ", " — ", " – ", " - "):
        if sep in stripped:
            candidate = stripped.split(sep)[0].strip()
            if candidate and candidate.lower() != stripped.lower():
                return candidate

    # Strip trailing city name: "Allure Medspa Aventura" → "Allure Medspa"
    city_lower = city_name.strip().lower()
    name_lower = stripped.lower()
    if city_lower and name_lower.endswith(" " + city_lower):
        candidate = stripped[: -(len(city_lower) + 1)].strip()
        if candidate:
            return candidate

    return ""


def _coerce_utc_datetime(value) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime for persisted lookup-cache values.

    WHY tolerate strings and naive datetimes: older ad-hoc scripts and tests have
    stored datetimes inconsistently in this app. The cache is only an optimization,
    so an unreadable value should be treated as absent rather than crashing sync.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _has_recent_discovery_attempt(biz: dict, now: datetime) -> bool:
    """True when this unrated discovery path was attempted recently enough to skip."""
    if biz.get("google_place_id"):
        return False
    attempted_at = _coerce_utc_datetime(biz.get("google_lookup_attempted_at"))
    if attempted_at is None:
        return False
    return now - attempted_at < _RECENT_DISCOVERY_SKIP_WINDOW


async def _run_sync_background(city_names: Dict[str, str], businesses: list) -> None:
    """Background coroutine: sync ratings for all businesses then log results.

    Called via FastAPI BackgroundTasks so the HTTP response returns immediately
    and Traefik's read timeout cannot abort a 2-minute sync of 1000+ businesses.
    """
    global _sync_running
    db = get_db()

    # WHY: semaphore of 3 (down from 5) to reduce burst rate. Combined with
    # the 0.1s inter-request sleep below, peak throughput is ~30 req/s —
    # well under Google's 100 QPS limit but far enough from the edge to
    # avoid triggering 429s on large syncs.
    sem = asyncio.Semaphore(3)
    updated = 0
    failed = 0
    no_match = 0
    skipped_recent = 0
    sync_started_at = datetime.now(timezone.utc)

    async def _sync_one(biz: dict) -> None:
        nonlocal updated, failed, no_match, skipped_recent
        city_id = biz.get("city_id", "")
        if city_id and city_id not in city_names:
            log.warning(
                "Business %r has unknown city_id %r — falling back to Miami",
                biz.get("name"), city_id,
            )
        city_name = city_names.get(city_id, "Miami")
        if _has_recent_discovery_attempt(biz, sync_started_at):
            skipped_recent += 1
            log.info(
                "Skipping Google discovery for %r — lookup was attempted recently at %s",
                biz.get("name"), biz.get("google_lookup_attempted_at"),
            )
            return
        try:
            async with sem:
                rating_result = await google_places.lookup_rating(
                    business_name=biz.get("name", ""),
                    city=city_name,
                    existing_place_id=biz.get("google_place_id"),
                )
                # WHY: 0.1s sleep inside the semaphore block paces each slot so
                # concurrent slots don't all fire requests at the same millisecond.
                await asyncio.sleep(0.1)

                # WHY: neighborhood-name fallback for businesses in sub-cities.
                # Some Google-registered cities (Wilton Manors, Flagler Village, Las Olas)
                # are neighborhoods of Fort Lauderdale but have their own Places listings.
                # Searching "Business Name Fort Lauderdale FL" fails to match them; trying
                # the neighborhood name (slug converted to title-case) as the city finds
                # the correct Places record. Only runs when no existing place_id is cached
                # (discovery phase) and the city search returned nothing.
                if rating_result is None and not biz.get("google_place_id"):
                    # WHY cap at 3: bounding the fallback loop prevents one business
                    # with many neighborhood slugs from holding the semaphore slot for
                    # an unbounded time.
                    nbhd_slugs = (biz.get("neighborhood_slugs") or [])[:3]
                    for nbhd_slug in nbhd_slugs:
                        nbhd_name = nbhd_slug.replace("-", " ").title()
                        if nbhd_name.lower() == city_name.lower():
                            continue
                        rating_result = await google_places.lookup_rating(
                            business_name=biz.get("name", ""),
                            city=nbhd_name,
                        )
                        await asyncio.sleep(0.1)
                        if rating_result:
                            log.info(
                                "Found %r via neighborhood fallback %r (primary city %r had no match)",
                                biz.get("name"), nbhd_name, city_name,
                            )
                            break

                # WHY: name-suffix stripping fallback. ~40 businesses include the city
                # name at the end of their stored name ("Allure Medspa Aventura") or use
                # a pipe/dash separator ("DIPLOMATIC IV | Brickell"). Google's listing
                # omits these extras, so searching the full stored name fails. Try a
                # cleaned name before giving up.
                if rating_result is None:
                    stripped_name = _strip_city_suffix(biz.get("name", ""), city_name)
                    if stripped_name:
                        rating_result = await google_places.lookup_rating(
                            business_name=stripped_name,
                            city=city_name,
                        )
                        await asyncio.sleep(0.1)
                        if rating_result:
                            log.info(
                                "Found %r via stripped-name fallback (tried %r in %r)",
                                biz.get("name"), stripped_name, city_name,
                            )

        except google_places.RateLimitError:
            # WHY: RateLimitError means the daily API quota is exhausted — not that
            # this business has no Google listing. Count as failed (transient) so it
            # stays in the unrated queue and gets retried on the next sync run,
            # rather than as no_match (permanent absence from Google).
            failed += 1
            return

        if rating_result is None:
            if biz.get("google_place_id"):
                # Had a place_id but fetch failed — transient error; keep old data
                failed += 1
            else:
                await db.businesses.update_one(
                    {"_id": biz["_id"]},
                    {"$set": {"google_lookup_attempted_at": sync_started_at}},
                )
                no_match += 1
            return

        # WHY (defense-in-depth duplicate-place guard): one real Google business
        # must never be attached to two different live listings. The AI match
        # judge (google_places._llm_same_business) is the primary defense, but if
        # it ever admits a wrong match the symptom is the SAME google_place_id
        # landing on multiple distinct businesses — which is exactly how ~283
        # listings ended up showing the wrong business's star rating before the
        # matcher was hardened. So before storing a NEWLY-discovered place_id, check whether
        # it is already assigned to a DIFFERENT live business. If it is, treat
        # this as a no-match (leave the business unrated) and warn, rather than
        # silently duplicating the rating.
        #
        # WHY scoped to the discovery path (no existing_place_id): re-fetching a
        # business's OWN cached place_id is legitimate and must not be blocked —
        # that lookup queries the place_id this very business already owns, so it
        # would always "collide" with itself. The guard only runs when this
        # business did not already own the place_id we're about to write.
        #
        # WHY a read-then-write check (not a unique index): this catches any
        # place_id that was ALREADY stored on another business before this run,
        # plus the common sequential case within a run. A theoretical race
        # remains if two tasks discover the SAME place_id in the same run before
        # either writes (the sync runs 3 at a time) — closing that fully would
        # need a unique index on google_place_id, a schema/data change out of
        # scope here while existing duplicate data is being cleaned up
        # separately. The hardened matcher above is what stops two distinct
        # businesses from resolving to the same place in the first place; this
        # guard is the backstop, and it shrinks the blast radius from "any
        # matcher gap duplicates ratings widely" to "at most one same-run race".
        if not biz.get("google_place_id"):
            conflicting = await db.businesses.find_one(
                {
                    "google_place_id": rating_result.place_id,
                    "status": "live",
                    "_id": {"$ne": biz["_id"]},
                },
                {"_id": 1, "name": 1},
            )
            if conflicting is not None:
                log.warning(
                    "Google place_id %r already assigned to live business %r (%s); "
                    "skipping assignment to %r (%s) to avoid duplicating one Google "
                    "business across two listings — left unrated",
                    rating_result.place_id,
                    conflicting.get("name"), conflicting["_id"],
                    biz.get("name"), biz["_id"],
                )
                await db.businesses.update_one(
                    {"_id": biz["_id"]},
                    {"$set": {"google_lookup_attempted_at": sync_started_at}},
                )
                no_match += 1
                return

        update_fields: dict = {
            "google_place_id": rating_result.place_id,
            "google_rating": rating_result.rating,
            "google_review_count": rating_result.review_count,
            "google_rating_synced_at": datetime.now(timezone.utc),
        }
        # WHY: only overwrite hours when Places returned data. An empty list means
        # Google had no hour data for this business — preserving any manually-entered
        # hours is better than blanking them.
        if rating_result.hours:
            update_fields["hours"] = [h.model_dump() for h in rating_result.hours]

        await db.businesses.update_one(
            {"_id": biz["_id"]},
            {
                "$set": update_fields,
                "$unset": {"google_lookup_attempted_at": ""},
            },
        )
        updated += 1

    try:
        await asyncio.gather(*[_sync_one(b) for b in businesses])
        log.info(
            "Google ratings sync complete: updated=%d no_match=%d failed=%d skipped_recent=%d",
            updated, no_match, failed, skipped_recent,
        )
    finally:
        # WHY: always clear the flag so the admin page doesn't stay stuck in
        # "running" state if the sync raises an unexpected error.
        _sync_running = False


@router.get("/sync")
async def sync_page(
    request: Request,
    result: Optional[str] = None,
    unrated_only: Optional[int] = None,
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
        request,
        "admin/sync.html",
        {
            "request": request,
            "total": total,
            "with_rating": with_rating,
            "without_rating": without_rating,
            "api_configured": google_places.is_configured(),
            "result": result,
            "unrated_only": bool(unrated_only),
            "sync_updated": updated,
            "sync_no_match": no_match,
            "sync_failed": failed,
            "sync_running": _sync_running,
        },
    )


def _resolve_unrated_only(form_value: Optional[bool], query_params) -> bool:
    """Decide whether to run an unrated-only sync, reading from form OR query string.

    WHY this exists (the footgun it guards against): the two web buttons submit
    `unrated_only` as a form field, so the browser path works fine. But a
    programmatic caller (curl/script) that passes `?unrated_only=true` as a URL
    query string would have it SILENTLY IGNORED by a plain `Form(...)` parameter —
    FastAPI never reads query strings into a Form field. The param would default to
    False and trigger an expensive FULL sync of every business in the directory,
    exhausting the entire daily Google Places API quota (Text Search AND Place
    Details per-day limits) in one shot. This actually happened and burned a full
    day of quota plus money. Reading the query string as a fallback makes the safe,
    cheap unrated-only request honored no matter how it was sent.

    The form body wins when present (so the web buttons keep their exact behavior);
    only when the form did not supply the field do we fall back to the query string.
    """
    if form_value is not None:
        return form_value

    raw = query_params.get("unrated_only")
    if raw is None:
        return False
    # WHY: accept the common truthy spellings a script might send. Anything else
    # (including "false"/"0") resolves to False, matching the safe-but-only-when-
    # explicit nature of a full sync.
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@router.post("/sync/ratings")
async def sync_ratings(
    request: Request,
    background_tasks: BackgroundTasks,
    unrated_only: Optional[bool] = Form(None),
    _admin=Depends(require_admin),
):
    """Trigger a Google Places sync for published businesses.

    Fetches ratings in parallel (3 at a time) in a background task so the
    HTTP response is returned immediately — avoiding Traefik's read timeout.
    Redirects to the sync page with result=started.

    unrated_only=True targets only businesses with no Google rating yet.
    WHY: conserves daily API quota — avoids re-fetching the ~880 businesses
    that already have ratings when the goal is filling in new additions.

    unrated_only is read from the form body (the web buttons) OR the URL query
    string (programmatic callers). See _resolve_unrated_only for why both paths
    matter — a query-string caller used to be silently ignored and trigger an
    expensive full sync that exhausted the daily Google Places quota.
    """
    global _sync_running

    unrated_only_effective = _resolve_unrated_only(unrated_only, request.query_params)

    if not google_places.is_configured():
        # WHY: redirect-then-GET so browser back/refresh doesn't re-POST the form
        return RedirectResponse(url="/admin/sync?result=error:no-key", status_code=303)

    if _sync_running:
        return RedirectResponse(url="/admin/sync?result=already-running", status_code=303)

    db = get_db()

    # WHY: load city names once for lookup in the sync loop — avoids N
    # separate city queries when building the Places search query per business.
    city_docs = await db.cities.find({}, {"_id": 1, "name": 1}).to_list(1000)
    city_names: Dict[str, str] = {c["_id"]: c.get("name", "") for c in city_docs}

    # WHY: when unrated_only=True, filter to businesses with no Google rating.
    # Use $or to catch both documents where the field is absent and where it is
    # explicitly null — both mean "never synced." This conserves daily API quota
    # by skipping the ~880 businesses that already have ratings.
    biz_filter: dict = {"status": "live"}
    if unrated_only_effective:
        biz_filter["$or"] = [
            {"google_rating": {"$exists": False}},
            {"google_rating": None},
        ]

    # WHY: cap at 5000 to avoid runaway memory usage. Log a warning if we hit
    # it so the operator knows they need to re-run or implement pagination.
    businesses = await db.businesses.find(
        biz_filter,
        {
            "_id": 1,
            "name": 1,
            "city_id": 1,
            "google_place_id": 1,
            "google_lookup_attempted_at": 1,
            "neighborhood_slugs": 1,
        },
    ).to_list(5000)

    if len(businesses) == 5000:
        log.warning(
            "sync_ratings hit the 5000-business cap — some businesses were not synced"
        )

    if not unrated_only_effective:
        # WHY: a full (non-unrated) sync re-fetches every business, consuming a
        # large slice of the daily Google Places quota (both Text Search and Place
        # Details per-day limits) and real money. Surface it loudly so an accidental
        # full sync — e.g. a script that forgot unrated_only — is obvious in the logs.
        log.warning(
            "FULL Google ratings sync triggered: will fetch ALL %d live businesses "
            "(unrated_only is OFF). This consumes significant daily Google Places "
            "API quota and money. If this was unintended, use unrated_only=true.",
            len(businesses),
        )

    log.info(
        "Queuing Google ratings sync for %d businesses (unrated_only=%s) (background task)",
        len(businesses), unrated_only_effective,
    )

    # WHY: set the flag BEFORE add_task so there is no window between the flag
    # being False and the background task starting where a second POST could
    # trigger a duplicate sync.
    _sync_running = True
    background_tasks.add_task(_run_sync_background, city_names, businesses)

    # WHY: include unrated_only in the redirect so the banner can tell the
    # operator exactly what mode was queued and how long it will take.
    suffix = "&unrated_only=1" if unrated_only_effective else ""
    return RedirectResponse(url=f"/admin/sync?result=started{suffix}", status_code=303)
