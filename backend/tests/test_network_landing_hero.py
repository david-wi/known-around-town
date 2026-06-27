"""Tests for the network landing page's city cards — every card must show real
content above the fold, never a blank gradient capsule.

The bug this guards against: the landing's city picker renders a photo from each
city's `hero_photo_url`. Most cities had that field empty, so their cards (the
first thing a visitor sees) rendered as flat pink gradients with no image — the
"photoless capsules above the fold" defect.

Two layers are tested:
  1. The backend fallback `_landing_city_hero_fallback` — any city with no hero
     photo still gets a deterministic, stable, valid curated image URL.
  2. The `network_landing.html` template — a city WITH a hero renders an <img>;
     a city WITHOUT one (and with the fallback disabled) renders a branded
     placeholder bearing the city's monogram + name, not an empty box.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.routes.public.pages import (
    _LANDING_CITY_HERO_FALLBACKS,
    _landing_city_hero_fallback,
)


def _render_landing(live_cities: list[dict]) -> str:
    """Render the real network_landing.html through the APP's Jinja environment.

    WHY the app env (not a bare jinja2.Environment): network_landing.html extends
    base.html and uses app-registered filters/globals (img_sized, markdown) plus
    base-context vars (now, request, theme); a bare environment can't compile it.
    We supply the base-context keys the layout touches so the render matches what
    the live route produces, then assert against the card markup.
    """
    from app.main import templates as app_templates

    ctx = {
        # base.html/footer reference `now` for the copyright year.
        "now": datetime(2026, 6, 27, tzinfo=timezone.utc),
        "footer_legal": None,
        "city": None,
        "network": {"name": "Knows Beauty"},
        "theme": {
            "category_banner_gradient": "from-rose-100 to-amber-50",
            "accent_text_strong": "text-rose-600",
            "accent_hover_text": "hover:text-rose-700",
            "accent_text": "text-rose-600",
            "accent_text_full": "text-rose-600",
            "ring_accent": "ring-rose-400",
        },
        "vertical_word": "Beauty",
        "header_variant": "sticky",
        "canonical_url": None,
        "og_image": None,
        "item_list_jsonld": None,
        "request": None,
        "seo_title": "Knows Beauty",
        "meta_description": "",
        "is_network_landing": True,
        "live_cities": live_cities,
        "planned_cities": [],
        "landing_eyebrow": "KNOWS BEAUTY — A LOCAL GUIDE NETWORK",
        "landing_subhead": "The curated directory of Miami's best.",
        "landing_cities_eyebrow": "CITIES",
        "landing_cities_intro": "We're starting in Miami and expanding.",
    }
    tpl = app_templates.env.get_template("network_landing.html")
    return tpl.render(**ctx)


# ── Backend fallback ─────────────────────────────────────────────────────────

def test_fallback_returns_a_curated_url_for_any_slug():
    url = _landing_city_hero_fallback("aventura")
    assert url in _LANDING_CITY_HERO_FALLBACKS
    assert url.startswith("https://")


def test_fallback_is_deterministic_per_slug():
    # Stable across calls so a city's card image doesn't flicker between renders.
    assert _landing_city_hero_fallback("boca-raton") == _landing_city_hero_fallback(
        "boca-raton"
    )


def test_fallback_spreads_across_curated_set():
    # A representative spread of slugs should not all collapse to one image —
    # otherwise adjacent cards would all look identical.
    slugs = [
        "aventura", "boca-raton", "coral-gables", "coconut-grove", "south-beach",
        "wynwood", "brickell", "midtown", "hialeah", "doral", "plantation",
        "weston", "miramar", "hollywood", "pinecrest", "key-biscayne",
    ]
    picks = {_landing_city_hero_fallback(s) for s in slugs}
    assert len(picks) >= 4, picks


def test_every_curated_fallback_is_an_unsplash_image_url():
    for u in _LANDING_CITY_HERO_FALLBACKS:
        assert u.startswith("https://images.unsplash.com/"), u
        assert "w=" in u  # sized for the card


# ── Template render ──────────────────────────────────────────────────────────

def _imgs(html: str) -> list[str]:
    return re.findall(r"<img[^>]*>", html)


def test_city_with_hero_photo_renders_an_img():
    html = _render_landing(
        [
            {
                "name": "Aventura",
                "slug": "aventura",
                "tagline": "Aventura's best.",
                "hero_photo_url": "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1600",
                "url": "https://aventura.knowsbeauty.test/",
            }
        ]
    )
    imgs = _imgs(html)
    assert len(imgs) == 1, imgs
    assert "unsplash.com" in imgs[0]
    assert 'alt="Aventura"' in imgs[0]


def test_city_with_hero_photo_has_branded_broken_image_fallback():
    """A card with a hero URL still needs fallback content underneath the image.

    The live failure mode was not only "missing hero_photo_url": a remote image
    can fail after render. The onerror handler hides the image, so the container
    must already contain branded city content rather than revealing an empty
    gradient.
    """
    html = _render_landing(
        [
            {
                "name": "Aventura",
                "slug": "aventura",
                "tagline": "Aventura's best.",
                "hero_photo_url": "https://example.com/broken-hero.jpg",
                "url": "https://aventura.knowsbeauty.test/",
            }
        ]
    )
    assert 'aria-hidden="true"' in html
    assert "items-center justify-center" in html
    assert re.search(r">\s*A\s*</div>", html), "fallback monogram under hero image is missing"
    assert "this.onerror=null;this.style.display='none';" in html


def test_city_without_hero_photo_renders_branded_placeholder_not_blank():
    """A city card with no hero photo must NOT be an empty gradient box — it must
    carry the city monogram + name so it still reads as finished content."""
    html = _render_landing(
        [
            {
                "name": "Boca Raton",
                "slug": "boca-raton",
                "tagline": "",
                "hero_photo_url": None,  # simulate a city that slipped through
                "url": "https://boca-raton.knowsbeauty.test/",
            }
        ]
    )
    # The media area must NOT be the old blank gradient box. The branded
    # placeholder is uniquely identified by its centered flex layout (the blank
    # gradient was a bare <div> with no flex/justify classes) and the monogram
    # element carrying the city's first letter. Asserting on these specific,
    # placeholder-only markers means this test goes RED if the fallback ever
    # reverts to a blank capsule — exactly the regression we are guarding.
    assert "items-center justify-center" in html, (
        "no-photo card must render the centered branded placeholder, not a blank gradient"
    )
    # The monogram "B" must appear as an isolated element (its own div), not just
    # as a letter inside "Boca"/"Beauty" prose elsewhere on the page.
    assert re.search(r">\s*B\s*</div>", html), "monogram element for the city initial is missing"
    # The placeholder also repeats the city name as an eyebrow under the monogram,
    # so the name appears at least twice (placeholder eyebrow + card heading).
    assert html.count("Boca Raton") >= 2
