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
WCAG_AA = 4.5  # WHY: WCAG 2.1 AA minimum for normal-size body text.


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


def test_contrast_helper_matches_known_values():
    """Sanity-check the math against the values that motivated the fix."""
    assert round(contrast(STONE["400"], WHITE), 2) == 2.52  # old bug
    assert round(contrast(STONE["500"], WHITE), 2) == 4.80  # the fix
    assert round(contrast(STONE["500"], STONE["950"]), 2) == 4.12  # old bug
    assert round(contrast(STONE["400"], STONE["950"]), 2) == 7.83  # the fix
