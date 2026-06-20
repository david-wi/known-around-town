"""Monthly "your listing is working" report aggregation.

This module computes the per-business numbers that go into the monthly
retention email for Featured salon owners: how many people viewed the
listing this month, how many reached out, and whether that's up or down
from last month.

WHY this exists as its own module (separate from the email rendering and
the admin route): the aggregation is pure data logic with one genuinely
tricky part — "views THIS month" — and that part deserves to be unit-tested
in isolation, without an HTTP layer or an email provider in the way.

----------------------------------------------------------------------
The "views this month" problem and how we solve it
----------------------------------------------------------------------
The business document only carries a LIFETIME view counter
(``page_view_count``), incremented on every real human visit. There is no
per-month history, so on its own the counter cannot answer "how many views
did I get in June?".

The smallest honest fix: take a SNAPSHOT of the lifetime counter at each
month boundary and store it in the ``monthly_view_snapshots`` collection.
Then:

    views in month M  =  lifetime_now  −  snapshot taken at the start of M

The snapshot for month M is written the first time a report is generated
for that business in month M. We store one snapshot row per (business,
period), each holding the lifetime count at the moment that period's report
was first produced. "Views in month M" is then:

    lifetime_now  −  (the most recent snapshot from a period BEFORE M)

The "most recent earlier snapshot" is our practical stand-in for "lifetime
count at the start of M": if a report ran last month, that snapshot was taken
near last month's end, which is close to this month's start. This is honest
about its one limitation — if reports run mid-month rather than exactly at the
boundary, "this month" really means "since the last report," not a strict
calendar slice. That trade keeps the implementation simple and never
over-claims a number we didn't measure.

When there is NO earlier snapshot (the very first report we ever generate for
a business), we cannot honestly claim a one-month number, so we report the
lifetime total and label the period as "since you joined" via
``is_first_report``. We never fabricate a month delta we don't have.

Messages need no snapshot: ``business_inquiries`` rows each carry a
``submitted_at`` timestamp, so "messages this month" is a direct date-range
count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# WHY: below this many monthly views the email should NOT dwell on the small
# number (small numbers accelerate churn — a salon owner who reads "3 people
# viewed your listing" may conclude the listing isn't working and cancel).
# Instead the email leans on a ready-to-post caption for next month. 10 is a
# deliberately conservative line: a listing pulling double-digit monthly views
# has a number worth celebrating; single digits do not. Tunable in one place.
THIN_VIEWS_THRESHOLD = 10

# WHY: the collection that stores one lifetime-counter snapshot per
# (business, month). Named here so the service, the indexes, and the tests
# all reference the same string.
SNAPSHOT_COLLECTION = "monthly_view_snapshots"


def period_key(when: datetime) -> str:
    """Return the calendar-month key ("YYYY-MM") for a timestamp.

    Pure function — kept separate so the snapshot read/write logic and the
    tests agree on exactly how a month is identified. Naive datetimes are
    treated as UTC so a stray naive value never shifts the month boundary.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    return f"{when.year:04d}-{when.month:02d}"


def month_label(key: str) -> str:
    """Turn a "YYYY-MM" key into a friendly label like "June 2026".

    Used for the email headline ("In June, N people viewed..."). Falls back
    to the raw key if it is malformed, so a bad value never raises inside
    email rendering.
    """
    try:
        year_s, month_s = key.split("-")
        dt = datetime(int(year_s), int(month_s), 1, tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return key
    # %B is the full month name ("June"); strip any locale padding.
    return f"{dt.strftime('%B')} {dt.year}"


def month_range(key: str) -> tuple[datetime, datetime]:
    """Return [start, end) tz-aware UTC bounds for a "YYYY-MM" period.

    ``start`` is the first instant of the month; ``end`` is the first instant
    of the NEXT month. Used for the messages date-range count. Half-open so a
    message timestamped exactly at a boundary is counted in exactly one month.
    """
    year_s, month_s = key.split("-")
    year, month = int(year_s), int(month_s)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


@dataclass(frozen=True)
class MonthlyReport:
    """The computed numbers for one business's monthly email.

    Everything the email template needs is here so the rendering layer never
    touches the database. ``trend`` is one of "up" / "down" / "flat" /
    "first" so the copy can lead with the trend when views are up.
    """

    business_id: str
    business_name: str
    period_key: str
    period_label: str
    views_this_month: int
    views_last_month: Optional[int]
    messages_this_month: int
    # WHY: the three high-intent shopper taps this month — call, directions,
    # website. They're snapshot-diffed exactly like views (all are lifetime
    # counters on the business doc). The email mentions them only when non-zero,
    # so a quiet month never leads with three zeros. On the first-ever report
    # (no prior snapshot) these hold the lifetime totals, framed "since you
    # joined" by the email — the same honest fallback used for views.
    calls_this_month: int = 0
    directions_this_month: int = 0
    website_clicks_this_month: int = 0
    # WHY: of this month's views, how many came from within Miami Knows Beauty
    # itself (a guide, on-site search, a category/neighborhood page, or a sister
    # listing). Snapshot-diffed exactly like views and taps — it's a lifetime
    # counter on the business doc. This is the number that proves WE drove the
    # traffic, so the eventual monthly email can say "Miami Knows Beauty sent you
    # N of your M visitors this month." Always <= views_this_month.
    mkb_referred_views_this_month: int = 0
    trend: str = "flat"  # "up" | "down" | "flat" | "first"
    is_first_report: bool = False
    is_thin_views: bool = False

    @property
    def views_up_from_last_month(self) -> bool:
        """True when this month beat last month — the email leads with this."""
        return self.trend == "up"

    @property
    def has_action_taps(self) -> bool:
        """True when any high-intent tap happened this period.

        WHY: the email only mentions taps when at least one occurred, so a
        listing with views but no taps yet never reads "0 calls, 0 directions".
        """
        return (
            self.calls_this_month
            + self.directions_this_month
            + self.website_clicks_this_month
        ) > 0

    @property
    def has_mkb_referral(self) -> bool:
        """True when we sent at least one visitor from within MKB this period.

        WHY: the email mentions the "we sent you N visitors" line only when N is
        non-zero, so a month whose visitors all came from Google or typed URLs
        never reads "Miami Knows Beauty sent you 0 visitors" — which would frame
        the report as a failure rather than leaving the proof out gracefully.
        """
        return self.mkb_referred_views_this_month > 0


async def _latest_snapshot_before(
    db: Any, business_id: str, current_period: str
) -> Optional[Dict[str, Any]]:
    """Most recent snapshot row strictly BEFORE the current period.

    WHY strictly before: the current period's own snapshot (if it was already
    written this run) records the lifetime count "as of the start of this
    month", so the month's gain is lifetime_now minus THAT row. But for the
    "last month" comparison we want the prior period's row. We sort by
    period_key descending and take the first row whose key is < current.
    """
    cursor = (
        db[SNAPSHOT_COLLECTION]
        .find({"business_id": business_id, "period_key": {"$lt": current_period}})
        .sort("period_key", -1)
        .limit(1)
    )
    rows = await cursor.to_list(length=1)
    return rows[0] if rows else None


async def _ensure_current_snapshot(
    db: Any,
    business_id: str,
    current_period: str,
    lifetime_count: int,
    now: datetime,
    action_counts: Optional[Dict[str, int]] = None,
) -> None:
    """Write this period's snapshot if it does not already exist.

    Idempotent: a second report run in the same month must not overwrite the
    counts captured the first time (which is what anchors next month's deltas).
    We only insert when absent. The stored counts are the lifetime totals at the
    moment this period's report was first produced — for page views AND the three
    shopper-action taps, so each gets a clean month-over-month delta.
    """
    existing = await db[SNAPSHOT_COLLECTION].find_one(
        {"business_id": business_id, "period_key": current_period}
    )
    if existing is not None:
        return
    doc: Dict[str, Any] = {
        "business_id": business_id,
        "period_key": current_period,
        "page_view_count": int(lifetime_count),
        "created_at": now,
    }
    # WHY: persist the tap counters in the SAME snapshot row so they diff exactly
    # like views. Older snapshot rows (written before taps were tracked) simply
    # lack these keys; _delta_from_snapshot treats a missing key as 0, which is
    # the correct baseline for a salon's first tracked month.
    if action_counts:
        doc.update({k: int(v) for k, v in action_counts.items()})
    await db[SNAPSHOT_COLLECTION].insert_one(doc)


async def _count_messages_in_period(db: Any, business_id: str, current_period: str) -> int:
    """Count visitor inquiries submitted within the given month.

    WHY a date-range count instead of a snapshot: each inquiry row carries
    its own ``submitted_at``, so the exact monthly count is a direct query —
    no running counter to snapshot.
    """
    start, end = month_range(current_period)
    return await db.business_inquiries.count_documents(
        {
            "business_id": business_id,
            "submitted_at": {"$gte": start, "$lt": end},
        }
    )


def _trend(views_this_month: int, views_last_month: Optional[int], is_first: bool) -> str:
    """Classify the month-over-month trend for the email copy."""
    if is_first or views_last_month is None:
        return "first"
    if views_this_month > views_last_month:
        return "up"
    if views_this_month < views_last_month:
        return "down"
    return "flat"


async def compute_report(
    db: Any,
    business: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> MonthlyReport:
    """Compute the monthly report numbers for one business.

    This is the single entry point used by both the preview route and the
    test-send route. It (a) takes/keeps a snapshot of the lifetime view
    counter for the current month, (b) derives this month's view gain from
    the prior snapshot, (c) counts this month's messages by date range, and
    (d) classifies the trend.

    Args:
      db: the Motor database handle.
      business: the business document (must include ``_id``, ``name``,
        ``page_view_count``).
      now: injectable clock for deterministic tests; defaults to UTC now.

    Returns a fully-populated :class:`MonthlyReport`.
    """
    now = now or datetime.now(timezone.utc)
    business_id = str(business["_id"])
    business_name = business.get("name", "your listing")
    lifetime_views = int(business.get("page_view_count") or 0)
    current_period = period_key(now)

    # WHY: the three shopper-action taps AND the MKB-referred view count are all
    # lifetime counters on the business doc, just like page views, so we read
    # them here and diff them against the prior snapshot the same way. A listing
    # that predates tracking simply has these absent (treated as 0). Putting
    # mkb_referred_view_count in this same dict means it gets snapshotted and
    # month-over-month diffed by the exact same proven machinery as the taps.
    lifetime_actions = {
        "call_click_count": int(business.get("call_click_count") or 0),
        "directions_click_count": int(business.get("directions_click_count") or 0),
        "website_click_count": int(business.get("website_click_count") or 0),
        "mkb_referred_view_count": int(business.get("mkb_referred_view_count") or 0),
    }

    # The prior snapshot anchors "views at the start of this month". We read it
    # BEFORE writing the current period's snapshot so the current write can't be
    # mistaken for the "last month" baseline.
    prior = await _latest_snapshot_before(db, business_id, current_period)

    # Persist the current period's snapshot (idempotent). Capturing the lifetime
    # counts now is what lets NEXT month compute its own gains — for views AND taps.
    await _ensure_current_snapshot(
        db, business_id, current_period, lifetime_views, now,
        action_counts=lifetime_actions,
    )

    if prior is None:
        # No history yet — we cannot honestly claim a one-month number, so we
        # report the lifetime total and let the email label it "since you
        # joined". We never invent a month delta we don't have.
        views_this_month = lifetime_views
        views_last_month: Optional[int] = None
        is_first = True
    else:
        prior_lifetime = int(prior.get("page_view_count") or 0)
        # WHY max(0, ...): the lifetime counter only ever grows, so the delta
        # should never be negative — but guard against a manual count reset or
        # a corrupt snapshot producing a nonsensical negative "views" number in
        # an owner-facing email.
        views_this_month = max(0, lifetime_views - prior_lifetime)
        # We don't have a separate "two months ago" snapshot in the smallest
        # version, so "last month" is approximated by the prior snapshot's own
        # delta only when a second-prior snapshot exists. To keep the first
        # version simple and honest, last-month views is the gain the prior
        # period represented if we can compute it, else None.
        second_prior = await _latest_snapshot_before(db, business_id, prior["period_key"])
        if second_prior is not None:
            views_last_month = max(
                0, prior_lifetime - int(second_prior.get("page_view_count") or 0)
            )
        else:
            views_last_month = None
        is_first = False

    # WHY: each tap counter diffs the same way as views — this month's gain is
    # the lifetime total now minus the prior snapshot's stored total, floored at
    # 0. On the first report (no prior snapshot) we report the lifetime total, so
    # the email's "since you joined" framing covers taps too. A missing key on an
    # older snapshot reads as 0, which is the right baseline for a salon's first
    # tracked month.
    def _action_delta(field: str, lifetime_now: int) -> int:
        if prior is None:
            return lifetime_now
        return max(0, lifetime_now - int(prior.get(field) or 0))

    calls_this_month = _action_delta("call_click_count", lifetime_actions["call_click_count"])
    directions_this_month = _action_delta(
        "directions_click_count", lifetime_actions["directions_click_count"]
    )
    website_clicks_this_month = _action_delta(
        "website_click_count", lifetime_actions["website_click_count"]
    )
    # WHY: same snapshot-diff as the taps — this month's MKB-referred views is
    # the lifetime count now minus the prior snapshot's stored total. On the
    # first report (no prior snapshot) it reports the lifetime total, framed
    # "since you joined" by the email, like every other counter here.
    mkb_referred_views_this_month = _action_delta(
        "mkb_referred_view_count", lifetime_actions["mkb_referred_view_count"]
    )

    messages_this_month = await _count_messages_in_period(db, business_id, current_period)
    trend = _trend(views_this_month, views_last_month, is_first)

    # WHY thin-views uses THIS month's number (not lifetime): the email's job is
    # to reflect the reporting period. A listing with thousands of lifetime
    # views but a quiet month still benefits from the caption nudge.
    is_thin = views_this_month < THIN_VIEWS_THRESHOLD

    return MonthlyReport(
        business_id=business_id,
        business_name=business_name,
        period_key=current_period,
        period_label=month_label(current_period),
        views_this_month=views_this_month,
        views_last_month=views_last_month,
        messages_this_month=messages_this_month,
        calls_this_month=calls_this_month,
        directions_this_month=directions_this_month,
        website_clicks_this_month=website_clicks_this_month,
        mkb_referred_views_this_month=mkb_referred_views_this_month,
        trend=trend,
        is_first_report=is_first,
        is_thin_views=is_thin,
    )
