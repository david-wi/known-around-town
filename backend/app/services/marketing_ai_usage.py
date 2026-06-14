"""Monthly usage tracking for AI marketing tools.

Featured subscribers get a fixed monthly allowance per tool:
  - Instagram captions: 50 per month
  - Ad copies:          20 per month

Usage is tracked in the ``marketing_ai_usage`` MongoDB collection, keyed by
(business_id, tool, year, month).  The increment is atomic so concurrent
requests can never race past the limit.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pymongo import ReturnDocument

from app.database import get_db

ToolName = Literal["caption", "ad_copy"]

# WHY: separate limits match the pricing page promise exactly.
# Captions (50) are generated daily by active owners; ad copy (20) is rarer.
# A dict keyed by ToolName string means a typo in a call site raises KeyError
# at test time, not silently applies no limit.
_MONTHLY_LIMITS: dict[str, int] = {
    "caption": 50,   # WHY: "50 AI captions/month" — pricing page Featured tier
    "ad_copy": 20,   # WHY: "20 AI ad copies/month" — pricing page Featured tier
}

_TOOL_LABELS: dict[str, str] = {
    "caption": "captions",
    "ad_copy": "ad copies",
}


def _current_period() -> tuple[int, int]:
    """Return (year, month) for the current UTC billing period."""
    now = datetime.now(timezone.utc)
    return now.year, now.month


def _reset_date_str(year: int, month: int) -> str:
    """Human-readable first day of the next billing month.

    WHY: tell owners exactly when their limit resets so they know to
    come back.  "Your limit resets on July 1, 2026" is actionable;
    "try again later" is not.
    """
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    return f"{calendar.month_name[next_month]} 1, {next_year}"


async def check_and_increment(business_id: str, tool: ToolName) -> None:
    """Atomically increment monthly usage and block at the limit.

    Raises HTTP 429 if the business has already used all allowed
    generations for the current calendar month.

    WHY atomic increment-then-check instead of check-then-increment:
    with check-then-increment, two concurrent caption requests can both
    read count=49 (under limit), both decide to proceed, and the owner
    ends up generating 51 captions.  The findAndModify $inc is atomic —
    the second request reads count=51 and is blocked.
    """
    limit = _MONTHLY_LIMITS[tool]
    year, month = _current_period()

    result = await get_db().marketing_ai_usage.find_one_and_update(
        {
            "business_id": business_id,
            "tool": tool,
            "year": year,
            "month": month,
        },
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    count = result["count"]
    if count > limit:
        label = _TOOL_LABELS[tool]
        reset = _reset_date_str(year, month)
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've used all {limit} AI {label} for this month. "
                f"Your limit resets on {reset}."
            ),
        )


async def get_usage(business_id: str, tool: ToolName) -> dict[str, int]:
    """Return current usage stats for a business and tool this month.

    Returns a dict with ``used`` and ``limit`` keys.  Useful for the
    owner dashboard to show a usage meter without incrementing the count.
    """
    limit = _MONTHLY_LIMITS[tool]
    year, month = _current_period()

    doc = await get_db().marketing_ai_usage.find_one(
        {
            "business_id": business_id,
            "tool": tool,
            "year": year,
            "month": month,
        }
    )
    used = doc["count"] if doc else 0
    return {"used": used, "limit": limit}
