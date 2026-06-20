"""Unit tests for the monthly listing-report aggregation and snapshot math.

These exercise the real ``compute_report`` logic against a mongomock database
(via the ``mock_db`` fixture) so the snapshot read/write and the date-range
message count run for real — no patching of the math itself. The tests assert
on BEHAVIOR (the computed numbers), not on comments or source text, so a broken
implementation fails them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import monthly_report
from app.services.monthly_report import (
    THIN_VIEWS_THRESHOLD,
    compute_report,
    month_label,
    month_range,
    period_key,
)


def _biz(business_id: str = "biz-1", name: str = "Glow Salon", views: int = 0) -> dict:
    return {"_id": business_id, "name": name, "page_view_count": views}


# ── Pure helpers ─────────────────────────────────────────────────────────────

class TestPeriodHelpers:
    def test_period_key_format(self):
        assert period_key(datetime(2026, 6, 20, tzinfo=timezone.utc)) == "2026-06"
        assert period_key(datetime(2026, 1, 3, tzinfo=timezone.utc)) == "2026-01"

    def test_period_key_treats_naive_as_utc(self):
        # A naive datetime must not shift the month boundary.
        assert period_key(datetime(2026, 12, 31, 23, 0, 0)) == "2026-12"

    def test_month_label_friendly(self):
        assert month_label("2026-06") == "June 2026"
        assert month_label("2026-01") == "January 2026"

    def test_month_label_bad_input_falls_back(self):
        assert month_label("garbage") == "garbage"

    def test_month_range_is_half_open(self):
        start, end = month_range("2026-06")
        assert start == datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert end == datetime(2026, 7, 1, tzinfo=timezone.utc)

    def test_month_range_december_rolls_to_next_year(self):
        start, end = month_range("2026-12")
        assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
        assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)


# ── Snapshot math ────────────────────────────────────────────────────────────

class TestSnapshotMath:
    async def test_first_report_uses_lifetime_and_flags_first(self, mock_db):
        report = await compute_report(
            mock_db, _biz(views=42), now=datetime(2026, 6, 20, tzinfo=timezone.utc)
        )
        assert report.is_first_report is True
        assert report.views_this_month == 42  # lifetime, since no prior snapshot
        assert report.views_last_month is None
        assert report.trend == "first"

    async def test_first_report_writes_a_snapshot(self, mock_db):
        await compute_report(
            mock_db, _biz(views=42), now=datetime(2026, 6, 20, tzinfo=timezone.utc)
        )
        snap = await mock_db[monthly_report.SNAPSHOT_COLLECTION].find_one(
            {"business_id": "biz-1", "period_key": "2026-06"}
        )
        assert snap is not None
        assert snap["page_view_count"] == 42

    async def test_second_month_delta_is_lifetime_minus_prior_snapshot(self, mock_db):
        # June report at 42 lifetime views.
        await compute_report(mock_db, _biz(views=42), now=datetime(2026, 6, 20, tzinfo=timezone.utc))
        # July: lifetime grew to 60 → 18 views "this month".
        report = await compute_report(
            mock_db, _biz(views=60), now=datetime(2026, 7, 10, tzinfo=timezone.utc)
        )
        assert report.is_first_report is False
        assert report.views_this_month == 18
        # WHY "first": with only ONE prior snapshot we cannot compute a
        # last-month comparison (there's no month-before-last baseline), so
        # views_last_month is None and the trend stays "first" — the email then
        # avoids claiming an increase/decrease it can't back up. This is the
        # honest second-report behaviour; a real month-over-month trend needs
        # three snapshots (see test_views_last_month_computed_with_three_snapshots).
        assert report.views_last_month is None
        assert report.trend == "first"

    async def test_idempotent_second_run_same_month_keeps_baseline(self, mock_db):
        # June run #1 at 42.
        await compute_report(mock_db, _biz(views=42), now=datetime(2026, 6, 1, tzinfo=timezone.utc))
        # July run #1 at 60 → writes the 2026-07 snapshot at 60.
        first = await compute_report(mock_db, _biz(views=60), now=datetime(2026, 7, 5, tzinfo=timezone.utc))
        # July run #2 later same month at 75. The baseline for July must still be
        # the JUNE snapshot (42), NOT July's own just-written snapshot — so the
        # delta is 75 − 42 = 33, not 75 − 60 = 15.
        second = await compute_report(mock_db, _biz(views=75), now=datetime(2026, 7, 25, tzinfo=timezone.utc))
        assert first.views_this_month == 18  # 60 − 42
        assert second.views_this_month == 33  # 75 − 42 (baseline unchanged)
        # Exactly one July snapshot row exists (no duplicate).
        count = await mock_db[monthly_report.SNAPSHOT_COLLECTION].count_documents(
            {"business_id": "biz-1", "period_key": "2026-07"}
        )
        assert count == 1

    async def test_negative_delta_guarded_to_zero(self, mock_db):
        # June at 100 lifetime; then lifetime "resets" to 30 (manual correction).
        await compute_report(mock_db, _biz(views=100), now=datetime(2026, 6, 10, tzinfo=timezone.utc))
        report = await compute_report(
            mock_db, _biz(views=30), now=datetime(2026, 7, 10, tzinfo=timezone.utc)
        )
        # Must never show a negative number in an owner-facing email.
        assert report.views_this_month == 0

    async def test_views_last_month_computed_with_three_snapshots(self, mock_db):
        # May 10, June 40, July 70 → June delta = 30, July delta = 30 → flat.
        await compute_report(mock_db, _biz(views=10), now=datetime(2026, 5, 5, tzinfo=timezone.utc))
        await compute_report(mock_db, _biz(views=40), now=datetime(2026, 6, 5, tzinfo=timezone.utc))
        report = await compute_report(
            mock_db, _biz(views=70), now=datetime(2026, 7, 5, tzinfo=timezone.utc)
        )
        assert report.views_this_month == 30  # 70 − 40
        assert report.views_last_month == 30  # 40 − 10
        assert report.trend == "flat"

    async def test_trend_up_when_this_month_beats_last(self, mock_db):
        # May 10, June 20 (delta 10), July 100 (delta 80) → up.
        await compute_report(mock_db, _biz(views=10), now=datetime(2026, 5, 5, tzinfo=timezone.utc))
        await compute_report(mock_db, _biz(views=20), now=datetime(2026, 6, 5, tzinfo=timezone.utc))
        report = await compute_report(
            mock_db, _biz(views=100), now=datetime(2026, 7, 5, tzinfo=timezone.utc)
        )
        assert report.views_this_month == 80
        assert report.views_last_month == 10
        assert report.trend == "up"
        assert report.views_up_from_last_month is True

    async def test_trend_down_when_this_month_below_last(self, mock_db):
        # May 0, June 50 (delta 50), July 55 (delta 5) → down.
        await compute_report(mock_db, _biz(views=0), now=datetime(2026, 5, 5, tzinfo=timezone.utc))
        await compute_report(mock_db, _biz(views=50), now=datetime(2026, 6, 5, tzinfo=timezone.utc))
        report = await compute_report(
            mock_db, _biz(views=55), now=datetime(2026, 7, 5, tzinfo=timezone.utc)
        )
        assert report.views_this_month == 5
        assert report.views_last_month == 50
        assert report.trend == "down"
        assert report.views_up_from_last_month is False


# ── Thin-views detection (drives the caption branch in the email) ────────────

class TestThinViews:
    async def test_thin_when_below_threshold(self, mock_db):
        # First report with very few lifetime views is thin.
        report = await compute_report(
            mock_db, _biz(views=THIN_VIEWS_THRESHOLD - 1), now=datetime(2026, 6, 20, tzinfo=timezone.utc)
        )
        assert report.is_thin_views is True

    async def test_not_thin_at_threshold(self, mock_db):
        report = await compute_report(
            mock_db, _biz(views=THIN_VIEWS_THRESHOLD), now=datetime(2026, 6, 20, tzinfo=timezone.utc)
        )
        assert report.is_thin_views is False

    async def test_thin_uses_this_month_not_lifetime(self, mock_db):
        # Lifetime is large, but THIS month's gain is tiny → thin.
        await compute_report(mock_db, _biz(views=1000), now=datetime(2026, 6, 1, tzinfo=timezone.utc))
        report = await compute_report(
            mock_db, _biz(views=1002), now=datetime(2026, 7, 1, tzinfo=timezone.utc)
        )  # only +2 this month
        assert report.views_this_month == 2
        assert report.is_thin_views is True


# ── Messages this month (date-range count) ──────────────────────────────────

class TestMessageCount:
    async def test_counts_only_inquiries_in_the_period(self, mock_db):
        # Two inquiries in July, one in June, one in August → July count is 2.
        await mock_db.business_inquiries.insert_many(
            [
                {"business_id": "biz-1", "submitted_at": datetime(2026, 7, 2, tzinfo=timezone.utc)},
                {"business_id": "biz-1", "submitted_at": datetime(2026, 7, 28, tzinfo=timezone.utc)},
                {"business_id": "biz-1", "submitted_at": datetime(2026, 6, 30, tzinfo=timezone.utc)},
                {"business_id": "biz-1", "submitted_at": datetime(2026, 8, 1, tzinfo=timezone.utc)},
            ]
        )
        report = await compute_report(
            mock_db, _biz(views=5), now=datetime(2026, 7, 15, tzinfo=timezone.utc)
        )
        assert report.messages_this_month == 2

    async def test_boundary_is_half_open(self, mock_db):
        # An inquiry exactly at the first instant of July counts for July, not June.
        await mock_db.business_inquiries.insert_one(
            {"business_id": "biz-1", "submitted_at": datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)}
        )
        july = await compute_report(mock_db, _biz(views=5), now=datetime(2026, 7, 10, tzinfo=timezone.utc))
        assert july.messages_this_month == 1

    async def test_messages_for_other_business_not_counted(self, mock_db):
        await mock_db.business_inquiries.insert_one(
            {"business_id": "OTHER", "submitted_at": datetime(2026, 7, 2, tzinfo=timezone.utc)}
        )
        report = await compute_report(
            mock_db, _biz(views=5), now=datetime(2026, 7, 15, tzinfo=timezone.utc)
        )
        assert report.messages_this_month == 0
