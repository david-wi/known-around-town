"""Behavioural-equivalence tests for the batched copy-block resolution.

The editable-wording system (`app.services.copy`) resolves a snippet by trying
scopes most-specific -> least (business -> category -> neighborhood -> city ->
network -> global default) and returning the first ACTIVE override.

Two paths now exist:

* the original per-key path (`get_copy`, one `find_one` per scope level), and
* a primed/batched path (`CopyResolver.prime` loads every override for the
  page's scope set in ONE query, then `.get` resolves from memory).

The contract is that the primed path returns EXACTLY what the per-key path
returns for every input. These tests pin that contract across every edge case
the cascade has: overrides at each scope level, no override at all, the two
ways a row can be inactive (future `active_from`, past `active_until`),
`{placeholder}` substitution, and multiple locales. They also confirm the
primed path actually issues far fewer queries, and that a `.get` whose scope
dimension was not primed falls back to the always-correct per-key path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import copy as copy_svc
from app.services.copy import CopyResolver, get_copy


# WHY: production reads through Motor configured with tz_aware=True, so
# datetimes round-trip as timezone-aware. mongomock-motor strips tzinfo on read
# (returns naive UTC). The copy code computes `now` as tz-aware and compares it
# to the stored active_from/active_until, so under bare mongomock that
# comparison would raise "can't compare offset-naive and offset-aware" in BOTH
# resolution paths — masking the real production behaviour we mean to test.
# These thin wrappers re-attach UTC to datetimes coming back from mongomock so
# the test environment matches production's tz_aware=True client exactly.

def _tz_aware(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _coerce_doc(doc):
    if doc is None:
        return None
    return {k: _tz_aware(v) for k, v in doc.items()}


class _AwareCursor:
    """Wraps a mongomock cursor, coercing naive datetimes to UTC on iteration."""

    def __init__(self, cursor):
        self._cursor = cursor

    def __aiter__(self):
        self._it = self._cursor.__aiter__()
        return self

    async def __anext__(self):
        return _coerce_doc(await self._it.__anext__())

    async def to_list(self, length=None):
        return [_coerce_doc(d) for d in await self._cursor.to_list(length)]


class _AwareCollection:
    """copy_blocks proxy that mimics Motor tz_aware=True on reads."""

    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, *a, **k):
        return _coerce_doc(await self._coll.find_one(*a, **k))

    def find(self, *a, **k):
        return _AwareCursor(self._coll.find(*a, **k))

    async def insert_one(self, *a, **k):
        return await self._coll.insert_one(*a, **k)


class _AwareDb:
    """Database proxy exposing a tz-aware copy_blocks collection."""

    def __init__(self, db):
        self._db = db
        self.copy_blocks = _AwareCollection(db.copy_blocks)


NETWORK_ID = "net-beauty"
CITY_ID = "city-miami"
CATEGORY_SLUG = "hair-salons"
NEIGHBORHOOD_SLUG = "wynwood"
BUSINESS_ID = "biz-1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _insert(db, **fields) -> None:
    """Insert one copy_blocks row, filling the columns the resolver reads.

    Mirrors the real document shape: tz-aware datetimes (the production Motor
    client uses tz_aware=True), an explicit locale, and explicit None for the
    active-window bounds unless overridden.
    """
    doc = {
        "scope_type": fields["scope_type"],
        "scope_ref": fields.get("scope_ref", {}),
        "key": fields["key"],
        "value": fields["value"],
        "locale": fields.get("locale", "en-US"),
        "active_from": fields.get("active_from"),
        "active_until": fields.get("active_until"),
    }
    await db.copy_blocks.insert_one(doc)


async def _seed(db) -> None:
    """A representative spread of overrides across every scope level + state."""
    past = _now() - timedelta(days=1)
    future = _now() + timedelta(days=1)

    # --- Same key overridden at every scope level (tests most-specific-wins) ---
    await _insert(db, scope_type="global", scope_ref={}, key="ladder", value="global-val")
    await _insert(db, scope_type="network", scope_ref={"network_id": NETWORK_ID}, key="ladder", value="network-val")
    await _insert(db, scope_type="city", scope_ref={"city_id": CITY_ID}, key="ladder", value="city-val")
    await _insert(db, scope_type="business", scope_ref={"business_id": BUSINESS_ID}, key="ladder", value="business-val")

    # --- Override only at global ---
    await _insert(db, scope_type="global", scope_ref={}, key="only.global", value="g-only")

    # --- Override only at network ---
    await _insert(db, scope_type="network", scope_ref={"network_id": NETWORK_ID}, key="only.network", value="n-only")

    # --- Override only at city ---
    await _insert(db, scope_type="city", scope_ref={"city_id": CITY_ID}, key="only.city", value="c-only")

    # --- Override only at business ---
    await _insert(db, scope_type="business", scope_ref={"business_id": BUSINESS_ID}, key="only.business", value="b-only")

    # --- Override at category scope (needs city_id + category_slug) ---
    await _insert(
        db, scope_type="category",
        scope_ref={"city_id": CITY_ID, "category_slug": CATEGORY_SLUG},
        key="only.category", value="cat-only",
    )

    # --- Override at neighborhood scope (needs city_id + neighborhood_slug) ---
    await _insert(
        db, scope_type="neighborhood",
        scope_ref={"city_id": CITY_ID, "neighborhood_slug": NEIGHBORHOOD_SLUG},
        key="only.neighborhood", value="nb-only",
    )

    # --- Inactive via FUTURE active_from: city override not yet live, so the
    #     network value below must win instead. ---
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="windowed.from", value="city-future", active_from=future,
    )
    await _insert(
        db, scope_type="network", scope_ref={"network_id": NETWORK_ID},
        key="windowed.from", value="network-live",
    )

    # --- Inactive via PAST active_until: city override expired, network wins. ---
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="windowed.until", value="city-expired", active_until=past,
    )
    await _insert(
        db, scope_type="network", scope_ref={"network_id": NETWORK_ID},
        key="windowed.until", value="network-live2",
    )

    # --- Active window that DOES cover now (both bounds set, now inside) ---
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="windowed.active", value="city-active",
        active_from=past, active_until=future,
    )

    # --- A DEFAULTS-backed key with a {placeholder} and no DB override.
    #     "footer.legal" = "© {year} {network_name}." in DEFAULTS. ---
    # (no insert — resolved from DEFAULTS)

    # --- fmt substitution against a DB override (not just a default) ---
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="fmt.db", value="Welcome to {city_name}, {network_name}",
    )

    # --- Multi-locale: same key, two locales, distinct values ---
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="locale.key", value="hello", locale="en-US",
    )
    await _insert(
        db, scope_type="city", scope_ref={"city_id": CITY_ID},
        key="locale.key", value="hola", locale="es-ES",
    )


# Inputs as (key, fmt, scope-dims) the resolver will be asked for. Each is run
# through BOTH paths and the results must be identical.
_CASES = [
    ("ladder", None, {}),                                   # business wins (when primed w/ business)
    ("ladder", None, {"network_only": True}),               # network/city/global only
    ("only.global", None, {}),
    ("only.network", None, {}),
    ("only.city", None, {}),
    ("only.business", None, {"business": True}),
    ("only.category", None, {"category": True}),
    ("only.neighborhood", None, {"neighborhood": True}),
    ("windowed.from", None, {}),                            # future-dated city skipped
    ("windowed.until", None, {}),                           # expired city skipped
    ("windowed.active", None, {}),                          # in-window city used
    ("no.override.anywhere", None, {}),                     # -> None (no DEFAULTS entry)
    ("footer.legal", {"year": "2026", "network_name": "Knows Beauty"}, {}),  # DEFAULTS + fmt
    ("fmt.db", {"city_name": "Miami", "network_name": "Knows Beauty"}, {}),  # DB override + fmt
    ("home.hero.eyebrow", {"city_name": "Miami"}, {}),      # DEFAULTS + fmt, format key present
]


def _dims(case_dims):
    """Translate a compact case spec into the kwargs both paths accept."""
    kw = {}
    if case_dims.get("business"):
        kw["business_id"] = BUSINESS_ID
    if case_dims.get("category"):
        kw["category_slug"] = CATEGORY_SLUG
    if case_dims.get("neighborhood"):
        kw["neighborhood_slug"] = NEIGHBORHOOD_SLUG
    return kw


@pytest.mark.asyncio
async def test_primed_matches_per_key_for_every_case(mock_db, monkeypatch):
    """The batched path returns EXACTLY the per-key path's value, every case."""
    # Route copy.get_db()/CopyResolver.prime at the mongomock database.
    monkeypatch.setattr(copy_svc, "get_db", lambda: _AwareDb(mock_db))
    await _seed(mock_db)

    for key, fmt, case_dims in _CASES:
        kw = _dims(case_dims)

        # OLD path: direct get_copy with full scope, no cache.
        old = await get_copy(
            key,
            network_id=NETWORK_ID,
            city_id=CITY_ID,
            locale="en-US",
            fmt=fmt,
            **kw,
        )

        # NEW path: a resolver primed for exactly these page dimensions.
        resolver = CopyResolver(
            network_id=NETWORK_ID,
            city_id=CITY_ID,
            network_name="Knows Beauty",
            city_name="Miami",
        )
        await resolver.prime(**kw)
        # `.get` derives fmt itself; for an apples-to-apples value comparison we
        # call the underlying get_copy with the resolver's cache + the same fmt.
        new = await get_copy(
            key,
            network_id=NETWORK_ID,
            city_id=CITY_ID,
            locale="en-US",
            fmt=fmt,
            cache=resolver._cache,
            **kw,
        )

        assert new == old, (
            f"MISMATCH for key={key!r} dims={case_dims}: "
            f"per-key={old!r} primed={new!r}"
        )


@pytest.mark.asyncio
async def test_multi_locale_resolves_independently(mock_db, monkeypatch):
    """A primed resolver only ever sees its own locale's rows."""
    monkeypatch.setattr(copy_svc, "get_db", lambda: _AwareDb(mock_db))
    await _seed(mock_db)

    en = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID, locale="en-US")
    await en.prime()
    es = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID, locale="es-ES")
    await es.prime()

    # Per-key reference values.
    en_old = await get_copy("locale.key", network_id=NETWORK_ID, city_id=CITY_ID, locale="en-US")
    es_old = await get_copy("locale.key", network_id=NETWORK_ID, city_id=CITY_ID, locale="es-ES")

    en_new = await get_copy("locale.key", network_id=NETWORK_ID, city_id=CITY_ID, locale="en-US", cache=en._cache)
    es_new = await get_copy("locale.key", network_id=NETWORK_ID, city_id=CITY_ID, locale="es-ES", cache=es._cache)

    assert en_old == "hello" and en_new == "hello"
    assert es_old == "hola" and es_new == "hola"


@pytest.mark.asyncio
async def test_resolver_get_matches_full_render(mock_db, monkeypatch):
    """End-to-end: CopyResolver.get (which builds fmt internally) matches the
    per-key get_copy with the equivalent fmt, including {placeholder} keys."""
    monkeypatch.setattr(copy_svc, "get_db", lambda: _AwareDb(mock_db))
    await _seed(mock_db)

    resolver = CopyResolver(
        network_id=NETWORK_ID, city_id=CITY_ID,
        network_name="Knows Beauty", city_name="Miami",
    )
    await resolver.prime()

    # footer.legal uses {year} + {network_name}; resolver supplies them.
    got = await resolver.get("footer.legal")
    year = str(datetime.now(timezone.utc).year)
    assert got == f"© {year} Knows Beauty."

    # fmt.db is a DB override with {city_name}/{network_name}.
    got2 = await resolver.get("fmt.db")
    assert got2 == "Welcome to Miami, Knows Beauty"

    # A key with no override and no DEFAULTS entry resolves to None so callers
    # can use `await copy.get(key) or "fallback"`.
    assert await resolver.get("totally.absent.key") is None


@pytest.mark.asyncio
async def test_primed_path_issues_far_fewer_queries(mock_db, monkeypatch):
    """Priming should turn N per-snippet round-trips into a single query.

    We wrap the collection's find/find_one with counters and compare the
    number of DB calls the two paths make to resolve the same set of snippets.
    """
    await _seed(mock_db)

    # WHY: mongomock returns a fresh collection wrapper on every `db.copy_blocks`
    # access, so monkeypatching `find`/`find_one` on one access doesn't stick.
    # Instead we count at the tz-aware proxy layer the production code actually
    # calls through, which is a single stable object for the whole test.
    counters = {"find_one": 0, "find": 0}

    class _CountingCollection(_AwareCollection):
        async def find_one(self, *a, **k):
            counters["find_one"] += 1
            return await super().find_one(*a, **k)

        def find(self, *a, **k):
            counters["find"] += 1
            return super().find(*a, **k)

    class _CountingDb(_AwareDb):
        def __init__(self, db):
            self._db = db
            self.copy_blocks = _CountingCollection(db.copy_blocks)

    counting_db = _CountingDb(mock_db)
    monkeypatch.setattr(copy_svc, "get_db", lambda: counting_db)

    keys = ["only.global", "only.network", "only.city", "ladder",
            "windowed.active", "fmt.db", "no.override.anywhere"]

    # OLD path: one find_one per scope level per key.
    counters["find_one"] = counters["find"] = 0
    for key in keys:
        await get_copy(key, network_id=NETWORK_ID, city_id=CITY_ID)
    old_total = counters["find_one"] + counters["find"]

    # NEW path: one find to prime, then zero DB calls per key.
    counters["find_one"] = counters["find"] = 0
    resolver = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID)
    await resolver.prime()
    for key in keys:
        await get_copy(key, network_id=NETWORK_ID, city_id=CITY_ID, cache=resolver._cache)
    new_total = counters["find_one"] + counters["find"]

    # The primed path must make exactly one DB call (the prime) regardless of
    # how many snippets are resolved, and strictly fewer than the per-key path.
    assert counters["find"] == 1
    assert counters["find_one"] == 0
    assert new_total < old_total, f"primed={new_total} not fewer than per-key={old_total}"


@pytest.mark.asyncio
async def test_unprimed_dimension_falls_back_to_per_key(mock_db, monkeypatch):
    """If a .get introduces a scope dimension the page did NOT prime, the
    cache must be bypassed so a real override at that scope is never missed."""
    monkeypatch.setattr(copy_svc, "get_db", lambda: _AwareDb(mock_db))
    await _seed(mock_db)

    # Prime ONLY city/network/global (no business dimension).
    resolver = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID)
    await resolver.prime()

    # Now ask for a key that has a BUSINESS-scope override, passing business_id.
    # The business scope was never primed; the primed fast-path would skip it
    # and wrongly fall through. The fallback to per-key must catch it.
    via_resolver = await get_copy(
        "only.business",
        network_id=NETWORK_ID, city_id=CITY_ID, business_id=BUSINESS_ID,
        cache=resolver._cache,
    )
    via_per_key = await get_copy(
        "only.business",
        network_id=NETWORK_ID, city_id=CITY_ID, business_id=BUSINESS_ID,
    )
    assert via_resolver == via_per_key == "b-only"


@pytest.mark.asyncio
async def test_duplicate_rows_resolve_deterministically(mock_db, monkeypatch):
    """If two rows exist for the same (scope, key, locale), both paths pick the
    same one (first active, insertion order)."""
    monkeypatch.setattr(copy_svc, "get_db", lambda: _AwareDb(mock_db))

    # Two active city-scope rows for the same key.
    await _insert(db=mock_db, scope_type="city", scope_ref={"city_id": CITY_ID}, key="dup", value="first")
    await _insert(db=mock_db, scope_type="city", scope_ref={"city_id": CITY_ID}, key="dup", value="second")

    old = await get_copy("dup", network_id=NETWORK_ID, city_id=CITY_ID)
    resolver = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID)
    await resolver.prime()
    new = await get_copy("dup", network_id=NETWORK_ID, city_id=CITY_ID, cache=resolver._cache)

    assert old == new == "first"


@pytest.mark.asyncio
async def test_reprime_widens_without_reloading_covered_scopes(mock_db, monkeypatch):
    """Calling prime() twice should widen coverage (a business-scope override
    becomes resolvable) without re-querying or double-loading scopes already
    primed. Result must still match the per-key path exactly."""
    await _seed(mock_db)

    counters = {"find": 0}

    class _CountingCollection(_AwareCollection):
        def find(self, *a, **k):
            counters["find"] += 1
            return super().find(*a, **k)

    class _CountingDb(_AwareDb):
        def __init__(self, db):
            self._db = db
            self.copy_blocks = _CountingCollection(db.copy_blocks)

    counting_db = _CountingDb(mock_db)
    monkeypatch.setattr(copy_svc, "get_db", lambda: counting_db)

    resolver = CopyResolver(network_id=NETWORK_ID, city_id=CITY_ID)
    await resolver.prime()                      # base: city/network/global
    assert counters["find"] == 1
    await resolver.prime(business_id=BUSINESS_ID)  # widen: adds business scope
    # Only the business scope was new, so exactly one more query ran (not a
    # re-query of the base scopes).
    assert counters["find"] == 2

    # The business-scope override is now resolvable from cache and matches.
    via_resolver = await get_copy(
        "only.business", network_id=NETWORK_ID, city_id=CITY_ID,
        business_id=BUSINESS_ID, cache=resolver._cache,
    )
    via_per_key = await get_copy(
        "only.business", network_id=NETWORK_ID, city_id=CITY_ID, business_id=BUSINESS_ID,
    )
    assert via_resolver == via_per_key == "b-only"

    # Re-priming an already-covered scope must issue NO new query.
    await resolver.prime()
    assert counters["find"] == 2

    # And a row in a base scope must not have been double-loaded: the "ladder"
    # key (overridden at global/network/city/business) still resolves to the
    # business value, identical to the per-key path.
    lad_new = await get_copy(
        "ladder", network_id=NETWORK_ID, city_id=CITY_ID,
        business_id=BUSINESS_ID, cache=resolver._cache,
    )
    lad_old = await get_copy(
        "ladder", network_id=NETWORK_ID, city_id=CITY_ID, business_id=BUSINESS_ID,
    )
    assert lad_new == lad_old == "business-val"
