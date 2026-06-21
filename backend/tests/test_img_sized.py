"""Tests for the `img_sized` Jinja filter — right-sizing photo URLs at render time.

The bug this guards against: the homepage painted photos straight from stored
data, and some of those URLs requested a huge image (e.g. a 2400px-wide photo
shipped to a 390px phone, plus an unoptimized 1.9MB PNG). That made the mobile
homepage weigh ~6.6MB. The filter rewrites Unsplash URLs to the width we render
at and caps quality, while leaving any non-Unsplash URL untouched (those can't
be resized by a query param).

Two layers are tested:
  1. The filter function itself (`_img_sized`) — the resize/cap/passthrough rules.
  2. That the filter is actually registered on the app's Jinja env AND wired into
     home.html, so a real render emits a sized `w=` (not the original baked-in one).
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from app.main import _img_sized, templates


# ── The filter function: Unsplash resize + quality cap ───────────────────────

def _qs(url: str) -> dict:
    """Parse a URL's query string into {param: value} for assertions."""
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_unsplash_oversized_width_is_replaced_and_quality_capped():
    """A 2400px-wide, q=90 Unsplash URL → width becomes the target, q capped at 70."""
    src = "https://images.unsplash.com/photo-123?w=2400&q=90&auto=format&fit=crop"
    out = _img_sized(src, 500)
    q = _qs(out)
    assert q["w"] == "500", out
    assert q["q"] == "70", out
    # Other params are preserved — we only touch w and (high) q.
    assert q["auto"] == "format", out
    assert q["fit"] == "crop", out
    assert urlsplit(out).netloc == "images.unsplash.com"


def test_unsplash_url_with_no_width_gets_width_added():
    """An Unsplash URL with no w= at all → w is added at the target width."""
    src = "https://images.unsplash.com/photo-456?auto=format&fit=crop"
    out = _img_sized(src, 800)
    q = _qs(out)
    assert q["w"] == "800", out
    # No q param was present, so none is invented.
    assert "q" not in q, out
    assert q["auto"] == "format", out


def test_unsplash_low_quality_is_left_below_the_cap():
    """A q already at or below 70 is left unchanged — we only cap, never raise."""
    src = "https://images.unsplash.com/photo-789?w=1600&q=60&auto=format"
    out = _img_sized(src, 500)
    q = _qs(out)
    assert q["w"] == "500", out
    assert q["q"] == "60", out  # untouched — already under the cap


def test_unsplash_quality_exactly_at_cap_is_unchanged():
    """q=70 is exactly the cap and must be left as-is (boundary case)."""
    src = "https://images.unsplash.com/photo-789?w=1600&q=70"
    out = _img_sized(src, 500)
    assert _qs(out)["q"] == "70", out


# ── Non-Unsplash and edge inputs: returned unchanged ─────────────────────────

def test_tildacdn_png_returned_unchanged():
    """The 1.9MB Tilda PNG can't be resized by a query param — pass it through
    untouched so the filter never mangles a non-Unsplash CDN URL."""
    src = "https://static.tildacdn.net/tild6434-3666-4630-a336-616137663538/photo.png"
    assert _img_sized(src, 500) == src


def test_relative_static_url_returned_unchanged():
    """A relative /static/... or /assets/... path (e.g. the placeholder) is not an
    Unsplash URL and must be returned exactly as given."""
    src = "/assets/placeholder-salon.svg"
    assert _img_sized(src, 200) == src


def test_other_https_photo_host_returned_unchanged():
    """Any other photo host is passed through — we only know how to size Unsplash."""
    src = "https://example.com/some/photo.jpg?w=2400"
    assert _img_sized(src, 500) == src


@pytest.mark.parametrize("empty", ["", None])
def test_empty_or_none_returned_as_is(empty):
    """Empty string and None are returned as-is so a missing photo never errors."""
    assert _img_sized(empty, 500) == empty


def test_non_string_returned_as_is():
    """A non-string (defensive) is returned unchanged rather than raising."""
    assert _img_sized(123, 500) == 123  # type: ignore[arg-type]


# ── Registration + template wiring (behavior, not narration) ─────────────────

def test_filter_is_registered_on_the_app_jinja_env():
    """Templates can only call `| img_sized(...)` if the filter is registered on
    the shared env — assert it's actually wired, not just defined."""
    assert templates.env.filters.get("img_sized") is _img_sized


def test_home_template_emits_sized_width_for_an_unsplash_hero(seeded_db):
    """A real render of the home page must apply the filter to the VISIBLE hero
    photo: the Miami seed hero is an Unsplash URL baked in at w=2400&q=90; after
    rendering through the template, the hero background-image must come out at the
    sized hero width (1200) with quality capped at 70 — proving the
    `| img_sized(1200)` in home.html is live, not just present in source.

    We assert on the hero's `background-image` div specifically, NOT on the whole
    page text: the social-share <meta og:image>/<twitter:image> tags and the
    JSON-LD logo intentionally keep the large 2400px URL (preview-card platforms
    want a big image), so a page-wide "no w=2400 anywhere" check would wrongly
    flag those. The browser never downloads the social-share image to paint the
    page, so it doesn't affect page weight — only the visible hero does."""
    import re

    from fastapi.testclient import TestClient
    from app.main import app

    r = TestClient(app).get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.status_code
    # Find the first background-image div (the hero is the first photo painted).
    # Capture the full URL up to the closing double-quote (query string included).
    m = re.search(r'background-image:\s*url\("(?P<u>https://images\.unsplash\.com[^"]*)"', r.text)
    assert m, "no Unsplash hero background-image found in rendered home page"
    hero_url = m.group("u")
    # &amp; entity-encoding in the attribute → normalise for query parsing.
    q = _qs(hero_url.replace("&amp;", "&"))
    assert q.get("w") == "1200", f"hero not sized to 1200: {hero_url}"
    assert q.get("q") == "70", f"hero quality not capped to 70: {hero_url}"
