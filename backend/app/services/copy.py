"""Cascading lookup for editable wording (`copy_blocks`).

Lookup order (most specific wins):
  business -> category(city) -> city -> network -> global default

Two resolution paths, with IDENTICAL semantics:

* Per-key (`get_copy` / an un-primed ``CopyResolver``): one ``find_one`` per
  scope level until the first active override is found. Correct but chatty —
  a page that renders dozens of snippets makes dozens of sequential Atlas
  round-trips.
* Primed/batched (``CopyResolver.prime`` + ``.get``): one ``find`` up front
  loads every override for the page's scope set, then each ``.get`` resolves
  from memory. Same cascade order, same active-window check, same formatting,
  same fall-through to ``DEFAULTS`` then ``None`` — just without the
  per-snippet round-trips. See ``prime`` for why this is safe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

from app.database import get_db
from app.models import CopyScopeType


# A cache key uniquely identifies one (scope, key) slot in the cascade. The
# scope_ref dict is reduced to a frozenset of its items so it is hashable and
# order-independent (e.g. {"city_id": x, "category_slug": y} matches regardless
# of insertion order). locale is NOT part of the key: a primed cache only ever
# holds one locale's rows (prime filters by locale), so adding it would be
# redundant.
_CacheKey = Tuple[str, FrozenSet[Tuple[str, str]], str]


def _scope_ref_fingerprint(scope_ref: Dict[str, str]) -> FrozenSet[Tuple[str, str]]:
    """Hashable, order-independent form of a scope_ref dict for cache keying."""
    return frozenset(scope_ref.items())


# Sentinel "key" used to record that a scope level was primed (queried), even
# when that scope had zero overrides. Chosen to be impossible as a real copy
# key (real keys are dotted lowercase identifiers like "home.hero.eyebrow"),
# so it can never collide with a stored row.
_PRIMED_MARKER = "\x00__primed__"


DEFAULTS: Dict[str, str] = {
    # Home page
    "home.hero.eyebrow": "{city_name}'s curated local guide",
    "home.hero.headline": "{city_name}'s best-kept addresses.",
    "home.hero.subhead": "A curated guide to the places locals book before the moment.",
    "home.categories.title": "Explore by category",
    "home.neighborhoods.title": "Explore by neighborhood",
    "home.featured.title": "Featured this month",
    "home.editorial.title": "From the editors",
    # Category page
    "category.hero.eyebrow": "{category_name} in {city_name}",
    "category.hero.subhead": "The places locals book.",
    "category.empty.title": "We're still building this list.",
    "category.empty.body": "Check back soon. If you run a {category_name} business in {city_name}, get listed.",
    # Neighborhood page — the eyebrow is the small all-caps tag above the
    # neighborhood name (e.g. "NEIGHBORHOOD GUIDE"). The subhead is a one-line
    # description of the neighborhood; if not set we leave it blank rather
    # than show a generic line that would look like editorial filler.
    "neighborhood.hero.eyebrow": "Neighborhood Guide",
    "neighborhood.hero.subhead": "",
    # Business profile
    "business.cta.book": "Book",
    "business.cta.call": "Call",
    "business.cta.website": "Visit website",
    "business.cta.directions": "Get directions",
    "business.claim.title": "Own this business?",
    "business.claim.body": "Claim free to add photos, respond to inquiries, and get found by people searching for salons in Miami.",
    "business.claim.cta": "Claim this listing",
    "business.section.known_for": "Known for",
    "business.section.best_for": "Best for",
    "business.section.before_booking": "Before you book",
    "business.section.services": "Services",
    "business.section.hours": "Hours",
    "business.section.contact": "Contact",
    "business.section.nearby": "Nearby",
    # Footer
    "footer.about.title": "About this guide",
    "footer.about.body": "{network_name} {city_name} is a curated local guide. Featured listings are clearly marked.",
    "footer.business.title": "For business owners",
    "footer.business.body": "Claim your profile or upgrade to a featured listing.",
    "footer.legal": "© {year} {network_name}.",
    # Badges
    "badge.editors_pick": "Editor's Pick",
    "badge.verified": "Verified",
    "badge.claimed": "Claimed",
    "badge.featured": "Featured",
    # Index disclosure
    "page.featured_disclosure": "Featured listings are paid placements. Editorial picks are not.",
}


def _scope_keys(
    network_id: Optional[str],
    city_id: Optional[str],
    category_slug: Optional[str],
    business_id: Optional[str],
    neighborhood_slug: Optional[str],
) -> Iterable[Tuple[str, Dict[str, str]]]:
    """Yield (scope_type, scope_ref) pairs from most specific to least."""
    if business_id:
        yield CopyScopeType.business.value, {"business_id": business_id}
    if category_slug and city_id:
        yield CopyScopeType.category.value, {"city_id": city_id, "category_slug": category_slug}
    if neighborhood_slug and city_id:
        yield CopyScopeType.neighborhood.value, {"city_id": city_id, "neighborhood_slug": neighborhood_slug}
    if city_id:
        yield CopyScopeType.city.value, {"city_id": city_id}
    if network_id:
        yield CopyScopeType.network.value, {"network_id": network_id}
    yield CopyScopeType.global_.value, {}


def _is_active(doc: Dict[str, Any], now: datetime) -> bool:
    """A row applies iff its active window covers ``now``.

    WHY: this is the single definition of "active" shared by both the per-key
    path (where ``active_from`` is pre-filtered in the Mongo query and only
    ``active_until`` is re-checked here) and the primed path (where the cache
    holds ALL rows and both bounds must be checked in memory). Keeping one
    function guarantees the two paths can never drift apart.
    """
    active_from = doc.get("active_from")
    if active_from is not None and active_from > now:
        return False
    active_until = doc.get("active_until")
    if active_until is not None and active_until < now:
        return False
    return True


async def get_copy(
    key: str,
    *,
    network_id: Optional[str] = None,
    city_id: Optional[str] = None,
    category_slug: Optional[str] = None,
    business_id: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
    locale: str = "en-US",
    fmt: Optional[Dict[str, str]] = None,
    cache: Optional[Dict[_CacheKey, List[Dict[str, Any]]]] = None,
) -> Optional[str]:
    """Resolve ``key`` through the scope cascade, most specific wins.

    When ``cache`` is supplied AND it covers every scope level this call
    needs, resolution happens entirely in memory (no DB round-trip). When it
    is missing, or does not cover the requested scope dimensions, the original
    per-key ``find_one`` cascade is used so correctness is never sacrificed
    for speed. See ``CopyResolver.prime``.
    """
    now = datetime.now(timezone.utc)

    scopes = list(
        _scope_keys(network_id, city_id, category_slug, business_id, neighborhood_slug)
    )

    # Fast path: every scope this lookup needs was primed into the cache.
    if cache is not None and _cache_covers(cache, scopes):
        for scope_type, scope_ref in scopes:
            ck: _CacheKey = (scope_type, _scope_ref_fingerprint(scope_ref), key)
            for doc in cache.get(ck, ()):  # rows already filtered to this locale
                if _is_active(doc, now):
                    return _format(doc["value"], fmt)
        # No active override at any scope — fall through to DEFAULTS, no DB hit.
        return _format_default(key, fmt)

    db = get_db()
    for scope_type, scope_ref in scopes:
        query = {
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "key": key,
            "locale": locale,
            "$or": [
                {"active_from": None},
                {"active_from": {"$lte": now}},
            ],
        }
        # `active_until` filter applied separately to keep $or simple.
        doc = await db.copy_blocks.find_one(query)
        if doc and (doc.get("active_until") is None or doc["active_until"] >= now):
            return _format(doc["value"], fmt)

    return _format_default(key, fmt)


def _format_default(key: str, fmt: Optional[Dict[str, str]]) -> Optional[str]:
    # WHY: returning None (rather than the key string) lets callers use the
    # idiomatic `await copy.get(key) or "fallback"` pattern. Returning the key
    # string previously caused literal "header.owners_cta" text to render when
    # neither a copy block nor a DEFAULTS entry existed.
    default = DEFAULTS.get(key)
    if default is None:
        return None
    return _format(default, fmt)


def _cache_covers(
    cache: Dict[_CacheKey, List[Dict[str, Any]]],
    scopes: List[Tuple[str, Dict[str, str]]],
) -> bool:
    """True iff the cache was primed for every scope this lookup will walk.

    WHY: a primed cache is keyed by the page's scope set. A ``.get`` that
    passes a scope dimension the page did NOT prime (e.g. a business_id on a
    page primed only for city+network+global) would, if resolved against the
    cache, silently skip the un-primed level and could miss an override that
    actually exists in the database. Detecting that here forces the slow but
    always-correct per-key path for such calls. Coverage is recorded by
    priming a sentinel marker per scope (see ``prime``); we check that marker
    rather than the presence of any matching row, because a scope with zero
    overrides is still "covered" — it was queried and found empty.
    """
    for scope_type, scope_ref in scopes:
        marker: _CacheKey = (scope_type, _scope_ref_fingerprint(scope_ref), _PRIMED_MARKER)
        if marker not in cache:
            return False
    return True


def _format(template: Optional[str], fmt: Optional[Dict[str, str]]) -> Optional[str]:
    if template is None:
        return None
    if not fmt:
        return template
    try:
        return template.format(**fmt)
    except (KeyError, IndexError):
        return template


class CopyResolver:
    """Per-request helper that bakes in the current tenant scope."""

    def __init__(
        self,
        *,
        network_id: Optional[str] = None,
        city_id: Optional[str] = None,
        network_name: str = "",
        city_name: str = "",
        locale: str = "en-US",
    ) -> None:
        self.network_id = network_id
        self.city_id = city_id
        self.network_name = network_name
        self.city_name = city_name
        self.locale = locale
        # Populated by ``prime``. While None, every ``.get`` uses the per-key
        # cascade — so an un-primed resolver behaves exactly as before.
        self._cache: Optional[Dict[_CacheKey, List[Dict[str, Any]]]] = None

    async def prime(
        self,
        *,
        category_slug: Optional[str] = None,
        business_id: Optional[str] = None,
        neighborhood_slug: Optional[str] = None,
    ) -> None:
        """Pre-load every copy override for this page's scope set in ONE query.

        Pass the page-specific scope dimensions it will actually resolve
        against (a category page passes ``category_slug``, a business page
        ``business_id``, etc.). The resolver's own ``network_id``/``city_id``
        always contribute the city/network/global levels. After priming, any
        ``.get`` whose scope dimensions are a subset of what was primed
        resolves from memory; a ``.get`` that introduces an un-primed
        dimension transparently falls back to the per-key DB cascade.

        Calling ``prime`` again merges additional scope dimensions into the
        same cache (a second query), so a route can prime base scopes once and
        widen later if needed. Safe to call with no extra dimensions to prime
        just city/network/global.
        """
        scopes = list(
            _scope_keys(
                self.network_id,
                self.city_id,
                category_slug,
                business_id,
                neighborhood_slug,
            )
        )

        cache: Dict[_CacheKey, List[Dict[str, Any]]] = self._cache or {}

        # WHY: on a repeat prime() (e.g. base scopes then a widen), only query
        # scopes not already covered. This keeps re-prime cheap AND prevents
        # loading the same row twice into a scope's cache list — important
        # because resolution returns the first active row, and a duplicated row
        # is harmless but pointless. Coverage is tracked by a per-scope marker.
        new_scopes = [
            (scope_type, scope_ref)
            for scope_type, scope_ref in scopes
            if (scope_type, _scope_ref_fingerprint(scope_ref), _PRIMED_MARKER) not in cache
        ]
        if not new_scopes:
            self._cache = cache
            return

        # Build a single $or over every (scope_type, scope_ref) pair, scoped to
        # this resolver's locale. active_from/active_until are intentionally NOT
        # filtered in the query: we load all rows and apply the active-window
        # check in memory (via _is_active) so the primed path and the per-key
        # path share one definition of "active" and can't drift.
        or_clauses = [
            {"scope_type": scope_type, "scope_ref": scope_ref}
            for scope_type, scope_ref in new_scopes
        ]

        # Record coverage for every new scope up front, so a scope with zero
        # overrides still counts as "primed" (see _cache_covers).
        for scope_type, scope_ref in new_scopes:
            marker: _CacheKey = (
                scope_type,
                _scope_ref_fingerprint(scope_ref),
                _PRIMED_MARKER,
            )
            cache.setdefault(marker, [])

        cursor = get_db().copy_blocks.find(
            {"locale": self.locale, "$or": or_clauses}
        )
        async for doc in cursor:
            ck: _CacheKey = (
                doc["scope_type"],
                _scope_ref_fingerprint(doc.get("scope_ref") or {}),
                doc["key"],
            )
            cache.setdefault(ck, []).append(doc)

        self._cache = cache

    async def get(
        self,
        key: str,
        *,
        category_slug: Optional[str] = None,
        category_name: Optional[str] = None,
        business_id: Optional[str] = None,
        neighborhood_slug: Optional[str] = None,
        neighborhood_name: Optional[str] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        fmt = {
            "network_name": self.network_name,
            "city_name": self.city_name,
            "category_name": category_name or "",
            "neighborhood_name": neighborhood_name or "",
            "year": str(datetime.now(timezone.utc).year),
        }
        if extra:
            fmt.update(extra)
        return await get_copy(
            key,
            network_id=self.network_id,
            city_id=self.city_id,
            category_slug=category_slug,
            business_id=business_id,
            neighborhood_slug=neighborhood_slug,
            locale=self.locale,
            fmt=fmt,
            cache=self._cache,
        )
