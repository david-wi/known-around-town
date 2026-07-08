"""Regression guard: every text-white/NN opacity utility a template uses
must have a compiled selector in the precompiled static/css/reference.css.

WHY: this app ships a PREcompiled Tailwind sheet — there is no CSS build at
render time. Jinja happily renders any class string, so a template author can
type `text-white/90` and nothing complains, but if that selector was never
compiled into reference.css the class is a silent no-op and the element just
inherits its ancestor's color. That is exactly how the Voice for Salons hero
CTA went invisible: reference.css compiles /30 /55 /60 /70 /75 /80 /85 /95 —
everything EXCEPT /90 — so the `text-white/90` links inherited near-black
text on a near-black hero (1.13:1 contrast).

Two checks, matching how the compiled sheet encodes things:
- base `text-white/NN`   -> reference.css must contain `.text-white\\/NN`.
- `hover:text-white/NN`  -> reference.css must contain
  `.hover\\:text-white\\/NN:hover` (hover variants compile with an escaped
  `hover\\:` prefix plus a `:hover` pseudo-class, e.g. the existing
  `.hover\\:text-white:hover`). Today the sheet compiles NO
  hover:text-white/NN variants at all, so any such class in a template is a
  silent no-op and fails here — use plain `hover:text-white` (compiled) or a
  compiled opacity step instead.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
TEMPLATES = BACKEND / "app" / "templates"
REFERENCE_CSS = BACKEND / "app" / "static" / "css" / "reference.css"

# A text-white/NN utility, optionally hover:-prefixed. The lookbehind stops
# false hits inside longer tokens (e.g. `decoration-white/40` can't match
# because the literal `text-white` is required; the lookbehind keeps a
# hypothetical `md:text-white/NN` from half-matching as a bare class).
CLASS_RE = re.compile(r"(?<![\w/:-])(hover:)?text-white/(\d+)")


def test_text_white_opacity_variants_are_compiled():
    css = REFERENCE_CSS.read_text()
    problems = []
    for template in sorted(TEMPLATES.rglob("*.html")):
        rel = template.relative_to(TEMPLATES)
        for lineno, line in enumerate(template.read_text().splitlines(), start=1):
            for match in CLASS_RE.finditer(line):
                is_hover, opacity = match.group(1), match.group(2)
                if is_hover:
                    selector = f".hover\\:text-white\\/{opacity}:hover"
                    hint = (
                        "no hover:text-white/NN variants are compiled — use "
                        "`hover:text-white` or compile the variant first"
                    )
                else:
                    selector = f".text-white\\/{opacity}"
                    hint = "use a compiled opacity step or compile this one first"
                if selector not in css:
                    problems.append(
                        f"{rel}:{lineno}: `{match.group(0)}` has no compiled "
                        f"selector in reference.css ({hint})"
                    )
    assert not problems, (
        "text-white opacity utilities with no compiled rule — these are "
        "silent no-ops that inherit the parent color:\n" + "\n".join(problems)
    )
