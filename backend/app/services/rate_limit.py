"""Per-IP rate limiting for the public, unauthenticated form endpoints.

WHY: the public claim / inquiry / owner-lead endpoints accept anonymous POSTs
and each one triggers side effects — it writes to the database, emails the
salon owner and/or admin, and (for claims) flips a listing into "pending". With
no limit, a script can flood owner inboxes, spam admin, or churn listing state.
We cap how many times one client IP can hit a given endpoint within a short
window, mirroring the owner-login code rate limit already in owner_auth.

The limiter reserves a slot in a dedicated MongoDB bucket before the endpoint
does its side effects. Callers should still record ``submit_ip`` on the document
they insert so admins can audit where accepted submissions came from.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional

from fastapi import HTTPException, Request
from pymongo import ReturnDocument

# WHY: a 10-minute window matches owner_auth.RATE_LIMIT_WINDOW. It is short
# enough that a blocked genuine user only waits a few minutes, and long enough
# that a scripted flood can't reset its budget by pausing briefly.
PUBLIC_FORM_RATE_LIMIT_WINDOW = timedelta(minutes=10)

# WHY per-endpoint caps: a real person submits at most a handful of these in ten
# minutes; a scripted flood submits hundreds. These caps leave generous headroom
# for genuine use — including a shared office / NAT IP where several real people
# sit behind one address — while still stopping automated abuse cold.
#   - claims: a real owner claims their listing once, maybe retries a time or two.
CLAIM_MAX_PER_WINDOW = 5
#   - inquiries: a visitor may legitimately message several salons in one sitting.
INQUIRY_MAX_PER_WINDOW = 10
#   - owner leads: a real owner drops their email once.
OWNER_LEAD_MAX_PER_WINDOW = 5


def client_ip(request: Request) -> str:
    """Return the requesting client's IP, or a shared bucket if unavailable.

    WHY: production is behind Traefik, which appends the socket peer to
    X-Forwarded-For. Uvicorn is currently configured to trust forwarded headers,
    and its ``*`` trust mode reads the leftmost value, which can be attacker-
    supplied if a browser sends its own X-Forwarded-For. Reading the rightmost
    forwarded value here ties the limiter to the IP Traefik appended. If the
    header is absent, fall back to ``request.client``; if that is unavailable,
    use one shared bucket rather than raising mid-request.
    """
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        for part in reversed(forwarded_for.split(",")):
            candidate = part.strip()
            if candidate:
                return candidate
    return request.client.host if request.client else "unknown"


# @define KAT-075 "Public side-effecting form endpoints are rate limited per client IP"
async def enforce_ip_rate_limit(
    *,
    db,
    collection: str,
    ip: str,
    max_events: int,
    window: timedelta = PUBLIC_FORM_RATE_LIMIT_WINDOW,
    now: Optional[datetime] = None,
) -> None:
    """Raise HTTP 429 if ``ip`` has reserved >= ``max_events`` slots in ``window``.

    The reservation is atomic: concurrent requests for the same endpoint/IP hit
    one MongoDB document and increment one counter, so only the first
    ``max_events`` callers can proceed to route side effects.
    """
    now = now or datetime.now(timezone.utc)
    window_seconds = int(window.total_seconds())
    bucket_epoch = int(now.timestamp()) // window_seconds * window_seconds
    bucket_start = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)
    reset_at = bucket_start + window
    # WHY: keep the raw IP on accepted submissions for audit, but hash it in the
    # limiter bucket. Operators can still reason about one bucket per client
    # without creating a second raw-IP store that lives until TTL cleanup.
    ip_hash = sha256(ip.encode("utf-8")).hexdigest()
    bucket_id = f"public-form:{collection}:{ip_hash}:{bucket_epoch}"
    bucket = await db.public_form_rate_limits.find_one_and_update(
        {"_id": bucket_id},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "collection": collection,
                "ip_hash": ip_hash,
                "bucket_start": bucket_start,
                "expires_at": reset_at + window,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if (bucket or {}).get("count", 0) > max_events:
        # WHY: 429 + Retry-After lets a polite client back off automatically.
        # The value is the remaining fixed-window time, rounded up to avoid
        # telling clients to retry before the bucket actually resets.
        retry_after = max(1, int((reset_at - now).total_seconds()) + 1)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a few minutes and try again.",
            headers={"Retry-After": str(retry_after)},
        )
