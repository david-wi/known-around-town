"""Regression guard: text/background color pairs we deliberately fixed for
WCAG AA contrast must keep passing 4.5:1.

This is a *behavioral* test, not a string match: it reads the live shade
(text-stone-NNN) used on each element from the template, maps it to its real
hex value, and computes the actual WCAG contrast ratio against the known
background. If someone nudges a shade back to a failing value, the recomputed
ratio drops below 4.5 and this test fails — regardless of which class string
they used.

The authoritative end-to-end check is the axe-core audit run against the
rendered pages after deploy; this guard just stops the specific regressions
from creeping back into the templates.

Why these elements: the "(optional)" field labels were `text-stone-400` on a
white form (2.5:1 — unreadable for low-vision users), and the footer's muted
text was `text-stone-500` on the near-black footer (4.1:1 — just under AA).
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

# Tailwind stone palette (the only shades these elements use).
STONE = {
    "300": "#d6d3d1",
    "400": "#a8a29e",
    "500": "#78716c",
    "600": "#57534e",
    "700": "#44403c",
    "800": "#292524",
    "900": "#1c1917",
    "950": "#0c0a09",
}
WHITE = "#ffffff"
# Tailwind amber palette (accent text such as the "Editor's Pick" badge).
AMBER = {"200": "#fde68a", "300": "#fcd34d", "500": "#f59e0b", "600": "#d97706",
         "700": "#b45309", "800": "#92400e"}
WCAG_AA = 4.5  # WHY: WCAG 2.1 AA minimum for normal-size body text.

# Page-specific muted metadata that must stay readable on the near-white pages.
# (template, substring identifying the element). The shade on that line is read
# live and its real contrast computed, so a regression to a faint shade fails
# here regardless of which class string is used. Background is treated as pure
# white; the real page bg (#fbfbfa) is a hair darker, and the live axe audit is
# the authoritative end-to-end check.
PAGE_MUTED_ON_WHITE = [
    ("home.html", "tabular-nums text-stone-"),                    # ranked-list ordinals
    ("partials/business_card.html", "({{ b.google_review_count"),  # card review count
    ("partials/business_card.html", "{{ b.price_cues }}"),        # card price cues
    ("business.html", "({{ business.google_review_count"),         # listing review count
    ("business.html", ">Closed</span>"),                         # listing closed-day label
    ("business.html", "(or email above)"),                       # listing phone hint
]


def _lin(c: int) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hexs: str) -> float:
    r, g, b = (int(hexs[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg: str, bg: str) -> float:
    a, b = _luminance(fg) + 0.05, _luminance(bg) + 0.05
    return max(a, b) / min(a, b)


def _shades_for(template: str, needle: str) -> list[str]:
    """Return the stone shade(s) used on spans/elements containing `needle`."""
    html = (TEMPLATES / template).read_text()
    shades = []
    for line in html.splitlines():
        if needle in line:
            for m in re.finditer(r"text-stone-(\d{3})", line):
                shades.append(m.group(1))
    return shades


def test_optional_labels_pass_aa_on_white():
    """Every "(optional)" field label must be readable on a white form."""
    found = False
    for tpl in ("partials/claim_form.html", "owner_me.html"):
        for shade in _shades_for(tpl, "(optional)"):
            found = True
            ratio = contrast(STONE[shade], WHITE)
            assert ratio >= WCAG_AA, (
                f"{tpl}: '(optional)' label uses stone-{shade} on white "
                f"= {ratio:.2f}:1, below WCAG AA {WCAG_AA}:1"
            )
    assert found, "expected to find at least one '(optional)' label to check"


def test_footer_muted_text_passes_aa_on_dark():
    """Footer muted text sits on the near-black footer (bg-stone-950)."""
    html = (TEMPLATES / "partials/footer.html").read_text()
    assert "bg-stone-950" in html, "footer background changed — revisit this test"
    shades = set(re.findall(r"text-stone-(\d{3})", html))
    # Only the muted/secondary shades matter; links (stone-300) and white are fine.
    for shade in shades:
        ratio = contrast(STONE[shade], STONE["950"])
        assert ratio >= WCAG_AA, (
            f"footer.html: text-stone-{shade} on stone-950 = {ratio:.2f}:1, "
            f"below WCAG AA {WCAG_AA}:1"
        )


def test_page_specific_muted_text_passes_aa_on_white():
    """Small grey metadata on the white pages (review counts, hours, ordinals,
    form hints) must still meet AA — these are real content, not decoration."""
    for tpl, needle in PAGE_MUTED_ON_WHITE:
        shades = _shades_for(tpl, needle)
        assert shades, f"{tpl}: no stone shade found near '{needle}' — test out of date"
        for shade in shades:
            ratio = contrast(STONE[shade], WHITE)
            assert ratio >= WCAG_AA, (
                f"{tpl}: text near '{needle}' uses stone-{shade} on white "
                f"= {ratio:.2f}:1, below WCAG AA {WCAG_AA}:1"
            )


def test_editors_pick_amber_text_passes_aa_on_white():
    """The list-view "Editor's Pick" accent puts amber on the actual words
    (not just the decorative star), so it must meet AA on the white page."""
    html = (TEMPLATES / "home.html").read_text()
    # Match only amber applied to the readable phrase ("...">★ Editor"), not the
    # amber-500 star icons in the photo-card pills (where the words are stone-900).
    matches = re.findall(r'text-amber-(\d{3})">★ Editor', html)
    assert matches, "expected an amber 'Editor's Pick' text accent to check"
    for shade in matches:
        ratio = contrast(AMBER[shade], WHITE)
        assert ratio >= WCAG_AA, (
            f"home.html: 'Editor's Pick' text uses amber-{shade} on white "
            f"= {ratio:.2f}:1, below WCAG AA {WCAG_AA}:1"
        )


def _blend(hexs, op, bg=(255, 255, 255)):
    """Effective color of `hexs` rendered at CSS opacity `op` over `bg`.
    A parent `opacity-70` dims text toward the page background, lowering its
    real contrast below what the class alone implies."""
    f = (int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16))
    e = tuple(round(op * f[i] + (1 - op) * bg[i]) for i in range(3))
    return "#%02x%02x%02x" % e


def test_network_landing_faded_card_passes_aa_through_opacity():
    """The network landing's "coming soon" city cards are wrapped in opacity-70.
    Their heading + badge text must be dark enough to still meet AA *through*
    that fade — otherwise the faded look makes them unreadable (the bug fixed
    here). We model the opacity-70 blend over white and require >= 4.5:1."""
    html = (TEMPLATES / "network_landing.html").read_text()
    assert "opacity-70" in html, "faded-card opacity changed — revisit this test"
    targets = [
        ("text-xl font-light text-stone-", "coming-soon card heading"),
        ("border border-stone-200 text-stone-", "coming-soon card badge"),
    ]
    for needle, label in targets:
        shades = []
        for line in html.splitlines():
            if needle in line:
                for m in re.finditer(r"text-stone-(\d{3})", line):
                    shades.append(m.group(1))
        assert shades, f"network_landing.html: no shade found for {label} ('{needle}')"
        for shade in shades:
            eff = _blend(STONE[shade], 0.70)
            ratio = contrast(eff, WHITE)
            assert ratio >= WCAG_AA, (
                f"network_landing.html {label}: stone-{shade} at opacity-70 "
                f"renders as {eff} = {ratio:.2f}:1, below WCAG AA {WCAG_AA}:1"
            )


def test_contrast_helper_matches_known_values():
    """Sanity-check the math against the values that motivated the fix."""
    assert round(contrast(STONE["400"], WHITE), 2) == 2.52  # old bug
    assert round(contrast(STONE["500"], WHITE), 2) == 4.80  # the fix
    assert round(contrast(STONE["500"], STONE["950"]), 2) == 4.12  # old bug
    assert round(contrast(STONE["400"], STONE["950"]), 2) == 7.83  # the fix
