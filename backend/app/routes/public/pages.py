"""Server-rendered public pages.

Every request resolves the (network, city) tenant from the Host header,
loads the relevant database records, and renders a Jinja2 template. The
template only receives plain data — no DB access from the template.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import markdown2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.services import content as content_svc
from app.services.copy import CopyResolver
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session
from app.services.tenant import TenantContext, resolve_tenant

router = APIRouter()

_templates: Optional[Jinja2Templates] = None


def attach_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t
    t.env.filters["markdown"] = lambda text: markdown2.markdown(
        text or "", extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists"]
    )
    t.env.filters["humantime"] = lambda when: (
        when.strftime("%b %-d, %Y") if isinstance(when, datetime) else str(when or "")
    )


async def _require_tenant(request: Request) -> TenantContext:
    host = request.headers.get("host", "")
    tenant = await resolve_tenant(host)
    if not tenant:
        raise HTTPException(404, f"Unknown host: {host}")
    return tenant


async def _build_copy(tenant: TenantContext) -> CopyResolver:
    network = tenant.network
    city = tenant.city
    return CopyResolver(
        network_id=network["_id"],
        city_id=city["_id"] if city else None,
        network_name=network.get("name", ""),
        city_name=city.get("name", "") if city else "",
    )


def _vertical_word(network: Dict[str, Any]) -> str:
    """Pull the trailing word from the network name ("Knows Beauty" -> "Beauty")."""
    name = network.get("name", "")
    if name.lower().startswith("knows "):
        return name.split(" ", 1)[1]
    return name


def _issue_label(now: datetime) -> str:
    months = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
              "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    return f"EDITION VOL. 1 — {months[now.month]} {now.year}"


# Per-network theme tokens. The reference design uses different accent colors
# per vertical (rose for Beauty, emerald for Wellness, sky-blue for Health).
# These are passed into every template as `theme` so the same templates can
# render network-specific accent colors without hand-tweaking the markup.
# Class strings must come from the reference's compiled Tailwind stylesheet
# (every utility class listed here is present in /assets/css/reference.css).
_NETWORK_THEMES: Dict[str, Dict[str, str]] = {
    "beauty": {
        "accent_text":              "text-rose-600",
        "accent_text_full":         "text-rose-600",
        "accent_text_strong":       "text-rose-700",
        "accent_text_light":        "text-rose-300",
        "accent_text_lighter":      "text-rose-200",
        "accent_text_lighter_full": "text-rose-200",
        "accent_border_subtle":     "border-rose-300/30",
        "accent_hover_text":        "hover:text-rose-600",
        "focus_ring":               "focus:ring-rose-400",
        "ring_accent":              "ring-rose-500",
        "button_bg":                "bg-rose-600",
        "button_bg_hover":          "hover:bg-rose-700",
        "category_banner_gradient": "from-rose-50 via-orange-50/40 to-amber-50",
        "owners_gradient":          "from-rose-100 via-orange-50 to-amber-50",
        "owners_blob_a":            "bg-rose-300",
        "owners_blob_b":            "bg-amber-300",
        "owners_eyebrow_color":     "text-rose-700",
        "highlight_border":         "border-rose-300",
    },
    "wellness": {
        "accent_text":              "text-emerald-600",
        "accent_text_full":         "text-emerald-600",
        "accent_text_strong":       "text-emerald-700",
        "accent_text_light":        "text-emerald-300",
        "accent_text_lighter":      "text-emerald-200",
        "accent_text_lighter_full": "text-emerald-200",
        "accent_border_subtle":     "border-emerald-300/30",
        "accent_hover_text":        "hover:text-emerald-600",
        "focus_ring":               "focus:ring-emerald-400",
        "ring_accent":              "ring-emerald-500",
        "button_bg":                "bg-emerald-600",
        "button_bg_hover":          "hover:bg-emerald-700",
        "category_banner_gradient": "from-emerald-50 via-teal-50/40 to-amber-50",
        "owners_gradient":          "from-emerald-100 via-teal-50 to-amber-50",
        "owners_blob_a":            "bg-emerald-300",
        "owners_blob_b":            "bg-teal-300",
        "owners_eyebrow_color":     "text-emerald-700",
        "highlight_border":         "border-emerald-300",
    },
    "health": {
        "accent_text":              "text-sky-700",
        "accent_text_full":         "text-sky-700",
        "accent_text_strong":       "text-sky-800",
        "accent_text_light":        "text-sky-300",
        "accent_text_lighter":      "text-sky-200",
        "accent_text_lighter_full": "text-sky-200",
        "accent_border_subtle":     "border-sky-300/30",
        "accent_hover_text":        "hover:text-sky-700",
        "focus_ring":               "focus:ring-sky-400",
        "ring_accent":              "ring-sky-500",
        "button_bg":                "bg-sky-700",
        "button_bg_hover":          "hover:bg-sky-800",
        "category_banner_gradient": "from-sky-50 via-blue-50/40 to-amber-50",
        "owners_gradient":          "from-sky-100 via-blue-50 to-amber-50",
        "owners_blob_a":            "bg-sky-300",
        "owners_blob_b":            "bg-amber-300",
        "owners_eyebrow_color":     "text-sky-800",
        "highlight_border":         "border-sky-300",
    },
}


def _network_theme(network: Dict[str, Any]) -> Dict[str, str]:
    return _NETWORK_THEMES.get(network.get("slug", ""), _NETWORK_THEMES["beauty"])


async def _base_context(request: Request, tenant: TenantContext) -> Dict[str, Any]:
    copy = await _build_copy(tenant)
    city = tenant.city
    network = tenant.network
    nav_categories: List[Dict[str, Any]] = []
    nav_neighborhoods: List[Dict[str, Any]] = []
    if city:
        nav_categories = await content_svc.list_categories(city["_id"])
        nav_neighborhoods = await content_svc.list_neighborhoods(city["_id"])

    now = datetime.now(timezone.utc)

    footer_owners_items_raw = await copy.get("footer.owners.items") or ""
    footer_owners_items = [s.strip() for s in footer_owners_items_raw.split("|") if s.strip()]

    # The header nav is a per-network short list of pinned links
    # (e.g. Beauty shows "Lashes" instead of "Lash & Brow"). The route stores
    # it on the city doc; fall back to the first 6 categories when not set.
    header_nav = (city or {}).get("header_nav") if city else None
    if not header_nav and nav_categories:
        header_nav = [
            {"slug": c["slug"], "label": c["name"]}
            for c in nav_categories[:6]
            if not c.get("parent_slug")
        ]

    # WHY: strip query params so search pages (?q=...) don't create duplicate
    # canonical URLs — the canonical always resolves to the bare page path.
    page_url = str(request.url).split("?")[0].rstrip("/")
    canonical_url: Optional[str] = page_url if page_url.startswith("http") else None

    return {
        "request": request,
        "tenant": tenant,
        "network": network,
        "city": city,
        "copy": copy,
        "theme": _network_theme(network),
        "vertical_word": _vertical_word(network),
        "canonical_url": canonical_url,
        # WHY: A short human label like "Miami Knows Beauty" used inside
        # the Founding Partner tooltip ("Founding member of <tenant_label>").
        # Falls back to the network name on the network-home page where
        # there's no city in context (e.g. the landing page before a city
        # has been picked).
        "tenant_label": (
            f"{city['name']} Knows {_vertical_word(network)}"
            if city else network.get("name", "this publication")
        ),
        # Word for one (or many) listings on this network. Beauty uses "Salons"/"salon",
        # Wellness "Studios"/"studio", Health "Clinics"/"clinic". Stored on the
        # city doc by the seed, with sensible fallbacks for older data.
        "listing_word_plural": (city or {}).get("listing_word_plural", "Listings"),
        "listing_word_singular": (city or {}).get("listing_word_singular", "listing"),
        "hero_issue_label": _issue_label(now),
        "nav_categories": nav_categories,
        "nav_neighborhoods": nav_neighborhoods,
        "header_nav": header_nav or [],
        "now": now,
        "footer_legal": await copy.get("footer.legal"),
        "footer_made_in": await copy.get("footer.made_in"),
        "footer_about_title": await copy.get("footer.about.title"),
        "footer_about_body": await copy.get("footer.about.body"),
        "footer_business_title": await copy.get("footer.business.title"),
        "footer_business_body": await copy.get("footer.business.body"),
        "footer_also_in": await copy.get("footer.also_in"),
        "footer_publication_label": await copy.get("footer.publication_label"),
        "footer_owners_label": await copy.get("footer.owners.label") or "OWNERS",
        "footer_owners_items": footer_owners_items,
        "page_featured_disclosure": await copy.get("page.featured_disclosure"),
        "owners_header_cta": await copy.get("header.owners_cta") or "For Owners",
        # WHY: GA4 is injected here (the shared base context) so every page
        # gets the tracking script without duplicating the env-var read in
        # each individual route handler.  An empty or absent var means the
        # {% if ga_measurement_id %} guard in base.html emits no script at
        # all — no dead snippet, no console noise on dev.
        "ga_measurement_id": os.environ.get("GA_MEASUREMENT_ID", ""),
    }


# Cities planned to launch next, per network. These render as dimmed
# "coming soon" tiles on the bare-apex landing page so visitors can see
# what's on the roadmap even before the city exists in the database.
#
# Order and timing come from the strategy note in Posey's space at
# notes/2026-05-20-known-around-town-verticals.md (Beauty is named as
# expanding into Austin / Philadelphia / Dallas / Scottsdale / LA / NY;
# Wellness and Health follow Beauty's footprint, slower for Health
# because the copy review is heavier).
_PLANNED_CITIES_BY_NETWORK: Dict[str, List[Dict[str, str]]] = {
    "beauty": [
        {"name": "Austin",       "eta": "Coming 2026"},
        {"name": "Philadelphia", "eta": "Coming 2026"},
        {"name": "Dallas",       "eta": "Coming 2027"},
        {"name": "Scottsdale",   "eta": "Coming 2027"},
        {"name": "Los Angeles",  "eta": "Coming 2027"},
        {"name": "New York",     "eta": "Coming 2027"},
    ],
    "wellness": [
        {"name": "Austin",       "eta": "Coming 2026"},
        {"name": "Los Angeles",  "eta": "Coming 2027"},
        {"name": "New York",     "eta": "Coming 2027"},
    ],
    "health": [
        {"name": "Austin",       "eta": "Coming 2027"},
        {"name": "New York",     "eta": "Coming 2027"},
    ],
}


async def _render_network_landing(request: Request, tenant: TenantContext) -> HTMLResponse:
    """Render the bare-apex landing page that lists the cities for a network.

    Reached when the request host is something like `knowsbeauty.ai.devintensive.com`
    with no city subdomain. Before this existed, the no-city branch served a
    near-empty stub with no city links — visitors had nowhere to click.
    """
    ctx = await _base_context(request, tenant)
    network = tenant.network
    host = request.headers.get("host", "")
    scheme = request.url.scheme or "https"
    suffix = tenant.network_domain_suffix or host

    live_cities_raw = await content_svc.list_cities(network["_id"])
    live_cities: List[Dict[str, Any]] = []
    for city in live_cities_raw:
        live_cities.append(
            {
                "name": city.get("name", ""),
                "slug": city.get("slug", ""),
                "tagline": city.get("tagline") or city.get("hero_description") or "",
                "hero_photo_url": city.get("hero_photo_url"),
                # WHY: the city is served at its own subdomain (e.g.
                # `miami.knowsbeauty.ai.devintensive.com/`), so we build an
                # absolute URL from the resolved network suffix rather than
                # a relative path the browser would route back to the apex.
                "url": f"{scheme}://{city.get('slug', '')}.{suffix}/",
            }
        )

    live_slugs = {c["slug"] for c in live_cities}
    live_names_lower = {c["name"].lower() for c in live_cities}
    planned = [
        p for p in _PLANNED_CITIES_BY_NETWORK.get(network.get("slug", ""), [])
        # WHY: don't show a city as "coming soon" if it has already been
        # seeded as a live edition (matches by display name or slug).
        if p["name"].lower() not in live_names_lower
        and p["name"].lower().replace(" ", "-") not in live_slugs
    ]

    vertical = _vertical_word(network)
    ctx.update(
        {
            "is_network_landing": True,
            "live_cities": live_cities,
            "planned_cities": planned,
            "landing_eyebrow": f"{network.get('name', '').upper()} — A LOCAL GUIDE NETWORK",
            "landing_subhead": (
                network.get("description")
                or f"A curated guide to the best {vertical.lower()} in every city we cover."
            ),
            "landing_cities_eyebrow": "CITIES",
            "landing_cities_intro": (
                f"We're starting in Miami and expanding. Pick a city to open its "
                f"{vertical.lower()} guide."
            ),
            "seo_title": network.get("name", ""),
            "meta_description": network.get("description"),
        }
    )
    return _templates.TemplateResponse("network_landing.html", ctx)


def _build_hero_headline_html(text: str) -> str:
    """The hero headline italicizes the last 2-3 words and accents one of them
    (matching the editorial treatment in the reference design)."""
    import html
    text = (text or "").strip()
    parts = text.rsplit(" ", 3)
    if len(parts) <= 1:
        return f'<em class="accent">{html.escape(text)}</em>'
    head = " ".join(parts[:-3]) if len(parts) > 3 else parts[0]
    tail = " ".join(parts[-3:]) if len(parts) > 3 else " ".join(parts[1:])
    if head:
        return f"{html.escape(head)} <em>{html.escape(tail)}</em>"
    return f'<em>{html.escape(tail)}</em>'


def _resolve_by_slug(records: List[Dict[str, Any]], slugs: List[str]) -> List[Dict[str, Any]]:
    """Return records in the order of the slug list."""
    by_slug = {r.get("slug"): r for r in records}
    return [by_slug[s] for s in (slugs or []) if s in by_slug]


def _build_item_list_jsonld(
    businesses: List[Dict[str, Any]],
    list_name: str,
    list_url: str,
    base_url: str,
) -> Optional[Dict[str, Any]]:
    """Build an ItemList JSON-LD dict for a page that lists businesses.

    WHY: extracted as a helper so the three route handlers (category, neighborhood,
    neighborhood+category) share identical logic rather than duplicating the list
    comprehension. Also centralises the slug/name guard — a business without a slug
    would produce '@id: .../b/' which resolves to the home page and would be
    misinterpreted by Google as associating the business name with the home URL.
    Returns None when there are no valid businesses so the template guard
    ({% if item_list_jsonld %}) suppresses the script block entirely.
    """
    # WHY: filter out businesses missing a slug or name — they would produce
    # malformed @id URLs (".../b/") or empty name strings, both of which
    # cause Google's structured-data parser to flag the block as invalid.
    valid = [b for b in businesses if b.get("slug") and b.get("name")]
    if not valid:
        return None
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": list_name,
        "url": list_url,
        "numberOfItems": len(valid),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "item": {
                    "@type": "LocalBusiness",
                    "@id": f"{base_url}/b/{b['slug']}",
                    "name": b["name"],
                    "url": f"{base_url}/b/{b['slug']}",
                },
            }
            for i, b in enumerate(valid)
        ],
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)

    if not tenant.city:
        if tenant.city_slug:
            raise HTTPException(404, "City not found")
        return await _render_network_landing(request, tenant)

    city = tenant.city
    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )

    ctx = await _base_context(request, tenant)

    # The hero headline carries inline italics — the seed stores the markup
    # directly (e.g. "Miami's <em>best-kept</em> beauty addresses.") so the
    # template can render it without guessing which words to italicize.
    headline_html_from_copy = await copy.get("home.hero.headline_html")
    if headline_html_from_copy:
        headline_html = headline_html_from_copy
    else:
        headline_text = content_svc.active_editorial_headline(city) or city.get("tagline") \
            or await copy.get("home.hero.headline") or ""
        headline_html = _build_hero_headline_html(headline_text)

    all_live = await content_svc.list_businesses(city["_id"], limit=200)

    # Editor's Picks + trending list — both pulled from the city doc when
    # configured, falling back to derived order when not.
    editor_picks = [b for b in all_live if b.get("editors_pick")][:8]

    trending_slugs = city.get("trending_business_slugs") or []
    trending = _resolve_by_slug(all_live, trending_slugs)[:8]
    if not trending:
        trending = [b for b in all_live if not b.get("editors_pick")][:8]

    # Spotlight neighborhood — pulled from the city config.
    spotlight_slug = city.get("spotlight_neighborhood_slug")
    spotlight_nb = None
    spotlight_businesses: List[Dict[str, Any]] = []
    if spotlight_slug:
        spotlight_nb = await content_svc.get_neighborhood(city["_id"], spotlight_slug)
        biz_slugs = city.get("spotlight_business_slugs") or []
        spotlight_businesses = _resolve_by_slug(all_live, biz_slugs)
        if not spotlight_businesses:
            spotlight_businesses = [
                b for b in all_live if spotlight_slug in (b.get("neighborhood_slugs") or [])
            ][:3]

    # Two-column neighborhood mini-lists (city-configured only — wellness and
    # health intentionally don't show this section on the reference).
    columns: List[Dict[str, Any]] = []
    for col in city.get("two_column_neighborhoods") or []:
        nb = await content_svc.get_neighborhood(city["_id"], col["slug"])
        if not nb:
            continue
        nb_biz = _resolve_by_slug(all_live, col.get("business_slugs") or [])
        columns.append({"name": nb["name"], "slug": col["slug"], "businesses": nb_biz})

    search_chips = city.get("search_chips") or []

    # Owner CTA mini-card sample
    owner_card_slug = city.get("owners_card_business_slug")
    owners_card: Optional[Dict[str, Any]] = None
    if owner_card_slug:
        owners_card = next(
            (b for b in all_live if b.get("slug") == owner_card_slug), None
        )
    if not owners_card:
        owners_card_list = (
            [b for b in all_live if (b.get("featured") or {}).get("enabled")] or all_live
        )
        owners_card = owners_card_list[0] if owners_card_list else None

    hero_featured = editor_picks[0] if editor_picks else (all_live[0] if all_live else None)

    category_names = {c["slug"]: c["name"] for c in ctx["nav_categories"]}
    neighborhood_names = {n["slug"]: n["name"] for n in ctx["nav_neighborhoods"]}

    ctx.update(
        {
            # Hero
            "hero_eyebrow": await copy.get("home.hero.eyebrow"),
            "hero_headline_html": headline_html,
            "hero_subhead": city.get("hero_description") or await copy.get("home.hero.subhead"),
            "hero_search_placeholder": (
                await copy.get("home.hero.search_placeholder") or ""
            ),
            "hero_featured": hero_featured,
            "hero_photo_url": city.get("hero_photo_url"),
            "search_chips": search_chips,
            "is_home": True,
            # Stats
            "stat_count_listings": (
                await copy.get("home.stat.listings.count") or str(len(all_live))
            ),
            "stat_label_listings": (
                await copy.get("home.stat.listings.label") or "LISTINGS"
            ),
            "stat_count_neighborhoods": (
                await copy.get("home.stat.neighborhoods.count")
                or str(len(ctx["nav_neighborhoods"]))
            ),
            "stat_count_editor_picks": (
                await copy.get("home.stat.editor_picks.count") or str(len(editor_picks))
            ),
            "stat_label_owners": (
                await copy.get("home.stat.owners.label") or "FOR OWNERS"
            ),
            # Map / browse
            "browse_axis_label": await copy.get("home.browse.axis_label") or "BY CATEGORY",
            "map_culture_word": await copy.get("home.map.culture_word") or _vertical_word(tenant.network).lower(),
            # Editor's Picks + trending
            "editor_picks": editor_picks,
            "trending_businesses": trending,
            # Spotlight
            "spotlight_neighborhood": spotlight_nb,
            "spotlight_businesses": spotlight_businesses,
            "spotlight_eyebrow": await copy.get("home.spotlight.eyebrow") or "NEIGHBORHOOD SPOTLIGHT",
            "spotlight_lead_a": await copy.get("home.spotlight.lead_a") or "",
            "spotlight_lead_b": await copy.get("home.spotlight.lead_b") or "",
            "spotlight_description": await copy.get("home.spotlight.description"),
            # Two-column mini-lists
            "neighborhood_columns": columns,
            "category_names": category_names,
            "neighborhood_names": neighborhood_names,
            # Owner CTA
            "owners_eyebrow": await copy.get("home.owners.eyebrow") or "FOR OWNERS",
            "owners_headline": (
                await copy.get("home.owners.headline") or "Own a business in this city?"
            ),
            "owners_italic": (
                await copy.get("home.owners.italic") or "Your listing's already here."
            ),
            "owners_body": await copy.get("home.owners.body") or "",
            "owners_cta": await copy.get("home.owners.cta") or "Claim your listing · Free",
            "owners_card": owners_card,
            "owners_card_action": await copy.get("home.owners.card_action") or "",
            "owners_card_views":    await copy.get("home.owners.card_stats.views")    or "—",
            "owners_card_calls":    await copy.get("home.owners.card_stats.calls")    or "—",
            "owners_card_bookings": await copy.get("home.owners.card_stats.bookings") or "—",
            "owners_card_bookings_label": (
                await copy.get("home.owners.card_stats.bookings_label") or "New bookings"
            ),
            # SEO
            "seo_title": city.get("seo_title") or f"{tenant.network.get('name')} {city.get('name')}",
            "meta_description": city.get("meta_description") or city.get("hero_description"),
            # WHY: Organization JSON-LD tells Google this is a named entity (a real
            # organization, not just a web page) and is how Google Knowledge Panels
            # are populated. Adding it alongside the existing WebSite block gives
            # Google two complementary signals: what the site IS and who OWNS it.
            "org_jsonld": {
                "@context": "https://schema.org",
                "@type": "Organization",
                "@id": f"{ctx.get('canonical_url')}/#organization",
                "name": city.get("seo_title") or f"{city.get('name', '')} {tenant.network.get('name', '')}",
                "url": ctx.get("canonical_url"),
                **({
                    "logo": {
                        "@type": "ImageObject",
                        "url": city.get("hero_photo_url"),
                    }
                } if city.get("hero_photo_url") else {}),
                **({
                    "description": city.get("meta_description") or city.get("hero_description")
                } if (city.get("meta_description") or city.get("hero_description")) else {}),
            } if ctx.get("canonical_url") else None,
        }
    )
    return _templates.TemplateResponse("home.html", ctx)


# WHY: /c/hair-salon is a common mis-hit — dozens of requests per hour arrive
# at this path from a monitoring tool or stale bookmark. The correct slug is
# /c/hair. A permanent (301) redirect fixes the 404 for these callers and
# preserves any SEO equity accumulated on the incorrect URL.
@router.get("/c/hair-salon")
async def redirect_hair_salon() -> RedirectResponse:
    return RedirectResponse(url="/c/hair", status_code=301)


# WHY: /c/nail-salon is the intuitive plural form people type or link; the
# actual category slug is /c/nails. 301 so search engines update their index.
@router.get("/c/nail-salon")
async def redirect_nail_salon() -> RedirectResponse:
    return RedirectResponse(url="/c/nails", status_code=301)


# WHY: /c/nail-salons (with trailing s) is another common variant.
@router.get("/c/nail-salons")
async def redirect_nail_salons() -> RedirectResponse:
    return RedirectResponse(url="/c/nails", status_code=301)


@router.get("/c/{category_slug}", response_class=HTMLResponse)
async def category_page(request: Request, category_slug: str) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    category = await content_svc.get_category(city["_id"], category_slug)
    if not category:
        raise HTTPException(404, "Category not found")

    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )

    ctx = await _base_context(request, tenant)
    businesses = await content_svc.list_businesses(
        city["_id"], category_slug=category_slug, limit=120
    )
    ctx.update(
        {
            "category": category,
            "active_category_slug": category_slug,
            "hero_eyebrow": await copy.get(
                "category.hero.eyebrow",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "hero_headline": category.get("editorial_blurb")
            or category.get("description")
            or category.get("name"),
            "hero_subhead": await copy.get(
                "category.hero.subhead",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "businesses": businesses,
            "empty_title": await copy.get(
                "category.empty.title",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "empty_body": await copy.get(
                "category.empty.body",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "sub_categories": await content_svc.list_categories(
                city["_id"], parent_slug=category_slug
            ),
            "seo_title": category.get("seo_title")
            or f"{category.get('name', '')} in {city.get('name', '')} — {city.get('name', '')} {tenant.network.get('name', '')}",
            # WHY: meta_description is rarely set in the DB; fall back to a
            # constructed sentence so Google has compelling snippet copy to
            # show in search results rather than a random page excerpt.
            # WHY: full brand name is "{city} {network}" (e.g. "Miami Knows Beauty"),
            # not just the network word alone — keeps brand consistent across all pages.
            "meta_description": category.get("meta_description") or (
                f"The best {category.get('name', '').lower()} in {city.get('name', '')} — "
                f"{category.get('description', '')}. Browse {city.get('name', '')} {tenant.network.get('name', '')}."
                if category.get("description")
                else f"The best {category.get('name', '').lower()} in {city.get('name', '')} — browse {city.get('name', '')} {tenant.network.get('name', '')}."
            ),
            # WHY: og:image controls the preview card when someone shares this
            # category page on social media. Prefer a real business photo from
            # the page (shows an actual Miami salon) and fall back to the city
            # hero so the card is never blank — a blank preview kills click-through.
            "og_image": next(
                (b["photos"][0]["url"] for b in businesses if b.get("photos")),
                city.get("hero_photo_url"),
            ),
            # WHY: ItemList JSON-LD gives Google a machine-readable enumeration
            # of the businesses on this page. Without it Google can only infer
            # the list from crawled HTML. With it, Google can surface individual
            # business names as rich results for category-level queries like
            # "hair salons Miami", increasing click-through before users even
            # reach the page.
            "item_list_jsonld": _build_item_list_jsonld(
                businesses,
                list_name=f"{category.get('name', '')} in {city.get('name', '')}",
                list_url=str(request.url).split("?")[0],
                base_url=str(request.base_url).rstrip("/"),
            ),
        }
    )
    return _templates.TemplateResponse("category.html", ctx)


@router.get("/n/{neighborhood_slug}", response_class=HTMLResponse)
async def neighborhood_page(request: Request, neighborhood_slug: str) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    nb = await content_svc.get_neighborhood(city["_id"], neighborhood_slug)
    if not nb:
        raise HTTPException(404, "Neighborhood not found")

    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )

    ctx = await _base_context(request, tenant)
    businesses = await content_svc.list_businesses(
        city["_id"], neighborhood_slug=neighborhood_slug, limit=120
    )
    ctx.update(
        {
            "neighborhood": nb,
            "hero_eyebrow": await copy.get(
                "neighborhood.hero.eyebrow",
                neighborhood_slug=neighborhood_slug,
                neighborhood_name=nb.get("name"),
            ),
            "hero_headline": nb.get("hero_description") or nb.get("description") or nb.get("name"),
            "hero_subhead": await copy.get(
                "neighborhood.hero.subhead",
                neighborhood_slug=neighborhood_slug,
                neighborhood_name=nb.get("name"),
            ),
            "businesses": businesses,
            "seo_title": nb.get("seo_title")
            or f"{nb.get('name', '')} — {city.get('name', '')} {tenant.network.get('name', '')}",
            # WHY: fall back to hero_description (the editorial paragraph added
            # in PR #51) so neighborhood pages always have meaningful Google
            # snippet copy — avoids a random page excerpt appearing in results.
            "meta_description": nb.get("meta_description") or nb.get("hero_description"),
            # WHY: same pattern as category pages — first business photo or
            # city hero fallback so social share cards always show an image.
            "og_image": next(
                (b["photos"][0]["url"] for b in businesses if b.get("photos")),
                city.get("hero_photo_url"),
            ),
            # WHY: ItemList JSON-LD enumerates the businesses in this neighborhood
            # so Google can surface them as rich results for neighborhood-level
            # queries like "salons in Wynwood Miami".
            "item_list_jsonld": _build_item_list_jsonld(
                businesses,
                list_name=f"{tenant.network.get('name', '')} in {nb.get('name', '')}, {city.get('name', '')}",
                list_url=str(request.url).split("?")[0],
                base_url=str(request.base_url).rstrip("/"),
            ),
        }
    )
    return _templates.TemplateResponse("neighborhood.html", ctx)


@router.get("/n/{neighborhood_slug}/c/{category_slug}", response_class=HTMLResponse)
async def neighborhood_category_page(
    request: Request, neighborhood_slug: str, category_slug: str
) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    nb = await content_svc.get_neighborhood(city["_id"], neighborhood_slug)
    category = await content_svc.get_category(city["_id"], category_slug)
    if not nb or not category:
        raise HTTPException(404, "Not found")

    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )

    ctx = await _base_context(request, tenant)
    businesses = [
        b
        for b in await content_svc.list_businesses(
            city["_id"], category_slug=category_slug, limit=200
        )
        if neighborhood_slug in (b.get("neighborhood_slugs") or [])
    ]
    ctx.update(
        {
            "neighborhood": nb,
            "category": category,
            "hero_eyebrow": f"{category.get('name')} in {nb.get('name')}",
            "hero_headline": f"{category.get('name')} in {nb.get('name')}, {city.get('name')}",
            "hero_subhead": category.get("editorial_blurb") or "",
            "businesses": businesses,
            "empty_title": await copy.get(
                "category.empty.title",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "empty_body": await copy.get(
                "category.empty.body",
                category_slug=category_slug,
                category_name=category.get("name"),
            ),
            "seo_title": f"{category.get('name', '')} in {nb.get('name', '')} — {city.get('name', '')} {tenant.network.get('name', '')}",
            # WHY: without meta_description Google picks a random excerpt from the page.
            # A constructed sentence ("The best hair salons in Wynwood, Miami") gives
            # Google compelling snippet copy and helps the page stand out in search results.
            "meta_description": (
                f"The best {category.get('name', '').lower()} in {nb.get('name', '')}, {city.get('name', '')} — "
                f"browse {city.get('name', '')} {tenant.network.get('name', '')}."
            ),
            # WHY: same pattern as category and neighborhood pages.
            "og_image": next(
                (b["photos"][0]["url"] for b in businesses if b.get("photos")),
                city.get("hero_photo_url"),
            ),
            # WHY: most specific ItemList — businesses in both this neighborhood
            # AND this category (e.g. "Hair salons in Wynwood, Miami"). High-intent
            # queries like "hair salon wynwood" are exactly what a tourist or local
            # types; this helps Google surface individual salon names in results.
            "item_list_jsonld": _build_item_list_jsonld(
                businesses,
                list_name=f"{category.get('name', '')} in {nb.get('name', '')}, {city.get('name', '')}",
                list_url=str(request.url).split("?")[0],
                base_url=str(request.base_url).rstrip("/"),
            ),
        }
    )
    return _templates.TemplateResponse("category.html", ctx)


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: Optional[str] = None) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city

    query = (q or "").strip()
    businesses: List[Dict[str, Any]] = []
    if query:
        businesses = await content_svc.search_businesses(city["_id"], query)

    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "query": query,
            "businesses": businesses,
            "result_count": len(businesses),
            "seo_title": f"Search{': ' + query if query else ''} — {tenant.network.get('name')}",
            "meta_description": (
                f"{len(businesses)} result{'s' if len(businesses) != 1 else ''} for '{query}' "
                f"in {city.get('name')} — {tenant.network.get('name')}."
                if query
                else f"Search {tenant.network.get('name')} — find salons, spas, and beauty businesses in {city.get('name')}."
            ),
            # WHY: og:image controls the preview card when someone copies and shares a
            # search-results URL. Prefer a business photo from the results (shows a real
            # Miami salon matching the query) and fall back to the city hero so the card
            # is never blank — a blank preview kills click-through on social.
            "og_image": next(
                (b["photos"][0]["url"] for b in businesses if b.get("photos")),
                city.get("hero_photo_url"),
            ),
        }
    )
    return _templates.TemplateResponse("search.html", ctx)


@router.get("/b/{business_slug}", response_class=HTMLResponse)
async def business_page(request: Request, business_slug: str) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    business = await content_svc.get_business(city["_id"], business_slug)
    if not business:
        raise HTTPException(404, "Business not found")

    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )

    nearby: List[Dict[str, Any]] = []
    if business.get("nearby_business_ids"):
        nearby_cur = content_svc.get_db().businesses.find(
            {"_id": {"$in": business["nearby_business_ids"]}}
        )
        nearby = await nearby_cur.to_list(length=12)
    else:
        # WHY: When no editorial nearby list is set, auto-suggest businesses
        # from the same category in the same city so the "You might also love"
        # section is always populated. Visitors browsing hair salons should
        # see more hair salons, not nothing.
        primary_cat = (business.get("category_slugs") or [None])[0]
        auto_q: Dict[str, Any] = {
            "_id": {"$ne": business["_id"]},
            "city_id": city["_id"],
            "status": "live",
        }
        if primary_cat:
            auto_q["category_slugs"] = primary_cat
        nearby_cur = content_svc.get_db().businesses.find(auto_q).limit(3)
        nearby = await nearby_cur.to_list(length=3)

    # WHY: Build a real Google Maps URL from the address so the template has
    # a proper href for the "Get directions" link. The CopyResolver only
    # supplies human-readable labels (e.g. "Get directions") — not URLs.
    addr = business.get("address") or {}
    _map_query = addr.get("street") or business.get("name", "")
    directions_url = (
        f"https://maps.google.com/?q={quote_plus(_map_query)}"
        if _map_query
        else ""
    )

    # WHY: og_image is computed here rather than in the template so base.html
    # can emit both og:image AND twitter:image from a single source. Previously
    # the template set og:image directly but never set twitter:image, leaving
    # Twitter/X cards with no photo when a salon page was shared.
    _biz_photos = business.get("photos") or []
    _hero = next((p for p in _biz_photos if isinstance(p, dict) and p.get("is_hero")), None)
    if not _hero and _biz_photos:
        _hero = _biz_photos[0]
    _hero_url = (_hero["url"] if isinstance(_hero, dict) else _hero) if _hero else None

    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "business": business,
            "nearby_businesses": nearby,
            "directions_url": directions_url,
            # WHY: prefer the salon's own photo over the city hero — it's more accurate
            # for sharing. Fall back to city hero so cards are never blank.
            "og_image": _hero_url or city.get("hero_photo_url"),
            "cta_book": await copy.get("business.cta.book", business_id=business["_id"]),
            "cta_call": await copy.get("business.cta.call", business_id=business["_id"]),
            "cta_website": await copy.get("business.cta.website", business_id=business["_id"]),
            "cta_directions": await copy.get("business.cta.directions", business_id=business["_id"]),
            "claim_title": await copy.get("business.claim.title", business_id=business["_id"]),
            "claim_body": await copy.get("business.claim.body", business_id=business["_id"]),
            "claim_cta": await copy.get("business.claim.cta", business_id=business["_id"]),
            "section_known_for": await copy.get("business.section.known_for"),
            "section_best_for": await copy.get("business.section.best_for"),
            "section_before_booking": await copy.get("business.section.before_booking"),
            "section_services": await copy.get("business.section.services"),
            "section_hours": await copy.get("business.section.hours"),
            "section_contact": await copy.get("business.section.contact"),
            "section_nearby": await copy.get("business.section.nearby"),
            "badge_editors_pick": await copy.get("badge.editors_pick"),
            "badge_verified": await copy.get("badge.verified"),
            "badge_claimed": await copy.get("badge.claimed"),
            "badge_featured": await copy.get("badge.featured"),
            "seo_title": business.get("meta_title_override")
            or f"{business.get('name')} — {city.get('name')} {tenant.network.get('name')}",
            "meta_description": business.get("meta_description_override")
            or business.get("short_description"),
        }
    )
    return _templates.TemplateResponse("business.html", ctx)


@router.get("/guides/{slug}", response_class=HTMLResponse)
async def editorial_guide_page(request: Request, slug: str) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    guide = await content_svc.get_editorial_guide(city["_id"], slug)
    if not guide:
        raise HTTPException(404, "Editorial guide not found")

    featured: List[Dict[str, Any]] = []
    if guide.get("featured_business_ids"):
        cur = content_svc.get_db().businesses.find(
            {"_id": {"$in": guide["featured_business_ids"]}}
        )
        featured = await cur.to_list(length=20)

    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "guide": guide,
            "featured_businesses_in_guide": featured,
            "seo_title": guide.get("seo_title") or guide.get("title"),
            "meta_description": guide.get("meta_description") or guide.get("subtitle"),
        }
    )
    return _templates.TemplateResponse("editorial_guide.html", ctx)


@router.get("/expertly-voice.html", response_class=HTMLResponse)
async def expertly_voice_page(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    ctx["seo_title"] = "Expertly Voice for Salons"
    ctx["meta_description"] = (
        "Never miss a booking. Expertly Voice answers your salon's phone "
        "when you're with a client or closed — and books appointments "
        "straight into your calendar."
    )
    return _templates.TemplateResponse("expertly_voice.html", ctx)


@router.get("/owners", response_class=HTMLResponse)
async def owners_page(
    request: Request,
    slug: Optional[str] = None,
) -> HTMLResponse:
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    city_name = tenant.city.get("name", "") if tenant.city else ""
    vertical = _vertical_word(tenant.network)
    ctx["seo_title"] = f"For Business Owners — {city_name} Knows {vertical}".strip(" —")
    ctx["meta_description"] = (
        f"Run a business in {city_name}? Your listing's already in {city_name} Knows "
        f"{vertical}. Claim it, upgrade it, and get found by people searching tonight."
    )

    # WHY: The claim form needs a real business_id to submit against the
    # existing POST /api/v1/claims endpoint (it rejects unknown business ids
    # with 404). We give the page two paths to resolve that id:
    #   1. A direct prefill when the visitor arrived via `?slug=<biz-slug>`
    #      (e.g. from a "Claim this listing" link on a business detail page).
    #   2. A lightweight client-side directory of {id, name, slug} for every
    #      live business in the city, so a free-text business-name typer can
    #      be matched against an existing record without a new endpoint.
    prefill: Optional[Dict[str, Any]] = None
    directory: List[Dict[str, Any]] = []
    if tenant.city:
        city_id = tenant.city["_id"]
        if slug:
            biz = await content_svc.get_business(city_id, slug)
            if biz:
                prefill = {
                    "id": biz["_id"],
                    "name": biz.get("name", ""),
                    "slug": biz.get("slug", ""),
                }
        # WHY: 500 keeps the embedded JSON small. Miami has well under 100
        # live businesses today; 500 leaves comfortable headroom before
        # we'd want a real server-side search endpoint instead.
        live = await content_svc.list_businesses(city_id, limit=500)
        directory = [
            {"id": b["_id"], "name": b.get("name", ""), "slug": b.get("slug", "")}
            for b in live
            if b.get("name")
        ]

    ctx["claim_prefill"] = prefill
    ctx["claim_directory"] = directory
    # WHY: og:image controls the preview card when this page is shared (e.g. David
    # pastes the link in a conversation with a prospective partner). The city hero
    # is the right image for an owner-acquisition landing page — it sets the Miami
    # beauty scene rather than spotlighting one business.
    ctx["og_image"] = tenant.city.get("hero_photo_url") if tenant.city else None
    return _templates.TemplateResponse("owners.html", ctx)


# Preferred sample salons for the preview dashboard. The first one that
# exists in the current city's seed is used. Rossano Ferretti is the first
# choice because it's an Editor's Pick on the reference site and reads as
# plausibly high-tier in the mockup; the others are real Miami salons
# included as fallbacks in case the priority slug ever leaves the seed.
_OWNER_DASHBOARD_SAMPLE_SLUGS: List[str] = [
    "rossano-ferretti-hair-spa-miami",
    "warren-tricomi-salon-miami-beach",
    "elia-spa-ritz-carlton-south-beach",
]


@router.get("/owner/dashboard", response_class=HTMLResponse)
async def owner_dashboard_preview(request: Request) -> HTMLResponse:
    """Static, unauthenticated preview of the owner dashboard.

    This is a UX mockup — the real claim-and-pay flow is being built on a
    separate workstream. We render a real seeded business as if its owner
    had just signed up for Featured, with every interactive control wired
    to a "Coming soon" toast instead of a backend action. A clearly visible
    preview banner at the top makes it obvious to any reviewer that the
    page is not live functionality.
    """
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city

    business: Optional[Dict[str, Any]] = None
    for slug in _OWNER_DASHBOARD_SAMPLE_SLUGS:
        business = await content_svc.get_business(city["_id"], slug)
        if business:
            break
    # Final fallback: any live business in this city. The preview is
    # supposed to be visually intact even if the slug list above gets stale
    # or the city's seed changes — we'd rather show *some* salon than 404.
    if not business:
        live = await content_svc.list_businesses(city["_id"], limit=1)
        business = live[0] if live else None
    if not business:
        raise HTTPException(404, "No businesses available for preview")

    primary_nb_slug = (business.get("neighborhood_slugs") or [None])[0]
    neighborhood = None
    if primary_nb_slug:
        neighborhood = await content_svc.get_neighborhood(
            city["_id"], primary_nb_slug
        )

    photos = business.get("photos") or []
    hero_photo = next((p for p in photos if p.get("is_hero")), None) or (
        photos[0] if photos else None
    )

    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "business": business,
            "neighborhood": neighborhood,
            "hero_photo": hero_photo,
            # Fake-but-plausible numbers so reviewers see realistic shapes.
            # Stat values are illustrative only and are not derived from
            # the seed or any live traffic data.
            "stat_views_this_week": 127,
            "stat_views_this_month": 482,
            "stat_claims_since_launch": 38,
            # Trial billing date — chosen as ~23 days out from "now" so
            # the date is always in the future relative to the page
            # render, and roughly matches the 30-day-free-trial promise
            # on the /owners page.
            "next_billing_date": (
                datetime.now(timezone.utc) + timedelta(days=23)
            ).strftime("%B %-d, %Y"),
            "seo_title": "Owner Dashboard Preview",
            "meta_description": (
                "Preview of the owner dashboard for the Featured tier — "
                "this is a mockup, not the live claim-and-pay flow."
            ),
        }
    )
    return _templates.TemplateResponse("owner_dashboard.html", ctx)

@router.get("/owners/preview/caption", response_class=HTMLResponse)
async def owners_caption_preview(request: Request) -> HTMLResponse:
    """Standalone preview of the Featured-tier Instagram caption generator.

    Why this route exists separately from the full owner dashboard:

    * The dashboard is being built in a parallel workstream and isn't
      live on stage yet. Reviewers (David, Posey) need to play with the
      caption panel right now to react to wording, length, and the
      copy/regenerate UX before the dashboard ships.
    * The panel is fully self-contained — it picks a business from the
      seed data and renders the panel pointed at that business. When
      the dashboard merges, the same JavaScript and the same backend
      endpoint power it; only the page wrapper changes.

    The route returns 404 when the marketing-AI feature flag is off so
    that production (which keeps the flag off) does not expose this
    surface even by URL guessing.
    """
    from app.services import ai_caption  # local import to avoid module cycles at startup

    if not ai_caption.feature_enabled():
        raise HTTPException(404, "Not found")

    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    city = tenant.city
    if not city:
        raise HTTPException(404, "Caption preview requires a known city")

    # Pick a Featured business if any exist, else the first business in the city.
    # Either way we get a real, recognizable business name in the preview so
    # the generated captions don't sound made-up.
    db = get_db()
    business_doc = await db.businesses.find_one(
        {"city_id": city["_id"], "featured.enabled": True}
    )
    if not business_doc:
        business_doc = await db.businesses.find_one({"city_id": city["_id"]})
    if not business_doc:
        raise HTTPException(404, "No businesses found for caption preview")

    # Resolve display-friendly neighborhood label
    neighborhood_name: Optional[str] = None
    neighborhood_slugs = business_doc.get("neighborhood_slugs") or []
    if neighborhood_slugs:
        nb = await db.neighborhoods.find_one(
            {"city_id": city["_id"], "slug": neighborhood_slugs[0]}
        )
        if nb:
            neighborhood_name = nb.get("name")

    category_slug = (business_doc.get("category_slugs") or [None])[0]
    category_name: Optional[str] = None
    if category_slug:
        cat = await db.categories.find_one(
            {"city_id": city["_id"], "slug": category_slug}
        )
        if cat:
            category_name = cat.get("name")

    ctx.update(
        {
            "seo_title": f"Caption generator preview — {business_doc.get('name')}",
            "meta_description": (
                "Featured-tier Instagram caption generator preview "
                f"for {business_doc.get('name')}."
            ),
            "preview_business": {
                "id": business_doc.get("_id"),
                "name": business_doc.get("name"),
                "slug": business_doc.get("slug"),
                "category_name": category_name,
                "neighborhood_name": neighborhood_name,
            },
        }
    )
    return _templates.TemplateResponse("owners_caption_preview.html", ctx)


@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    city_name = tenant.city.get("name", "") if tenant.city else ""
    vertical = _vertical_word(tenant.network)
    ctx["seo_title"] = f"Pricing — {city_name} Knows {vertical}".strip(" —")
    ctx["meta_description"] = (
        f"Three ways to show up on {city_name} Knows {vertical}. "
        f"Free listing, $29/month Featured, or $299/month Concierge with an AI phone "
        f"receptionist. First month free on Featured, cancel anytime."
    ).strip()
    # WHY: og:image controls the preview card when this page is shared with a potential
    # customer or partner. The city hero is the right image for a pricing page — it
    # represents the Miami beauty market we're selling into.
    ctx["og_image"] = tenant.city.get("hero_photo_url") if tenant.city else None
    return _templates.TemplateResponse("pricing.html", ctx)


@router.get("/owners/login", response_class=HTMLResponse)
async def owners_login_page(request: Request) -> HTMLResponse:
    """The two-step sign-in form for salon owners.

    Step 1 collects the email; step 2 collects the code. Both steps live
    on the same page — the JS in the template swaps which one is
    visible without a full reload.
    """
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    ctx["seo_title"] = "Sign in for owners"
    ctx["meta_description"] = (
        "Sign in to manage your Knows Beauty listing. Enter your email and we'll "
        "send you a one-time code."
    )
    # If the visitor is already signed in, send them to the placeholder
    # dashboard rather than asking for an email they don't need.
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie and verify_session(cookie):
        return RedirectResponse(url="/owners/me", status_code=303)
    return _templates.TemplateResponse("owner_login.html", ctx)


@router.get("/owners/me", response_class=HTMLResponse)
async def owners_me_page(request: Request) -> HTMLResponse:
    """Placeholder 'you're signed in' page.

    This is the dashboard stub: it confirms the cookie works end-to-end
    and gives the owner a logout button. The actual dashboard will
    replace this template in a follow-up change.
    """
    tenant = await _require_tenant(request)
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    session = verify_session(cookie) if cookie else None
    if not session:
        return RedirectResponse(url="/owners/login", status_code=303)

    ctx = await _base_context(request, tenant)
    ctx["owner_email"] = session["email"]
    db = get_db()
    business = await db.businesses.find_one({"claimed_email": session["email"]})
    ctx["owner_business"] = business

    # WHY: When the claim is still pending, claimed_email hasn't been set yet
    # (it's only written at verification time), so owner_business is None.
    # We still want to show the owner a link to their live listing on the
    # "claim pending" page so they have somewhere useful to go. Look up the
    # most recent pending claim for this email and resolve the business slug.
    if not business:
        pending_claim = await db.business_claims.find_one(
            {"submitter_email": session["email"], "status": {"$ne": "rejected"}},
            sort=[("submitted_at", -1)],
        )
        if pending_claim and pending_claim.get("business_id"):
            pending_business = await db.businesses.find_one(
                {"_id": pending_claim["business_id"]},
                projection={"slug": 1, "name": 1},
            )
            ctx["pending_business"] = pending_business

    if business:
        # WHY: Pass the ID as a plain string so JavaScript in the template
        # can embed it in an API request body without ObjectId serialisation
        # concerns. str() on a Mongo ObjectId returns the 24-char hex string.
        ctx["owner_business_id"] = str(business["_id"])
        ctx["seo_title"] = business.get("name", "Your account")
        ctx["meta_description"] = (
            f"Manage your {business.get('name', 'salon')} listing on Knows Beauty."
        )
    else:
        ctx["seo_title"] = "Your account"
        ctx["meta_description"] = "Your Knows Beauty owner account."
    response = _templates.TemplateResponse("owner_me.html", ctx)
    # WHY: rolling 30-day expiry. Reissue the cookie on every successful
    # visit so an active owner never has to sign in again. The freshly
    # signed cookie carries a new issued_at, so the 30-day clock starts
    # over from this hit.
    from app.services.owner_auth import SESSION_LIFETIME, sign_session
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sign_session(session["email"]),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/robots.txt")
async def robots_txt(request: Request) -> HTMLResponse:
    tenant = await resolve_tenant(request.headers.get("host", ""))
    if not tenant:
        return HTMLResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")
    host = request.headers.get("host", "")
    scheme = request.url.scheme
    return HTMLResponse(
        f"User-agent: *\nAllow: /\nSitemap: {scheme}://{host}/sitemap.xml\n",
        media_type="text/plain",
    )


@router.get("/sitemap.xml")
async def sitemap(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)
    host = request.headers.get("host", "")
    scheme = request.url.scheme
    base = f"{scheme}://{host}"

    # WHY: today's date is used for pages that don't carry per-record
    # timestamps (static pages, category pages, neighborhood pages). Google
    # uses lastmod to decide how frequently to re-crawl; stale dates cause
    # under-crawling, so a live "today" value on structural pages is the
    # right signal — those pages do change whenever new businesses are added.
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # List of (url, lastmod_str) tuples. Business pages carry per-record
    # updated_at when available; everything else uses today's date.
    entries: List[tuple[str, str]] = [(base + "/", today_str)]

    if tenant.city:
        city_id = tenant.city["_id"]
        for cat in await content_svc.list_categories(city_id):
            entries.append((f"{base}/c/{cat['slug']}", today_str))
        for nb in await content_svc.list_neighborhoods(city_id):
            entries.append((f"{base}/n/{nb['slug']}", today_str))
        cur = content_svc.get_db().businesses.find(
            {"city_id": city_id, "status": "live", "index_status": {"$ne": "noindex"}}
        )
        # WHY: collect nb+cat pairs during the business loop so we can add
        # /n/<nb>/c/<cat> intersection pages without a second DB query.
        nb_cat_pairs: set[tuple[str, str]] = set()
        async for b in cur:
            # WHY: prefer the business's own updated_at timestamp so Google
            # knows when the listing content last changed — a hair salon that
            # updated its hours last week should be re-crawled sooner than one
            # that hasn't changed since the site launched.
            raw_ts = b.get("updated_at")
            if isinstance(raw_ts, datetime):
                lastmod = raw_ts.strftime("%Y-%m-%d")
            elif isinstance(raw_ts, str) and len(raw_ts) >= 10:
                lastmod = raw_ts[:10]  # accept ISO strings like "2025-03-01T..."
            else:
                lastmod = today_str
            entries.append((f"{base}/b/{b['slug']}", lastmod))
            for nb_slug in b.get("neighborhood_slugs") or []:
                for cat_slug in b.get("category_slugs") or []:
                    nb_cat_pairs.add((nb_slug, cat_slug))
        # WHY: neighborhood+category intersection pages (/n/wynwood/c/hair) are
        # high-value long-tail landing pages but were missing from the sitemap,
        # so Google couldn't discover them through crawl. Adding all combos that
        # actually have businesses ensures they get indexed without cluttering
        # the sitemap with empty pages.
        for nb_slug, cat_slug in sorted(nb_cat_pairs):
            entries.append((f"{base}/n/{nb_slug}/c/{cat_slug}", today_str))
        for g in await content_svc.list_editorial_guides(city_id, limit=500):
            entries.append((f"{base}/guides/{g['slug']}", today_str))

    def _url_tag(loc: str, lastmod: str) -> str:
        return f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>\n"

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(_url_tag(loc, lm) for loc, lm in entries)
        + "</urlset>\n"
    )
    return HTMLResponse(body, media_type="application/xml")


async def render_not_found(request: Request, templates: Jinja2Templates) -> HTMLResponse:
    host = request.headers.get("host", "")
    tenant = await resolve_tenant(host)
    if tenant:
        ctx = await _base_context(request, tenant)
        ctx["seo_title"] = "Not found"
        return templates.TemplateResponse("not_found.html", ctx, status_code=404)
    return HTMLResponse(
        f"<h1>404</h1><p>Unknown site: {host}</p>", status_code=404
    )
