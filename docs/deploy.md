# Deploy guide — Who Knows Local

This file documents how to put the site on the shared dev server
(`174.138.81.31`) where Expertly's other dev apps already live, plus the DNS
that makes `miami.knowsbeauty.ai.devintensive.com` resolve.

## First-time setup on the server

```bash
ssh -p 2222 root@174.138.81.31
mkdir -p /opt/who-knows-local
git clone https://github.com/david-wi/who-knows-local.git /opt/who-knows-local

# Production env. MongoDB Atlas connection string is already in
# /opt/expertly-develop/.env as MONGODB_ATLAS_URL — point this app at the
# same cluster but a separate database name so it doesn't share collections.
cat > /opt/who-knows-local/.env <<'EOF'
MONGODB_URL=mongodb+srv://expertly-app:<password>@expertly.xuf7uv.mongodb.net
MONGODB_DATABASE=who_knows_local
NETWORK_DOMAINS=beauty:knowsbeauty.ai.devintensive.com,wellness:knowswellness.ai.devintensive.com,health:knowshealth.ai.devintensive.com,beauty:knowsbeauty.com,wellness:knowswellness.com,health:knowshealth.com
ADMIN_API_KEY=<generate-one-with: openssl rand -base64 32>
EOF

bash /opt/who-knows-local/scripts/deploy.sh
```

## DNS records (need to be added in DigitalOcean)

For the dev URLs the user asked about, add these A records pointing at
`174.138.81.31`:

| Type | Host | Value |
|------|------|-------|
| A | `*.knowsbeauty.ai.devintensive.com` | 174.138.81.31 |
| A | `knowsbeauty.ai.devintensive.com` | 174.138.81.31 |
| A | `*.knowswellness.ai.devintensive.com` | 174.138.81.31 |
| A | `knowswellness.ai.devintensive.com` | 174.138.81.31 |
| A | `*.knowshealth.ai.devintensive.com` | 174.138.81.31 |
| A | `knowshealth.ai.devintensive.com` | 174.138.81.31 |

Note: `ai.devintensive.com` lives in the same DigitalOcean account as the
other Expertly dev domains. Wildcard records (`*.knowsbeauty...`) let any
city subdomain resolve without needing one record per city. The Let's
Encrypt cert is still issued per-hostname via the existing HTTP-01 flow, so
each city's first request takes an extra second to provision a cert; after
that it's cached.

For production (`knowsbeauty.com` etc.), do the same wildcard A record at
the registrar of those domains. The current router rule already lists the
production hostnames so it'll just work the moment DNS is in place.

## CI auto-deploy

`.github/workflows/deploy.yml` triggers on push to `main`. Add three
secrets in the GitHub repo settings:

- `DEPLOY_HOST` — `174.138.81.31`
- `DEPLOY_USER` — `root`
- `DEPLOY_KEY` — the same SSH private key the other Expertly repos use to
  deploy (`~/.ssh/do_droplet` on the deploy-orchestrator account)

Until that's wired, deploys are a single SSH command:

```bash
ssh -p 2222 root@174.138.81.31 'bash /opt/who-knows-local/scripts/deploy.sh'
```

## Health check

```bash
curl https://miami.knowsbeauty.ai.devintensive.com/health
# {"status":"ok"}
```

## Adding a new city

```bash
# 1. Add the A record (or rely on the wildcard)
# 2. POST /api/v1/cities to create the city + seed neighborhoods/categories
# Nothing else to deploy.
```

## Adding a new network (e.g. Fitness)

```bash
# 1. POST /api/v1/networks with the slug, name, theme, category_map, and
#    the domain suffixes it'll answer to.
# 2. Add DNS for the new network's domains.
# 3. Add a Traefik router rule for the new hostnames in
#    docker-compose.prod.yml and `docker compose up -d` to apply.
```
