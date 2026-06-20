"""Miami-Knows-Beauty-referred view tracking (KAT-039).

These tests pin the behaviour of the ``mkb_referred_view_count`` counter — the
subset of page views where the shopper clicked through from within Miami Knows
Beauty itself (a guide, on-site search, a category/neighborhood page, or a
sister listing). That distinction is what proves WE drove the traffic, which a
salon's free Google Business Profile can't show — so it must be captured at the
moment of the visit (it can never be reconstructed later).

They assert against real behaviour — call the business-page route, then read the
DB counters — never against comments. TestClient runs FastAPI background tasks
synchronously, so the $inc has happened by the time the request returns and we
can read the counts immediately.

Coverage:
  * a same-host referer increments BOTH page_view_count and mkb_referred_view_count;
  * an external referer (google.com) increments ONLY page_view_count;
  * a no-referer request increments ONLY page_view_count;
  * a bot User-Agent increments NEITHER counter;
  * the _is_mkb_referred decision function in isolation;
  * the owner-stats endpoint surfaces the new field;
  * compute_report snapshot-diffs the referred count month over month.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient


_HOST = "miami.knowsbeauty.localhost"
# A real browser User-Agent so the bot filter lets the view through and the
# counters fire. Mirrors test_shopper_actions / test_smoke.
_HUMAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
# A crawler User-Agent containing a fragment from _BOT_UA_FRAGMENTS so neither
# counter may fire.
_BOT_UA = "Googlebot/2.1 (+http://www.google.com/bot.html)"

# A referer URL on OUR OWN host — what an internal click from a guide, search,
# category, neighborhood, or sister listing looks like.
_INTERNAL_REFERER = f"http://{_HOST}/guides/best-balayage-miami"
# A referer from outside the network — Google search, social, the salon's own
# site. Must NOT count as MKB-driven.
_EXTERNAL_REFERER = "https://www.google.com/search?q=miami+hair+salon"
# What a click on the "As Featured on Miami Knows Beauty" website badge looks
# like: the referer is the SALON'S OWN external site, but the URL carries the
# ?ref=mkb-badge marker we stamped on the badge link. This MUST count as
# MKB-driven — the badge is traffic we drove.
_BADGE_REFERER = "https://thissalon.example.com/"
_BADGE_MARKER = "mkb-badge"


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


async def _insert_business(db, *, slug: str = "referer-test-salon",
                           claimed_email: Optional[str] = None) -> str:
    """Insert one live business in the seeded Miami beauty city."""
    network = await db.networks.find_one({"slug": "beauty"})
    city = await db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    biz_id = str(uuid.uuid4())
    doc: Dict[str, Any] = {
        "_id": biz_id,
        "network_id": network["_id"],
        "city_id": city["_id"],
        "name": "Referer Test Salon",
        "slug": slug,
        "status": "live",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wynwood"],
    }
    if claimed_email is not None:
        doc["claimed_email"] = claimed_email
    await db.businesses.insert_one(doc)
    return biz_id


def _count(db, biz_id: str, field: str) -> int:
    doc = asyncio.run(db.businesses.find_one({"_id": biz_id}))
    return int(doc.get(field) or 0)


def _visit(client, slug: str, *, referer: Optional[str], ua: str = _HUMAN_UA,
           ref: Optional[str] = None):
    headers = {"host": _HOST, "user-agent": ua}
    if referer is not None:
        headers["referer"] = referer
    path = f"/b/{slug}"
    if ref is not None:
        path = f"{path}?ref={ref}"
    return client.get(path, headers=headers)


# ─── Route-level counter behaviour (the core of KAT-039) ─────────────────────


def test_internal_referer_increments_both_counters(seeded_db, client):
    """A view clicked through from one of OUR pages bumps the total AND the
    Miami-Knows-Beauty-referred counter — the whole point of the feature."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_INTERNAL_REFERER)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 1


def test_external_referer_increments_only_total(seeded_db, client):
    """A view arriving from Google (an external host) counts toward the total
    but NEVER toward the MKB-referred number — we didn't send that visitor."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_EXTERNAL_REFERER)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 0


def test_no_referer_increments_only_total(seeded_db, client):
    """A typed URL or bookmark (no Referer header) counts toward the total only —
    we can't claim credit for a visit with no traceable source."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=None)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 0


def test_bot_user_agent_increments_neither_counter(seeded_db, client):
    """A crawler must inflate NEITHER counter, even with a same-host referer —
    bots are never real shopper interest and never our 'driven' traffic."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_INTERNAL_REFERER, ua=_BOT_UA)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 0
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 0


def test_mkb_referred_never_exceeds_total_across_mixed_visits(seeded_db, client):
    """Across a mix of internal and external visits, the referred count tracks
    exactly the internal ones and stays a subset of the total."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    _visit(client, "referer-test-salon", referer=_INTERNAL_REFERER)   # +1 both
    _visit(client, "referer-test-salon", referer=_EXTERNAL_REFERER)   # +1 total only
    _visit(client, "referer-test-salon", referer=None)                # +1 total only
    _visit(client, "referer-test-salon", referer=_INTERNAL_REFERER)   # +1 both
    assert _count(seeded_db, biz_id, "page_view_count") == 4
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 2


# ─── Website-badge clicks (the ?ref=mkb-badge marker) ────────────────────────


def test_badge_marker_with_external_referer_increments_both(seeded_db, client):
    """A click on our website badge arrives from the salon's OWN site (external
    referer) but carries the ?ref=mkb-badge marker. It MUST count as MKB-driven —
    the badge is our #1 way of sending the salon shoppers, and that traffic is
    exactly what we want to prove we drove."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_BADGE_REFERER, ref=_BADGE_MARKER)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 1


def test_badge_marker_with_no_referer_increments_both(seeded_db, client):
    """Some browsers strip the Referer on a cross-site navigation, so a badge
    click can land with the marker but no referer at all. The marker alone is
    enough to credit it as MKB-driven."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=None, ref=_BADGE_MARKER)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 1


def test_external_referer_with_wrong_marker_increments_only_total(seeded_db, client):
    """Only OUR exact badge marker counts. A different ?ref value plus an external
    referer is still just external traffic — the marker carve-out must not become
    a loophole that any ?ref query string can walk through."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_EXTERNAL_REFERER, ref="instagram")
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 1
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 0


def test_badge_marker_bot_increments_neither(seeded_db, client):
    """A crawler hitting the badge URL is still a bot — the marker must not let
    bot traffic inflate either counter."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = _visit(client, "referer-test-salon", referer=_BADGE_REFERER,
               ref=_BADGE_MARKER, ua=_BOT_UA)
    assert r.status_code == 200, r.text
    assert _count(seeded_db, biz_id, "page_view_count") == 0
    assert _count(seeded_db, biz_id, "mkb_referred_view_count") == 0


# ─── _is_mkb_referred in isolation (no HTTP layer) ───────────────────────────


def test_is_mkb_referred_decision_function():
    from app.routes.public.pages import _is_mkb_referred

    # Same host (with or without scheme/path/port) → MKB-driven.
    assert _is_mkb_referred("http://miami.knowsbeauty.localhost/guides/x", "miami.knowsbeauty.localhost") is True
    assert _is_mkb_referred("https://miami.knowsbeauty.com/c/hair", "miami.knowsbeauty.com") is True
    # Host header carrying a dev port still matches a port-less referer host.
    assert _is_mkb_referred("http://miami.knowsbeauty.localhost/x", "miami.knowsbeauty.localhost:8000") is True
    # Case-insensitive host comparison.
    assert _is_mkb_referred("http://MIAMI.knowsbeauty.com/x", "miami.knowsbeauty.com") is True
    # External host → not MKB-driven.
    assert _is_mkb_referred("https://www.google.com/search", "miami.knowsbeauty.com") is False
    # A different edition's host is NOT same-host (kept simple; documented caveat).
    assert _is_mkb_referred("https://austin.knowsbeauty.com/x", "miami.knowsbeauty.com") is False
    # No referer / empty / malformed → not MKB-driven, never raises.
    assert _is_mkb_referred(None, "miami.knowsbeauty.com") is False
    assert _is_mkb_referred("", "miami.knowsbeauty.com") is False
    assert _is_mkb_referred("not a url", "miami.knowsbeauty.com") is False
    assert _is_mkb_referred("http://", "miami.knowsbeauty.com") is False

    # Badge marker counts even with an EXTERNAL referer (the salon's own site).
    assert _is_mkb_referred("https://thissalon.example.com/", "miami.knowsbeauty.com",
                            "mkb-badge") is True
    # Marker counts even with NO referer at all (browser stripped it).
    assert _is_mkb_referred(None, "miami.knowsbeauty.com", "mkb-badge") is True
    # A non-matching marker is NOT a free pass — external referer stays uncounted.
    assert _is_mkb_referred("https://www.google.com/x", "miami.knowsbeauty.com",
                            "instagram") is False
    assert _is_mkb_referred("https://www.google.com/x", "miami.knowsbeauty.com",
                            "") is False
    # Same-host still wins regardless of the marker argument (backwards-compatible).
    assert _is_mkb_referred("https://miami.knowsbeauty.com/c/hair",
                            "miami.knowsbeauty.com", None) is True
    # The marker constant the link builder uses is exactly what the detector checks.
    from app.routes.public.pages import MKB_BADGE_REF_MARKER
    assert MKB_BADGE_REF_MARKER == "mkb-badge"


# ─── Owner stats endpoint surfaces the new field ─────────────────────────────


def _signed_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session

    return sign_session(email)


def test_owner_stats_returns_mkb_referred_count(seeded_db, client):
    email = "referer-owner@example.com"
    biz_id = asyncio.run(_insert_business(seeded_db, claimed_email=email))
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz_id},
            {"$set": {"page_view_count": 20, "mkb_referred_view_count": 7}},
        )
    )
    r = client.get(
        "/api/v1/owner/stats",
        headers={"host": _HOST},
        cookies={"kb_owner_session": _signed_cookie(email)},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["page_view_count"] == 20
    assert data["mkb_referred_view_count"] == 7


def test_owner_stats_mkb_referred_defaults_zero(seeded_db, client):
    """A listing that predates the counter (field absent) reports 0, not an error."""
    email = "referer-owner2@example.com"
    asyncio.run(_insert_business(seeded_db, slug="referer-test-salon-2", claimed_email=email))
    r = client.get(
        "/api/v1/owner/stats",
        headers={"host": _HOST},
        cookies={"kb_owner_session": _signed_cookie(email)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["mkb_referred_view_count"] == 0


# ─── Monthly report snapshot-diffs the referred count ────────────────────────


def _biz(business_id="biz-mkb", views=0, mkb_referred=0):
    return {
        "_id": business_id,
        "name": "Glow Salon",
        "page_view_count": views,
        "mkb_referred_view_count": mkb_referred,
    }


async def test_monthly_report_first_run_uses_lifetime_mkb_referred(mock_db):
    from app.services.monthly_report import compute_report

    report = await compute_report(
        mock_db, _biz(views=30, mkb_referred=12),
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
    # First report has no prior snapshot, so it reports the lifetime total.
    assert report.mkb_referred_views_this_month == 12
    assert report.has_mkb_referral is True


async def test_monthly_report_second_month_diffs_mkb_referred(mock_db):
    from app.services.monthly_report import compute_report

    # June snapshot: 12 referred so far.
    await compute_report(
        mock_db, _biz(views=30, mkb_referred=12),
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
    # July: lifetime grew to 20 referred → this month's gain is 8.
    report = await compute_report(
        mock_db, _biz(views=55, mkb_referred=20),
        now=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert report.mkb_referred_views_this_month == 8
    assert report.has_mkb_referral is True


async def test_monthly_report_zero_mkb_referral_hides_credit(mock_db):
    from app.services.monthly_report import compute_report

    report = await compute_report(
        mock_db, _biz(views=15, mkb_referred=0),
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
    assert report.mkb_referred_views_this_month == 0
    # has_mkb_referral is False so the email omits the credit line entirely —
    # a month with no referred views never reads "we sent you 0 visitors".
    assert report.has_mkb_referral is False
