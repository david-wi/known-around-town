"""Server-rendered public pages.

Every request resolves the (network, city) tenant from the Host header,
loads the relevant database records, and renders a Jinja2 template. The
template only receives plain data — no DB access from the template.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

import markdown2
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_db
from app.services import content as content_svc
from app.services.copy import CopyResolver
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session
from app.services.site_settings import get_google_site_verification, get_preview_mode_enabled
from app.services.tenant import TenantContext, resolve_tenant


router = APIRouter()

_templates: Optional[Jinja2Templates] = None


def _is_representative_photo_url(url: Any) -> bool:
    """True when a photo URL is a generic/stock image, not an owner photo."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        host = urlparse(url).hostname or ""
    except (TypeError, ValueError):
        return False
    host = host.lower()
    return host == "images.unsplash.com" or host.endswith(".unsplash.com")


def attach_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t
    t.env.filters["markdown"] = lambda text: markdown2.markdown(
        text or "", extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists"]
    )
    t.env.filters["humantime"] = lambda when: (
        when.strftime("%b %-d, %Y") if isinstance(when, datetime) else str(when or "")
    )
    # WHY: schema.org datePublished needs an ISO-8601 string. Some editorial
    # guides were imported with published_at stored as a string ("2026-06-12T06:00:00Z")
    # rather than a datetime, so calling .isoformat() on it in the template raised
    # AttributeError and 500'd the whole guide page (23 Miami guides were down).
    # This filter mirrors humantime: a real datetime is normalised via isoformat(),
    # a string is passed through as-is (it is already ISO from the import), and
    # anything empty becomes "" so the {% if %} guard above still controls output.
    t.env.filters["iso_datetime"] = lambda when: (
        when.isoformat() if isinstance(when, datetime) else str(when or "")
    )
    t.env.filters["is_representative_photo"] = _is_representative_photo_url


async def _require_tenant(request: Request) -> TenantContext:
    host = request.headers.get("host", "")
    tenant = await resolve_tenant(host)
    if not tenant:
        raise HTTPException(404, f"Unknown host: {host}")
    return tenant


# WHY: ~367 imported salon records (256 of them live) store their address as a
# single line of text — e.g. "2001 N Federal Hwy, Suite 208, Pompano Beach, FL
# 33062" — instead of the structured {street, city, state, postal_code} object
# the Business.address model defines. The business detail route and JSON-LD both
# expect a dict, so a plain string crashed the page with
# `AttributeError: 'str' object has no attribute 'get'` (HTTP 500). Normalising
# here makes the page tolerant: a dict is returned as-is, and a single-line
# string is wrapped into the dict shape so the address still renders, the
# directions link still works, and the page never crashes. This is a
# display-time fix only — it does NOT rewrite the stored data.
def _normalize_address(raw: Any) -> Dict[str, Any]:
    """Return an address dict regardless of how the record stored it.

    Accepts the structured dict (returned unchanged), a single-line string
    (parsed best-effort into street/city/state/postal_code), or anything else
    (returned as an empty dict). Never raises.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}

    text = raw.strip()
    # WHY: the whole original line is kept as `street` so the Address card —
    # which renders only `address.street` — shows the complete human-readable
    # address, matching the existing "full address in one string" assumption
    # noted in business.html. City/state/postal are additionally pulled out so
    # the Google Maps query and JSON-LD get the more precise fields when the
    # line follows the common US "..., City, ST 33444" / "..., City, ST" shape.
    result: Dict[str, Any] = {"street": text}
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 2:
        # Last comma-separated chunk is usually "ST 33444", "ST", or "FL 33062-1234".
        tail = parts[-1].split()
        state: Optional[str] = None
        postal: Optional[str] = None
        if tail:
            # A 2-letter US state code, optionally followed by a ZIP / ZIP+4.
            if len(tail[0]) == 2 and tail[0].isalpha():
                state = tail[0].upper()
                if len(tail) >= 2 and tail[1][:5].isdigit():
                    postal = tail[1]
            elif tail[0][:5].isdigit():
                # Bare ZIP with no state token.
                postal = tail[0]
        if state:
            result["state"] = state
        if postal:
            result["postal_code"] = postal
        # WHY: when the final chunk was a recognised state/zip, the city is the
        # chunk before it ("..., Pompano Beach, FL 33062" -> "Pompano Beach").
        # When the final chunk was NOT a state/zip (e.g. "..., Miami Beach"), that
        # final chunk is itself the city — so don't grab the wrong chunk.
        if state or postal:
            result["city"] = parts[-2]
        else:
            result["city"] = parts[-1]
    return result


def _directions_url_for_business(business: Dict[str, Any]) -> str:
    """Build a Google Maps directions URL for a business, or "" if we can't.

    WHY: shared by the listing page (which renders the "Get directions" link)
    and the /b/{slug}/go/directions tracking redirect, so the URL a shopper is
    sent to is computed identically in both places. Returns "" when there's no
    usable address and no name to fall back on.

    WHY include city/state/postal alongside street: a street-only query is
    ambiguous — "1234 SW 8th St" matches dozens of cities — so the full address
    pins Maps to the right neighborhood. Fields whose text already appears in
    `street` (the single-line-address case) are skipped to avoid duplicating it.
    """
    addr = _normalize_address(business.get("address"))
    street = addr.get("street") or ""
    map_parts = [street]
    for field in ("city", "state", "postal_code"):
        val = addr.get(field)
        if val and val not in street:
            map_parts.append(val)
    map_query = ", ".join(filter(None, map_parts)) or business.get("name", "")
    if not map_query:
        return ""
    return f"https://maps.google.com/?q={quote_plus(map_query)}"


async def _build_copy(tenant: TenantContext) -> CopyResolver:
    network = tenant.network
    city = tenant.city
    resolver = CopyResolver(
        network_id=network["_id"],
        city_id=city["_id"] if city else None,
        network_name=network.get("name", ""),
        city_name=city.get("name", "") if city else "",
    )
    # WHY: the base/footer context resolves dozens of copy snippets at
    # city/network/global scope. Priming loads them all in one query instead
    # of one round-trip per snippet — the bulk of the home/listing TTFB win.
    await resolver.prime()
    return resolver


def _dedup_photos(
    businesses: list[dict],
    seen: Optional[set[str]] = None,
) -> list[dict]:
    """Remove duplicate photo URLs so no image appears twice on one page.

    WHY: When multiple businesses share the same stock photo URL (common in
    seeded data with a small image pool), the listing grid looks like the
    same photo was copy-pasted. Showing a neutral gray placeholder is better
    than visual repetition — the card still renders correctly, just without
    a hero image.

    Pass a shared `seen` set to deduplicate across multiple sections of the
    same page (e.g. Editor's Picks + Trending on the home page). When omitted
    a fresh set is created, making dedup local to the single list.
    """
    if seen is None:
        seen = set()
    result = []
    for b in businesses:
        photos = b.get("photos") or []
        if photos:
            first = photos[0]
            url = first.get("url", "") if isinstance(first, dict) else (first or "")
            if url and url in seen:
                b = {**b, "photos": []}
            elif url:
                seen.add(url)
        result.append(b)
    return result


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
        # WHY: neighbourhood cards without a photo fall back to this diagonal gradient
        # instead of a plain black rectangle. The deep rose start colour matches the
        # beauty network's brand so the card looks intentional even without a photo.
        # Hex values are used (not Tailwind utilities) because the CSS is pre-compiled
        # and these specific shades aren't in the reference.css safelist.
        "card_gradient_color_from": "#2d0a12",  # deep rose-950-ish
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
        # WHY: neighbourhood cards without a photo fall back to a deep emerald gradient
        # matching the wellness network's brand colour. Hex (not Tailwind) for same
        # reason as beauty: pre-compiled CSS doesn't include these specific shades.
        "card_gradient_color_from": "#052e16",  # deep emerald-950-ish
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
        # WHY: neighbourhood cards without a photo fall back to a deep sky-blue gradient
        # matching the health network's brand colour. Hex (not Tailwind) for same
        # reason as beauty: pre-compiled CSS doesn't include these specific shades.
        "card_gradient_color_from": "#082f49",  # deep sky-950-ish
    },
}


def _network_theme(network: Dict[str, Any]) -> Dict[str, str]:
    return _NETWORK_THEMES.get(network.get("slug", ""), _NETWORK_THEMES["beauty"])


_CITY_FOOTER_PATH_OVERRIDES: Dict[tuple[str, str], tuple[str, str]] = {
    # WHY: Wynwood was once seeded as its own city edition, but in the current
    # Miami product it is a neighborhood landing page. Keep footer cross-links
    # from reviving the stale `wynwood.knowsbeauty.*` domain.
    ("beauty", "wynwood"): ("miami", "/n/wynwood"),
}


def _city_footer_url(network_slug: str, city_slug: str, suffix: str) -> str:
    override = _CITY_FOOTER_PATH_OVERRIDES.get((network_slug, city_slug))
    if override:
        host_slug, path = override
        return f"https://{host_slug}.{suffix}{path}"
    return f"https://{city_slug}.{suffix}/"


async def _base_context(request: Request, tenant: TenantContext) -> Dict[str, Any]:
    copy = await _build_copy(tenant)
    city = tenant.city
    network = tenant.network
    nav_categories: List[Dict[str, Any]] = []
    nav_neighborhoods: List[Dict[str, Any]] = []
    if city:
        nav_categories = await content_svc.list_categories(city["_id"])
        nav_neighborhoods = await content_svc.list_neighborhoods(city["_id"])

    # Cross-city footer links — all sibling cities on the same network, ordered
    # alphabetically, each pointing at the root of their city subdomain.
    # WHY: cross-linking every page to every sibling city signals to Google that
    # the pages form a coherent site network; authority flows between them, and
    # Google understands the geographic breadth of the publication without having
    # to crawl through sitemaps to discover the relationship.
    network_cities: List[Dict[str, Any]] = []
    if network:
        suffix = tenant.network_domain_suffix
        current_city_id = city["_id"] if city else None
        if suffix:
            all_network_cities = await content_svc.list_cities(network["_id"])
            # WHY: exclude the current city — a link back to the page the visitor
            # is already on adds noise rather than helpful navigation.
            network_cities = [
                {
                    "name": c["name"],
                    "url": _city_footer_url(network.get("slug", ""), c["slug"], suffix),
                }
                for c in all_network_cities
                if c.get("_id") != current_city_id
            ]

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

    canonical_base = get_settings().canonical_base_url.rstrip("/")
    request_host = request.headers.get("host", "")
    if canonical_base and canonical_url:
        # WHY: CANONICAL_BASE_URL has two different jobs depending on who is
        # making the request:
        #
        # (A) Dev/staging host (e.g. *.ai.devintensive.com or *.knowsbeauty.localhost):
        #     Replace the entire origin — both hostname AND scheme — with the
        #     canonical base. This makes staging pages declare the production
        #     .com URL as their canonical, so Google doesn't index the dev
        #     subdomain.
        #
        # (B) Production host (e.g. doral.knowsbeauty.com, miami.knowsbeauty.com):
        #     Keep the request's own subdomain (so each city stays distinct) but
        #     upgrade the scheme to HTTPS when the canonical base is HTTPS.
        #     Without the scheme upgrade the canonical would be "http://..." but
        #     all production traffic arrives over HTTPS — mismatched scheme causes
        #     Google to treat http and https versions as separate URLs.
        #     DO NOT replace the host with canonical_base's host — that would
        #     make doral.knowsbeauty.com declare miami.knowsbeauty.com as its
        #     canonical, causing Google to treat all 22 city pages as duplicates
        #     of the Miami homepage.
        canonical_base_parsed = urlparse(canonical_base)
        canonical_base_netloc = canonical_base_parsed.netloc  # e.g. "miami.knowsbeauty.com"
        canonical_scheme = canonical_base_parsed.scheme       # e.g. "https"
        # Derive the apex domain by stripping the leftmost label so we match
        # any city subdomain (doral.knowsbeauty.com, plantation.knowsbeauty.com, …).
        canonical_apex = ".".join(canonical_base_netloc.rsplit(".", 2)[-2:])  # "knowsbeauty.com"
        host_is_canonical_domain = (
            request_host == canonical_apex
            or request_host.endswith("." + canonical_apex)
        )
        parsed = urlparse(canonical_url)
        if host_is_canonical_domain:
            # Case B: already on the right domain — keep the city subdomain,
            # just ensure the scheme matches the canonical (http→https upgrade).
            canonical_url = f"{canonical_scheme}://{request_host}{parsed.path or '/'}"
        else:
            # Case A: dev/staging host — replace origin with canonical base.
            canonical_url = canonical_base + (parsed.path or "/")

    return {
        "request": request,
        "tenant": tenant,
        "network": network,
        "city": city,
        "copy": copy,
        "theme": _network_theme(network),
        "vertical_word": _vertical_word(network),
        "canonical_url": canonical_url,
        # WHY: A short human label like "Miami Knows Beauty" used in page
        # copy and meta tags. Falls back to the network name on the
        # network-home page where there's no city in context (e.g. the
        # landing page before a city has been picked).
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
        "footer_also_in_url": await copy.get("footer.also_in_url"),
        "footer_publication_label": await copy.get("footer.publication_label"),
        "footer_owners_label": await copy.get("footer.owners.label") or "OWNERS",
        "footer_owners_items": footer_owners_items,
        "network_cities": network_cities,
        "page_featured_disclosure": await copy.get("page.featured_disclosure"),
        "owners_header_cta": await copy.get("header.owners_cta") or "For Owners",
        # WHY: GA4 is injected here (the shared base context) so every page
        # gets the tracking script without duplicating the env-var read in
        # each individual route handler.  An empty or absent var means the
        # {% if ga_measurement_id %} guard in base.html emits no script at
        # all — no dead snippet, no console noise on dev.
        "ga_measurement_id": get_settings().ga_measurement_id,
        # WHY: DB value read first so the admin settings page can set the GSC
        # code without an SSH restart. Falls back to the env var automatically.
        "google_site_verification": await get_google_site_verification(),
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

# WHY: the network landing's city cards render a photo from each city's
# `hero_photo_url`. A city that launches before an editor sets that field used to
# render a blank gradient capsule above the fold — the visible "photoless capsule"
# defect a visitor sees first. As a backend safety net, any live city still
# missing a hero gets a deterministic pick from this curated set (distinct,
# license-clear Unsplash beauty/spa images, sized to match the template's
# img_sized(800) usage) so no card is ever photoless, even before the database is
# backfilled. Deterministic-by-slug so the same city always gets the same image
# (stable across renders) and adjacent cities don't collide.
_LANDING_CITY_HERO_FALLBACKS: List[str] = [
    "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1521590832167-7bcbfaa6381f?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1487412947147-5cebf100ffc2?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1562322140-8baeececf3df?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1633681926022-84c23e8cb2d6?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1600948836101-f9ffda59d250?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1571875257727-256c39da42af?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1595476108010-b4d1f102b1b1?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1633681926035-ec1ac984418a?w=1600&q=80&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1532710093739-9470acff878f?w=1600&q=80&auto=format&fit=crop",
]


def _landing_city_hero_fallback(slug: str) -> str:
    """Deterministic curated hero image for a city that has no `hero_photo_url`.

    WHY exists: keeps the network landing's city cards from ever rendering a blank
    gradient capsule (see `_LANDING_CITY_HERO_FALLBACKS`). Stable per slug so a
    city's card image doesn't change between page loads.
    """
    if not _LANDING_CITY_HERO_FALLBACKS:
        return ""
    digest = hashlib.md5(slug.encode("utf-8")).hexdigest()
    return _LANDING_CITY_HERO_FALLBACKS[int(digest, 16) % len(_LANDING_CITY_HERO_FALLBACKS)]


def _city_og_image(city: Optional[Dict[str, Any]]) -> Optional[str]:
    """City-level photo for the og:image / twitter:image share-preview card,
    guaranteed non-blank for ANY launched city — not just Miami.

    WHY exists: every og_image site fell back to ``city.get("hero_photo_url")``,
    but only Miami has that field set. So a listing or city page shared from
    Brickell, Coconut Grove, Pinecrest, etc. unfurled as a bare link with no
    photo — which kills click-through in exactly the moment a salon owner first
    sees their listing link. This terminal fallback reuses the same deterministic
    curated image set the network-landing city cards already use, so the preview
    card always carries a tasteful, on-brand beauty photo.
    """
    if not city:
        return None
    return city.get("hero_photo_url") or _landing_city_hero_fallback(city.get("slug", ""))


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
                # WHY: fall back to a deterministic curated image when the city has
                # no hero photo set, so the card is never a blank gradient capsule.
                "hero_photo_url": (
                    city.get("hero_photo_url")
                    or _landing_city_hero_fallback(city.get("slug", ""))
                ),
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
    return _templates.TemplateResponse(request, "network_landing.html", ctx)


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
        # WHY: when the visitor lands on the bare root domain (knowsbeauty.com)
        # and only one city is live, redirect straight to that city's subdomain
        # rather than showing a one-item "pick a city" landing page. The landing
        # page becomes useful once multiple cities are live; until then a redirect
        # is a better first impression. Using 302 (not 301) so browsers don't
        # cache it — this condition changes as new cities are seeded.
        live_cities = await content_svc.list_cities(tenant.network["_id"])
        if len(live_cities) == 1:
            scheme = request.url.scheme or "https"
            suffix = tenant.network_domain_suffix
            slug = live_cities[0].get("slug", "")
            if slug and suffix:
                return RedirectResponse(
                    url=f"{scheme}://{slug}.{suffix}/",
                    status_code=302,
                )
        return await _render_network_landing(request, tenant)

    city = tenant.city
    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )
    # WHY: the home page resolves all its copy at city/network/global scope.
    # Prime once so the ~dozens of snippets cost a single query, not one each.
    await copy.prime()

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

    # Deduplicate photos across all home-page sections so the same stock image
    # never appears twice on the page. A single shared set is passed through
    # every call so a URL claimed by editor_picks is suppressed in trending,
    # spotlight, and the neighborhood mini-lists.
    _page_seen: set[str] = set()
    editor_picks = _dedup_photos(editor_picks, _page_seen)
    trending = _dedup_photos(trending, _page_seen)
    spotlight_businesses = _dedup_photos(spotlight_businesses, _page_seen)

    # Two-column neighborhood mini-lists (city-configured only — wellness and
    # health intentionally don't show this section on the reference).
    columns: List[Dict[str, Any]] = []
    for col in city.get("two_column_neighborhoods") or []:
        nb = await content_svc.get_neighborhood(city["_id"], col["slug"])
        if not nb:
            continue
        nb_biz = _dedup_photos(_resolve_by_slug(all_live, col.get("business_slugs") or []), _page_seen)
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

    # WHY: load up to 6 guides for the homepage section; showing them here
    # surfaces editorial content to visitors who land on the homepage directly
    # and creates internal links that help Google discover the guide pages.
    recent_guides = await content_svc.list_editorial_guides(city["_id"], limit=6)

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
            # WHY: always count live businesses dynamically so the stat stays
            # accurate as businesses are added — the copy override was seeded
            # with an early-launch hardcoded value ("29") that drifted stale.
            "stat_count_listings": str(len(all_live)),
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
            # WHY: og_image lets base.html emit the og:image tag uniformly — without
            # it, home.html added a second manual tag in head_extra, producing two
            # og:image meta tags on the home page (one blank, one correct).
            "og_image": _city_og_image(city),
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
            # Editorial guides for the homepage section
            "recent_guides": recent_guides,
        }
    )
    return _templates.TemplateResponse(request, "home.html", ctx)


# WHY: /categories is a natural URL visitors and links use to browse by service
# type, but the site has no categories index page — category browsing lives on
# the home page. 301 so search engines update any indexed links.
@router.get("/categories")
async def redirect_categories() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=301)


# WHY: old URL scheme used /{city}/salon/{slug} (e.g. /miami/salon/rossano-ferretti).
# The current scheme is /b/{slug}. Permanently redirect the old pattern so any
# external links or bookmarks resolve to the correct listing page.
@router.get("/{city}/salon/{slug}")
async def redirect_city_salon(city: str, slug: str) -> RedirectResponse:
    return RedirectResponse(url=f"/b/{slug}", status_code=301)


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
    # WHY: this page resolves copy at category scope as well as city/network/
    # global. Prime the category dimension so all its lookups hit memory.
    await copy.prime(category_slug=category_slug)

    ctx = await _base_context(request, tenant)
    businesses = _dedup_photos(await content_svc.list_businesses(
        city["_id"], category_slug=category_slug, limit=120
    ))
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
                (
                    p["url"] if isinstance(p, dict) else p
                    for b in businesses if b.get("photos")
                    for p in [b["photos"][0]]
                ),
                _city_og_image(city),
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
    return _templates.TemplateResponse(request, "category.html", ctx)


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
    # WHY: this is the salon-listing page — the slowest one, because every
    # `business.*` snippet misses through all four scope levels. Priming the
    # neighborhood dimension collapses those per-snippet misses into one query.
    await copy.prime(neighborhood_slug=neighborhood_slug)

    ctx = await _base_context(request, tenant)
    businesses = _dedup_photos(await content_svc.list_businesses(
        city["_id"], neighborhood_slug=neighborhood_slug, limit=120
    ))
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
                (
                    p["url"] if isinstance(p, dict) else p
                    for b in businesses if b.get("photos")
                    for p in [b["photos"][0]]
                ),
                _city_og_image(city),
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
    return _templates.TemplateResponse(request, "neighborhood.html", ctx)


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
    # WHY: this page resolves copy at both neighborhood and category scope.
    # Prime both dimensions so its lookups resolve from memory.
    await copy.prime(neighborhood_slug=neighborhood_slug, category_slug=category_slug)

    ctx = await _base_context(request, tenant)
    businesses = _dedup_photos([
        b
        for b in await content_svc.list_businesses(
            city["_id"], category_slug=category_slug, limit=200
        )
        if neighborhood_slug in (b.get("neighborhood_slugs") or [])
    ])
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
            # WHY: including the business count ("Browse 3 hair salons") makes the
            # search snippet more informative and increases click-through rate —
            # a searcher for "hair salons wynwood" is more likely to click a result
            # that shows 3 real listings exist than one that just says "the best".
            "meta_description": (
                f"Browse {len(businesses)} {category.get('name', '').lower()} in {nb.get('name', '')}, {city.get('name', '')} — "
                f"find the best on {city.get('name', '')} {tenant.network.get('name', '')}."
                if businesses else
                f"The best {category.get('name', '').lower()} in {nb.get('name', '')}, {city.get('name', '')} — "
                f"browse {city.get('name', '')} {tenant.network.get('name', '')}."
            ),
            # WHY: same pattern as category and neighborhood pages.
            "og_image": next(
                (
                    p["url"] if isinstance(p, dict) else p
                    for b in businesses if b.get("photos")
                    for p in [b["photos"][0]]
                ),
                _city_og_image(city),
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
    return _templates.TemplateResponse(request, "category.html", ctx)


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
            "seo_title": f"Search {city.get('name')}{': ' + query if query else ''} — {tenant.network.get('name')}",
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
                (
                    p["url"] if isinstance(p, dict) else p
                    for b in businesses if b.get("photos")
                    for p in [b["photos"][0]]
                ),
                _city_og_image(city),
            ),
        }
    )
    return _templates.TemplateResponse(request, "search.html", ctx)


_BOT_UA_FRAGMENTS = (
    "bot", "crawler", "spider", "slurp", "facebookexternalhit",
    "twitterbot", "linkedinbot", "whatsapp", "telegrambot", "applebot",
    "semrushbot", "ahrefsbot", "mj12bot", "dotbot", "petalbot",
)


# WHY: the marker we hang on the "As Featured on Miami Knows Beauty" website
# badge's link (``?ref=mkb-badge``). The badge sits on the salon's OWN site, so
# a click on it arrives with the salon's domain as the referer (external) and
# can't be recognised by same-host matching — see _is_mkb_referred. Stamping the
# link with this stable marker lets us credit the badge click as MKB-driven the
# moment the shopper lands, which can never be reconstructed later. Defined once
# so the link builder and the view detector can't drift apart.
MKB_BADGE_REF_MARKER = "mkb-badge"


def _is_mkb_referred(
    referer: Optional[str], request_host: str, ref_marker: Optional[str] = None
) -> bool:
    """Decide whether a page view came from within Miami Knows Beauty itself.

    Two independent signals make a view "MKB-driven", either is sufficient:

    1. **Same-host referer.** The page the shopper clicked FROM (the ``Referer``
       header) lives on the SAME host as the listing they landed on. On this
       network every editorial guide, on-site search result, category page,
       neighborhood page, and sister listing for a given city edition is served
       from that one host (e.g. miami.knowsbeauty.com) — so a same-host referer
       is, by construction, an internal click from one of OUR pages.

    2. **Badge marker.** The request URL carries ``?ref=mkb-badge`` (the
       ``ref_marker`` argument equals ``MKB_BADGE_REF_MARKER``). This is how we
       credit the website badge — see the badge note below.

    WHY same-host (not a broader network match): it's the cleanest signal that
    can't over-claim. A referer with no host (typed URL / bookmark) or an
    external host (Google, Instagram, the salon's own website) is NOT counted on
    that signal alone — we never claim credit for a visit we didn't send.

    WHY the badge needs a marker: the "As Featured on Miami Knows Beauty" badge
    lives on the salon's OWN external website, so a click on it arrives with the
    salon's domain as the referer — an external host — which same-host matching
    can't see. The badge IS our traffic (the salon shows it because we featured
    them, and it's our #1 shopper-acquisition lever), so we tag the badge's link
    with ``?ref=mkb-badge`` and count that marked click as MKB-driven even though
    the referer is external. Every other external referer is still NOT counted,
    so this stays a tight, intentional carve-out rather than a loophole.
    """
    # WHY: a marked badge click counts even when the referer is the salon's own
    # (external) site — that's the whole reason the marker exists. Checked first
    # so the same-host path below stays purely about internal clicks.
    if ref_marker == MKB_BADGE_REF_MARKER:
        return True
    if not referer:
        return False
    try:
        ref_host = urlparse(referer).hostname or ""
    except (ValueError, TypeError):
        # A malformed Referer header must never raise inside view counting.
        return False
    if not ref_host:
        return False
    # WHY strip the request host's port and casefold both sides: the Host header
    # can carry a port (":8000" in dev) while a Referer URL's hostname never
    # does, so compare bare hostnames case-insensitively. Splitting on ":" takes
    # the host portion before any port.
    own_host = (request_host or "").split(":", 1)[0]
    return ref_host.casefold() == own_host.casefold()


async def _increment_business_view(business_id: str, mkb_referred: bool = False) -> None:
    """Atomically increment the page view counter(s) for one business.

    Always bumps the lifetime ``page_view_count``. When ``mkb_referred`` is True
    — the visit came from within Miami Knows Beauty (see ``_is_mkb_referred``) —
    it ALSO bumps ``mkb_referred_view_count`` in the same atomic write, so the
    owner can be shown how many of their visitors WE sent (vs. visitors who
    arrived from Google, social, or by typing the URL).

    WHY: background task so the atomic DB write happens after the response
    is sent — no added latency for the visitor. Using $inc is safe under
    concurrent requests without a read-modify-write race, and incrementing both
    fields in one $inc keeps the two counters consistent (a MKB-referred view is
    always also a total view).
    WHY str: business _id values are UUID strings (not ObjectIds), so the
    str() call in the caller is a no-op and querying with the string is correct.
    """
    from app.database import get_db as _get_db  # local import to avoid circular
    db = _get_db()
    inc: Dict[str, int] = {"page_view_count": 1}
    if mkb_referred:
        inc["mkb_referred_view_count"] = 1
    await db.businesses.update_one(
        {"_id": business_id},
        {"$inc": inc},
    )


# WHY: the three shopper-action redirect routes below each bump one of these
# counters. Mapping the URL action segment to the DB field in one place keeps
# the route handler a thin lookup and makes the allowed actions explicit — an
# unknown action can never increment an arbitrary field.
_ACTION_COUNTER_FIELDS = {
    "call": "call_click_count",
    "directions": "directions_click_count",
    "website": "website_click_count",
}


async def _increment_business_action(business_id: str, counter_field: str) -> None:
    """Atomically increment one shopper-action counter for a business.

    WHY: mirrors _increment_business_view — a background task so the $inc
    happens after the redirect is sent (no added latency on the tap), and a
    single-field $inc is race-safe under concurrent taps. counter_field is
    always one of the values in _ACTION_COUNTER_FIELDS (the route validates the
    action segment before calling), so this never writes an attacker-named field.
    """
    from app.database import get_db as _get_db  # local import to avoid circular
    db = _get_db()
    await db.businesses.update_one(
        {"_id": business_id},
        {"$inc": {counter_field: 1}},
    )


@router.get("/b/{business_slug}", response_class=HTMLResponse)
async def business_page(
    request: Request, business_slug: str, background_tasks: BackgroundTasks
) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    business = await content_svc.get_business(city["_id"], business_slug)
    if not business or business.get("status") != "live":
        raise HTTPException(404, "Business not found")

    copy = CopyResolver(
        network_id=tenant.network["_id"],
        city_id=city["_id"],
        network_name=tenant.network.get("name", ""),
        city_name=city.get("name", ""),
    )
    # WHY: the business profile resolves its CTA/claim/section snippets at
    # business scope (with city/network/global fallback). Prime the business
    # dimension so those lookups hit memory instead of cascading per snippet.
    await copy.prime(business_id=business["_id"])

    nearby: List[Dict[str, Any]] = []
    if business.get("nearby_business_ids"):
        nearby_cur = content_svc.get_db().businesses.find(
            {"_id": {"$in": business["nearby_business_ids"]}, "status": "live"}
        )
        nearby = await nearby_cur.to_list(length=12)
    else:
        # WHY: When no editorial nearby list is set, auto-suggest businesses in
        # the same city so the "You might also love" section is populated.
        # Ordinary listings keep the original same-category fallback because
        # shoppers comparing hair salons often want more hair salons. Featured
        # listings are different: showing direct same-category competitors next
        # to a paid owner undercuts the Featured value. For Featured listings,
        # prefer complementary cross-category businesses and show fewer cards if
        # necessary rather than filling the section with competitors.
        primary_cat = (business.get("category_slugs") or [None])[0]
        is_featured = bool((business.get("featured") or {}).get("enabled"))
        auto_q: Dict[str, Any] = {
            "_id": {"$ne": business["_id"]},
            "city_id": city["_id"],
            "status": "live",
        }
        if primary_cat and is_featured:
            auto_q["category_slugs"] = {"$ne": primary_cat}
        elif primary_cat:
            auto_q["category_slugs"] = primary_cat
        nearby_cur = content_svc.get_db().businesses.find(auto_q).limit(3)
        nearby = await nearby_cur.to_list(length=3)

    # WHY: normalise the address into a dict in place so BOTH the directions-URL
    # helper and the template (Address card + JSON-LD, which read address.street /
    # .city / .state / .postal_code) tolerate records whose address was stored as
    # a single line of text rather than a structured object. See
    # _normalize_address. Reassigning on `business` (the same dict passed to the
    # template below) means the template renders the address instead of a blank.
    business["address"] = _normalize_address(business.get("address"))
    # WHY: the on-page "Get directions" link points at the /go/directions tracking
    # redirect (below), so this raw Maps URL is no longer used as the link href.
    # It's still computed and passed to the template as a no-JS / structured-data
    # fallback and so the link only renders when a real directions target exists.
    directions_url = _directions_url_for_business(business)

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
    # WHY: include category and neighborhood in the page title so it targets
    # the actual search terms ("hair salon design district miami") rather than
    # just the brand name. Both nav lists are already loaded in _base_context
    # so this costs zero extra DB queries.
    _biz_primary_cat_slug = (business.get("category_slugs") or [None])[0]
    _biz_primary_nb_slug = (business.get("neighborhood_slugs") or [None])[0]
    _biz_cat_name = next((c["name"] for c in ctx["nav_categories"] if c["slug"] == _biz_primary_cat_slug), "")
    _biz_nb_name = next((n["name"] for n in ctx["nav_neighborhoods"] if n["slug"] == _biz_primary_nb_slug), "")
    if business.get("meta_title_override"):
        _biz_seo_title = business["meta_title_override"]
    elif _biz_cat_name and _biz_nb_name:
        _biz_seo_title = f"{business.get('name')} | {_biz_cat_name} in {_biz_nb_name}, {city.get('name')}"
    elif _biz_cat_name:
        _biz_seo_title = f"{business.get('name')} | {_biz_cat_name} in {city.get('name')}"
    else:
        _biz_seo_title = f"{business.get('name')} — {city.get('name')} {tenant.network.get('name')}"

    # WHY: surface guides that feature this business so visitors can discover related
    # editorial content and so Google sees bidirectional link equity between listing pages
    # and the guides they appear in. Capped at 5 to keep the section scannable.
    # The $or checks both featured_business_ids (UUID, for older guides) and
    # business_slugs (slug, for guides published via the editorial API).
    related_guides = await get_db().editorial_guides.find(
        {
            "city_id": city["_id"],
            "status": "live",
            "$or": [
                {"featured_business_ids": business["_id"]},
                {"business_slugs": business["slug"]},
            ],
        },
        {"slug": 1, "title": 1, "_id": 0},
    ).to_list(length=5)

    # WHY: detect if the logged-in owner is viewing their OWN listing so the
    # template can show a contextual upgrade nudge. This is the same session-check
    # pattern used in pricing_page() — a convenience UX signal, not a security gate,
    # so any decoding or DB error silently falls back to "not the owner" (False).
    is_own_listing: bool = False
    owner_is_subscribed: bool = False
    try:
        raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        _session = verify_session(raw_cookie) if raw_cookie else None
        if _session:
            _email = _session["email"].lower()
            claimed_email = (business.get("claimed_email") or "").lower()
            if claimed_email and _email == claimed_email:
                is_own_listing = True
                owner_is_subscribed = bool(business.get("stripe_subscription_id"))
    except Exception:
        pass  # WHY: any DB or decoding error falls back to the anonymous visitor path

    ctx.update(
        {
            "business": business,
            "nearby_businesses": nearby,
            "related_guides": related_guides,
            "directions_url": directions_url,
            "is_own_listing": is_own_listing,
            "owner_is_subscribed": owner_is_subscribed,
            # WHY: prefer the salon's own photo over the city hero — it's more accurate
            # for sharing. Fall back to city hero so cards are never blank.
            "og_image": (
                None if _is_representative_photo_url(_hero_url) else _hero_url
            ) or _city_og_image(city),
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
            "seo_title": _biz_seo_title,
            "meta_description": business.get("meta_description_override")
            or business.get("short_description"),
        }
    )
    # WHY: count real visitor views (not bot/crawler traffic) so the owner
    # sees a number that reflects actual human interest in their listing.
    # Checking User-Agent before the $inc avoids inflating the counter with
    # Googlebot and other automated traffic that visits multiple times a day.
    ua = (request.headers.get("user-agent") or "").lower()
    if not any(f in ua for f in _BOT_UA_FRAGMENTS):
        # WHY decide MKB-referred HERE (in the request, not the background task):
        # the Referer/Host headers and the URL query params are only available on
        # the live request object, not inside the deferred task, so we resolve the
        # flag now and pass it in. A same-host referer means the shopper clicked
        # through from one of our own pages (a guide, search, category,
        # neighborhood, or sister listing); a ``?ref=mkb-badge`` marker means they
        # clicked our website badge on the salon's own site. Either way it's
        # traffic Miami Knows Beauty drove. See _is_mkb_referred for the rule.
        mkb_referred = _is_mkb_referred(
            request.headers.get("referer"),
            request.headers.get("host", ""),
            request.query_params.get("ref"),
        )
        background_tasks.add_task(
            _increment_business_view, str(business["_id"]), mkb_referred
        )
    return _templates.TemplateResponse(request, "business.html", ctx)


def _action_target_url(action: str, business: Dict[str, Any]) -> str:
    """Resolve the real destination for a shopper-action redirect.

    Returns the URL the /go/{action} route should 302 to, or "" when the
    business has no target for that action (no phone / no address / no website),
    in which case the route returns 404 rather than redirect nowhere.

    WHY tel: with non-digits stripped: mobile browsers dial most reliably from a
    bare-digit tel: URI. This mirrors the AI-receptionist link in business.html.
    """
    if action == "call":
        phone = (business.get("phone") or "").strip()
        if not phone:
            return ""
        digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        return f"tel:{digits}" if digits else ""
    if action == "directions":
        return _directions_url_for_business(business)
    if action == "website":
        website = (business.get("website") or "").strip()
        if not website:
            return ""
        # WHY: a stored website without a scheme (e.g. "example.com") would make
        # the 302 Location browser-relative — it'd resolve against OUR domain and
        # dead-end. Seed data carries full https:// URLs, but admin-entered or
        # imported records might not. So: pass http(s) through unchanged, and for
        # anything else default to https://, stripping any non-http(s) scheme
        # prefix (ftp:, javascript:, etc.) so a dangerous scheme can never become
        # the redirect target — the shopper is always sent to an https web page.
        lowered = website.lower()
        if lowered.startswith(("http://", "https://")):
            return website
        if "://" in website:
            website = website.split("://", 1)[1]
        elif ":" in website.split("/", 1)[0]:
            # A scheme-like prefix with no "//" (e.g. "javascript:alert(1)") —
            # drop everything up to and including the first colon in the host part.
            website = website.split(":", 1)[1]
        return f"https://{website.lstrip('/')}"
    return ""


@router.get("/b/{business_slug}/go/{action}")
async def business_action_redirect(
    request: Request,
    business_slug: str,
    action: str,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    """Track a high-intent shopper tap, then redirect to the real target.

    WHY a server-side redirect instead of a JavaScript click handler: it works
    even with JavaScript disabled, can't be silently dropped, and lets us count
    the tap once on the server before sending the shopper on. The listing's
    phone / directions / website buttons point here (e.g. /b/<slug>/go/call);
    this route bumps the matching counter (bot-filtered, in a background task so
    the tap has no added latency) and 302s to the salon's tel:/Maps/website
    target. Counts taps-to-call, taps-for-directions, and website clicks — the
    strongest "your listing is working" signals an owner can be shown.
    """
    counter_field = _ACTION_COUNTER_FIELDS.get(action)
    if counter_field is None:
        raise HTTPException(404, "Unknown action")

    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    business = await content_svc.get_business(tenant.city["_id"], business_slug)
    if not business or business.get("status") != "live":
        raise HTTPException(404, "Business not found")

    target = _action_target_url(action, business)
    if not target:
        # WHY 404 (not a redirect to the listing): the button only renders when a
        # target exists, so reaching here means the link was hand-built or the
        # data changed. Don't fabricate a redirect — and never count a tap that
        # can't reach a real destination.
        raise HTTPException(404, "No destination for this action")

    # WHY: same bot filter the page-view counter uses, so crawlers that follow
    # the /go/ links don't inflate the owner's shopper-action numbers.
    ua = (request.headers.get("user-agent") or "").lower()
    if not any(f in ua for f in _BOT_UA_FRAGMENTS):
        background_tasks.add_task(
            _increment_business_action, str(business["_id"]), counter_field
        )

    # WHY 302 (temporary), not 301: a 301 is cached by the browser, so the next
    # tap would skip the server entirely and never be counted. 302 keeps every
    # tap flowing through the counter.
    return RedirectResponse(url=target, status_code=302)


@router.get("/guides", response_class=HTMLResponse)
async def editorial_guides_index(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)
    if not tenant.city:
        raise HTTPException(404, "City required")
    city = tenant.city
    guides = await content_svc.list_editorial_guides(city["_id"], limit=50)
    ctx = await _base_context(request, tenant)
    ctx.update(
        {
            "guides": guides,
            "seo_title": f"Beauty & Wellness Guides · {city.get('name', 'Miami')}",
            "meta_description": (
                f"Expert guides to the best salons, spas, and beauty destinations "
                f"in {city.get('name', 'Miami')}."
            ),
        }
    )
    return _templates.TemplateResponse(request, "editorial_guides_index.html", ctx)


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
    # WHY: fall back to slug-based lookup when featured_business_ids is absent.
    # Guides published via the editorial API use business_slugs (human-readable)
    # rather than internal UUIDs. Both paths produce the same result for the
    # "Featured in this guide" section and the ItemList JSON-LD block.
    if not featured and guide.get("business_slugs"):
        cur = content_svc.get_db().businesses.find(
            {"city_id": city["_id"], "slug": {"$in": guide["business_slugs"]}}
        )
        featured = await cur.to_list(length=20)

    ctx = await _base_context(request, tenant)
    # WHY: og_image controls the preview card when anyone shares a guide link on
    # social media or iMessage. Prefer the guide's own hero image, then fall back
    # to the first featured business photo, then the city hero — so the card is
    # never blank regardless of how the guide was authored.
    _og_image = (
        guide.get("hero_image_url")
        or next(
            (
                (b["photos"][0].get("url") if isinstance(b["photos"][0], dict) else b["photos"][0])
                for b in featured
                if b.get("photos")
            ),
            None,
        )
        or _city_og_image(city)
    )
    ctx.update(
        {
            "guide": guide,
            "featured_businesses_in_guide": featured,
            "seo_title": guide.get("seo_title") or guide.get("title"),
            "meta_description": guide.get("meta_description") or guide.get("subtitle"),
            "og_image": _og_image,
            # WHY: ItemList JSON-LD lets Google surface individual business names
            # as rich results for guide-level queries like "best med spas Miami",
            # increasing click-through before the user even reaches the page.
            "item_list_jsonld": _build_item_list_jsonld(
                featured,
                list_name=guide.get("title", ""),
                list_url=str(request.url).split("?")[0],
                base_url=str(request.base_url).rstrip("/"),
            ) if featured else None,
        }
    )
    return _templates.TemplateResponse(request, "editorial_guide.html", ctx)


@router.get("/expertly-voice.html", response_class=HTMLResponse)
async def expertly_voice_page(request: Request) -> HTMLResponse:
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    ctx["seo_title"] = "Expertly Voice for Salons"
    ctx["meta_description"] = (
        "Expertly Voice answers your salon's phone when you're with a client "
        "or closed, then guides booking requests through the workflow we "
        "configure with you."
    )
    return _templates.TemplateResponse(request, "expertly_voice.html", ctx)


# WHY: Any link to /owners/claim (marketing emails, social posts, ads) would
# hit a 404 — the claim form lives at /owners#claim-form. Redirect so those
# links still land the owner on the right page.
@router.get("/owners/claim", response_class=HTMLResponse)
async def owners_claim_redirect() -> RedirectResponse:
    return RedirectResponse(url="/owners#claim-form", status_code=301)


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
                    # WHY: cast to str so the dict survives tojson in the
                    # Jinja template — MongoDB ObjectIds are not JSON-serialisable.
                    "id": str(biz["_id"]),
                    "name": biz.get("name", ""),
                    "slug": biz.get("slug", ""),
                }
        # WHY: 500 keeps the embedded JSON small. Miami has well under 100
        # live businesses today; 500 leaves comfortable headroom before
        # we'd want a real server-side search endpoint instead.
        live = await content_svc.list_businesses(city_id, limit=500)
        directory = [
            # WHY: cast _id to str — ObjectId is not JSON-serialisable and
            # the template passes this list straight through tojson.
            {"id": str(b["_id"]), "name": b.get("name", ""), "slug": b.get("slug", "")}
            for b in live
            if b.get("name")
        ]

    ctx["claim_prefill"] = prefill
    ctx["claim_directory"] = directory
    # WHY: og:image controls the preview card when this page is shared (e.g. David
    # pastes the link in a conversation with a prospective partner). The city hero
    # is the right image for an owner-acquisition landing page — it sets the Miami
    # beauty scene rather than spotlighting one business.
    ctx["og_image"] = _city_og_image(tenant.city)
    return _templates.TemplateResponse(request, "owners.html", ctx)


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
            # WHY: this is a static, unauthenticated MOCKUP of a real salon's
            # dashboard with every control rigged to "Coming soon". The live
            # owner dashboard now exists at /owners/me, so this page must never
            # be indexed — otherwise Google could surface a half-built "Coming
            # soon" version of our product to a prospect. base.html renders the
            # robots meta from this var (its comment documents exactly this
            # demo-page use); it was simply never set here.
            "robots": "noindex, nofollow",
        }
    )
    return _templates.TemplateResponse(request, "owner_dashboard.html", ctx)

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
    return _templates.TemplateResponse(request, "owners_caption_preview.html", ctx)


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
        f"receptionist. Cancel anytime. No long-term contract."
    ).strip()
    # WHY: og:image controls the preview card when this page is shared with a potential
    # customer or partner. The city hero is the right image for a pricing page — it
    # represents the Miami beauty market we're selling into.
    ctx["og_image"] = _city_og_image(tenant.city)

    # WHY: if the visiting owner is already logged in, the generic "Claim your listing"
    # CTA is confusing — they already claimed, they want to upgrade. We check the session
    # cookie here so the template can show the right button for each case:
    #   - not logged in → "Claim your listing" (new owner path)
    #   - logged in, free tier → "Upgrade to Featured" → /owners/me
    #   - logged in, already subscribed → "You're on Featured ✓" (no action needed)
    # All failures fall back to None (not logged in) — this is a convenience UX
    # enhancement, not a security gate, so silent failure is the right behaviour.
    owner_logged_in: bool = False
    owner_is_subscribed: bool = False
    owner_business_name: Optional[str] = None
    try:
        raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
        session = verify_session(raw_cookie) if raw_cookie else None
        if session:
            email = session["email"].lower()
            biz = await get_db().businesses.find_one(
                {"claimed_email": email},
                {"name": 1, "stripe_subscription_id": 1},
            )
            if biz:
                owner_logged_in = True
                owner_is_subscribed = bool(biz.get("stripe_subscription_id"))
                owner_business_name = biz.get("name")
    except Exception:
        pass  # WHY: any DB or decoding error falls back to the anonymous visitor path

    ctx["owner_logged_in"] = owner_logged_in
    ctx["owner_is_subscribed"] = owner_is_subscribed
    ctx["owner_business_name"] = owner_business_name
    return _templates.TemplateResponse(request, "pricing.html", ctx)


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
    return _templates.TemplateResponse(request, "owner_login.html", ctx)


@router.get("/owners/me", response_class=HTMLResponse)
async def owners_me_page(request: Request) -> HTMLResponse:
    """Owner dashboard — shows listing details, edit form, and subscription state."""
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
        # WHY: stripe_subscription_id is the authoritative signal that the owner
        # has an active paid subscription. We expose it as a clean boolean so
        # the template doesn't need to know the Stripe-specific field name, and
        # so route-level tests can assert on ctx directly without parsing HTML.
        ctx["is_subscribed"] = bool(business.get("stripe_subscription_id"))

        # WHY: the website-badge embed code (a Featured perk) needs the salon's
        # ABSOLUTE public listing URL — the badge is dropped on the salon's OWN
        # external site, so a relative "/b/slug" would resolve against the salon's
        # domain, not ours. Build it from the authoritative public host so the
        # link drives the salon's visitors to its real Miami Knows Beauty page
        # and earns us a backlink. Prefer CANONICAL_BASE_URL's origin (the
        # production .com domain) so the embed never hard-codes a dev/staging
        # subdomain; fall back to the request's own origin when no canonical base
        # is configured (single-domain dev). The badge image itself is served
        # from the same origin so it loads past the preview gate on the salon's
        # site.
        slug = business.get("slug") or ""
        canonical_base = get_settings().canonical_base_url.rstrip("/")
        if canonical_base:
            origin = canonical_base
        else:
            origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
        ctx["listing_absolute_url"] = f"{origin}/b/{slug}" if slug else ""
        ctx["badge_image_url"] = f"{origin}/badge/featured.svg"
        # WHY: the badge link gets its own URL with the ``?ref=mkb-badge`` marker,
        # SEPARATE from listing_absolute_url. The badge is on the salon's own site,
        # so a click on it refers from an external host that same-host matching
        # can't credit; the marker is what lets us count badge clicks as
        # MKB-driven (see _is_mkb_referred). We do NOT stamp the marker on
        # listing_absolute_url itself because that same URL feeds the Instagram
        # share caption and the on-dashboard preview link — only an actual badge
        # click on the salon's external site should carry the badge marker.
        ctx["badge_link_url"] = (
            f"{ctx['listing_absolute_url']}?ref={MKB_BADGE_REF_MARKER}"
            if ctx["listing_absolute_url"]
            else ""
        )
        # WHY: pre-write the exact embed snippet server-side so the template
        # renders identical text to what the owner copies (no client-side string
        # building that could drift). The href carries the badge marker so every
        # shopper who clicks the embedded badge is credited to Miami Knows Beauty.
        # target="_blank" rel="noopener" opens our listing in a new tab (a footer
        # badge shouldn't navigate the salon's visitor away from the salon's own
        # site), the image is sized with inline style so it works in any site
        # footer, and the alt text doubles as the link's accessible name.
        ctx["badge_embed_code"] = (
            f'<a href="{ctx["badge_link_url"]}" '
            f'title="As Featured on Miami Knows Beauty" '
            f'target="_blank" rel="noopener">'
            f'<img src="{ctx["badge_image_url"]}" '
            f'alt="As Featured on Miami Knows Beauty" '
            f'style="width:300px;max-width:100%;height:auto;border:0" />'
            f'</a>'
        )
        # WHY: a ready-to-post Instagram caption so the owner can share their
        # feature in seconds (the "share your feature" affordance). Kept as a
        # simple template — no AI call needed for a good caption — with their
        # listing link appended so followers can tap straight through to the
        # salon's directory page.
        biz_name = business.get("name", "our salon")
        nb_slugs = business.get("neighborhood_slugs") or []
        nb_name = ""
        if nb_slugs:
            nb_match = next(
                (n for n in ctx.get("nav_neighborhoods", []) if n.get("slug") == nb_slugs[0]),
                None,
            )
            nb_name = nb_match.get("name", "") if nb_match else ""
        where = f" in {nb_name}" if nb_name else ""
        ctx["share_caption"] = (
            f"We're featured on {ctx['tenant_label']}! ✨ "
            f"{biz_name} is one of the salons{where} they'd send a friend to. "
            f"Come see us — find us on the guide: {ctx['listing_absolute_url']}"
        )
    else:
        ctx["seo_title"] = "Your account"
        ctx["meta_description"] = "Your Knows Beauty owner account."
        ctx["is_subscribed"] = False

    # WHY: Stripe redirects the owner back to /owners/me?subscribed=1 after a
    # successful checkout. We detect this server-side so we can render a
    # prominent confirmation banner in the HTML (no JavaScript required).
    # We also require is_subscribed=True so that an owner who bookmarks this
    # URL doesn't see a stale "you just subscribed" banner on every visit.
    # In the rare case where the Stripe webhook fires AFTER the browser
    # redirect (is_subscribed is still False on this load), the JS toast in
    # the template acts as a fallback — it reads ?subscribed=1 from the URL
    # and shows a floating confirmation regardless of subscription state.
    ctx["show_subscribed_banner"] = (
        request.query_params.get("subscribed") == "1"
        and ctx["is_subscribed"]
    )
    response = _templates.TemplateResponse(request, "owner_me.html", ctx)
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


@router.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough_page(request: Request) -> HTMLResponse:
    """Shareable owner-journey explainer sent to prospective salon owners.

    WHY: David sends this URL in outreach emails so owners can see the
    journey from "find your listing" to "manage your Featured profile" before
    they decide to claim. It is also linked from the /owners page and the
    pricing page as a "see how it works" path. The page is added to the preview
    gate bypass list so it is always publicly accessible regardless of preview mode.
    """
    tenant = await _require_tenant(request)
    ctx = await _base_context(request, tenant)
    city_name = tenant.city.get("name", "") if tenant.city else ""
    vertical = _vertical_word(tenant.network)
    ctx["seo_title"] = f"How it works — {city_name} Knows {vertical}".strip(" —")
    ctx["meta_description"] = (
        f"From finding your listing to managing your Featured profile on "
        f"{city_name} Knows {vertical}. Claim free, upgrade anytime."
    ).strip()
    ctx["og_image"] = _city_og_image(tenant.city)
    return _templates.TemplateResponse(request, "walkthrough.html", ctx)


def _lastmod_str(raw: Any, fallback: str) -> str:
    """Format a sitemap <lastmod> from a record timestamp, tolerating strings.

    WHY: records in this database store their timestamps inconsistently — most
    are real datetimes, but a chunk of imported editorial guides and salons
    carry an ISO STRING ("2026-06-12T06:00:00Z") instead. Calling .strftime()
    on a string raises AttributeError and would 500 the entire sitemap. This
    helper accepts a datetime (formatted as YYYY-MM-DD), an ISO string (first
    10 chars are already YYYY-MM-DD), or anything else (use the fallback date),
    so one bad record can never take the whole sitemap down.
    """
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d")
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]
    return fallback


def _seo_base_url(request: Request) -> str:
    """Absolute origin (scheme://host) to use for THIS request's robots.txt and
    sitemap.xml URLs.

    WHY this exists: every city edition is its own subdomain
    (miami.knowsbeauty.com, hialeah.knowsbeauty.com, doral.knowsbeauty.com, …)
    and each is its OWN canonical site — the per-page <link rel="canonical">
    keeps the request's own subdomain (see _base_context). robots.txt and
    sitemap.xml MUST agree with that: a city's sitemap has to list ITS OWN host's
    URLs and its robots.txt has to point at its own sitemap. The previous code
    used ``CANONICAL_BASE_URL`` (always set to miami in production) as the base
    for every city, so e.g. hialeah.knowsbeauty.com/sitemap.xml listed
    miami.knowsbeauty.com URLs. Google ignores cross-host sitemap entries, so 25
    of 26 city sites effectively had no sitemap of their own pages.

    This mirrors the page-canonical logic in _base_context EXACTLY so the two
    never drift:
      * No CANONICAL_BASE_URL set -> self-host at the request's own scheme.
      * Production host (the request host IS the canonical apex, e.g.
        knowsbeauty.com, OR ends with "." + apex, e.g. hialeah.knowsbeauty.com)
        -> keep the request's own host, but use the canonical base's scheme so
        the URL is https (production always arrives over https).
      * Dev/staging host (e.g. *.ai.devintensive.com, *.knowsbeauty.localhost)
        -> consolidate to the production .com base so dev pages don't get their
        own (wrong) sitemap/robots host.
    """
    request_host = request.headers.get("host", "")
    canonical_base = get_settings().canonical_base_url.rstrip("/")
    if not canonical_base:
        scheme = request.url.scheme or "https"
        return f"{scheme}://{request_host}"
    parsed = urlparse(canonical_base)
    # Apex = the last two dot-labels of the canonical netloc, e.g.
    # "miami.knowsbeauty.com" -> "knowsbeauty.com". This lets every city
    # subdomain be recognised as a production host.
    apex = ".".join(parsed.netloc.rsplit(".", 2)[-2:])
    host_is_production = request_host == apex or request_host.endswith("." + apex)
    if host_is_production:
        # Self-host (each city is its own canonical site), https from the
        # canonical base.
        return f"{parsed.scheme}://{request_host}"
    # Dev/staging: consolidate to the production .com base.
    return canonical_base


async def _seo_show_live(request: Request) -> bool:
    """Return True when robots.txt / sitemap.xml should render their LIVE form.

    The live form means "allow crawling, list every public URL". It is shown
    whenever the launch gate is OFF (the normal post-launch state).

    WHY a verification override exists: before launch we need to prove that the
    live robots+sitemap are correct WITHOUT actually opening the site to the
    public (flipping the launch gate is David's decision, not an automated one).
    A request carrying the admin API key plus ``?preview_state=live`` renders
    the live form even while the gate is still on, so the deployed site can be
    verified ahead of launch. The override is gated on the admin key so an
    anonymous visitor can never use it to enumerate business slugs before launch
    — exactly the leak the empty-while-gated behaviour was designed to prevent.
    The opposite override (``?preview_state=gated`` with the admin key) forces
    the gated form, which lets us confirm the pre-launch response is unchanged.
    """
    override = request.query_params.get("preview_state", "")
    if override in ("live", "gated"):
        from app.routes.api.v1._auth import admin_key_matches

        api_key = request.headers.get("X-API-Key", "")
        if admin_key_matches(api_key):
            return override == "live"
    # No (valid) override: the live form shows exactly when the launch gate is
    # off. Use the DB-backed helper so the admin toggle is reflected instantly.
    return not await get_preview_mode_enabled()


@router.get("/robots.txt")
async def robots_txt(request: Request) -> HTMLResponse:
    tenant = await resolve_tenant(request.headers.get("host", ""))
    if not tenant:
        return HTMLResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")
    # WHY: while the launch gate is on, every public page redirects to a login
    # wall, so telling Google "Allow: /" would just burn crawl budget on 302s.
    # Return "Disallow: /" until the site is public. The preview-gate bypass for
    # /robots.txt means crawlers actually reach this handler (they aren't
    # redirected first). _seo_show_live() is the single decision that flips this:
    # it returns False while the gate is on and True once it's off, and ALSO
    # honours the admin-key ?preview_state= override so the live response can be
    # verified before launch without flipping the real gate. robots.txt and
    # sitemap.xml both read this one decision, so they flip together on one gate
    # change.
    if not await _seo_show_live(request):
        return HTMLResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")
    # WHY: disallow the auth and owner-dashboard routes so Google doesn't spend crawl
    # budget on pages that always redirect to login or require authentication. The
    # public-facing content pages (/, /b/*, /c/*, /n/*, /owners, /pricing) remain
    # fully crawlable — only the private account flow is excluded.
    # WHY: /owners/verify was removed — that route never existed in this codebase.
    # Having a Disallow for a non-existent URL makes SEO audit tools (Screaming
    # Frog, Semrush, Google Search Console) flag it as a misconfiguration without
    # protecting anything useful. The real owner auth routes are /owners/login
    # (magic-code sign-in form), /owners/auth (the POST endpoint that sends the
    # code), and /owners/me (the authenticated listing dashboard).
    disallowed = "\n".join(
        [
            "Disallow: /owners/login",
            "Disallow: /owners/auth",
            "Disallow: /owners/me",
        ]
    )
    # WHY: the Sitemap: directive must point at THIS host's own sitemap. Each
    # city subdomain is its own canonical site (its pages self-canonical), so
    # hialeah.knowsbeauty.com/robots.txt must reference
    # hialeah.knowsbeauty.com/sitemap.xml — not miami's. _seo_base_url() returns
    # the right origin (self-host in production, the production .com on dev), and
    # mirrors the per-page canonical logic so the two never disagree.
    sitemap_base = _seo_base_url(request)
    return HTMLResponse(
        f"User-agent: *\nAllow: /\n{disallowed}\nSitemap: {sitemap_base}/sitemap.xml\n",
        media_type="text/plain",
    )


@router.get("/sitemap.xml")
async def sitemap(request: Request) -> HTMLResponse:
    # WHY: check preview mode BEFORE _require_tenant so that:
    # (a) the empty sitemap is returned even for unknown test hosts, and
    # (b) we avoid a DB lookup when the result is unconditionally empty anyway.
    # While preview mode is active, return a valid but empty sitemap rather than
    # listing all business slugs. The full slug list being enumerable before
    # launch would let anyone discover business names before the site is public.
    # robots.txt already returns "Disallow: /" during preview, so well-behaved
    # crawlers won't request the sitemap — but this guard closes the gap for
    # direct requests. Once preview mode is off, execution falls through to the
    # full sitemap that lists every business, category, and neighborhood URL.
    # WHY: _seo_show_live() is the SAME single decision robots.txt uses, so the
    # two files flip together on one gate-flip. It also honours the admin-key
    # verification override so the populated sitemap can be checked before launch
    # without opening the site to the public.
    if not await _seo_show_live(request):
        return HTMLResponse(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
            media_type="application/xml",
        )
    tenant = await _require_tenant(request)
    host = request.headers.get("host", "")
    scheme = request.url.scheme
    # WHY: every <loc> for a city's sitemap must point at THAT city's own host.
    # Each city subdomain is its own canonical site (its pages self-canonical), so
    # hialeah.knowsbeauty.com/sitemap.xml must list hialeah URLs — not miami's.
    # Using CANONICAL_BASE_URL (always miami in production) here was the bug: it
    # made every city's sitemap list miami URLs, which Google ignores as
    # cross-host, leaving 25 of 26 city sites with no usable sitemap. _seo_base_url
    # self-hosts in production and consolidates dev hosts to the production .com,
    # mirroring the per-page canonical logic so they never drift.
    # NOTE: the apex/network branch below intentionally does NOT use `base` — it
    # builds each city's home URL from the request host's network suffix, because
    # the apex landing page links out to many city subdomains, each a different
    # host. That branch keeps using `scheme`/`host` directly.
    base = _seo_base_url(request)

    # WHY: today's date is used for pages that don't carry per-record
    # timestamps (static pages, category pages, neighborhood pages). Google
    # uses lastmod to decide how frequently to re-crawl; stale dates cause
    # under-crawling, so a live "today" value on structural pages is the
    # right signal — those pages do change whenever new businesses are added.
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # List of (url, lastmod_str) tuples. Business pages carry per-record
    # updated_at when available; everything else uses today's date.
    # WHY: /pricing and /owners are the two highest-value owner-acquisition
    # pages — if Google can't crawl them the "upgrade to Pro" funnel is
    # invisible to organic search. /guides lists all editorial content.
    entries: List[tuple[str, str]] = [
        (base + "/", today_str),
        (base + "/pricing", today_str),
        (base + "/owners", today_str),
        # WHY: /walkthrough is a shareable owner-acquisition page sent in outreach
        # emails. Including it in the sitemap lets Google surface it organically for
        # searches like "how to claim my salon listing Miami".
        (base + "/walkthrough", today_str),
        (base + "/guides", today_str),
    ]

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
            # that hasn't changed since the site launched. _lastmod_str tolerates
            # the string-vs-datetime storage inconsistency (see its docstring).
            lastmod = _lastmod_str(b.get("updated_at"), today_str)
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
            # WHY: use the guide's actual publish date as lastmod rather than
            # today — telling Google every guide changed daily caused unnecessary
            # re-crawling and weakened the trustworthiness of our lastmod signals.
            # WHY string-tolerant: ~25 of Miami's live guides store published_at /
            # updated_at as an ISO STRING ("2026-06-12T06:00:00Z") rather than a
            # datetime (same import quirk fixed for the guide page in PR #377).
            # Calling .strftime() on a string raises AttributeError, which would
            # 500 the WHOLE sitemap the moment the launch gate flips off — turning
            # a launch into an invisible-to-Google outage. _lastmod_str() handles
            # datetime, ISO string, and missing values uniformly.
            _g_date = g.get("updated_at") or g.get("published_at")
            entries.append((f"{base}/guides/{g['slug']}", _lastmod_str(_g_date, today_str)))
    else:
        # WHY: the bare-apex host (e.g. knowsbeauty.com, no city subdomain)
        # renders the network landing page, which links out to every city — but
        # each city lives on its OWN subdomain (miami.knowsbeauty.com, …), a
        # different host with its own sitemap. Without listing those city home
        # pages here, the only way Google discovers a brand-new city is by
        # crawling the apex landing HTML; a sitemap entry makes the discovery
        # explicit and immediate. We build each city URL from the request host's
        # network suffix rather than CANONICAL_BASE_URL, because the canonical
        # base is a single city's domain and would point every city at the wrong
        # host. Each city's own per-city sitemap still enumerates its businesses.
        suffix = tenant.network_domain_suffix or host
        for city in await content_svc.list_cities(tenant.network["_id"]):
            city_slug = city.get("slug")
            if city_slug:
                entries.append((f"{scheme}://{city_slug}.{suffix}/", today_str))

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
        return templates.TemplateResponse(request, "not_found.html", ctx, status_code=404)
    return HTMLResponse(
        f"<h1>404</h1><p>Unknown site: {host}</p>", status_code=404
    )
