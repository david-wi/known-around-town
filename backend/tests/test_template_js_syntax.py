"""Regression guard: every inline ``<script>`` block in our Jinja templates must
be syntactically valid JavaScript.

WHY this exists
---------------
On 2026-06-16, the shared claim form (rendered on every city's /owners and
/pricing pages) was completely dead site-wide. Two lines of its inline JavaScript
used "smart"/curly double-quotes (U+201C / U+201D) as string delimiters instead
of straight ASCII quotes. Curly quotes are a *syntax error* when used as JS
delimiters, so the browser refused to run the entire script — the claim form,
the owner-conversion engine, and the path into paid Featured upgrades silently
did nothing across all 26 cities. Nothing caught it; only manual end-to-end
clicking found it (fixed in PR #344).

A single bad character in one inline script breaks the whole script with no
server error and no visible warning. This test makes any future JavaScript
syntax error in a template fail CI automatically, so the next curly quote (or
stray brace, or unterminated string) is caught before it ships.

How it works
------------
1. Discover every Jinja template under ``backend/app/templates/`` that contains
   one or more inline ``<script>...</script>`` blocks. We skip external scripts
   (``<script src=...>``) and non-JavaScript blocks (e.g.
   ``type="application/ld+json"``) — those are not JavaScript and must not be
   fed to a JS parser.
2. For each inline JS block, neutralize Jinja so the remaining text is parseable
   as plain JavaScript: every ``{{ ... }}`` expression becomes a harmless
   placeholder identifier, and every ``{% ... %}`` statement is stripped. The
   placeholder is chosen to be valid both in *value* position
   (``var x = {{ y }};`` → ``var x = JINJA_EXPR;``) and inside a JS string
   literal (``'id-{{ y }}'`` → ``'id-JINJA_EXPR'``).
3. Syntax-check each neutralized block with a real JavaScript parser and FAIL —
   naming the template and the parser error — if any block does not parse.

WHY a Python parser instead of ``node --check``
-----------------------------------------------
The "Smoke tests" CI job (.github/workflows/ci.yml) only runs
``actions/setup-python`` and ``pip install -r backend/requirements.txt``. It
never sets up Node. GitHub's ``ubuntu-latest`` image happens to ship a Node
binary today, but relying on undeclared, image-provided tooling is exactly the
fragility this guard exists to prevent: a future runner-image change could drop
Node from ``PATH`` and the check would error or silently skip, re-opening the
hole. ``esprima`` is a pure-Python JS parser pinned in ``requirements.txt``, so
the guard runs deterministically with the same dependencies CI already installs.
"""

from __future__ import annotations

import re
from pathlib import Path

import esprima
import pytest

# WHY: resolve templates relative to this file so the test works from any cwd
# (CI runs pytest with working-directory=backend; a developer may run it from
# the repo root). __file__ is backend/tests/test_template_js_syntax.py, so
# parent.parent is backend/.
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

# WHY: matches a <script ...> opening tag and captures its attributes so we can
# decide whether the block is inline JavaScript we should check. re.IGNORECASE
# because tag/attribute casing is not guaranteed in hand-written HTML.
_SCRIPT_OPEN_RE = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)

# WHY: a Jinja expression ``{{ ... }}`` is replaced with this token. It is a
# valid JavaScript identifier, so it parses in value position
# (``var x = JINJA_EXPR;``); it is also harmless inside a string literal
# (``'prefix-JINJA_EXPR'``). We only care whether the surrounding JavaScript is
# *syntactically* valid — the placeholder never runs — so an undefined
# identifier reference is fine.
_JINJA_EXPR_PLACEHOLDER = "JINJA_EXPR"

# WHY: ``{{ ... }}`` (expressions) and ``{% ... %}`` (statements). Non-greedy and
# DOTALL so multi-line Jinja constructs are matched whole. We do not try to match
# ``{# ... #}`` comments: Jinja strips them before JS ever sees them, and they
# are extremely rare inside <script> bodies.
_JINJA_EXPR_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_JINJA_STMT_RE = re.compile(r"\{%.*?%\}", re.DOTALL)


def _is_inline_javascript(attrs: str) -> bool:
    """Return True if a ``<script ...>`` tag with these attributes is an inline
    JavaScript block we should syntax-check.

    Skips external scripts (``src=...`` — the JS lives in another file) and any
    block whose ``type`` is not JavaScript (e.g. ``application/ld+json``, which
    is data, not code).
    """
    lowered = attrs.lower()
    if "src=" in lowered:
        return False
    # Extract a type="..." value if present.
    type_match = re.search(r"""type\s*=\s*["']([^"']*)["']""", attrs, re.IGNORECASE)
    if type_match:
        script_type = type_match.group(1).strip().lower()
        # WHY: the JavaScript MIME types a browser will actually execute as JS.
        # "module" and "text/javascript" run as JS; "application/ld+json",
        # "application/json", "text/template", etc. do not and must be skipped.
        js_types = {
            "",
            "module",
            "text/javascript",
            "application/javascript",
            "text/ecmascript",
            "application/ecmascript",
        }
        return script_type in js_types
    # No type attribute → defaults to JavaScript.
    return True


def _extract_inline_scripts(html: str) -> list[str]:
    """Return the body text of every inline JavaScript ``<script>`` block in
    ``html`` (external and non-JS blocks excluded)."""
    scripts: list[str] = []
    for open_match in _SCRIPT_OPEN_RE.finditer(html):
        if not _is_inline_javascript(open_match.group(1)):
            continue
        # WHY: find the matching closing tag. Script bodies cannot contain a
        # literal "</script>" without breaking the HTML parser, so a plain
        # search for the next "</script>" is correct and matches browser
        # behavior.
        close_idx = html.lower().find("</script>", open_match.end())
        if close_idx == -1:
            # Unclosed <script> is itself a template bug worth surfacing.
            scripts.append(html[open_match.end():])
        else:
            scripts.append(html[open_match.end():close_idx])
    return scripts


def _neutralize_jinja(js: str) -> str:
    """Replace Jinja so the result is checkable as plain JavaScript.

    ``{{ expr }}`` → ``JINJA_EXPR`` (valid in value position and inside strings);
    ``{% stmt %}`` → removed (control flow that lives between JS statements).
    """
    js = _JINJA_EXPR_RE.sub(_JINJA_EXPR_PLACEHOLDER, js)
    js = _JINJA_STMT_RE.sub("", js)
    return js


def _syntax_error(js: str) -> str | None:
    """Parse ``js`` as JavaScript. Return None if it parses, else the parser's
    error message.

    WHY tolerant=False: we want hard syntax errors (the curly-quote class) to be
    reported. WHY jsx=False: our templates are plain JS, not JSX.

    WHY try parseScript first, then parseModule: classic ``<script>`` bodies are
    scripts, but a ``<script type="module">`` block (which we accept as JS) may
    legitimately use ``import``/``export``, which are syntax errors in script
    mode. Accepting the block if *either* grammar parses avoids a false failure
    on a valid future ES module, while still catching genuine syntax errors —
    a real syntax error (e.g. a curly-quote delimiter) fails in both modes, so
    we report the script-mode error in that case.
    """
    opts = {"tolerant": False, "jsx": False}
    try:
        esprima.parseScript(js, opts)
        return None
    except esprima.Error as script_exc:  # esprima raises its own Error subclass
        try:
            esprima.parseModule(js, opts)
            return None
        except esprima.Error:
            # Both grammars rejected it → a genuine syntax error. Report the
            # script-mode message, which is the relevant one for our classic
            # inline scripts (the overwhelming majority).
            return str(script_exc)


def _discover_templates_with_inline_js() -> list[tuple[str, list[str]]]:
    """Find every template containing at least one inline JS block.

    Returns a list of ``(relative_path, [script_bodies])`` tuples.
    """
    found: list[tuple[str, list[str]]] = []
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        html = path.read_text(encoding="utf-8")
        scripts = _extract_inline_scripts(html)
        if scripts:
            rel = path.relative_to(TEMPLATES_DIR).as_posix()
            found.append((rel, scripts))
    return found


# WHY: build the discovery list once at import time so we can parametrize one
# test case per template — a failure then names exactly which template is broken.
_TEMPLATES_WITH_INLINE_JS = _discover_templates_with_inline_js()


def test_templates_dir_exists():
    """Sanity guard: if the templates directory moves, the whole suite would
    silently check nothing. Fail loudly instead."""
    assert TEMPLATES_DIR.is_dir(), f"Templates directory not found: {TEMPLATES_DIR}"


def test_found_some_inline_scripts():
    """Guard against the discovery silently matching zero templates (e.g. a regex
    regression). We know the codebase has inline scripts (base.html, business.html,
    the claim form, ...), so finding none means the *test* is broken, not the
    templates."""
    assert _TEMPLATES_WITH_INLINE_JS, (
        "Found no templates with inline <script> blocks — the discovery logic is "
        "broken, so this guard would pass vacuously."
    )


@pytest.mark.parametrize(
    "rel_path,scripts",
    _TEMPLATES_WITH_INLINE_JS,
    ids=[t[0] for t in _TEMPLATES_WITH_INLINE_JS],
)
def test_inline_script_blocks_are_valid_javascript(rel_path: str, scripts: list[str]):
    """Every inline <script> block in this template must parse as JavaScript.

    This is the core regression guard. A curly-quote delimiter, an unterminated
    string, a stray brace — anything that makes the browser refuse to run the
    script — fails here with the template name and the parser error.
    """
    for index, raw_js in enumerate(scripts):
        neutralized = _neutralize_jinja(raw_js)
        error = _syntax_error(neutralized)
        assert error is None, (
            f"Inline <script> block #{index + 1} in template '{rel_path}' is not "
            f"valid JavaScript: {error}\n"
            f"(This is the same failure class as PR #344's curly-quote bug — a "
            f"syntax error here breaks the entire page script silently in the "
            f"browser.)"
        )


# ── Red-green self-test ──────────────────────────────────────────────────────
# WHY: a guard that never goes red is not a guard. These cases prove the parser
# actually rejects the exact bug class (curly-quote delimiters) and accepts clean
# JS — so we know a real future regression would be caught, not silently passed.

# WHY: U+201C / U+201D used as string delimiters — the literal PR #344 bug.
_CURLY_QUOTE_BUG_JS = (
    "var msg = “We couldn't find that listing”;\n"
    "console.log(msg);\n"
)

# WHY: straight-quote version of the same line — valid JS, must parse clean.
_CLEAN_JS = (
    'var msg = "We couldn\'t find that listing";\n'
    "console.log(msg);\n"
)


def test_self_test_curly_quote_delimiters_fail():
    """The injected curly-quote bug MUST be detected as a syntax error.

    If this ever passes, the parser/neutralizer can no longer see the very class
    of bug this whole file exists to catch.
    """
    error = _syntax_error(_neutralize_jinja(_CURLY_QUOTE_BUG_JS))
    assert error is not None, (
        "Curly-quote string delimiters parsed as valid JavaScript — the guard is "
        "no longer catching the PR #344 bug class."
    )


def test_self_test_clean_js_passes():
    """Clean JavaScript (straight quotes) must parse without error, so the guard
    does not produce false positives on correct templates."""
    assert _syntax_error(_neutralize_jinja(_CLEAN_JS)) is None


def test_self_test_neutralizer_handles_jinja_in_value_and_string_positions():
    """The neutralizer must produce valid JS whether Jinja appears as a bare
    value or inside a string literal — both occur in our real templates
    (claim_form.html uses ``var DIRECTORY = {{ ... | tojson }};`` while
    business.html uses ``'claim-bar-dismissed-{{ business.slug }}'``)."""
    value_position = "var DIRECTORY = {{ claim_directory | tojson | safe }};"
    string_position = "var key = 'claim-bar-dismissed-{{ business.slug }}';"
    statement_around = "{% if x %}var a = 1;{% endif %}"
    for snippet in (value_position, string_position, statement_around):
        assert _syntax_error(_neutralize_jinja(snippet)) is None, (
            f"Neutralizer produced unparseable JS for: {snippet!r}"
        )
