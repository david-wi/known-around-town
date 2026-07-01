"""Per-IP rate limiting for the public, unauthenticated form endpoints.

WHY: the public claim / inquiry / owner-lead endpoints accept anonymous POSTs
and each one triggers side effects — it writes to the database, emails the
salon owner and/or admin, and (for claims) flips a listing into "pending". With
no limit, a script can flood owner inboxes, spam admin, or churn listing state.
We cap how many times one client IP can hit a given endpoint within a short
window, mirroring the owner-login code rate limit already in owner_auth.

The real visitor IP is trustworthy here: the app runs uvicorn with
``--proxy-headers --forwarded-allow-ips *`` (see backend/Dockerfile), so
``request.client.host`` resolves the X-Forwarded-For client address rather than
the nginx/proxy hop in front of it.

The limiter counts the endpoint's own collection on its natural timestamp
field, so it needs no separate bookkeeping store. Callers must (a) call
``enforce_ip_rate_limit`` before doing the work, and (b) record ``submit_ip`` on
the document they insert, so later requests from the same IP are counted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request

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

    WHY: ``request.client`` can be ``None`` for some ASGI transports and test
    clients. Falling back to a constant string keeps those callers sharing one
    limit bucket rather than raising an AttributeError mid-request.
    """
    return request.client.host if request.client else "unknown"


async def enforce_ip_rate_limit(
    *,
    db,
    collection: str,
    ip: str,
    max_events: int,
    window: timedelta = PUBLIC_FORM_RATE_LIMIT_WINDOW,
    ip_field: str = "submit_ip",
    timestamp_field: str = "submitted_at",
    now: Optional[datetime] = None,
) -> None:
    """Raise HTTP 429 if ``ip`` created >= ``max_events`` docs in ``window``.

    Counts documents in ``collection`` whose ``ip_field`` equals ``ip`` and
    whose ``timestamp_field`` falls inside the recent window. Callers must
    record ``ip_field`` on the documents they insert for the count to see them.
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - window
    recent = await db[collection].count_documents(
        {ip_field: ip, timestamp_field: {"$gte": window_start}}
    )
    if recent >= max_events:
        # WHY: 429 + Retry-After lets a polite client back off automatically.
        # The value is the window length — the longest a blocked client would
        # wait for its oldest counted request to age out of the window.
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a few minutes and try again.",
            headers={"Retry-After": str(int(window.total_seconds()))},
        )
