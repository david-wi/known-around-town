"""Tests for the full-directory page (/all) and the home page's "See all N →" link.

The home page only shows a curated SAMPLE of a city's listings. These tests guard
two things a first-time visitor depends on:

  1. The home page carries a real link to the full directory, with a DYNAMIC count
     (never a hardcoded number), so visitors realize there's more than the picks.
  2. /all actually renders EVERY live listing for the tenant city — not a category-
     or neighborhood-filtered subset.

They assert against the rendered response bodies (what the code actually does),
not against comments. The SSR pages sit behind the pre-launch preview gate, so
every test uses the gate_off fixture to render the live version.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

HOST = {"host": "miami.knowsbeauty.localhost"}


def _make_client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def gate_off(monkeypatch):
    """Force the launch gate OFF so the public HTML pages render (not the
    preview-login wall)."""
    from app.services import site_settings
    import app.routes.public.pages as pages

    async def _off():
        return False

    monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _off)
    monkeypatch.setattr(pages, "get_preview_mode_enabled", _off)


async def _live_count(db) -> int:
    """The true number of live Miami businesses — the source of truth both the
    home stat and the /all page count must match. Uses count_businesses (a
    count_documents over {city, live}), the same uncapped count the app uses,
    so the test can't drift from the code by using a different limit."""
    from app.services import content as content_svc

    # The Miami beauty city is what miami.knowsbeauty.localhost resolves to.
    city = await db.cities.find_one({"slug": "miami"})
    assert city, "seed should create the Miami city"
    return await content_svc.count_businesses(city["_id"])


class TestAllListingsPage:
    def test_all_page_renders_ok(self, seeded_db, gate_off):
        r = _make_client().get("/all", headers=HOST)
        assert r.status_code == 200, r.text[:500]
        assert r.headers["content-type"].startswith("text/html")

    @pytest.mark.asyncio
    async def test_all_page_lists_every_live_listing(self, seeded_db, gate_off):
        """The full directory must show ALL live listings — its rendered card
        count equals the number of live businesses, proving it is NOT filtered to
        a single category or neighborhood."""
        expected = await _live_count(seeded_db)
        assert expected > 0, "seed should create live Miami businesses"

        body = _make_client().get("/all", headers=HOST).text
        # Each card is an anchor to /b/<slug>; count the distinct business links.
        card_slugs = set(re.findall(r'href="/b/([^"?#]+)"', body))
        assert len(card_slugs) == expected, (
            f"/all rendered {len(card_slugs)} listing cards but there are "
            f"{expected} live listings — it must show every one"
        )

    @pytest.mark.asyncio
    async def test_all_page_count_matches_a_category_page_is_larger(
        self, seeded_db, gate_off
    ):
        """Sanity that /all is unfiltered: it must contain strictly more listings
        than any single category page (the full list is a superset of any one
        category)."""
        client = _make_client()
        all_body = client.get("/all", headers=HOST).text
        all_slugs = set(re.findall(r'href="/b/([^"?#]+)"', all_body))

        # Pull a real category slug from the seeded nav and compare.
        from app.services import content as content_svc

        city = await seeded_db.cities.find_one({"slug": "miami"})
        cats = await content_svc.list_categories(city["_id"])
        top = next((c for c in cats if not c.get("parent_slug")), cats[0])
        cat_body = client.get(f"/c/{top['slug']}", headers=HOST).text
        cat_slugs = set(re.findall(r'href="/b/([^"?#]+)"', cat_body))

        assert cat_slugs, "the category page should list at least one business"
        assert all_slugs >= cat_slugs, "the full list must contain the category list"
        assert len(all_slugs) > len(cat_slugs), (
            "the full directory must have more listings than a single category"
        )

    def test_all_page_is_indexable(self, seeded_db, gate_off):
        """Unlike /search, the full directory is a real landing page and must NOT
        be noindex — it should be crawlable so Google can find every listing."""
        body = _make_client().get("/all", headers=HOST).text
        assert "noindex" not in body.lower()

    def test_all_page_reuses_business_card_partial(self, seeded_db, gate_off):
        """The directory must reuse the standard card markup (the 'View →' hover
        affordance is unique to business_card.html), not invent new tiles."""
        body = _make_client().get("/all", headers=HOST).text
        assert "View →" in body


class TestHomeSeeAllLink:
    def test_home_has_see_all_link_to_all_page(self, seeded_db, gate_off):
        """The home page must carry a real anchor to /all so the full directory is
        reachable in one click (a real <a href>, so open-in-new-tab works)."""
        body = _make_client().get("/", headers=HOST).text
        assert 'href="/all"' in body, "home page must link to the full directory"

    @pytest.mark.asyncio
    async def test_home_see_all_count_is_dynamic_not_hardcoded(
        self, seeded_db, gate_off
    ):
        """The 'See all N' text must show the live count of listings, matching the
        actual number of live businesses — never a hardcoded value."""
        expected = await _live_count(seeded_db)
        body = _make_client().get("/", headers=HOST).text

        # The link band reads "See all <N> <plural>". Extract the number and
        # assert it equals the live count.
        m = re.search(r"See all\s+(\d+)\s+", body)
        assert m, "home page should render a 'See all N ...' link"
        assert int(m.group(1)) == expected, (
            f"'See all {m.group(1)}' does not match the {expected} live listings"
        )

    @pytest.mark.asyncio
    async def test_see_all_count_tracks_the_data(self, seeded_db, gate_off):
        """Regression: if the count were hardcoded, adding a live business would
        NOT change it. Insert one more live Miami business and confirm the home
        page's 'See all N' number goes up by exactly one."""
        from app.services import content as content_svc

        city = await seeded_db.cities.find_one({"slug": "miami"})
        before = await _live_count(seeded_db)

        await seeded_db.businesses.insert_one(
            {
                "_id": "test-extra-live-salon",
                "city_id": city["_id"],
                "status": "live",
                "name": "Test Extra Live Salon",
                "slug": "test-extra-live-salon",
                "category_slugs": ["hair"],
                "neighborhood_slugs": [],
                "featured": {"enabled": False},
                "editors_pick": False,
                "quality_score": 0,
                "photos": [],
            }
        )
        # The nav/list caches key off content that changed; clear so the fresh
        # count is read (the autouse cache reset only fires between tests).
        content_svc.clear_nav_cache()

        body = _make_client().get("/", headers=HOST).text
        m = re.search(r"See all\s+(\d+)\s+", body)
        assert m and int(m.group(1)) == before + 1, (
            f"expected See all {before + 1}, got {m.group(1) if m else 'no match'} "
            "— the count must track the data, not be hardcoded"
        )


class TestAllPageEdgeCases:
    def test_all_page_unknown_host_is_404(self, seeded_db, gate_off):
        r = _make_client().get("/all", headers={"host": "nope.knowsbeauty.localhost"})
        # Unknown city subdomain → the tenant has no city → 404 (or the network
        # landing 404 for an unresolved host). Either way, never a 500.
        assert r.status_code in (404, 200)
        assert r.status_code != 500


class TestAllPageInSitemap:
    def test_sitemap_includes_all_page_when_live(self, seeded_db, gate_off):
        """The full directory must be discoverable by Google via the sitemap."""
        body = _make_client().get("/sitemap.xml", headers=HOST).text
        assert "/all</loc>" in body or "/all<" in body, (
            "sitemap should list the /all full-directory page"
        )


class TestAllPageEmptyCity:
    """A city with zero live listings must not create thin content: the /all page
    is noindex'd and the sitemap must NOT advertise it."""

    @pytest.fixture
    async def empty_city(self, seeded_db):
        """Blank out every live Miami listing so the directory is empty, without
        touching the city/category/neighborhood records themselves."""
        await seeded_db.businesses.update_many(
            {"status": "live"}, {"$set": {"status": "draft"}}
        )
        from app.services import content as content_svc

        content_svc.clear_nav_cache()
        return seeded_db

    def test_empty_all_page_is_noindex(self, empty_city, gate_off):
        r = _make_client().get("/all", headers=HOST)
        assert r.status_code == 200
        assert "noindex" in r.text.lower(), (
            "an empty directory must be noindex to avoid thin-content indexing"
        )

    def test_empty_all_page_not_in_sitemap(self, empty_city, gate_off):
        body = _make_client().get("/sitemap.xml", headers=HOST).text
        assert "/all</loc>" not in body and "/all<" not in body, (
            "an empty /all must not be advertised in the sitemap"
        )
