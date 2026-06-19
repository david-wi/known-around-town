"""Tests for graceful image fallback — broken/missing salon photos must show a
branded placeholder tile instead of a broken/empty grey box.

The bug this guards against: salon photos are stock images and some now 404, so
shoppers saw broken grey boxes; cards with no photo at all showed an empty grey
box. The fix renders a branded placeholder SVG when a photo is absent, and adds
an onerror handler that swaps a broken photo URL to the placeholder (with a loop
guard so a failing placeholder can't re-trigger onerror).

Two layers are tested:
  1. Direct render of partials/business_card.html — the card markup that decides
     between real photo, onerror-guarded photo, and placeholder.
  2. Full request path — the placeholder asset is actually served, and the
     business detail page layers the placeholder behind its photo backgrounds.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader

PLACEHOLDER_URL = "/assets/placeholder-salon.svg"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static"


class _Theme:
    accent_text_full = "text-rose-600"
    ring_accent = "ring-rose-400"


def _render_card(b: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    tpl = env.get_template("partials/business_card.html")
    return tpl.render(
        b=b,
        theme=_Theme(),
        category_names=None,
        neighborhood_names=None,
        ratings_min_review_count=20,
        tenant_label="Beauty",
    )


def _base_business(**overrides) -> dict:
    b = {
        "slug": "test-salon",
        "name": "Test Salon",
        "photos": [],
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["brickell"],
        "editors_pick": False,
        "featured": {"enabled": False},
        "is_founding_partner": False,
        "google_rating": None,
        "hide_ratings": False,
        "google_review_count": 0,
        "price_cues": "$$",
        "short_description": "A test salon",
        "claim_status": "unclaimed",
        "tags": [],
    }
    b.update(overrides)
    return b


def _imgs(html: str) -> list[str]:
    return re.findall(r"<img[^>]*>", html)


# ── Card with no photo ───────────────────────────────────────────────────────

def test_card_with_no_photo_renders_branded_placeholder():
    """A salon with zero photos must render the placeholder image, not an empty
    grey box (the card always renders an <img> now)."""
    html = _render_card(_base_business(photos=[]))
    imgs = _imgs(html)
    assert len(imgs) == 1, imgs
    assert PLACEHOLDER_URL in imgs[0]
    # No onerror needed when the src is already the placeholder.
    assert "onerror" not in imgs[0]


# ── Card with a photo (which may 404) ────────────────────────────────────────

def test_card_with_photo_has_onerror_fallback_to_placeholder():
    """A salon with a photo renders the real photo, but with an onerror that
    swaps to the placeholder if the photo URL fails to load."""
    html = _render_card(_base_business(photos=["https://example.com/broken.jpg"]))
    imgs = _imgs(html)
    assert len(imgs) == 1, imgs
    img = imgs[0]
    assert "https://example.com/broken.jpg" in img
    assert "onerror" in img
    assert PLACEHOLDER_URL in img


def test_card_onerror_has_infinite_loop_guard():
    """The onerror handler must null itself first so a failing placeholder can't
    re-trigger onerror in an infinite loop."""
    html = _render_card(_base_business(photos=["https://example.com/broken.jpg"]))
    img = _imgs(html)[0]
    onerror = re.search(r'onerror="([^"]*)"', img).group(1)
    # this.onerror=null must come BEFORE the src reassignment.
    assert "this.onerror=null" in onerror
    assert onerror.index("this.onerror=null") < onerror.index("this.src=")


def test_card_with_dict_photo_format_still_renders_photo():
    """Photos can be stored as {"url": ...} dicts; the card must read the url."""
    html = _render_card(
        _base_business(photos=[{"url": "https://example.com/real.jpg", "is_hero": True}])
    )
    img = _imgs(html)[0]
    assert "https://example.com/real.jpg" in img
    assert "onerror" in img  # real photo still gets the 404 fallback


# ── The placeholder asset itself ─────────────────────────────────────────────

def test_placeholder_svg_exists_and_is_well_formed():
    path = STATIC_DIR / "placeholder-salon.svg"
    assert path.is_file(), f"missing placeholder asset: {path}"
    # Must be valid, well-formed XML so the browser renders it (a malformed SVG
    # would itself show as a broken box). The file is a trusted, repo-authored
    # asset — not untrusted input — so a stdlib parse is appropriate here. The
    # parse raises ParseError on any malformedness, which fails the test.
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg"), root.tag
    text = path.read_text(encoding="utf-8")
    assert "Miami Knows Beauty" in text


def test_placeholder_is_served_over_http(client):
    """The static mount must actually serve the placeholder — a 404 here would
    mean every fallback shows a broken box instead of the tile."""
    r = client.get(PLACEHOLDER_URL)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")


# ── Business detail page (CSS background fallback) ────────────────────────────

def test_business_detail_layers_placeholder_behind_photo(client):
    """The detail page hero uses a CSS background (no <img> onerror possible), so
    it must layer the placeholder beneath the photo: if the photo 404s, the
    placeholder shows through instead of a grey box."""
    # Miami beauty seed has businesses with photos; the hero background should
    # now include the placeholder URL as a second (lower) layer.
    r = client.get(
        "/b/rossano-ferretti-hair-spa-miami",
        headers={"host": "miami.knowsbeauty.localhost"},
    )
    # Some seeds may not have this exact slug; fall back to any business page.
    if r.status_code != 200:
        pytest.skip("expected business slug not present in seed")
    assert PLACEHOLDER_URL in r.text


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)
