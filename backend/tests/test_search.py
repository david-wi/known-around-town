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
         short_description="Blowouts and styling"),
    _biz("four-seasons-spa", "The Spa at Four Seasons",
         category_slugs=["spa"], neighborhood_slugs=["brickell"],
         short_description="Hotel day spa", status="draft"),
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
