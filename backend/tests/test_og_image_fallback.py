"""Tests for the og:image / twitter:image share-preview fallback.

The bug this guards against: when someone shares a salon listing (or a city
home/pricing/owners page) for any city other than Miami, the link unfurled with
NO preview photo. Every page computed its og:image with a final fallback of
``city.get("hero_photo_url")`` — but only Miami had that field set, so links
from Brickell, Coconut Grove, Pinecrest, Bal Harbour, etc. came out as bare,
photoless cards. That is exactly the moment a salon owner first clicks the link
we send them, so a blank card costs us conversions.

`_city_og_image` is the fix: it always returns a non-blank, on-brand image for
any launched city by reusing the same deterministic curated set the network
landing's city cards already use.
"""

from __future__ import annotations

from app.routes.public.pages import (
    _LANDING_CITY_HERO_FALLBACKS,
    _city_og_image,
)


def test_real_city_hero_is_used_verbatim():
    """A city that has its own hero photo keeps it — we never override a real
    editor-set image with a generic fallback."""
    real = "https://images.unsplash.com/photo-real-miami?w=2400"
    assert _city_og_image({"slug": "miami", "hero_photo_url": real}) == real


def test_city_without_hero_gets_nonblank_curated_image():
    """THE REGRESSION GUARD: a city with no hero photo must still yield a usable
    image so its shared links are never photoless. If the fallback is ever
    removed, this fails."""
    for slug in ("brickell", "coconut-grove", "pinecrest", "bal-harbour"):
        result = _city_og_image({"slug": slug})  # no hero_photo_url at all
        assert result, f"{slug} produced a blank og:image"
        assert result in _LANDING_CITY_HERO_FALLBACKS
        assert result.startswith("https://")


def test_explicit_none_hero_still_falls_back():
    """A hero_photo_url present but set to None (the real DB shape for these
    cities) must still fall back, not return None."""
    result = _city_og_image({"slug": "brickell", "hero_photo_url": None})
    assert result
    assert result in _LANDING_CITY_HERO_FALLBACKS


def test_fallback_is_deterministic_per_slug():
    """The same city always shows the same preview image, so a shared link's
    card doesn't change between loads."""
    a = _city_og_image({"slug": "pinecrest"})
    b = _city_og_image({"slug": "pinecrest"})
    assert a == b


def test_no_city_returns_none():
    """The network-root pages (no tenant city) pass None through — base.html
    then simply omits the tag rather than emitting a broken one."""
    assert _city_og_image(None) is None
