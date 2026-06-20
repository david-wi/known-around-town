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

from fastapi import APIRouter
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

# WHY: the badge is a self-contained SVG with all type drawn as <text> in a
# common system font stack. Embedding the font as <text> (rather than outlined
# paths) keeps the file tiny and crisp at any size, and the generic font stack
# renders consistently without shipping a webfont. The pill shape, dark card,
# rose star, and warm-white wordmark mirror the site's editorial look so the
# badge reads as "official" on a salon's site rather than a generic widget.
#
# viewBox 0 0 340 96 → a ~3.5:1 landscape pill that sits naturally in a website
# footer. The width is 340 (not 300) so the serif "Miami Knows Beauty" wordmark
# at font-size 20 clears the rounded right corner with comfortable padding — an
# earlier 300-wide box clipped the final letter. width/height are omitted from
# the root <svg> so the embed code can size it with CSS (the dashboard snippet
# sets width:300 / height:auto, and the SVG scales to fit that box).
_BADGE_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 96" role="img" aria-label="As Featured on Miami Knows Beauty">
  <title>As Featured on Miami Knows Beauty</title>
  <rect x="1" y="1" width="338" height="94" rx="18" fill="{_BG}"/>
  <rect x="1" y="1" width="338" height="94" rx="18" fill="none" stroke="{_ACCENT}" stroke-opacity="0.35" stroke-width="1.5"/>
  <!-- four-point sparkle star, the site's ✦ motif -->
  <path d="M34 30 c2.2 8.4 5.4 11.6 13.8 13.8 c-8.4 2.2 -11.6 5.4 -13.8 13.8 c-2.2 -8.4 -5.4 -11.6 -13.8 -13.8 c8.4 -2.2 11.6 -5.4 13.8 -13.8 z" fill="{_ACCENT}"/>
  <text x="64" y="37" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="11" font-weight="700" letter-spacing="2.2" fill="{_EYEBROW}">AS FEATURED ON</text>
  <text x="64" y="63" font-family="Georgia, Cambria, Times New Roman, serif" font-size="20" font-weight="700" fill="{_TEXT}">Miami Knows Beauty</text>
  <text x="64" y="80" font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" font-size="10" letter-spacing="0.5" fill="{_SUBTLE}">miami.knowsbeauty.com</text>
</svg>"""


@router.get("/badge/featured.svg")
async def featured_badge() -> Response:
    """Return the 'As Featured on Miami Knows Beauty' badge as an SVG image.

    Publicly reachable even while the preview gate is on (see preview_gate.py),
    because Featured salons embed it on their own external websites.
    """
    return Response(
        content=_BADGE_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": _CACHE_CONTROL},
    )
