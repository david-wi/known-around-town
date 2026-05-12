"""Server-rendered public pages.

Every request resolves the (network, city) tenant from the Host header,
loads the relevant database records, and renders a Jinja2 template. The
template only receives plain data — no DB access from the template.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import markdown2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services import content as content_svc
from app.services.copy import CopyResolver
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

    return {
        "request": request,
        "tenant": tenant,
        "network": network,
        "city": city,
        "copy": copy,
        "vertical_word": _vertical_word(network),
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
    }


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


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)

    if not tenant.city:
        return _templates.TemplateResponse(
            "network_home.html",
            await _base_context(request, tenant),
        )

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
            "search_chips": search_chips,
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
        }
    )
    return _templates.TemplateResponse("home.html", ctx)


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
            or f"{category.get('name')} in {city.get('name')} — {tenant.network.get('name')}",
            "meta_description": category.get("meta_description"),
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
            or f"{nb.get('name')} — {tenant.network.get('name')} {city.get('name')}",
            "meta_description": nb.get("meta_description"),
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
            "seo_title": f"{category.get('name')} in {nb.get('name')} — {tenant.network.get('name')} {city.get('name')}",
        }
    )
    return _templates.TemplateResponse("category.html", ctx)


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

    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "business": business,
            "nearby_businesses": nearby,
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

    urls: List[str] = [base + "/"]
    if tenant.city:
        city_id = tenant.city["_id"]
        for cat in await content_svc.list_categories(city_id):
            urls.append(f"{base}/c/{cat['slug']}")
        for nb in await content_svc.list_neighborhoods(city_id):
            urls.append(f"{base}/n/{nb['slug']}")
        cur = content_svc.get_db().businesses.find(
            {"city_id": city_id, "status": "live", "index_status": {"$ne": "noindex"}}
        )
        async for b in cur:
            urls.append(f"{base}/b/{b['slug']}")
        for g in await content_svc.list_editorial_guides(city_id, limit=500):
            urls.append(f"{base}/guides/{g['slug']}")

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
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
