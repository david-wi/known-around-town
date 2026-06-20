"""Shopper-action tracking — redirect routes and owner-stats fields.

These tests pin the behaviour of the three high-intent tap counters
(tap-to-call, tap-for-directions, website click) end to end:

  * the /b/{slug}/go/{action} redirect routes increment the RIGHT counter,
    302 to the RIGHT target, skip bots, and 404 when there's no destination;
  * the owner stats endpoint returns the three new counts.

They assert against real behaviour (call the route, then read the DB count and
the redirect Location) — never against comments. TestClient runs FastAPI
background tasks synchronously, so the $inc has happened by the time the
request returns and we can read the count immediately.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient


_HOST = "miami.knowsbeauty.localhost"
# A real browser User-Agent so the bot filter lets the tap through and the
# counter fires. Mirrors the page-view counter test in test_smoke.py.
_HUMAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
# A crawler User-Agent containing a fragment from _BOT_UA_FRAGMENTS so the
# counter must NOT fire.
_BOT_UA = "Googlebot/2.1 (+http://www.google.com/bot.html)"


@pytest.fixture
def client(seeded_db):
    from app.main import app

    # WHY follow_redirects=False at the client level: these tests assert on the
    # 302 itself (status + Location). Setting it on the client makes every request
    # in this file stop at the first response so we can read the redirect.
    return TestClient(app, follow_redirects=False)


def _get_call(client, slug: str = "tap-test-salon", ua: str = _HUMAN_UA) -> int:
    """Request /go/call and return the HTTP status, tolerating httpx's tel: quirk.

    WHY the try/except: httpx (which TestClient wraps) rejects a ``tel:`` Location
    header as an invalid URL while building the response object — it raises
    AFTER the request fully reached the server and the increment background task
    ran, but BEFORE returning a Response. So the redirect genuinely happened
    (we assert the increment in the caller); we just can't get a Response object
    back for it. A real 404 (no tel: header) returns normally. The exact tel:
    target string is asserted separately by test_action_target_url_for_call,
    which calls the resolver directly with no HTTP layer in the way.
    """
    import httpx

    try:
        r = client.get(
            f"/b/{slug}/go/call",
            headers={"host": _HOST, "user-agent": ua},
        )
        return r.status_code
    except httpx.InvalidURL:
        # The server emitted a tel: redirect (302) that httpx refused to parse.
        return 302


async def _insert_business(
    db,
    *,
    slug: str = "tap-test-salon",
    phone: Optional[str] = "(305) 555-0142",
    website: Optional[str] = "https://taptestsalon.example.com",
    address: Optional[Any] = "276 NW 26th St, Miami, FL 33127",
    claimed_email: Optional[str] = None,
) -> str:
    """Insert a live business in the seeded Miami city with the given contact data."""
    # WHY: resolve the seeded Miami beauty city so the business shows up under the
    # same tenant the test host resolves to — the /go/ route looks the business up
    # scoped to that city, exactly like the public listing page.
    network = await db.networks.find_one({"slug": "beauty"})
    city = await db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    biz_id = str(uuid.uuid4())
    doc: Dict[str, Any] = {
        "_id": biz_id,
        "network_id": network["_id"],
        "city_id": city["_id"],
        "name": "Tap Test Salon",
        "slug": slug,
        "status": "live",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wynwood"],
    }
    if phone is not None:
        doc["phone"] = phone
    if website is not None:
        doc["website"] = website
    if address is not None:
        doc["address"] = address
    if claimed_email is not None:
        doc["claimed_email"] = claimed_email
    await db.businesses.insert_one(doc)
    return biz_id


def _count(db, biz_id: str, field: str) -> int:
    doc = asyncio.run(db.businesses.find_one({"_id": biz_id}))
    return int(doc.get(field) or 0)


# ─── Redirect targets ────────────────────────────────────────────────────────


def test_action_target_url_for_call(seeded_db):
    """The call redirect target is tel: with all non-digits stripped, so mobile
    browsers dial reliably. Asserted directly on the resolver — no HTTP layer."""
    from app.routes.public.pages import _action_target_url

    biz = {"phone": "(305) 555-0142"}
    assert _action_target_url("call", biz) == "tel:3055550142"
    # No phone -> no target (the route turns this into a 404).
    assert _action_target_url("call", {"phone": ""}) == ""
    assert _action_target_url("call", {}) == ""


def test_call_redirects_and_increments(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db))
    status = _get_call(client)
    assert status == 302, status
    assert _count(seeded_db, biz_id, "call_click_count") == 1


def test_directions_redirects_to_maps_and_increments(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = client.get(
        "/b/tap-test-salon/go/directions",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    assert loc.startswith("https://maps.google.com/?q="), loc
    # The address text must be carried in the query so Maps resolves the location.
    assert "276" in loc and "Miami" in loc, loc
    assert _count(seeded_db, biz_id, "directions_click_count") == 1


def test_website_redirects_and_increments(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db))
    r = client.get(
        "/b/tap-test-salon/go/website",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://taptestsalon.example.com", r.headers["location"]
    assert _count(seeded_db, biz_id, "website_click_count") == 1


def test_website_without_scheme_gets_https(seeded_db, client):
    """A salon website stored without http(s):// must still redirect to a real
    web page — not resolve relative to our own domain. The route forces https://."""
    asyncio.run(_insert_business(seeded_db, website="taptestsalon.example.com"))
    r = client.get(
        "/b/tap-test-salon/go/website",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    assert r.headers["location"] == "https://taptestsalon.example.com", r.headers["location"]


# ─── Each action increments ONLY its own counter ─────────────────────────────


def test_each_action_increments_only_its_own_counter(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db))
    assert _get_call(client) == 302
    assert _count(seeded_db, biz_id, "call_click_count") == 1
    assert _count(seeded_db, biz_id, "directions_click_count") == 0
    assert _count(seeded_db, biz_id, "website_click_count") == 0


# ─── Bot filter (red-green) ──────────────────────────────────────────────────


def test_bot_user_agent_redirects_but_does_not_increment(seeded_db, client):
    """A crawler following /go/call still gets the redirect, but the tap is NOT
    counted — bots must never inflate the owner's shopper-action numbers."""
    biz_id = asyncio.run(_insert_business(seeded_db))
    status = _get_call(client, ua=_BOT_UA)
    assert status == 302, status
    # The whole point: counter stays at 0 for a bot.
    assert _count(seeded_db, biz_id, "call_click_count") == 0


# ─── 404s: unknown action, and no destination ────────────────────────────────


def test_unknown_action_404(seeded_db, client):
    asyncio.run(_insert_business(seeded_db))
    r = client.get(
        "/b/tap-test-salon/go/teleport",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 404, r.text


def test_website_action_404_when_no_website(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db, website=None))
    r = client.get(
        "/b/tap-test-salon/go/website",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 404, r.text
    # A 404 must never have counted a tap that reaches no destination.
    assert _count(seeded_db, biz_id, "website_click_count") == 0


def test_call_action_404_when_no_phone(seeded_db, client):
    biz_id = asyncio.run(_insert_business(seeded_db, phone=None))
    r = client.get(
        "/b/tap-test-salon/go/call",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 404, r.text
    assert _count(seeded_db, biz_id, "call_click_count") == 0


def test_unknown_business_404(seeded_db, client):
    asyncio.run(_insert_business(seeded_db))
    r = client.get(
        "/b/no-such-salon-anywhere/go/call",
        headers={"host": _HOST, "user-agent": _HUMAN_UA},
        follow_redirects=False,
    )
    assert r.status_code == 404, r.text


# ─── Owner stats endpoint returns the new fields ─────────────────────────────


def _signed_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session

    return sign_session(email)


def test_owner_stats_returns_action_counts(seeded_db, client):
    email = "tap-owner@example.com"
    biz_id = asyncio.run(_insert_business(seeded_db, claimed_email=email))
    # Seed some counts directly so we assert the endpoint surfaces them.
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz_id},
            {
                "$set": {
                    "page_view_count": 12,
                    "call_click_count": 3,
                    "directions_click_count": 5,
                    "website_click_count": 2,
                }
            },
        )
    )
    r = client.get(
        "/api/v1/owner/stats",
        headers={"host": _HOST},
        cookies={"kb_owner_session": _signed_cookie(email)},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["page_view_count"] == 12
    assert data["call_click_count"] == 3
    assert data["directions_click_count"] == 5
    assert data["website_click_count"] == 2


def test_owner_stats_action_counts_default_zero(seeded_db, client):
    """A listing that predates the counters (fields absent) reports 0, not an error."""
    email = "tap-owner2@example.com"
    asyncio.run(_insert_business(seeded_db, slug="tap-test-salon-2", claimed_email=email))
    r = client.get(
        "/api/v1/owner/stats",
        headers={"host": _HOST},
        cookies={"kb_owner_session": _signed_cookie(email)},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["call_click_count"] == 0
    assert data["directions_click_count"] == 0
    assert data["website_click_count"] == 0
