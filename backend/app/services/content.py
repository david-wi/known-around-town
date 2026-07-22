"""Lookup helpers for content collections, scoped to a (network, city) tenant."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable, Collection
from typing import Any, Dict, List, Optional, Tuple

from app.database import get_db
from app.services.ai_caption import CaptionGenerationError, call_gateway_text

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-process TTL cache for navigation lookups
# ---------------------------------------------------------------------------
# The category / neighborhood / city lists drive the header nav and footer on
# EVERY public page, but they only change on rare admin edits or a re-seed. Yet
# `_base_context` re-queried all three on every single request (3-5 DB
# round-trips per page). PR #452 already batched the editable-copy lookups; this
# is the documented follow-up ("fix #2"): cache the nav lists in-process so they
# aren't re-fetched on every render.
#
# WHY a plain module-level dict of {key: (value, expires_at)} rather than a
# library: it's dependency-free, fast, and exactly enough. We deliberately do
# NOT build cross-process invalidation — production runs multiple uvicorn
# workers, so each worker keeps its own copy and a short TTL bounds how long any
# one worker can serve stale nav data. The admin write routes also call
# `clear_nav_cache()` best-effort, which only clears the worker that handled the
# write; the other workers still self-heal within the TTL. That tradeoff is
# acceptable because nav data changes rarely and a brief (<=TTL) lag before an
# admin edit appears on every worker is harmless for navigation links.

# WHY 120s: nav data changes only on infrequent admin edits / re-seeds, so a
# short TTL is plenty to slash per-request DB load. 120s caps worst-case
# staleness on workers that didn't handle the write to two minutes — short
# enough that an admin sees their change propagate quickly without any
# cross-process invalidation machinery, long enough to absorb the request
# bursts this cache exists to flatten. Chosen by judgment, not measurement;
# safe to tune.
_NAV_CACHE_TTL_SECONDS = 120.0

# WHY: cities and neighborhoods are compact navigation catalogs; 200 is well
# above current inventory while preventing an accidental unbounded page render.
_NAV_PRIMARY_LIST_LIMIT = 200

# WHY: category navigation can include many parent-specific entries across a
# mature city; 500 preserves the existing generous ceiling without unbounded IO.
_NAV_CATEGORY_LIST_LIMIT = 500

# Maps a cache key to (cached_value, expires_at_monotonic_seconds).
_nav_cache: Dict[Tuple[Any, ...], Tuple[List[Dict[str, Any]], float]] = {}

# WHY: A cache miss can overlap an admin write. The generation lets that
# already-running read return to its caller without repopulating data that the
# successful write just invalidated. Zero is only the process-local starting
# point; correctness depends on equality, not the absolute value.
_nav_cache_generation = 0

# WHY: neighborhood eligibility reads exactly these business fields. Keeping
# the dependency beside the cached query makes future predicate changes and
# their invalidation requirements reviewable in one module.
_NAV_RELEVANT_BUSINESS_FIELDS = frozenset(
    {"city_id", "status", "neighborhood_slugs"}
)


def _nav_clock() -> float:
    # WHY: monotonic, not wall-clock — TTL math must be immune to system clock
    # adjustments (NTP steps, DST). Tests monkeypatch this single seam to drive
    # the clock instead of sleeping.
    return time.monotonic()


def _nav_cache_get(key: Tuple[Any, ...]) -> Optional[List[Dict[str, Any]]]:
    now = _nav_clock()
    expired_keys = [
        cached_key
        for cached_key, (_, expires_at) in _nav_cache.items()
        if now >= expires_at
    ]
    for expired_key in expired_keys:
        _nav_cache.pop(expired_key, None)
    entry = _nav_cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    return value


def _nav_cache_set(
    key: Tuple[Any, ...],
    value: List[Dict[str, Any]],
    generation: int,
) -> None:
    if generation != _nav_cache_generation:
        return
    _nav_cache[key] = (value, _nav_clock() + _NAV_CACHE_TTL_SECONDS)


def clear_nav_cache() -> None:
    """Drop cached lists and prevent older in-flight reads from refilling them.

    Best-effort, single-worker invalidation: admin write routes call this after
    creating/updating/archiving a category, neighborhood, city, or business so
    the worker that handled the edit reflects it immediately. Other workers (and
    any future process) self-heal within `_NAV_CACHE_TTL_SECONDS`. There is
    intentionally no cross-process broadcast — see the module-level note above.
    """
    global _nav_cache_generation

    _nav_cache.clear()
    _nav_cache_generation += 1


def invalidate_nav_after_business_write(
    changed_fields: Optional[Collection[str]] = None,
) -> None:
    """Invalidate navigation when a successful business write can affect it.

    ``None`` represents create/archive, where the lifecycle effect is always
    relevant. PATCH callers provide only the submitted field names.
    """
    if changed_fields is None or _NAV_RELEVANT_BUSINESS_FIELDS.intersection(
        changed_fields
    ):
        clear_nav_cache()


async def _cached_nav_lookup(
    cache_key: Tuple[Any, ...],
    load: Callable[[], Awaitable[List[Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    cached = _nav_cache_get(cache_key)
    if cached is not None:
        return cached
    cache_generation = _nav_cache_generation
    result = await load()
    _nav_cache_set(cache_key, result, cache_generation)
    return result


# @define KAT-010 "Neighborhood browsing follows current live businesses"
async def list_neighborhoods(city_id: str) -> List[Dict[str, Any]]:
    cache_key = ("neighborhoods", city_id)

    async def load() -> List[Dict[str, Any]]:
        db = get_db()
        # WHY: listed_count is editorial display metadata and can fall behind
        # ordinary business lifecycle writes. Live business records are the
        # source of truth for public-page eligibility.
        live_neighborhood_slugs = await db.businesses.distinct(
            "neighborhood_slugs", {"city_id": city_id, "status": "live"}
        )
        cur = db.neighborhoods.find(
            {
                "city_id": city_id,
                "status": {"$ne": "archived"},
                "slug": {"$in": live_neighborhood_slugs},
            }
        )
        return await cur.sort([("order", 1), ("name", 1)]).to_list(
            length=_NAV_PRIMARY_LIST_LIMIT
        )

    return await _cached_nav_lookup(cache_key, load)


async def list_cities(network_id: str) -> List[Dict[str, Any]]:
    """Cities that have been seeded under a network, sorted by name.

    Used by the network-wide landing page (rendered at the bare apex host like
    `knowsbeauty.ai.devintensive.com/`) to show visitors which cities they can
    open.
    """
    cache_key = ("cities", network_id)

    async def load() -> List[Dict[str, Any]]:
        db = get_db()
        cur = db.cities.find(
            {"network_id": network_id, "status": {"$ne": "archived"}}
        )
        # WHY: alphabetical is the safest default when there's more than one
        # city; it's a stable order that needs no per-city configuration.
        return await cur.sort([("name", 1)]).to_list(
            length=_NAV_PRIMARY_LIST_LIMIT
        )

    return await _cached_nav_lookup(cache_key, load)


async def list_categories(
    city_id: str, parent_slug: Optional[str] = None
) -> List[Dict[str, Any]]:
    # WHY: key on BOTH args — `list_categories(city_id)` (top-level nav) and
    # `list_categories(city_id, parent_slug=...)` (a category page's
    # sub-categories) return different result sets and must not share an entry.
    cache_key = ("categories", city_id, parent_slug)

    async def load() -> List[Dict[str, Any]]:
        db = get_db()
        q: Dict[str, Any] = {"city_id": city_id, "status": {"$ne": "archived"}}
        if parent_slug is None:
            q["parent_slug"] = None
        else:
            q["parent_slug"] = parent_slug
        cur = db.categories.find(q)
        return await cur.sort([("order", 1), ("name", 1)]).to_list(
            length=_NAV_CATEGORY_LIST_LIMIT
        )

    return await _cached_nav_lookup(cache_key, load)


async def get_category(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().categories.find_one({"city_id": city_id, "slug": slug})


async def get_neighborhood(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().neighborhoods.find_one({"city_id": city_id, "slug": slug})


async def get_business(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().businesses.find_one(
        {"city_id": city_id, "slug": slug, "status": "live"}
    )


async def list_businesses(
    city_id: str,
    *,
    category_slug: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
    featured_only: bool = False,
    limit: int = 60,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    if featured_only:
        q["featured.enabled"] = True

    db = get_db()
    cur = db.businesses.find(q)
    cur = cur.sort(
        [
            ("featured.enabled", -1),
            ("editors_pick", -1),
            ("quality_score", -1),
            ("name", 1),
        ]
    )
    cur = cur.skip(offset).limit(limit)
    return await cur.to_list(length=limit)


# WHY: Public search is a semantic selector over business summaries, so sending
# every live listing to the LLM would scale poorly. Current city catalogs are
# far below this size; the cap keeps future prompt cost bounded while preserving
# the same featured/editorial ordering users already see.
SEARCH_AI_CANDIDATE_LIMIT = 80

# WHY: name matching must see the complete current-city catalog so a newly
# seeded listing cannot be hidden behind the AI prompt cap. Current catalogs
# are well below this bound; the cap is a defensive ceiling until normalized
# name fields are indexed for direct database lookup.
SEARCH_NAME_CANDIDATE_LIMIT = 1000

# WHY: The model only returns business IDs. 450 tokens leaves room for JSON and
# whitespace while preventing the gateway call from turning into copywriting.
SEARCH_AI_MAX_TOKENS = 450

# WHY: "light" is a registered centralized gateway alias. The model choice stays
# in Admin AI Config while code-level cost tags still attribute KAT public search.
SEARCH_AI_USE_CASE = "light"

SEARCH_AI_SYSTEM_PROMPT = """You select local business search results.

Return ONLY JSON with this shape:
{"business_ids": ["business-id"]}

Rules:
- Match the user's meaning, not just exact words.
- Use category, neighborhood, tags, descriptions, what the business is
  known for, and the specific services it offers. A query naming a service
  (e.g. "keratin", "brazilian blowout", "balayage") should match any
  business whose services or known-for text covers that service.
- Include only IDs from the provided candidate list.
- Do not invent IDs.
- Exclude weak or generic matches.
- Return {"business_ids": []} if nothing clearly matches.
"""


# WHY: These words describe a business type, common service, search connective,
# or location constraint rather than a distinctive brand. Generic-only queries
# must use semantic matching instead of claiming a name match from "Nails" or
# "Brickell" appearing in many unrelated listing names.
_NAME_MATCH_GENERIC_TERMS = {
    "a", "an", "and", "at", "bar", "barber", "barbers", "barbershop", "bars",
    "balayage", "beauty", "blow", "blowout", "blowouts", "braid", "braids", "brow",
    "brows", "by", "center", "centre", "clinic", "clinics", "co", "color", "colour",
    "company", "cut", "cuts", "extensions", "facial", "facials", "for", "gel", "hair",
    "in", "inc", "lash", "lashes", "make", "makeup", "manicure", "manicures", "massage",
    "med", "medical", "near", "nail", "nails", "of", "pedicure", "pedicures", "salon",
    "salons", "shop", "shops", "skin", "spa", "spas", "studio", "studios", "the", "total",
    "wax", "waxing", "wellness",
}


def _normalize_search_text(value: Any) -> str:
    """Normalize search/name text for stable, punctuation-insensitive matching."""
    if not isinstance(value, str):
        return ""
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = folded.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _search_terms(values: Any) -> set[str]:
    terms: set[str] = set()
    if not isinstance(values, list):
        return terms
    for value in values:
        terms.update(_normalize_search_text(value).split())
    return terms


def _meaningful_search_token_runs(
    query: str,
    *,
    category_terms: set[str],
    neighborhood_terms: set[str],
) -> List[tuple[str, ...]]:
    """Return contiguous query runs that can express a distinctive name."""
    generic_terms = _NAME_MATCH_GENERIC_TERMS | category_terms | neighborhood_terms
    meaningful_runs: List[tuple[str, ...]] = []
    current_run: List[str] = []
    for token in _normalize_search_text(query).split():
        if token in generic_terms or len(token) < 3:
            if current_run:
                meaningful_runs.append(tuple(current_run))
                current_run = []
            continue
        current_run.append(token)
    if current_run:
        meaningful_runs.append(tuple(current_run))
    return meaningful_runs


def _search_service_vocabulary(candidates: List[Dict[str, Any]]) -> set[str]:
    """Return current-catalog evidence that makes semantic fallback eligible."""
    evidence: List[Any] = []
    for business in candidates:
        evidence.extend(
            [business.get("short_description"), business.get("known_for")]
        )
        if isinstance(business.get("tags"), list):
            evidence.extend(business["tags"])
        if isinstance(business.get("services"), list):
            evidence.extend(
                service.get("name")
                for service in business["services"]
                if isinstance(service, dict)
            )

    # WHY: This bounded, tenant-scoped scan admits semantic fallback only for
    # evidence the current live catalog actually contains. It prevents an
    # unknown brand plus a real neighborhood from becoming unrelated results.
    return _NAME_MATCH_GENERIC_TERMS | _search_terms(evidence)


async def _search_name_generic_terms(
    city_id: str,
    candidates: List[Dict[str, Any]],
) -> tuple[set[str], set[str]]:
    """Return generic words from candidate data and current-city navigation."""
    category_terms = _search_terms(
        [slug for business in candidates for slug in (business.get("category_slugs") or [])]
    )
    neighborhood_terms = _search_terms(
        [
            slug
            for business in candidates
            for slug in (business.get("neighborhood_slugs") or [])
        ]
    )

    # WHY: nav names are the current city's source of truth. Slugs cover most
    # labels, but names can contain additional words such as a city's fuller
    # neighborhood label; those words must also stay out of deterministic brand
    # matching when they are the only query signal.
    for nav_item in await list_categories(city_id):
        category_terms.update(
            _search_terms([nav_item.get("slug"), nav_item.get("name")])
        )
    for nav_item in await list_neighborhoods(city_id):
        neighborhood_terms.update(
            _search_terms([nav_item.get("slug"), nav_item.get("name")])
        )
    return category_terms, neighborhood_terms


def _name_match_score(
    query: str,
    business: Dict[str, Any],
    *,
    category_terms: set[str],
    neighborhood_terms: set[str],
) -> Optional[int]:
    """Return a deterministic name-match rank, or ``None`` for no match."""
    query_normalized = _normalize_search_text(query)
    name_normalized = _normalize_search_text(business.get("name"))
    if not query_normalized or not name_normalized:
        return None
    if query_normalized == name_normalized:
        return 0

    name_tokens = name_normalized.split()
    meaningful_runs = _meaningful_search_token_runs(
        query,
        category_terms=category_terms,
        neighborhood_terms=neighborhood_terms,
    )
    if not meaningful_runs:
        return None

    # A contiguous meaningful run is the strongest partial-name signal after
    # an exact match (for example, "muse" in "MUSE Total Beauty"). Requiring
    # token adjacency prevents unrelated query words from combining into a
    # false brand match.
    for run in meaningful_runs:
        run_length = len(run)
        for index in range(len(name_tokens) - run_length + 1):
            if tuple(name_tokens[index : index + run_length]) == run:
                return 1
    return None


# @define-start KAT-078 "Business-name search with independent service and neighborhood filters"
async def search_businesses(
    city_id: str,
    query: str = "",
    *,
    service_slug: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Search live businesses by name first, then semantic intent.

    Service and neighborhood are explicit constraints. If a query does not
    identify a distinctive business name, the existing centralized AI selector
    handles semantic service and intent matching over the already-filtered set.
    """
    search_text = " ".join(query.split())
    if limit <= 0:
        return []
    if not search_text and not service_slug and not neighborhood_slug:
        return []

    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if service_slug:
        q["category_slugs"] = service_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug

    db = get_db()
    cur = db.businesses.find(q).sort(
        [("featured.enabled", -1), ("editors_pick", -1), ("quality_score", -1), ("name", 1)]
    )
    cur = cur.limit(SEARCH_NAME_CANDIDATE_LIMIT)
    candidates = await cur.to_list(length=SEARCH_NAME_CANDIDATE_LIMIT)

    if not search_text:
        # Filter-only browsing is deterministic and deliberately does not call
        # the AI gateway; /search?service=... is a normal browse result.
        return candidates[:limit]

    category_terms, neighborhood_terms = await _search_name_generic_terms(
        city_id, candidates
    )
    name_matches = [
        (score, index, business)
        for index, business in enumerate(candidates)
        if (score := _name_match_score(
            search_text,
            business,
            category_terms=category_terms,
            neighborhood_terms=neighborhood_terms,
        )) is not None
    ]
    if name_matches:
        # The Mongo query already supplies the established ordering. Grouping
        # by relevance rank without sorting the rows again preserves that order
        # exactly within exact, partial, and semantic-equivalent name matches.
        ordered_matches = [
            business
            for score in (0, 1, 2)
            for match_score, _, business in name_matches
            if match_score == score
        ]
        return ordered_matches[:limit]

    distinctive_tokens = {
        token
        for run in _meaningful_search_token_runs(
            search_text,
            category_terms=category_terms,
            neighborhood_terms=neighborhood_terms,
        )
        for token in run
    }
    if distinctive_tokens and not distinctive_tokens.issubset(
        _search_service_vocabulary(candidates)
    ):
        # A name-like token with no live catalog evidence is safer as a clear
        # no-results state than an AI-selected list of unrelated businesses.
        return []

    # The AI prompt remains bounded even though deterministic name matching
    # inspected the larger current-city catalog above.
    ai_candidates = candidates[:SEARCH_AI_CANDIDATE_LIMIT]
    selected_ids = await _select_matching_business_ids(
        query=search_text,
        businesses=ai_candidates,
    )
    selected = set(selected_ids)
    return [business for business in ai_candidates if str(business.get("_id")) in selected][:limit]


# @define-end KAT-078


async def _select_matching_business_ids(
    *,
    query: str,
    businesses: List[Dict[str, Any]],
) -> List[str]:
    """Select search results with AI rather than regex over listing text.

    WHY: The user's search intent can be broader than listing wording ("mani",
    "self-care day", "natural curls near downtown"). Regex terms either miss
    those matches or over-match incidental words. The LLM receives a bounded
    candidate set that Mongo has already scoped to the city, and callers keep no
    results if the gateway cannot make a reliable semantic decision.
    """
    if not query or not businesses:
        return []

    candidate_ids = {str(business.get("_id")) for business in businesses}
    candidate_payload = [
        {
            "id": str(business.get("_id")),
            "name": business.get("name", ""),
            "short_description": business.get("short_description", ""),
            # WHY: known_for is the "what they're celebrated for" line, often
            # the most service-specific signal a salon has ("known for balayage
            # and keratin"). Including it lets the matcher surface a salon for a
            # service-intent query even when the service isn't in name/tags.
            "known_for": business.get("known_for", "") or "",
            # WHY: a salon's own service-menu item names ("Keratin Treatment",
            # "Brazilian Blowout") are ground-truth for what it offers. Without
            # them, a high-intent query like "keratin" matched only the 1 salon
            # with the word in its description; with them it matches every salon
            # that actually lists the service. Capped at 15 names to keep the
            # candidate payload bounded across up to SEARCH_AI_CANDIDATE_LIMIT
            # candidates (most menus are well under 15; the cap just guards a
            # pathological outlier from bloating the prompt).
            "services": [
                s.get("name", "")
                for s in (business.get("services") or [])[:15]
                if isinstance(s, dict) and s.get("name")
            ],
            "tags": business.get("tags") or [],
            "category_slugs": business.get("category_slugs") or [],
            "neighborhood_slugs": business.get("neighborhood_slugs") or [],
        }
        for business in businesses
    ]

    try:
        response = await call_gateway_text(
            use_case=SEARCH_AI_USE_CASE,
            system_prompt=SEARCH_AI_SYSTEM_PROMPT,
            user_content=(
                f"Search query: {query}\n\n"
                "Candidate businesses:\n"
                f"{json.dumps(candidate_payload, ensure_ascii=True)}"
            ),
            max_tokens_override=SEARCH_AI_MAX_TOKENS,
            cost_tags={
                "product": "known-around-town",
                "feature": "public.search",
                "call": "public.search.match_businesses",
            },
        )
        parsed = json.loads(_strip_json_code_fence(response))
    # WHY: The gateway wrapper normally converts transport failures to
    # CaptionGenerationError, but a test double or a future adapter may raise a
    # different runtime exception. Public search must fail closed for every
    # gateway-side failure rather than accidentally showing unverified matches.
    except CaptionGenerationError as exc:
        log.warning("AI business search unavailable; returning no semantic matches: %s", exc)
        return []
    except Exception as exc:  # noqa: BLE001 - fail closed at the AI boundary
        log.warning("AI business search unavailable; returning no semantic matches: %s", exc)
        return []

    raw_ids = parsed.get("business_ids") if isinstance(parsed, dict) else []
    if not isinstance(raw_ids, list):
        return []

    selected: List[str] = []
    for raw_id in raw_ids:
        business_id = str(raw_id)
        if business_id in candidate_ids and business_id not in selected:
            selected.append(business_id)
    return selected


def _strip_json_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


async def count_businesses(
    city_id: str,
    *,
    category_slug: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
) -> int:
    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    return await get_db().businesses.count_documents(q)


async def list_editorial_guides(city_id: str, limit: int = 12) -> List[Dict[str, Any]]:
    cur = get_db().editorial_guides.find(
        {"city_id": city_id, "status": "live"}
    ).sort("published_at", -1).limit(limit)
    return await cur.to_list(length=limit)


async def get_editorial_guide(city_id: str, slug: str) -> Optional[Dict[str, Any]]:
    return await get_db().editorial_guides.find_one(
        {"city_id": city_id, "slug": slug}
    )


def active_editorial_headline(city: Dict[str, Any]) -> Optional[str]:
    """Pick the editorial headline that's active right now."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    headlines = city.get("editorial_headlines") or []
    default = None
    for h in headlines:
        if h.get("is_default"):
            default = h.get("headline")
        active_from = h.get("active_from")
        active_until = h.get("active_until")
        if (active_from is None or active_from <= now) and (
            active_until is None or active_until >= now
        ):
            if not h.get("is_default"):
                return h.get("headline")
    return default or (headlines[0].get("headline") if headlines else None)
