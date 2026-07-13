"""Tests for content_svc.search_businesses semantic search.

The bug this guards against: visitor searches are semantic, not fixed-format
strings. A multi-word query like "nails brickell" should return nail salons in
Brickell even if no listing contains that literal phrase. The service now scopes
candidate listings with Mongo and delegates result selection to AI.

Patch path: search_businesses calls app.database.get_db, which resolves the
client via app.database.get_client. The mock_db fixture patches get_client, so
inserts into the returned db are visible to the service.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

CITY = "city-miami"
OTHER_CITY = "city-elsewhere"


def _biz(
    _id: str,
    name: str,
    *,
    category_slugs: List[str],
    neighborhood_slugs: List[str],
    short_description: str = "",
    tags: List[str] | None = None,
    known_for: str = "",
    services: List[Dict[str, Any]] | None = None,
    status: str = "live",
    city_id: str = CITY,
    featured_enabled: bool = False,
    editors_pick: bool = False,
    quality_score: int = 0,
) -> Dict[str, Any]:
    return {
        "_id": _id,
        "city_id": city_id,
        "status": status,
        "name": name,
        "slug": _id,
        "category_slugs": category_slugs,
        "neighborhood_slugs": neighborhood_slugs,
        "short_description": short_description,
        "tags": tags or [],
        "known_for": known_for,
        "services": services or [],
        "featured": {"enabled": featured_enabled},
        "editors_pick": editors_pick,
        "quality_score": quality_score,
    }


# A small, controlled fixture set mirroring real Miami slugs:
#   lets-nail-bar-brickell : nails in brickell
#   wynwood-nails          : nails in wynwood
#   blow-dry-bar-brickell  : hair in brickell
#   four-seasons-spa       : spa in brickell (draft — must never surface)
#   other-city-nail-bar    : nails in brickell but a DIFFERENT city
_SEED = [
    _biz("lets-nail-bar-brickell", "Let's Nail Bar Brickell",
         category_slugs=["nails"], neighborhood_slugs=["brickell"],
         short_description="Gel and acrylic nail care"),
    _biz("wynwood-nails", "Wynwood Nails",
         category_slugs=["nails"], neighborhood_slugs=["wynwood"],
         short_description="Nail art studio"),
    _biz("blow-dry-bar-brickell", "Blow Dry Bar Brickell",
         category_slugs=["hair"], neighborhood_slugs=["brickell"],
         short_description="Blowouts and styling",
         services=[{"name": "Keratin Treatment"}]),
    _biz("four-seasons-spa", "The Spa at Four Seasons",
         category_slugs=["spa"], neighborhood_slugs=["brickell"],
         short_description="Hotel day spa", status="draft"),
    _biz("draft-name-match", "Let's Nail Bar Brickell",
         category_slugs=["nails"], neighborhood_slugs=["brickell"], status="draft"),
    _biz("archived-name-match", "Let's Nail Bar Brickell",
         category_slugs=["nails"], neighborhood_slugs=["brickell"], status="archived"),
    _biz("other-city-name-match", "Let's Nail Bar Brickell",
         category_slugs=["nails"], neighborhood_slugs=["brickell"], city_id=OTHER_CITY),
    _biz("other-city-nail-bar", "Other City Nail Bar",
         category_slugs=["nails"], neighborhood_slugs=["brickell"],
         city_id=OTHER_CITY, short_description="nails"),
]


async def _seed(db) -> None:
    await db.businesses.insert_many([dict(d) for d in _SEED])


def _patch_ai_matches(monkeypatch, matches_by_query: Dict[str, set[str]]):
    from app.services import content as content_svc

    async def fake_selector(*, query: str, businesses: List[Dict[str, Any]]) -> List[str]:
        allowed = matches_by_query.get(" ".join(query.lower().split()), set())
        return [str(business["_id"]) for business in businesses if str(business["_id"]) in allowed]

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", fake_selector)
    return content_svc


@pytest.mark.asyncio
async def test_nails_brickell_returns_brickell_nail_salons(mock_db, monkeypatch):
    """The headline bug: "nails brickell" must return Brickell nail salons —
    and only those that are BOTH nails AND in Brickell."""
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails brickell": {"lets-nail-bar-brickell"}},
    )
    res = await content_svc.search_businesses(CITY, "nails brickell")

    ids = {r["_id"] for r in res}
    assert ids == {"lets-nail-bar-brickell"}, ids
    # And the match really IS a nail salon in Brickell.
    hit = res[0]
    assert "nails" in hit["category_slugs"]
    assert "brickell" in hit["neighborhood_slugs"]


@pytest.mark.asyncio
async def test_nails_alone_returns_all_nail_salons(mock_db, monkeypatch):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails": {"lets-nail-bar-brickell", "wynwood-nails"}},
    )
    res = await content_svc.search_businesses(CITY, "nails")
    ids = {r["_id"] for r in res}
    # Both Miami nail salons, regardless of neighborhood.
    assert ids == {"lets-nail-bar-brickell", "wynwood-nails"}, ids


@pytest.mark.asyncio
async def test_brickell_alone_returns_all_brickell_businesses(mock_db, monkeypatch):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"brickell": {"lets-nail-bar-brickell", "blow-dry-bar-brickell"}},
    )
    res = await content_svc.search_businesses(CITY, "brickell")
    ids = {r["_id"] for r in res}
    # Both live Miami businesses in Brickell (the spa is draft → excluded).
    assert ids == {"lets-nail-bar-brickell", "blow-dry-bar-brickell"}, ids


@pytest.mark.asyncio
async def test_nonsense_term_returns_empty(mock_db, monkeypatch):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(monkeypatch, {"zzqxnope": set()})
    res = await content_svc.search_businesses(CITY, "zzqxnope")
    assert res == []


# @define-test KAT-078-fallback-intent-gate
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "extra_candidate"),
    [
        (
            "Supercuts Downtown",
            _biz(
                "downtown-styling",
                "Downtown Styling Studio",
                category_slugs=["hair"],
                neighborhood_slugs=["downtown"],
            ),
        ),
        ("Great Clips Wynwood", None),
    ],
)
async def test_unmatched_business_name_queries_skip_ai(
    mock_db, monkeypatch, query, extra_candidate
):
    """A real location word must not turn an unknown brand into a fuzzy match."""
    await _seed(mock_db)
    if extra_candidate is not None:
        await mock_db.businesses.insert_one(extra_candidate)

    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("unmatched business-name queries must fail closed before AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)

    assert await content_svc.search_businesses(CITY, query) == []


# @define-test KAT-078-fallback-intent-gate
@pytest.mark.asyncio
async def test_gibberish_query_skips_ai(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("uncovered gibberish must fail closed before AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)

    assert await content_svc.search_businesses(CITY, "zzqxnope") == []


# @define-test KAT-078-fallback-intent-gate
@pytest.mark.asyncio
async def test_catalog_menu_service_query_keeps_semantic_fallback(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    called = False

    async def service_ai_selector(*, query, businesses):
        nonlocal called
        called = True
        assert query == "keratin"
        assert any(
            service.get("name") == "Keratin Treatment"
            for business in businesses
            for service in business.get("services", [])
        )
        return ["blow-dry-bar-brickell"]

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", service_ai_selector)

    result = await content_svc.search_businesses(CITY, "keratin")

    assert [business["_id"] for business in result] == ["blow-dry-bar-brickell"]
    assert called


@pytest.mark.asyncio
async def test_partial_match_across_terms_excludes_non_matches(mock_db, monkeypatch):
    """"hair brickell" must return the Brickell hair salon, not the nail bar."""
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"hair brickell": {"blow-dry-bar-brickell"}},
    )
    res = await content_svc.search_businesses(CITY, "hair brickell")
    ids = {r["_id"] for r in res}
    assert ids == {"blow-dry-bar-brickell"}, ids


@pytest.mark.asyncio
async def test_term_with_no_match_yields_empty(mock_db, monkeypatch):
    """If the AI selector finds no coherent result, search returns []."""
    await _seed(mock_db)
    content_svc = _patch_ai_matches(monkeypatch, {"nails wynwood brickell": set()})
    res = await content_svc.search_businesses(CITY, "nails wynwood brickell")
    assert res == []


@pytest.mark.asyncio
async def test_empty_query_returns_empty(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    assert await content_svc.search_businesses(CITY, "") == []
    assert await content_svc.search_businesses(CITY, "   ") == []


# @define-test KAT-078-name-exact
@pytest.mark.asyncio
async def test_exact_business_name_match_is_deterministic(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("exact business names must not require AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)
    res = await content_svc.search_businesses(CITY, " let's nail bar brickell ")
    assert [business["_id"] for business in res] == ["lets-nail-bar-brickell"]


# @define-test KAT-078-name-partial
@pytest.mark.asyncio
async def test_meaningful_partial_business_name_match_is_deterministic(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("meaningful partial names must not require AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)
    res = await content_svc.search_businesses(CITY, "lets nail")
    assert [business["_id"] for business in res] == ["lets-nail-bar-brickell"]


# @define-test KAT-078-fallback-intent-gate
@pytest.mark.asyncio
async def test_generic_only_name_terms_use_semantic_fallback(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    called = False

    async def empty_ai_selector(*, query, businesses):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", empty_ai_selector)
    res = await content_svc.search_businesses(CITY, "nail bar brickell")

    assert res == []
    assert called, "generic service/category/neighborhood words must not be name matches"


# @define-test KAT-078-filter-composition
@pytest.mark.asyncio
async def test_service_and_neighborhood_filters_are_independent_constraints(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails": {"lets-nail-bar-brickell", "wynwood-nails"}},
    )
    res = await content_svc.search_businesses(
        CITY,
        "nails",
        service_slug="nails",
        neighborhood_slug="brickell",
    )
    assert [business["_id"] for business in res] == ["lets-nail-bar-brickell"]

    service_only = await content_svc.search_businesses(CITY, service_slug="nails")
    assert {business["_id"] for business in service_only} == {
        "lets-nail-bar-brickell",
        "wynwood-nails",
    }
    neighborhood_only = await content_svc.search_businesses(CITY, neighborhood_slug="brickell")
    assert {business["_id"] for business in neighborhood_only} == {
        "lets-nail-bar-brickell",
        "blow-dry-bar-brickell",
    }


@pytest.mark.asyncio
async def test_filter_only_search_returns_live_filtered_list_without_ai(mock_db, monkeypatch):
    await _seed(mock_db)
    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("filter-only browsing must not require AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)
    res = await content_svc.search_businesses(CITY, service_slug="nails")
    assert {business["_id"] for business in res} == {
        "lets-nail-bar-brickell",
        "wynwood-nails",
    }


@pytest.mark.asyncio
async def test_search_normalizes_case_before_ai_selection(mock_db, monkeypatch):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails brickell": {"lets-nail-bar-brickell"}},
    )
    res = await content_svc.search_businesses(CITY, "NAILS BRICKELL")
    ids = {r["_id"] for r in res}
    assert ids == {"lets-nail-bar-brickell"}, ids


@pytest.mark.asyncio
# @define-test KAT-078-visibility-boundary
async def test_other_city_results_excluded(mock_db, monkeypatch):
    await _seed(mock_db)
    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails brickell": {"lets-nail-bar-brickell", "other-city-nail-bar"}},
    )
    # other-city-nail-bar is nails in brickell but in a different city.
    res = await content_svc.search_businesses(CITY, "nails brickell")
    ids = {r["_id"] for r in res}
    assert "other-city-nail-bar" not in ids


# @define-test KAT-078-visibility-boundary
@pytest.mark.asyncio
async def test_exact_names_for_draft_archived_and_other_city_rows_stay_hidden(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    await mock_db.businesses.insert_one(
        _biz(
            "archived-nail-bar",
            "Archived Nail Bar",
            category_slugs=["nails"],
            neighborhood_slugs=["brickell"],
            status="archived",
        )
    )
    from app.services import content as content_svc

    async def empty_ai_selector(*, query, businesses):
        return []

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", empty_ai_selector)
    for query in (
        "The Spa at Four Seasons",
        "Archived Nail Bar",
        "Other City Nail Bar",
    ):
        assert await content_svc.search_businesses(CITY, query) == []


@pytest.mark.asyncio
async def test_featured_and_editors_pick_ordering_preserved(mock_db, monkeypatch):
    """When multiple businesses match, featured-first then editor's-pick then
    quality_score then name — the same ordering the old code used."""
    # Three nail salons that all match "nails", with a deliberate sort order.
    rows = [
        _biz("plain-nails", "AAA Plain Nails",
             category_slugs=["nails"], neighborhood_slugs=["brickell"],
             quality_score=10),
        _biz("featured-nails", "ZZZ Featured Nails",
             category_slugs=["nails"], neighborhood_slugs=["brickell"],
             featured_enabled=True, quality_score=1),
        _biz("editors-nails", "MMM Editors Nails",
             category_slugs=["nails"], neighborhood_slugs=["brickell"],
             editors_pick=True, quality_score=5),
    ]
    await mock_db.businesses.insert_many([dict(r) for r in rows])

    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails": {"plain-nails", "featured-nails", "editors-nails"}},
    )
    res = await content_svc.search_businesses(CITY, "nails")
    order = [r["_id"] for r in res]
    # Featured first, then editor's pick, then the plain one.
    assert order == ["featured-nails", "editors-nails", "plain-nails"], order


# @define-test KAT-078-name-partial
@pytest.mark.asyncio
async def test_equal_relevance_name_matches_keep_existing_listing_order(
    mock_db, monkeypatch
):
    rows = [
        _biz(
            "plain-glow",
            "Glow Plain Studio",
            category_slugs=["hair"],
            neighborhood_slugs=["brickell"],
            quality_score=10,
        ),
        _biz(
            "featured-glow",
            "Glow Featured Studio",
            category_slugs=["hair"],
            neighborhood_slugs=["brickell"],
            featured_enabled=True,
            quality_score=1,
        ),
        _biz(
            "editors-glow",
            "Glow Editors Studio",
            category_slugs=["hair"],
            neighborhood_slugs=["brickell"],
            editors_pick=True,
            quality_score=5,
        ),
    ]
    await mock_db.businesses.insert_many(rows)

    from app.services import content as content_svc

    async def unexpected_ai_call(**kwargs):
        raise AssertionError("meaningful name matches must not require AI")

    monkeypatch.setattr(content_svc, "_select_matching_business_ids", unexpected_ai_call)
    res = await content_svc.search_businesses(CITY, "glow")

    assert [business["_id"] for business in res] == [
        "featured-glow",
        "editors-glow",
        "plain-glow",
    ]


@pytest.mark.asyncio
async def test_limit_is_respected(mock_db, monkeypatch):
    rows = [
        _biz(f"nail-{i}", f"Nail Salon {i:02d}",
             category_slugs=["nails"], neighborhood_slugs=["brickell"])
        for i in range(10)
    ]
    await mock_db.businesses.insert_many([dict(r) for r in rows])

    content_svc = _patch_ai_matches(
        monkeypatch,
        {"nails": {f"nail-{i}" for i in range(10)}},
    )
    res = await content_svc.search_businesses(CITY, "nails", limit=3)
    assert len(res) == 3


# @define-test KAT-078-ai-fallback
@pytest.mark.asyncio
async def test_select_matching_business_ids_uses_gateway_and_filters_invented_ids(monkeypatch):
    from app.services import content as content_svc

    async def fake_gateway(**kwargs):
        assert kwargs["use_case"] == "light"
        assert kwargs["cost_tags"]["feature"] == "public.search"
        assert "nails near Brickell" in kwargs["user_content"]
        return '{"business_ids": ["lets-nail-bar-brickell", "not-real"]}'

    monkeypatch.setattr(content_svc, "call_gateway_text", fake_gateway)

    result = await content_svc._select_matching_business_ids(
        query="nails near Brickell",
        businesses=[
            _biz("lets-nail-bar-brickell", "Let's Nail Bar Brickell",
                 category_slugs=["nails"], neighborhood_slugs=["brickell"]),
            _biz("wynwood-nails", "Wynwood Nails",
                 category_slugs=["nails"], neighborhood_slugs=["wynwood"]),
        ],
    )

    assert result == ["lets-nail-bar-brickell"]


@pytest.mark.asyncio
# @define-test KAT-078-ai-fallback
async def test_select_matching_business_ids_fails_closed_on_gateway_failure(monkeypatch):
    from app.services import content as content_svc

    async def fake_gateway(**kwargs):
        raise content_svc.CaptionGenerationError("gateway unavailable")

    monkeypatch.setattr(content_svc, "call_gateway_text", fake_gateway)

    result = await content_svc._select_matching_business_ids(
        query="nails",
        businesses=[
            _biz("lets-nail-bar-brickell", "Let's Nail Bar Brickell",
                 category_slugs=["nails"], neighborhood_slugs=["brickell"]),
        ],
    )

    assert result == []


@pytest.mark.asyncio
async def test_select_matching_business_ids_fails_closed_on_unexpected_gateway_error(
    monkeypatch,
):
    from app.services import content as content_svc

    async def fake_gateway(**kwargs):
        raise RuntimeError("gateway connection reset")

    monkeypatch.setattr(content_svc, "call_gateway_text", fake_gateway)
    result = await content_svc._select_matching_business_ids(
        query="lash near Aventura",
        businesses=[
            _biz(
                "lash-studio",
                "Lash Studio",
                category_slugs=["lash-brow"],
                neighborhood_slugs=["aventura"],
            )
        ],
    )

    assert result == []


@pytest.mark.asyncio
async def test_search_payload_includes_services_and_known_for(monkeypatch):
    """The candidate payload sent to the AI matcher must include each salon's
    service-menu names and its known_for text.

    Regression for the bug where a service-intent query ("keratin", "brazilian
    blowout") returned only the single salon that happened to have the word in
    its short_description — because the matcher was never shown the salons'
    actual service menus. With services + known_for in the payload, every salon
    that genuinely offers the service is eligible to match.
    """
    from app.services import content as content_svc

    captured: Dict[str, Any] = {}

    async def fake_gateway(*, use_case, system_prompt, user_content, **kwargs):
        captured["user_content"] = user_content
        return '{"business_ids": []}'

    monkeypatch.setattr(content_svc, "call_gateway_text", fake_gateway)

    business = {
        "_id": "glow-studio",
        "name": "Glow Studio",
        "short_description": "Hair and color studio",
        "known_for": "Famous for lived-in balayage",
        "services": [
            {"name": "Keratin Treatment", "price": "$250"},
            {"name": "Brazilian Blowout", "price": "$300"},
        ],
        "tags": ["color"],
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wynwood"],
    }

    await content_svc._select_matching_business_ids(
        query="keratin", businesses=[business]
    )

    user_content = captured.get("user_content", "")
    # The service names the salon actually lists must reach the matcher.
    assert "Keratin Treatment" in user_content
    assert "Brazilian Blowout" in user_content
    # known_for text must reach the matcher too.
    assert "balayage" in user_content


@pytest.mark.asyncio
async def test_search_payload_tolerates_malformed_services(monkeypatch):
    """Malformed service entries (non-dict items, missing names) must not crash
    payload construction — they are simply skipped."""
    from app.services import content as content_svc

    captured: Dict[str, Any] = {}

    async def fake_gateway(*, use_case, system_prompt, user_content, **kwargs):
        captured["user_content"] = user_content
        return '{"business_ids": []}'

    monkeypatch.setattr(content_svc, "call_gateway_text", fake_gateway)

    business = {
        "_id": "messy-salon",
        "name": "Messy Data Salon",
        "services": [
            "not-a-dict",              # non-dict entry — must be skipped
            {"price": "$50"},          # dict without a name — must be skipped
            {"name": "Gel Manicure"},  # valid — must be kept
        ],
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["brickell"],
    }

    # Must not raise.
    await content_svc._select_matching_business_ids(
        query="manicure", businesses=[business]
    )

    user_content = captured.get("user_content", "")
    assert "Gel Manicure" in user_content
    assert "not-a-dict" not in user_content
