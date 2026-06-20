"""Tests for the "As Featured on Miami Knows Beauty" website badge (KAT-037).

Two concerns:

1. The badge image (`/badge/featured.svg`) returns a real SVG.
2. The badge path is exempt from the preview gate — it MUST load for the whole
   public internet even while the site is private, because Featured salons embed
   it on their OWN external websites. The exemption must be surgical: the badge
   loads without a preview token, but a normal gated page still redirects to the
   login wall.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    from app.main import app

    # raise_server_exceptions=False so a 500 surfaces as a response we can assert
    # on rather than bubbling out of the test client.
    return TestClient(app, raise_server_exceptions=False)


# ─── The badge image itself ──────────────────────────────────────────────────


class TestBadgeAsset:
    def test_badge_returns_svg(self, mock_db):
        client = _make_client()
        r = client.get("/badge/featured.svg", headers={"host": "miami.knowsbeauty.localhost"})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/svg+xml")

    def test_badge_body_is_real_svg_with_brand_text(self, mock_db):
        client = _make_client()
        r = client.get("/badge/featured.svg", headers={"host": "miami.knowsbeauty.localhost"})
        body = r.text
        # It is an SVG document …
        assert body.lstrip().startswith("<svg"), "badge body should be an <svg> document"
        assert "</svg>" in body
        # … carrying the brand wordmark and the "AS FEATURED ON" eyebrow, so the
        # image actually reads as the feature badge (not a blank rectangle).
        assert "Miami Knows Beauty" in body
        assert "AS FEATURED ON" in body

    def test_badge_is_cacheable(self, mock_db):
        """The badge ships a public cache header so embedding sites/CDNs can
        cache it rather than refetch on every visitor."""
        client = _make_client()
        r = client.get("/badge/featured.svg", headers={"host": "miami.knowsbeauty.localhost"})
        assert "public" in r.headers.get("cache-control", "")


# ─── Preview-gate exemption (surgical) ───────────────────────────────────────


@pytest.fixture
def gated_client(monkeypatch):
    """A client with the preview gate ENABLED, mirroring production pre-launch.

    conftest sets PREVIEW_MODE_ENABLED=false for the suite; here we force the
    DB-backed gate check to report "on" so we exercise the real gated behavior.
    """
    from app.services import site_settings

    async def _on():
        return True

    monkeypatch.setattr(site_settings, "get_preview_mode_enabled", _on)
    # The middleware imports the helper inside dispatch() via
    # `from app.services.site_settings import get_preview_mode_enabled`, so
    # patching the attribute on the module is what the request actually calls.
    return _make_client()


class TestBadgeBypassesPreviewGate:
    def test_badge_loads_without_preview_token(self, mock_db, gated_client):
        """With the gate ON and NO preview cookie, the badge still returns the
        SVG — otherwise it would render broken on every salon's external site."""
        r = gated_client.get(
            "/badge/featured.svg",
            headers={"host": "miami.knowsbeauty.localhost"},
            follow_redirects=False,
        )
        assert r.status_code == 200, (
            "badge must be reachable without a preview token while the gate is on; "
            f"got {r.status_code} (a 302 means it would show broken on salon sites)"
        )
        assert r.headers["content-type"].startswith("image/svg+xml")

    def test_normal_page_still_gated(self, mock_db, gated_client):
        """The exemption is surgical: a normal content page still redirects to
        the preview login. If THIS regresses to 200, the gate is wide open."""
        r = gated_client.get(
            "/",
            headers={"host": "miami.knowsbeauty.localhost"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/preview-login" in r.headers.get("location", "")

    def test_only_badge_prefix_is_exempt(self, mock_db, gated_client):
        """A sibling path under no special prefix is NOT exempt — proving the
        bypass is scoped to /badge/ and did not accidentally open other paths."""
        r = gated_client.get(
            "/c/hair",
            headers={"host": "miami.knowsbeauty.localhost"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 301)
        assert "/preview-login" in r.headers.get("location", "")
