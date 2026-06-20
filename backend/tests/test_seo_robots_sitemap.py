"""Tests for robots.txt and sitemap.xml launch readiness.

The whole point of these two files is that ONE launch-gate flip must open the
site to search engines. While the gate is on (pre-launch) both files must say
"this site is private" — robots.txt returns ``Disallow: /`` and the sitemap is
an empty ``<urlset>`` — so Google does not waste crawl budget on a login wall
and cannot enumerate business names early. The moment the gate flips off both
must flip together: robots.txt allows crawling and points at the sitemap, and
the sitemap lists every real public URL for the city.

These tests validate that behaviour against what the code actually does (the
rendered response bodies), not against comments. They also cover the
admin-key-gated ``?preview_state=`` verification override, which lets us prove
the live response on the deployed site WITHOUT flipping the real gate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

HOST = {"host": "miami.knowsbeauty.localhost"}
APEX = {"host": "knowsbeauty.localhost"}
ADMIN_KEY = "seo-test-admin-key"


def _make_client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def gate_on(monkeypatch):
    """Force the launch gate ON (pre-launch state), like production today.

    conftest sets PREVIEW_MODE_ENABLED=false for the suite, so we patch the
    DB-backed helper the handlers actually call to report "on".
    """
    from app.services import site_settings
    import app.routes.public.pages as pages

    async def _on():
        return True

    monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _on)
    # The handlers import the helper at module load, so patch the bound name too.
    monkeypatch.setattr(pages, "get_preview_mode_enabled", _on)


@pytest.fixture
def gate_off(monkeypatch):
    """Force the launch gate OFF (live state)."""
    from app.services import site_settings
    import app.routes.public.pages as pages

    async def _off():
        return False

    monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _off)
    monkeypatch.setattr(pages, "get_preview_mode_enabled", _off)


@pytest.fixture
def admin_key(monkeypatch):
    """Give the app a known admin API key so the verification override works."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    yield ADMIN_KEY
    get_settings.cache_clear()


# ─── robots.txt ──────────────────────────────────────────────────────────────


class TestRobotsGated:
    def test_robots_disallows_all_when_gated(self, mock_db, gate_on):
        """Pre-launch: robots.txt must block every crawler so Google does not
        index pages that all redirect to a login wall."""
        r = _make_client().get("/robots.txt", headers=HOST)
        assert r.status_code == 200
        assert "Disallow: /" in r.text
        # It must NOT advertise an Allow: / or a sitemap while private.
        assert "Allow: /" not in r.text
        assert "Sitemap:" not in r.text


class TestRobotsLive:
    def test_robots_allows_and_references_sitemap_when_live(
        self, seeded_db, gate_off
    ):
        """Post-launch: robots.txt must allow crawling and point crawlers at the
        sitemap — otherwise every page stays unindexed after launch."""
        r = _make_client().get("/robots.txt", headers=HOST)
        assert r.status_code == 200
        assert "Allow: /" in r.text
        # A blanket Disallow: / would keep the whole site out of the index.
        assert "Disallow: /\n" not in r.text
        # The Sitemap: directive must give an absolute URL to sitemap.xml.
        assert "Sitemap: " in r.text
        sitemap_line = next(
            line for line in r.text.splitlines() if line.startswith("Sitemap:")
        )
        assert sitemap_line.rstrip().endswith("/sitemap.xml")
        assert "http" in sitemap_line  # absolute, not a relative path

    def test_robots_still_disallows_private_account_paths_when_live(
        self, seeded_db, gate_off
    ):
        """Even when live, the owner sign-in / dashboard routes stay out of the
        index — they always redirect or require auth, so crawling them wastes
        budget and surfaces nothing useful."""
        r = _make_client().get("/robots.txt", headers=HOST)
        assert "Disallow: /owners/login" in r.text
        assert "Disallow: /owners/me" in r.text


# ─── sitemap.xml ─────────────────────────────────────────────────────────────


class TestSitemapGated:
    def test_sitemap_empty_when_gated(self, seeded_db, gate_on):
        """Pre-launch the sitemap must be a valid but EMPTY urlset — listing
        every business slug before launch would leak the directory early."""
        r = _make_client().get("/sitemap.xml", headers=HOST)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/xml")
        assert "<urlset" in r.text
        assert r.text.count("<loc>") == 0


class TestSitemapLive:
    def test_sitemap_lists_real_urls_when_live(self, seeded_db, gate_off):
        """Post-launch the sitemap must enumerate the city's real public URLs.
        The seeded Miami beauty city has live businesses, categories and
        neighborhoods, so the count must be well above the handful of static
        pages."""
        r = _make_client().get("/sitemap.xml", headers=HOST)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/xml")
        loc_count = r.text.count("<loc>")
        # 5 static pages + 8 categories + 11 neighborhoods + dozens of
        # businesses and intersection pages — comfortably over 30.
        assert loc_count > 30, f"expected a populated sitemap, got {loc_count} URLs"

    def test_sitemap_includes_business_category_and_neighborhood_pages(
        self, seeded_db, gate_off
    ):
        """The populated sitemap must include each kind of public page, not just
        the home page — business detail (/b/), category (/c/) and neighborhood
        (/n/) URLs all need to be discoverable."""
        body = _make_client().get("/sitemap.xml", headers=HOST).text
        assert "/b/" in body, "business detail pages must be in the sitemap"
        assert "/c/" in body, "category pages must be in the sitemap"
        assert "/n/" in body, "neighborhood pages must be in the sitemap"
        # Static high-value pages too.
        assert "/pricing" in body
        assert "/guides" in body

    def test_sitemap_entries_carry_lastmod(self, seeded_db, gate_off):
        """Each URL carries a <lastmod> so Google knows how fresh it is."""
        body = _make_client().get("/sitemap.xml", headers=HOST).text
        assert body.count("<lastmod>") == body.count("<loc>")
        assert body.count("<lastmod>") > 0

    def test_apex_sitemap_lists_city_home_pages_when_live(self, seeded_db, gate_off):
        """The bare-apex host (no city subdomain) must list each city's home page
        so a brand-new city is discoverable via the sitemap, not only by crawling
        the landing-page HTML. City pages live on their own subdomains."""
        body = _make_client().get("/sitemap.xml", headers=APEX).text
        # The seeded city is miami; its home lives at miami.<network-suffix>/
        assert "miami.knowsbeauty.localhost/" in body


# ─── one gate-flip opens BOTH (robots + sitemap flip together) ───────────────


class TestSingleFlipOpensSearchEngines:
    def test_both_flip_together_on_one_gate_change(self, seeded_db, monkeypatch):
        """The core launch guarantee: flipping the single gate from on→off must
        change BOTH robots.txt (private→crawlable) and sitemap.xml (empty→full)
        with no second manual step."""
        from app.services import site_settings
        import app.routes.public.pages as pages

        state = {"on": True}

        async def _gate():
            return state["on"]

        monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _gate)
        monkeypatch.setattr(pages, "get_preview_mode_enabled", _gate)
        client = _make_client()

        # Gate ON: private signals on both files.
        assert "Disallow: /" in client.get("/robots.txt", headers=HOST).text
        assert client.get("/sitemap.xml", headers=HOST).text.count("<loc>") == 0

        # Flip the ONE gate.
        state["on"] = False

        # Gate OFF: both files now invite crawling, no other change needed.
        robots = client.get("/robots.txt", headers=HOST).text
        assert "Allow: /" in robots and "Sitemap:" in robots
        assert client.get("/sitemap.xml", headers=HOST).text.count("<loc>") > 30


class TestSitemapToleratesStringDates:
    """Regression: some editorial guides and businesses store their date as an
    ISO STRING rather than a datetime. Formatting a <lastmod> from a string used
    to call .strftime() on it and raise AttributeError, which would 500 the
    WHOLE sitemap the moment the launch gate flipped off. The sitemap must
    survive a string-dated record and still list it."""

    async def _seed_guide(self, mock_db, *, published_at):
        """Insert one live editorial guide into the seeded Miami beauty city."""
        net = await mock_db.networks.find_one({"slug": "beauty"})
        city = await mock_db.cities.find_one(
            {"network_id": net["_id"], "slug": "miami"}
        )
        await mock_db.editorial_guides.insert_one(
            {
                "_id": "guide-strdate",
                "city_id": city["_id"],
                "slug": "best-blowouts-miami",
                "title": "Best Blowouts in Miami",
                "status": "live",
                "published_at": published_at,  # may be a STRING on purpose
            }
        )

    @pytest.mark.asyncio
    async def test_sitemap_renders_when_guide_date_is_a_string(
        self, seeded_db, gate_off
    ):
        # A guide whose published_at is an ISO string — the shape that crashed.
        await self._seed_guide(seeded_db, published_at="2026-06-12T06:00:00Z")
        r = _make_client().get("/sitemap.xml", headers=HOST)
        assert r.status_code == 200, (
            "a guide with a string date must not 500 the whole sitemap; "
            f"got {r.status_code}"
        )
        # The string-dated guide is still listed, with the date's first 10 chars
        # used as lastmod (not today, not a crash).
        assert "/guides/best-blowouts-miami" in r.text
        assert "<lastmod>2026-06-12</lastmod>" in r.text

    @pytest.mark.asyncio
    async def test_sitemap_renders_when_guide_date_is_a_datetime(
        self, seeded_db, gate_off
    ):
        from datetime import datetime, timezone

        await self._seed_guide(
            seeded_db, published_at=datetime(2026, 5, 1, tzinfo=timezone.utc)
        )
        r = _make_client().get("/sitemap.xml", headers=HOST)
        assert r.status_code == 200
        assert "/guides/best-blowouts-miami" in r.text
        assert "<lastmod>2026-05-01</lastmod>" in r.text


# ─── verification override (admin-key gated) ─────────────────────────────────


class TestPreviewStateOverride:
    def test_override_live_with_admin_key_renders_live_while_gated(
        self, seeded_db, gate_on, admin_key
    ):
        """With the gate ON, an admin-key request asking for the live state gets
        the live robots+sitemap — so we can verify the deployed live response
        before launch without flipping the real gate."""
        client = _make_client()
        hk = {**HOST, "X-API-Key": admin_key}

        robots = client.get("/robots.txt?preview_state=live", headers=hk).text
        assert "Allow: /" in robots and "Sitemap:" in robots

        sitemap = client.get("/sitemap.xml?preview_state=live", headers=hk)
        assert sitemap.text.count("<loc>") > 30

    def test_override_live_without_admin_key_stays_gated(self, seeded_db, gate_on):
        """The override is admin-key gated: an anonymous visitor adding
        ?preview_state=live must STILL get the empty/private response, so the
        business directory cannot be enumerated before launch."""
        client = _make_client()
        # No X-API-Key header.
        sitemap = client.get("/sitemap.xml?preview_state=live", headers=HOST)
        assert sitemap.text.count("<loc>") == 0
        robots = client.get("/robots.txt?preview_state=live", headers=HOST)
        assert "Disallow: /" in robots.text
        assert "Allow: /" not in robots.text

    def test_override_live_with_wrong_admin_key_stays_gated(
        self, seeded_db, gate_on, admin_key
    ):
        """A wrong admin key must not unlock the live response."""
        client = _make_client()
        hk = {**HOST, "X-API-Key": "not-the-real-key"}
        sitemap = client.get("/sitemap.xml?preview_state=live", headers=hk)
        assert sitemap.text.count("<loc>") == 0

    def test_override_gated_with_admin_key_forces_private_while_live(
        self, seeded_db, gate_off, admin_key
    ):
        """The opposite override forces the gated form even when live — handy for
        confirming the pre-launch response is unchanged."""
        client = _make_client()
        hk = {**HOST, "X-API-Key": admin_key}
        sitemap = client.get("/sitemap.xml?preview_state=gated", headers=hk)
        assert sitemap.text.count("<loc>") == 0
        robots = client.get("/robots.txt?preview_state=gated", headers=hk)
        assert "Disallow: /" in robots.text
