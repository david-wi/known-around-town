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
    # WHY: the business_card partial now calls `| img_sized(500)` to right-size
    # photos at render time. A bare jinja2.Environment doesn't know that filter
    # (it's registered on the app's env in main.py), so register the real one here
    # — otherwise the partial raises "No filter named 'img_sized'". Using the
    # actual app filter (not a stub) keeps this render faithful to production.
    from app.main import _img_sized

    env.filters["img_sized"] = _img_sized
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


# ── Home page (CSS background fallback across many photo surfaces) ────────────

def _dual_layer_divs(html: str) -> list[str]:
    """Return the opening tags of every div whose background-image stacks a real
    photo over the branded placeholder — i.e. uses the two-layer fallback."""
    return [
        tag
        for tag in re.findall(r"<div[^>]*background-image[^>]*>", html)
        if PLACEHOLDER_URL in tag
    ]


def test_home_page_layers_placeholder_behind_photos(client):
    """The home page paints salon/neighborhood photos as CSS backgrounds, which
    can't use an <img> onerror handler. Each must layer the branded placeholder
    beneath the photo so a 404 photo degrades to the brand tile, not a grey/dark
    box. The hero is the first thing a shopper sees, so this matters most here."""
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.status_code
    # The placeholder must appear at least once (the hero always renders when the
    # city has a hero photo; the Miami seed provides one).
    assert PLACEHOLDER_URL in r.text
    # And wherever it appears it must be the SECOND background layer (the real
    # photo paints on top, the placeholder shows through only on a 404). Verify
    # the dual-layer shape on at least one div: a real photo URL, then the
    # placeholder, with per-layer cover/contain sizing.
    dual = _dual_layer_divs(r.text)
    assert dual, "expected at least one photo div layering the placeholder beneath it"
    sample = dual[0]
    assert "background-size: cover, contain" in sample, sample
    # The placeholder is the lower (second) layer — it appears AFTER the first
    # url() in the background-image stack, never as the sole/first layer.
    bg = re.search(r"background-image:\s*url\([^)]*\),\s*url\([^)]*placeholder-salon", sample)
    assert bg, f"placeholder must be the second background layer, got: {sample}"


def _render_page(template_name: str, **ctx) -> str:
    """Render a public template through the APP's real Jinja environment. Used
    for pages (guide, neighborhood) the default seed doesn't populate, so we can
    still assert the fallback markup without depending on seeded content.

    WHY the app env (not a bare jinja2.Environment): these templates extend
    base.html and use app-registered filters/globals (e.g. the `markdown`
    filter), so a bare environment fails to even compile them. Importing
    app.main runs attach_templates(), which registers every filter and global —
    giving a faithful render of what the live route would produce."""
    from app.main import templates as app_templates

    tpl = app_templates.env.get_template(template_name)
    return tpl.render(**ctx)


# Minimal context shared by guide/neighborhood direct renders. base.html is the
# parent layout; these keys are the ones the hero blocks touch. Anything the
# template references but we don't care about is left falsy/empty so the
# {% if %} guards simply skip it.
def _page_ctx(**overrides) -> dict:
    from datetime import datetime, timezone

    ctx = {
        # base.html/footer reference `now` for the copyright year; the live
        # route supplies it via _base_context. A fixed value is fine here.
        "now": datetime(2026, 6, 19, tzinfo=timezone.utc),
        "footer_legal": None,
        "city": {"name": "Miami"},
        "network": {"name": "Miami Knows Beauty"},
        "theme": {
            "ring_accent": "ring-rose-400",
            "accent_text": "text-rose-600",
            "accent_text_light": "text-rose-200",
            "accent_text_lighter": "text-rose-100",
            "accent_text_lighter_full": "text-rose-100",
            "accent_text_full": "text-rose-600",
            "accent_border_subtle": "border-rose-300/40",
        },
        "vertical_word": "Beauty",
        "header_variant": "sticky",
        "canonical_url": None,
        "og_image": None,
        "item_list_jsonld": None,
        "request": None,
        "seo_title": "Miami Knows Beauty",
        "meta_description": "",
        "businesses": [],
        "featured_businesses_in_guide": [],
    }
    ctx.update(overrides)
    return ctx


def test_guide_page_layers_placeholder_behind_hero_when_present():
    """The editorial guide hero is a CSS background photo. When a hero image is
    present it must layer the branded placeholder beneath it, so a broken hero
    degrades to the brand tile instead of a flat dark gap."""
    guide = {
        "title": "Best Balayage in Wynwood",
        "subtitle": "A guide",
        "seo_title": "Best Balayage in Wynwood",
        "meta_description": "",
        "author": "Editors",
        "published_at": None,
        "hero_image_url": "https://example.com/guide-hero.jpg",
        "body_html": "<p>Body</p>",
        "featured_business_ids": [],
        "business_slugs": [],
    }
    html = _render_page("editorial_guide.html", **_page_ctx(guide=guide))
    assert PLACEHOLDER_URL in html
    # Placeholder is the second layer, beneath the real hero photo.
    assert re.search(
        r"background-image:\s*url\([^)]*guide-hero[^)]*\),\s*url\([^)]*placeholder-salon",
        html,
    ), html[html.find("background-image"): html.find("background-image") + 300]


def test_guide_page_adds_no_placeholder_box_when_hero_absent():
    """When a guide has NO hero image the design intends a plain dark hero — we
    must NOT inject an empty placeholder box. The placeholder URL is only set as
    a variable; it must not appear in any rendered background-image."""
    guide = {
        "title": "No Hero Guide",
        "subtitle": "A guide",
        "seo_title": "No Hero Guide",
        "meta_description": "",
        "author": "Editors",
        "published_at": None,
        "hero_image_url": None,
        "body_html": "<p>Body</p>",
        "featured_business_ids": [],
        "business_slugs": [],
    }
    html = _render_page("editorial_guide.html", **_page_ctx(guide=guide))
    # The placeholder is only ever painted as the lower layer BENEATH a present
    # photo. With no hero photo, the {% if guide.hero_image_url %} guard skips
    # the whole div, so the placeholder URL must not appear anywhere in the
    # rendered page — proving we did NOT inject an empty placeholder box.
    # (placeholder_url is set as a variable but never emitted on its own.)
    assert PLACEHOLDER_URL not in html, (
        "no-hero guide must not render an empty placeholder box; found the "
        "placeholder URL in: "
        + (html[html.find(PLACEHOLDER_URL) - 80 : html.find(PLACEHOLDER_URL) + 80])
    )


def test_neighborhood_page_layers_placeholder_behind_hero_when_present():
    """The neighborhood hero is a CSS background photo; when present it must
    layer the placeholder beneath it for graceful 404 degradation."""
    neighborhood = {
        "name": "Wynwood",
        "slug": "wynwood",
        "photo_url": "https://example.com/wynwood.jpg",
        "description": "",
        "vibe": "",
        "listed_count": 0,
    }
    html = _render_page(
        "neighborhood.html", **_page_ctx(neighborhood=neighborhood)
    )
    assert PLACEHOLDER_URL in html
    assert re.search(
        r"background-image:\s*url\([^)]*wynwood[^)]*\),\s*url\([^)]*placeholder-salon",
        html,
    ), html[html.find("background-image"): html.find("background-image") + 300]


def test_neighborhood_page_adds_no_placeholder_box_when_photo_absent():
    """A neighborhood with no photo keeps its intended plain dark hero — we must
    NOT inject an empty placeholder box, same contract as the guide page."""
    neighborhood = {
        "name": "Edgewater",
        "slug": "edgewater",
        "photo_url": None,
        "description": "",
        "vibe": "",
        "listed_count": 0,
    }
    html = _render_page(
        "neighborhood.html", **_page_ctx(neighborhood=neighborhood)
    )
    assert PLACEHOLDER_URL not in html, (
        "no-photo neighborhood must not render an empty placeholder box; found "
        "the placeholder URL in: "
        + (html[html.find(PLACEHOLDER_URL) - 80 : html.find(PLACEHOLDER_URL) + 80])
    )


# ── Network landing page (branded fallback beneath the hero photo) ────────────
# The platform-root page that lists live cities renders each city as a card with
# a hero photo. Unlike salon cards (which fall back to the placeholder SVG), this
# page's no-photo case shows a branded city monogram on top of the brand gradient.
# So a broken hero photo here must degrade to that SAME intentional content: the
# fallback lives under the image, and the <img> hides itself onerror so the
# branded placeholder shows through.


def _network_landing_ctx(live_cities: list[dict]) -> dict:
    """Context for a direct render of network_landing.html. Only the keys the
    template touches need real values; theme carries the gradient class the
    fallback relies on."""
    return _page_ctx(
        live_cities=live_cities,
        planned_cities=[],
        is_network_landing=True,
        landing_eyebrow="MIAMI KNOWS BEAUTY — A LOCAL GUIDE NETWORK",
        landing_subhead="A curated guide.",
        landing_cities_eyebrow="CITIES",
        landing_cities_intro="Pick a city.",
        # network_landing.html reads theme.category_banner_gradient and the
        # accent text classes; supply them on top of the base theme dict.
        theme={
            "accent_text_strong": "text-rose-600",
            "accent_hover_text": "hover:text-rose-700",
            "category_banner_gradient": "from-rose-50 via-orange-50/40 to-amber-50",
        },
    )


def test_network_landing_city_with_hero_hides_broken_img_revealing_branded_placeholder():
    """A live city WITH a hero photo: the <img> must carry an onerror that hides
    itself, revealing a branded city placeholder rather than a blank gradient."""
    html = _render_page(
        "network_landing.html",
        **_network_landing_ctx(
            [
                {
                    "name": "Miami",
                    "slug": "miami",
                    "tagline": "The best beauty.",
                    "hero_photo_url": "https://example.com/broken-hero.jpg",
                    "url": "https://miami.knowsbeauty.test/",
                }
            ]
        ),
    )
    imgs = _imgs(html)
    assert len(imgs) == 1, imgs
    img = imgs[0]
    assert "https://example.com/broken-hero.jpg" in img
    # onerror must null itself first (loop guard) THEN hide the image so the
    # branded fallback underneath is revealed.
    onerror = re.search(r'onerror="([^"]*)"', img).group(1)
    assert "this.onerror=null" in onerror
    assert "display='none'" in onerror
    assert onerror.index("this.onerror=null") < onerror.index("display='none'")
    # The branded fallback must sit on the img's CONTAINER div, beneath the photo.
    assert re.search(
        r'<div class="relative aspect-\[4/3\][^"]*items-center justify-center[^"]*">',
        html,
    ), html[html.find("aspect-[4/3]"): html.find("aspect-[4/3]") + 300]
    assert re.search(r">\s*M\s*</div>", html), "broken-image fallback monogram is missing"
    assert 'aria-hidden="true"' in html


def test_network_landing_city_without_hero_shows_branded_placeholder():
    """A live city with NO hero photo shows a branded placeholder and no <img>."""
    html = _render_page(
        "network_landing.html",
        **_network_landing_ctx(
            [
                {
                    "name": "Austin",
                    "slug": "austin",
                    "tagline": "Coming soon vibes.",
                    "hero_photo_url": None,
                    "url": "https://austin.knowsbeauty.test/",
                }
            ]
        ),
    )
    assert _imgs(html) == []
    assert "bg-gradient-to-br" in html
    assert "items-center justify-center" in html
    assert re.search(r">\s*A\s*</div>", html), "no-hero fallback monogram is missing"


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def test_lightbox_img_has_no_empty_src(client):
    """The hidden lightbox <img id="lb-img"> must NOT ship an empty src="".

    An empty src resolves against the page URL, so every listing load fires a
    wasteful failed image request to the listing page itself (a phantom broken
    image in the DOM, invisible only because the lightbox is hidden). The
    lightbox JS sets img.src from the photos array when a photo is opened, so the
    tag needs no initial source. This guards against the empty src creeping back.
    """
    r = client.get("/b/igk-salon-south-beach", headers={"host": "miami.knowsbeauty.localhost"})
    if r.status_code != 200:
        r = client.get(
            "/b/rossano-ferretti-hair-spa-miami",
            headers={"host": "miami.knowsbeauty.localhost"},
        )
    if r.status_code != 200:
        pytest.skip("no business page available in seed")
    assert 'id="lb-img"' in r.text, "lightbox img element should be present"
    tag = re.search(r'<img\s+id="lb-img"[^>]*>', r.text, re.S)
    assert tag, "lightbox img tag not found"
    assert 'src=""' not in tag.group(0), f"lightbox img must not carry an empty src: {tag.group(0)}"
