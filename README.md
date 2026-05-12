# Who Knows Local

A network of beautiful, AI-assisted local guide sites. One codebase, many cities, many verticals.

The same backend serves every site in the network. Whoever visits
`miami.knowsbeauty.ai.devintensive.com` and `austin.knowshealth.ai.devintensive.com`
is hitting the same server. The server reads the hostname, figures out which **network**
(Beauty, Wellness, Health, …) and which **city** the visitor wants, and renders the
matching content from MongoDB.

## What's in here

```
backend/
  app/
    main.py            FastAPI entry point
    config.py          Settings (env vars)
    database.py        MongoDB client + index setup
    models/            Pydantic models for every collection
    services/          Tenant resolution, copy-block fallback, business lookups
    routes/public/     Server-rendered pages (Jinja2)
    routes/api/v1/     JSON API for content management
    templates/         Jinja2 templates
    static/            CSS + lightweight JS
  seed/
    seed_networks.py   Beauty, Wellness, Health networks with full category maps
    seed_miami.py      Miami across all three networks + neighborhoods + sample businesses
  tests/
docker-compose.yml      Local dev with MongoDB
docker-compose.prod.yml Production (Traefik labels)
.env.example
```

## Run locally

```bash
cp .env.example .env
docker compose up --build
# in another terminal, once the backend is up:
docker compose exec backend python -m seed.seed_networks
docker compose exec backend python -m seed.seed_miami
```

Then point your `/etc/hosts` to the local dev subdomains:

```
127.0.0.1 miami.knowsbeauty.localhost miami.knowshealth.localhost miami.knowswellness.localhost
```

Visit `http://miami.knowsbeauty.localhost:8000/` and you should see Miami Knows Beauty.

## URL structure

| Page | URL |
|------|-----|
| City home | `miami.knowsbeauty.ai.devintensive.com/` |
| Category | `miami.knowsbeauty.ai.devintensive.com/c/hair` |
| Neighborhood | `miami.knowsbeauty.ai.devintensive.com/n/brickell` |
| Business profile | `miami.knowsbeauty.ai.devintensive.com/b/glamour-nails` |
| Category in neighborhood | `miami.knowsbeauty.ai.devintensive.com/n/brickell/c/nails` |
| Editorial guide | `miami.knowsbeauty.ai.devintensive.com/guides/best-blowouts-before-art-basel` |

## Editing wording

Every page surface (eyebrow text, CTA labels, footer copy, claim-modal headings…) is a
record in the `copy_blocks` collection. Update the value, refresh, the page reflects it.
No code change, no deploy.

Lookup order (most specific wins):

```
business -> category(city) -> category(network default) -> city -> network -> global default
```

## Status

Initial scaffold. Public pages render from the DB; JSON API supports CRUD. Admin UI is
the JSON API for now — a React admin panel can come later.
