#!/usr/bin/env python3
"""Standalone script: sync Google star ratings for every live business.

Run from the repo root or from inside the container:

    python3 backend/scripts/sync_google_ratings.py

Requirements
------------
- GOOGLE_PLACES_API_KEY environment variable must be set.
  If it is not set, the script prints a message and exits cleanly (exit 0).
- MONGODB_URL (or the app's default connection string) must point at the
  production Atlas cluster so the script can read and write business records.

The script reuses the existing ``app.services.google_places`` module so the
lookup logic (name-similarity check, Place Details fallback, rate-limiting)
stays in one place. Only business records with ``status == "live"`` are
processed. Progress is logged to stdout; errors per-business are logged but
do not abort the run.

WHY a standalone script in addition to the admin UI sync:
The admin UI sync requires an authenticated browser session and a running
FastAPI server. This script can be run from a cron job, a CI pipeline, or
a one-off terminal command without any web server in the loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


async def _main() -> None:
    # Check for the API key before importing app modules (which trigger DB
    # connection setup). This keeps the exit-cleanly-if-no-key behaviour fast
    # and avoids confusing MongoDB connection errors for users who just forgot
    # the key.
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        log.info(
            "GOOGLE_PLACES_API_KEY is not set — nothing to sync. "
            "Set the variable and re-run to fetch Google ratings."
        )
        # WHY: exit 0 (not 1) so a cron job or CI step doesn't fail just
        # because the key hasn't been configured yet.
        sys.exit(0)

    # Import app modules after the key check so we don't drag in DB
    # connection overhead when the script exits immediately.
    # WHY: sys.path manipulation lets the script be run from the repo root
    # (python3 backend/scripts/sync_google_ratings.py) without installing
    # the package first.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from app.database import get_db, ensure_indexes
    from app.services import google_places

    if not google_places.is_configured():
        # Shouldn't happen — we just checked the env var — but guard anyway
        # in case the service module uses a different env var name in future.
        log.error("google_places.is_configured() returned False despite key being set. Aborting.")
        sys.exit(1)

    log.info("Connecting to database and ensuring indexes…")
    await ensure_indexes()

    db = get_db()

    # Load city names once for lookup in the sync loop.
    city_docs = await db.cities.find({}, {"_id": 1, "name": 1}).to_list(1000)
    city_names: Dict[str, str] = {c["_id"]: c.get("name", "") for c in city_docs}

    # WHY: 5000 cap mirrors the admin UI sync; log a warning if we hit it.
    businesses = await db.businesses.find(
        {"status": "live"},
        {"_id": 1, "name": 1, "city_id": 1, "google_place_id": 1},
    ).to_list(5000)

    if len(businesses) == 5000:
        log.warning(
            "Hit the 5000-business cap — some businesses were not synced. "
            "Add pagination to handle larger directories."
        )

    total = len(businesses)
    log.info("Syncing ratings for %d live businesses…", total)

    # WHY: semaphore of 5 — same as the admin UI sync — to stay comfortably
    # under Google's 10-QPS per-project rate limit while still parallelising
    # most of the work.
    sem = asyncio.Semaphore(5)
    updated = 0
    no_match = 0
    failed = 0

    async def _sync_one(biz: dict, idx: int) -> None:
        nonlocal updated, no_match, failed

        city_id = biz.get("city_id", "")
        if city_id and city_id not in city_names:
            log.warning(
                "Business %r has unknown city_id %r — falling back to 'Miami'",
                biz.get("name"),
                city_id,
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
                log.warning(
                    "[%d/%d] %r — fetch failed (transient error, old data kept)",
                    idx, total, biz.get("name"),
                )
                failed += 1
            else:
                log.info("[%d/%d] %r — no Google match found", idx, total, biz.get("name"))
                no_match += 1
            return

        update_fields: dict = {
            "google_place_id": rating_result.place_id,
            "google_rating": rating_result.rating,
            "google_review_count": rating_result.review_count,
            "google_rating_synced_at": datetime.now(timezone.utc),
        }
        # WHY: only overwrite hours when Places returned data — same policy as
        # the admin UI sync. Blank hours from the API are less reliable than
        # manually entered ones.
        if rating_result.hours:
            update_fields["hours"] = [h.model_dump() for h in rating_result.hours]

        await db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": update_fields},
        )
        log.info(
            "[%d/%d] %r — %.1f ★ (%d reviews)",
            idx, total, biz.get("name"),
            rating_result.rating or 0,
            rating_result.review_count or 0,
        )
        updated += 1

    tasks = [_sync_one(b, i + 1) for i, b in enumerate(businesses)]
    await asyncio.gather(*tasks)

    log.info(
        "Done. updated=%d  no_match=%d  failed=%d  total=%d",
        updated, no_match, failed, total,
    )


if __name__ == "__main__":
    asyncio.run(_main())
