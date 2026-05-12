# Deploy guide — Known Around Town

This file documents how to put the site on the shared dev server
(`174.138.81.31`) where Expertly's other dev apps already live, plus the DNS
that makes `miami.knowsbeauty.ai.devintensive.com` resolve.

## First-time setup on the server

```bash
ssh -p 2222 root@174.138.81.31
mkdir -p /opt/known-around-town
git clone https://github.com/david-wi/known-around-town.git /opt/known-around-town

# Production env. MongoDB Atlas connection string is already in
# /opt/expertly-develop/.env as MONGODB_ATLAS_URL — point this app at the
# same cluster but a separate database name so it doesn't share collections.
cat > /opt/known-around-town/.env <<'EOF'
MONGODB_URL=mongodb+srv://expertly-app:<password>@expertly.xuf7uv.mongodb.net
MONGODB_DATABASE=known_around_town
NETWORK_DOMAINS=beauty:knowsbeauty.ai.devintensive.com,wellness:knowswellness.ai.devintensive.com,health:knowshealth.ai.devintensive.com,beauty:knowsbeauty.com,wellness:knowswellness.com,health:knowshealth.com
ADMIN_API_KEY=<generate-one-with: openssl rand -base64 32>
EOF

bash /opt/known-around-town/scripts/deploy.sh
```

## DNS records

Wildcard records `*.knowsbeauty.ai.devintensive.com`,
`*.knowswellness.ai.devintensive.com`, and
`*.knowshealth.ai.devintensive.com` already resolve to the dev droplet via
the existing parent zone, so no DNS work is required for dev URLs. For
production (`knowsbeauty.com` etc.), add A records at the registrar of
those domains pointing to the production load balancer.

## CI auto-deploy

`docs/github-actions-deploy.yml.example` can be dropped into
`.github/workflows/deploy.yml` once the GitHub token has `workflow` scope.
Add three secrets in the GitHub repo settings:

- `DEPLOY_HOST` — `174.138.81.31`
- `DEPLOY_USER` — `root`
- `DEPLOY_KEY` — the same SSH private key the other Expertly repos use to
  deploy (`~/.ssh/do_droplet` on the deploy-orchestrator account)

Until that's wired, deploys are a single SSH command:

```bash
ssh -p 2222 root@174.138.81.31 'bash /opt/known-around-town/scripts/deploy.sh'
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
