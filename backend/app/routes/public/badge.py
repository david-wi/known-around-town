"""Public "As Featured on Miami Knows Beauty" website badge.

A Featured salon embeds this badge on its own website (typically in the footer)
wrapped in a link to its Miami Knows Beauty listing. That sends the salon's own
website visitors to its directory page AND creates an SEO backlink from every
salon's site — the highest-leverage shopper-acquisition artifact in the
acquisition strategy (one build, every Featured salon, traffic + ranking signal).

Route: GET /badge/featured.svg

WHY a dedicated route (not a /assets/ static file): the badge image is embedded
on EXTERNAL salon websites, so it must load for the whole public internet even
while our own site is still private behind the preview gate. Serving it from its
own /badge/ path lets us exempt exactly that one path in the preview-gate
allowlist (see middleware/preview_gate.py) — surgical, unambiguous, and it
exposes no gated directory content (the SVG is a static brand mark with no
private data). A file under /assets/ would have worked too, but /assets/ already
carries the login page's own CSS/JS, so a path-prefix exemption there would be
broader than we want. The dedicated /badge/ prefix keeps the exemption tight.
"""

from __future__ import annotations

import html
from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()

# WHY: 1-day browser cache. The badge mark is effectively static, but we keep it
# to a day (not a year) so a future brand tweak propagates to every embedding
# salon site within 24 hours without us having to version the URL. `public` lets
# shared/CDN caches store it; `immutable` is intentionally omitted so the day-long
# refresh actually happens.
_CACHE_CONTROL = "public, max-age=86400"

# Brand tokens, taken from the site's compiled theme (see favicon.svg and the
# beauty network theme in routes/public/pages.py):
#   #1c1917  near-black "stone-900" card background (matches site chrome)
#   #fb7185  rose-400 accent star (the beauty network's accent color)
#   #fff7ed  warm off-white ("orange-50") used for primary text
#   #fdba74  warm amber ("orange-300") for the small "AS FEATURED ON" eyebrow
#   #a8a29e  muted "stone-400" for the de-emphasized domain line
_BG = "#1c1917"
_ACCENT = "#fb7185"
_TEXT = "#fff7ed"
_EYEBROW = "#fdba74"
_SUBTLE = "#a8a29e"  # stone-400, for the trailing ".com" de-emphasis


def build_badge_svg(
    site_name: str,
    domain_name: str,
) -> str:
    # Default parameters for "Miami Knows Beauty"
    viewbox_width = 340
    font_size = 20
    text_y = 63
    
    # If the site name is longer, adjust them
    name_len = len(site_name)
    if name_len > 18:
        font_size = max(14, int(20 * 18 / name_len))
        if font_size < 17:
            text_y = 61
        estimated_text_width = int(name_len * font_size * 0.55)
        viewbox_width = max(340, 64 + estimated_text_width + 30)

    # Adjust for very long domains if needed, though they usually fit
    domain_len = len(domain_name)
    estimated_domain_width = int(domain_len * 6)
    viewbox_width = max(viewbox_width, 64 + estimated_domain_width + 30)

    rect_width = viewbox_width - 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {viewbox_width} 96" role="img" aria-label="As Featured on {html.escape(site_name)}">
  <title>As Featured on {html.escape(site_name)}</title>
  <rect x="1" y="1" width="{rect_width}" height="94" rx="18" fill="{_BG}"/>
  <rect x="1" y="1" width="{rect_width}" height="94" rx="18" fill="none" stroke="{_ACCENT}" stroke-opacity="0.35" stroke-width="1.5"/>
  <!-- four-point sparkle star, the site's ✦ motif -->
  <path d="M34 30 c2.2 8.4 5.4 11.6 13.8 13.8 c-8.4 2.2 -11.6 5.4 -13.8 13.8 c-2.2 -8.4 -5.4 -11.6 -13.8 -13.8 c8.4 -2.2 11.6 -5.4 13.8 -13.8 z" fill="{_ACCENT}"/>
  <text x="64" y="37" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="11" font-weight="700" letter-spacing="2.2" fill="{_EYEBROW}">AS FEATURED ON</text>
  <text x="64" y="{text_y}" font-family="Georgia, Cambria, Times New Roman, serif" font-size="{font_size}" font-weight="700" fill="{_TEXT}">{html.escape(site_name)}</text>
  <text x="64" y="80" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="10" letter-spacing="0.5" fill="{_SUBTLE}">{html.escape(domain_name)}</text>
</svg>"""


@router.get("/badge/featured.svg")
async def featured_badge(request: Request) -> Response:
    """Return the 'As Featured on Miami Knows Beauty' badge as an SVG image.

    Publicly reachable even while the preview gate is on (see preview_gate.py),
    because Featured salons embed it on their own external websites.
    """
    from app.services.tenant import resolve_tenant
    host = request.headers.get("host", "")
    tenant = await resolve_tenant(host)

    site_name = "Miami Knows Beauty"
    domain_name = "miami.knowsbeauty.com"

    if tenant and tenant.city:
        network_name = tenant.network.get("name", "Knows Beauty")
        city_name = tenant.city.get("name", "Miami")
        site_name = f"{city_name} {network_name}"
        domain_name = f"{tenant.city_slug}.{tenant.network_domain_suffix}"

    svg_content = build_badge_svg(site_name, domain_name)

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Cache-Control": _CACHE_CONTROL},
    )
