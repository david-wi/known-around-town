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


# ─── _seo_base_url: per-host sitemap/robots base (multi-tenant correctness) ───


def _make_request(host: str, scheme: str = "https"):
    """Build a minimal Starlette Request carrying just a Host header and scheme.

    _seo_base_url only reads request.headers["host"] and request.url.scheme, so a
    bare ASGI scope is enough to exercise it as a pure function — no TestClient,
    no DB, no seed needed.
    """
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "scheme": scheme,
        "path": "/sitemap.xml",
        "query_string": b"",
        "headers": [(b"host", host.encode("latin-1"))],
        "server": (host.split(":")[0], 443 if scheme == "https" else 80),
    }
    return Request(scope)


@pytest.fixture
def canonical_miami(monkeypatch):
    """Set CANONICAL_BASE_URL to production miami, like the real deployment.

    get_settings() is @lru_cache, so the cache must be cleared around the env
    change (same pattern as the admin_key fixture above).
    """
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("CANONICAL_BASE_URL", "https://miami.knowsbeauty.com")
    get_settings.cache_clear()
    yield "https://miami.knowsbeauty.com"
    get_settings.cache_clear()


@pytest.fixture
def canonical_unset(monkeypatch):
    """Ensure CANONICAL_BASE_URL is unset (developer shells may export it)."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("CANONICAL_BASE_URL", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestSeoBaseUrl:
    """The multi-tenant SEO base: each city subdomain is its own canonical site,
    so its sitemap/robots must reference ITS OWN host. The previous code used
    CANONICAL_BASE_URL (always miami) for every city, so every city's sitemap
    listed miami URLs — which Google ignores as cross-host, leaving 25 of 26 city
    sites with no usable sitemap of their own pages.

    These assert the actual return value of the helper (behaviour, not comments),
    and mirror the four cases in the page-canonical logic so the two stay in sync.
    """

    def test_production_city_subdomain_self_hosts(self, canonical_miami):
        """hialeah.knowsbeauty.com (a production city subdomain, NOT miami) with
        CANONICAL_BASE_URL=https://miami.knowsbeauty.com must return its OWN host
        — not miami. THIS is the bug: the old `base = canonical_base ...` returned
        miami here, so hialeah's sitemap listed miami URLs."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("hialeah.knowsbeauty.com")
        assert _seo_base_url(req) == "https://hialeah.knowsbeauty.com"

    def test_production_flagship_self_hosts(self, canonical_miami):
        """The miami flagship returns miami — unchanged from the old behaviour, so
        we know the fix did not move the one host that was already correct."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("miami.knowsbeauty.com")
        assert _seo_base_url(req) == "https://miami.knowsbeauty.com"

    def test_production_apex_self_hosts(self, canonical_miami):
        """The bare apex (knowsbeauty.com, the network landing host) is also a
        production host and returns itself, https."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("knowsbeauty.com")
        assert _seo_base_url(req) == "https://knowsbeauty.com"

    def test_dev_host_consolidates_to_production_com(self, canonical_miami):
        """A dev/staging host (e.g. *.ai.devintensive.com) is NOT on the
        knowsbeauty.com apex, so it consolidates to the production .com base — the
        dev subdomain must never get its own sitemap host indexed."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("knowsbeauty.ai.devintensive.com")
        assert _seo_base_url(req) == "https://miami.knowsbeauty.com"

    def test_no_canonical_base_falls_back_to_request_host(self, canonical_unset):
        """With no CANONICAL_BASE_URL set, the base is the request's own
        scheme://host — every host self-hosts (the test/dev default)."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("doral.knowsbeauty.com", scheme="http")
        assert _seo_base_url(req) == "http://doral.knowsbeauty.com"

    def test_production_upgrades_scheme_to_https(self, canonical_miami):
        """A production city request that arrives over http still gets an https
        base (the scheme comes from the canonical base), matching the per-page
        canonical's http->https upgrade so http/https aren't indexed separately."""
        from app.routes.public.pages import _seo_base_url

        req = _make_request("doral.knowsbeauty.com", scheme="http")
        assert _seo_base_url(req) == "https://doral.knowsbeauty.com"

    def test_red_green_old_logic_would_return_miami_for_hialeah(
        self, canonical_miami
    ):
        """Red-green guard: prove the OLD logic (`base = canonical_base if
        canonical_base else ...`) returned miami for hialeah — the exact bug — and
        that the new helper does NOT. If someone reverts _seo_base_url to the old
        one-liner, the first assertion below mirrors that old result and the
        second (the real fix) fails."""
        from app.config import get_settings
        from app.routes.public.pages import _seo_base_url

        old_logic = get_settings().canonical_base_url.rstrip("/")  # the old `base`
        assert old_logic == "https://miami.knowsbeauty.com"  # what the bug did
        # The fix must NOT equal that for a non-miami city.
        req = _make_request("hialeah.knowsbeauty.com")
        assert _seo_base_url(req) != old_logic
        assert _seo_base_url(req) == "https://hialeah.knowsbeauty.com"


@pytest.fixture
def canonical_other_city(monkeypatch):
    """Set CANONICAL_BASE_URL to a DIFFERENT city on the same production apex
    than the one we request from.

    The test network suffix is knowsbeauty.localhost, and the seeded city is
    miami. By pointing the canonical base at a sibling city (orlando) on the same
    apex, a request to miami.knowsbeauty.localhost is a production host that does
    NOT match the canonical host — reproducing the cross-host bug in the test
    environment: the OLD code would put orlando URLs in miami's sitemap; the fix
    must use miami's own host.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("CANONICAL_BASE_URL", "https://orlando.knowsbeauty.localhost")
    get_settings.cache_clear()
    yield "https://orlando.knowsbeauty.localhost"
    get_settings.cache_clear()


class TestSitemapRobotsUseRequestHost:
    """End-to-end guard: with a production CANONICAL_BASE_URL pointing at a
    DIFFERENT city, a sitemap/robots fetched from this city's subdomain must
    reference THIS subdomain's own host, not the canonical city. This is the
    user-visible bug, asserted through the real rendered response."""

    def test_sitemap_from_city_host_lists_its_own_host_not_canonical(
        self, seeded_db, gate_off, canonical_other_city
    ):
        # Request the seeded miami city's sitemap while the canonical base points
        # at a sibling city (orlando). Every <loc> must carry miami's own host.
        body = _make_client().get("/sitemap.xml", headers=HOST).text
        assert "<loc>https://miami.knowsbeauty.localhost/" in body
        # The bug: with the old logic these would all be orlando URLs.
        assert "orlando.knowsbeauty.localhost" not in body

    def test_robots_from_city_host_points_sitemap_at_its_own_host(
        self, seeded_db, gate_off, canonical_other_city
    ):
        robots = _make_client().get("/robots.txt", headers=HOST).text
        sitemap_line = next(
            line for line in robots.splitlines() if line.startswith("Sitemap:")
        )
        assert sitemap_line.strip() == (
            "Sitemap: https://miami.knowsbeauty.localhost/sitemap.xml"
        )
        assert "orlando" not in robots
