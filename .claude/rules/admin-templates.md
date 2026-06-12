# Admin Templates — Gotchas

## Tailwind JIT and dynamic class names

Tailwind's JIT compiler scans source files for complete class names at build time.
Any class name that's assembled at runtime — including in Jinja2 templates — gets
purged from the output CSS.

**Wrong (class gets purged):**
```html
{% set color = "amber" %}
<div class="bg-{{ color }}-400">...</div>  {# bg-amber-400 never appears literally #}
```

**Right (inline style, or hardcode the full class name):**
```html
<div style="background-color: #fbbf24">...</div>
```

If you need several color variants (e.g. funnel progress bars), use a Jinja2 tuple/list
with hardcoded hex values and apply them via `style="background-color: {{ hex }}"`.

## Admin layout and the `attach_templates` pattern

Every admin router follows a two-step wiring pattern:
1. Module-level `_templates: Jinja2Templates | None = None` + `attach_templates(t)` function
2. In `main.py`: call `<module>.attach_templates(templates)` then `app.include_router(<module>.router)`

The attach call must come BEFORE `include_router` because FastAPI resolves the template
reference at request time, but it's cleaner to call attach right after all templates are
built. See `claims_admin.py` for the canonical pattern.

## Admin route registration order

Admin routers must be registered BEFORE the public SSR catch-all in `main.py`.
The public router catches broad URL patterns and will swallow `/admin/*` if registered first.

## Admin API key bypass (preview gate)

The preview gate middleware now allows requests with a valid `X-API-Key` header
to pass through without a `preview_token` cookie. This means admin scripts can
call any API endpoint directly from outside a browser:

```bash
curl -H "X-API-Key: <ADMIN_API_KEY>" https://miami.knowsbeauty.com/api/v1/businesses/by-slug/<city_id>/<slug>
```

The admin key is in `/opt/known-around-town/.env` as `ADMIN_API_KEY`. The
city UUID for Miami is `c9a53e0a-638c-43f9-96c0-d72a6e830c5c`.

## Seed data JSON safety

`backend/seed/_real_businesses.json` contains Unicode curly-quote characters
inside string values (e.g., `"invisible cut"`). The Edit tool corrupts this
file by converting ASCII `"` delimiters to curly quotes when it matches a
block containing them. Always use Python's `json` module (load → modify → dump)
to patch this file — never the Edit tool.
