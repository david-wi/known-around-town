"""Tests for content_svc.search_businesses — multi-word, AND-across-terms search.

The bug this guards against: a multi-word query like "nails brickell" used to be
regex-matched as one contiguous string against name/description/tags only, so it
returned nothing (no business holds that literal phrase, and category +
neighborhood were never searched). Now each whitespace-separated term must match
at least one searchable field (name, short_description, tags, category_slugs,
neighborhood_slugs), and every term must match — so "nails brickell" returns nail
salons that are in Brickell.

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


@pytest.mark.asyncio
async def test_nails_brickell_returns_brickell_nail_salons(mock_db):
    """The headline bug: "nails brickell" must return Brickell nail salons —
    and only those that are BOTH nails AND in Brickell."""
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "nails brickell")

    ids = {r["_id"] for r in res}
    assert ids == {"lets-nail-bar-brickell"}, ids
    # And the match really IS a nail salon in Brickell.
    hit = res[0]
    assert "nails" in hit["category_slugs"]
    assert "brickell" in hit["neighborhood_slugs"]


@pytest.mark.asyncio
async def test_nails_alone_returns_all_nail_salons(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "nails")
    ids = {r["_id"] for r in res}
    # Both Miami nail salons, regardless of neighborhood.
    assert ids == {"lets-nail-bar-brickell", "wynwood-nails"}, ids


@pytest.mark.asyncio
async def test_brickell_alone_returns_all_brickell_businesses(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "brickell")
    ids = {r["_id"] for r in res}
    # Both live Miami businesses in Brickell (the spa is draft → excluded).
    assert ids == {"lets-nail-bar-brickell", "blow-dry-bar-brickell"}, ids


@pytest.mark.asyncio
async def test_nonsense_term_returns_empty(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "zzqxnope")
    assert res == []


@pytest.mark.asyncio
async def test_partial_match_across_terms_excludes_non_matches(mock_db):
    """"hair brickell" must return the Brickell hair salon, not the nail bar."""
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "hair brickell")
    ids = {r["_id"] for r in res}
    assert ids == {"blow-dry-bar-brickell"}, ids


@pytest.mark.asyncio
async def test_term_with_no_match_yields_empty(mock_db):
    """If one term matches but another matches nothing, AND semantics → []."""
    from app.services import content as content_svc

    await _seed(mock_db)
    # "nails" matches, "wynwood" matches wynwood-nails — but wynwood-nails is
    # not a brickell business, so "nails wynwood brickell" must be empty.
    res = await content_svc.search_businesses(CITY, "nails wynwood brickell")
    assert res == []


@pytest.mark.asyncio
async def test_empty_query_returns_empty(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    assert await content_svc.search_businesses(CITY, "") == []
    assert await content_svc.search_businesses(CITY, "   ") == []


@pytest.mark.asyncio
async def test_search_is_case_insensitive(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    res = await content_svc.search_businesses(CITY, "NAILS BRICKELL")
    ids = {r["_id"] for r in res}
    assert ids == {"lets-nail-bar-brickell"}, ids


@pytest.mark.asyncio
async def test_other_city_results_excluded(mock_db):
    from app.services import content as content_svc

    await _seed(mock_db)
    # other-city-nail-bar is nails in brickell but in a different city.
    res = await content_svc.search_businesses(CITY, "nails brickell")
    ids = {r["_id"] for r in res}
    assert "other-city-nail-bar" not in ids


@pytest.mark.asyncio
async def test_featured_and_editors_pick_ordering_preserved(mock_db):
    """When multiple businesses match, featured-first then editor's-pick then
    quality_score then name — the same ordering the old code used."""
    from app.services import content as content_svc

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

    res = await content_svc.search_businesses(CITY, "nails")
    order = [r["_id"] for r in res]
    # Featured first, then editor's pick, then the plain one.
    assert order == ["featured-nails", "editors-nails", "plain-nails"], order


@pytest.mark.asyncio
async def test_limit_is_respected(mock_db):
    from app.services import content as content_svc

    rows = [
        _biz(f"nail-{i}", f"Nail Salon {i:02d}",
             category_slugs=["nails"], neighborhood_slugs=["brickell"])
        for i in range(10)
    ]
    await mock_db.businesses.insert_many([dict(r) for r in rows])

    res = await content_svc.search_businesses(CITY, "nails", limit=3)
    assert len(res) == 3
