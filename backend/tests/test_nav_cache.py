"""Tests for the in-process TTL cache over the navigation lookups.

`app.services.content` caches `list_categories`, `list_neighborhoods`, and
`list_cities` so the header nav and footer don't re-query MongoDB on every
public page render. These tests pin three properties:

1. Cache HIT — repeated calls within the TTL run the underlying DB query only
   ONCE (we count queries through a wrapper).
2. Behaviour-equivalence — the cached value equals what an uncached call
   returns (same documents, same order).
3. TTL EXPIRY — after the TTL elapses, the data is refetched (so an edit shows
   up within the TTL bound). We drive the clock by monkeypatching the cache's
   clock seam rather than sleeping.

Also covered: each function keys its cache on its own argument(s) so different
tenants/parents don't share an entry, and `clear_nav_cache()` busts the cache.

The DB is mongomock (see conftest). We never sleep — the cache reads time from
`content._nav_clock`, which we patch to a controllable fake.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.services import content as content_svc


# ---------------------------------------------------------------------------
# Helpers: a controllable clock and a query-counting database wrapper.
# ---------------------------------------------------------------------------
class _FakeClock:
    """A monotonic-style clock we can advance by hand, in seconds."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _CountingCursor:
    def __init__(self, cursor, counters):
        self._cursor = cursor
        self._counters = counters

    def sort(self, *a, **k):
        # Motor cursors are chainable; mirror that so the production code's
        # `.find(...).sort(...).to_list(...)` keeps working through the wrapper.
        self._cursor = self._cursor.sort(*a, **k)
        return self

    async def to_list(self, length=None):
        return await self._cursor.to_list(length)


class _CountingCollection:
    """Wraps one mongomock collection and counts every `find` call."""

    def __init__(self, coll, counters):
        self._coll = coll
        self._counters = counters

    def find(self, *a, **k):
        self._counters["find"] += 1
        return _CountingCursor(self._coll.find(*a, **k), self._counters)


class _CountingDb:
    """Exposes counting wrappers for the three nav collections."""

    def __init__(self, db, counters):
        self._db = db
        self._counters = counters
        self.categories = _CountingCollection(db.categories, counters)
        self.neighborhoods = _CountingCollection(db.neighborhoods, counters)
        self.cities = _CountingCollection(db.cities, counters)


async def _seed_nav(db) -> None:
    """Insert a small representative spread across all three nav collections."""
    city_id = "city-1"
    network_id = "net-1"

    await db.categories.insert_many(
        [
            {"_id": "c1", "city_id": city_id, "slug": "hair", "name": "Hair",
             "parent_slug": None, "order": 1, "status": "active"},
            {"_id": "c2", "city_id": city_id, "slug": "nails", "name": "Nails",
             "parent_slug": None, "order": 2, "status": "active"},
            # A sub-category (has a parent) — must NOT show up in the top-level
            # (parent_slug=None) query, and proves keying on parent_slug.
            {"_id": "c3", "city_id": city_id, "slug": "balayage", "name": "Balayage",
             "parent_slug": "hair", "order": 1, "status": "active"},
            # Archived — excluded from every query.
            {"_id": "c4", "city_id": city_id, "slug": "old", "name": "Old",
             "parent_slug": None, "order": 9, "status": "archived"},
        ]
    )
    await db.neighborhoods.insert_many(
        [
            {"_id": "n1", "city_id": city_id, "slug": "wynwood", "name": "Wynwood",
             "listed_count": 5, "order": 1, "status": "active"},
            # listed_count == 0 — hidden from nav.
            {"_id": "n2", "city_id": city_id, "slug": "ghost", "name": "Ghost",
             "listed_count": 0, "order": 2, "status": "active"},
        ]
    )
    await db.cities.insert_many(
        [
            {"_id": "city-1", "network_id": network_id, "slug": "miami", "name": "Miami",
             "status": "active"},
            {"_id": "city-2", "network_id": network_id, "slug": "tampa", "name": "Tampa",
             "status": "active"},
        ]
    )


@pytest.fixture
def fake_clock(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(content_svc, "_nav_clock", clock)
    return clock


@pytest.fixture
def counters(mock_db, monkeypatch):
    """Route content's get_db at a query-counting wrapper over mongomock."""
    c = {"find": 0}
    counting_db = _CountingDb(mock_db, c)
    monkeypatch.setattr(content_svc, "get_db", lambda: counting_db)
    return c


# ---------------------------------------------------------------------------
# (a) Cache HIT: repeated calls within the TTL run the DB query exactly once.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repeat_calls_within_ttl_hit_cache(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    # First call: one query. Three more calls well inside the TTL: zero queries.
    for _ in range(4):
        await content_svc.list_categories("city-1")
    assert counters["find"] == 1, "expected exactly one DB query for 4 cached reads"

    counters["find"] = 0
    for _ in range(4):
        await content_svc.list_neighborhoods("city-1")
    assert counters["find"] == 1

    counters["find"] = 0
    for _ in range(4):
        await content_svc.list_cities("net-1")
    assert counters["find"] == 1


# ---------------------------------------------------------------------------
# (b) Behaviour-equivalence: the cached value equals the uncached value.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cached_value_equals_uncached(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    # Uncached reference: read with the cache empty, then clear so the next read
    # also starts cold and we can compare cold-vs-warm.
    cold_categories = await content_svc.list_categories("city-1")
    cold_neighborhoods = await content_svc.list_neighborhoods("city-1")
    cold_cities = await content_svc.list_cities("net-1")
    content_svc.clear_nav_cache()

    # Warm path: first read populates the cache, second read serves from it.
    first_categories = await content_svc.list_categories("city-1")
    warm_categories = await content_svc.list_categories("city-1")
    assert first_categories == cold_categories
    assert warm_categories == cold_categories

    first_neighborhoods = await content_svc.list_neighborhoods("city-1")
    warm_neighborhoods = await content_svc.list_neighborhoods("city-1")
    assert first_neighborhoods == cold_neighborhoods
    assert warm_neighborhoods == cold_neighborhoods

    first_cities = await content_svc.list_cities("net-1")
    warm_cities = await content_svc.list_cities("net-1")
    assert first_cities == cold_cities
    assert warm_cities == cold_cities

    # And the cached lists honour the production filters/order:
    assert [c["slug"] for c in cold_categories] == ["hair", "nails"]  # archived + sub-cat excluded
    assert [n["slug"] for n in cold_neighborhoods] == ["wynwood"]      # listed_count==0 hidden
    assert [c["slug"] for c in cold_cities] == ["miami", "tampa"]      # alphabetical


# ---------------------------------------------------------------------------
# (c) TTL expiry: after the TTL elapses, the data is refetched (and reflects an
#     edit made directly in the DB).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_data_refetched_after_ttl_expires(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    first = await content_svc.list_categories("city-1")
    assert [c["slug"] for c in first] == ["hair", "nails"]
    assert counters["find"] == 1

    # Edit the DB directly (bypassing the cache-clearing admin route) and read
    # again while still inside the TTL — the stale cached list is returned.
    await mock_db.categories.insert_one(
        {"_id": "c5", "city_id": "city-1", "slug": "lashes", "name": "Lashes",
         "parent_slug": None, "order": 3, "status": "active"}
    )
    fake_clock.advance(content_svc._NAV_CACHE_TTL_SECONDS - 1)  # just under TTL
    still_cached = await content_svc.list_categories("city-1")
    assert [c["slug"] for c in still_cached] == ["hair", "nails"], (
        "within the TTL the cached (pre-edit) list should still be served"
    )
    assert counters["find"] == 1, "no refetch while the entry is still fresh"

    # Cross the TTL boundary — now the next read must refetch and see the edit.
    fake_clock.advance(2)  # now strictly past expiry
    refreshed = await content_svc.list_categories("city-1")
    assert [c["slug"] for c in refreshed] == ["hair", "nails", "lashes"], (
        "after the TTL expires the list must be refetched and include the edit"
    )
    assert counters["find"] == 2, "exactly one refetch after expiry"


# ---------------------------------------------------------------------------
# Keying: each function caches per-argument, so distinct inputs don't collide.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cache_keys_on_arguments(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    top_level = await content_svc.list_categories("city-1")            # parent_slug=None
    sub = await content_svc.list_categories("city-1", parent_slug="hair")
    assert counters["find"] == 2, "different parent_slug must be a separate query/key"
    assert [c["slug"] for c in top_level] == ["hair", "nails"]
    assert [c["slug"] for c in sub] == ["balayage"]

    # A different city_id is a different key (here it has no rows, but still its
    # own cache entry and its own query).
    counters["find"] = 0
    await content_svc.list_categories("city-other")
    assert counters["find"] == 1


# ---------------------------------------------------------------------------
# clear_nav_cache() busts the cache (the admin write-route invalidation path).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_clear_nav_cache_forces_refetch(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    await content_svc.list_categories("city-1")
    await content_svc.list_categories("city-1")
    assert counters["find"] == 1  # second read served from cache

    content_svc.clear_nav_cache()
    await content_svc.list_categories("city-1")
    assert counters["find"] == 2, "after clear_nav_cache the next read must refetch"


# ---------------------------------------------------------------------------
# RED/GREEN guard: if caching is bypassed (e.g. someone removes the cache check
# from list_categories), the "single query" assertion above MUST fail. We prove
# the test has teeth by simulating the no-cache behaviour and asserting the
# query count would climb — i.e. the cache test is not vacuously green.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_without_cache_query_runs_every_call(mock_db, fake_clock, counters):
    await _seed_nav(mock_db)

    # Simulate "caching disabled" by clearing the cache before every call, which
    # forces the DB query each time — the same query pattern the OLD (uncached)
    # code had. If the cache-hit test were vacuous, this contrast wouldn't hold.
    for _ in range(4):
        content_svc.clear_nav_cache()
        await content_svc.list_categories("city-1")
    assert counters["find"] == 4, (
        "with caching bypassed every call must hit the DB — proves the cache-hit "
        "test (1 query for N reads) is actually exercising the cache"
    )
