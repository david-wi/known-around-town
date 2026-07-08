"""Regression guard: every color/opacity utility class a template uses
(`bg-black/90`, `border-stone-200/40`, `hover:decoration-white/70`, ...)
must have a compiled selector in the precompiled static/css/reference.css.

WHY: this app ships a PREcompiled Tailwind sheet — there is no CSS build at
render time. Jinja happily renders any class string, so a template author can
type `from-stone-950/90` and nothing complains, but if that selector was never
compiled into reference.css the class is a silent no-op. That is exactly how
the homepage "By neighborhood" tile labels went white-on-white illegible
(`from-stone-950/90 via-stone-950/5` — neither compiled, so the label scrim
computed to `background-image: none`), and how the photo-lightbox backdrop
went fully transparent (`bg-black/90` — reference.css compiles NO bg-black
opacity at all).

This generalizes the retired test_text_white_opacity.py (added for the
Voice-page invisible-CTA bug, PR #496) from text-white only to EVERY
opacity-suffixed color utility: text/bg/from/via/to/border/decoration/ring/
divide/outline/shadow/fill/stroke, with any variant prefixes (hover:,
group-hover:, md:, ...).

How the compiled sheet encodes things (verified against reference.css):
- base `bg-white/95`             -> selector `.bg-white\\/95`
- `hover:bg-white/10`            -> `.hover\\:bg-white\\/10:hover`
- `group-hover:from-stone-950/95`-> `.group:hover .group-hover\\:from-stone-950\\/95`
- `md:` variants                 -> `.md\\:...` inside a media query
In every case the class token itself appears verbatim with `:` escaped to
`\\:` and `/` escaped to `\\/`, so the check is: the escaped token must occur
in the sheet as a class selector (`.` prefix, followed by a selector
delimiter). A variant-prefixed token whose compiled form doesn't exist at all
(e.g. `hover:decoration-white/70` — no hover:decoration-white is compiled at
ANY opacity) fails the same way.

Comments are stripped first: several templates document *previously fixed*
no-op classes in `{# ... #}` / `<!-- ... -->` prose (e.g. "the earlier
bg-white/70"), and those must not trip the guard.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TEMPLATES = BACKEND / "app" / "templates"
REFERENCE_CSS = BACKEND / "app" / "static" / "css" / "reference.css"

# Any opacity-suffixed color utility, with optional variant prefixes.
# The lookbehind stops mid-token false hits (e.g. the `white/40` tail of
# `decoration-white/40` re-matching, or url path segments); the lookahead
# makes sure we consumed the whole opacity (so `/9` can't "match" inside
# `/95`). Fractions like `w-1/2` or `translate-x-1/3` never match because the
# utility prefix list is colors-only.
CLASS_RE = re.compile(
    r"(?<![\w/:.\[-])"
    r"(?:[a-z][a-z-]*:)*"
    r"(?:text|bg|from|via|to|border|decoration|ring|divide|outline|shadow|fill|stroke)"
    r"-[a-z]+(?:-\d+)?/\d+"
    r"(?![\w/-])"
)

COMMENT_RE = re.compile(r"\{#.*?#\}|<!--.*?-->", re.DOTALL)


def _blank_comments(text: str) -> str:
    """Remove Jinja and HTML comments, keeping newlines so line numbers hold."""
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _is_compiled(css: str, token: str) -> bool:
    """True if reference.css contains a class selector for this exact token."""
    needle = "." + token.replace(":", "\\:").replace("/", "\\/")
    for match in re.finditer(re.escape(needle), css):
        following = css[match.end():match.end() + 1]
        # The selector must END here (next char is `{`, `,`, `:`, space, ...).
        # A continuation char would mean we matched a prefix of a LONGER class
        # (e.g. `.text-white\/9` inside `.text-white\/95`).
        if not following or not re.match(r"[0-9A-Za-z_-]", following):
            return True
    return False


def test_every_opacity_utility_in_templates_is_compiled():
    css = REFERENCE_CSS.read_text()
    problems = []
    for template in sorted(TEMPLATES.rglob("*.html")):
        rel = template.relative_to(TEMPLATES)
        text = _blank_comments(template.read_text())
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in CLASS_RE.finditer(line):
                token = match.group(0)
                if not _is_compiled(css, token):
                    problems.append(
                        f"{rel}:{lineno}: `{token}` has no compiled selector "
                        "in reference.css"
                    )
    assert not problems, (
        "opacity utility classes with no compiled rule — these are silent "
        "no-ops (the property just doesn't apply):\n"
        + "\n".join(problems)
        + "\nFix: swap to the nearest compiled variant (inspect reference.css"
        " for what exists) or compile the class into the sheet."
    )


def test_guard_catches_known_bug_classes():
    """Meta-check: the scanner must recognize the exact class shapes from the
    original defects, so a regex regression can't silently gut the guard."""
    for known_bad in (
        "bg-black/90",                  # lightbox backdrop, no bg-black/NN compiled
        "from-stone-950/90",            # neighborhood tile scrim
        "via-stone-950/5",              # single-digit opacity
        "hover:decoration-white/70",    # variant prefix, nothing compiled
        "border-stone-200/40",
        "to-amber-50/40",
        "decoration-white/40",
    ):
        match = CLASS_RE.search(f'<div class="p-4 {known_bad} flex">')
        assert match and match.group(0) == known_bad, (
            f"CLASS_RE no longer matches `{known_bad}` — the guard would miss "
            "the original bug class"
        )
    css = REFERENCE_CSS.read_text()
    # Encoding checks against selectors known to exist in the shipped sheet.
    assert _is_compiled(css, "text-white/95")
    assert _is_compiled(css, "hover:bg-white/10")
    assert _is_compiled(css, "group-hover:from-stone-950/95")
    # ...and known not to.
    assert not _is_compiled(css, "text-white/9")   # prefix of /95, must not hit
    assert not _is_compiled(css, "bg-black/90")
