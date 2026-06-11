
## Deployment — how to push new code to production

CI runs tests only (no auto-deploy, no image push to GHCR). After merging a PR:

1. SSH to the server: `ssh -p 2222 root@152.42.152.243`
2. Pull latest code: `cd /opt/known-around-town && git pull origin main`
3. Rebuild and tag the image for the prod compose:
   ```bash
   docker build -t ghcr.io/david-wi/known-around-town:latest ./backend
   ```
4. Restart the prod container:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
5. Verify it's healthy: `docker compose -f docker-compose.prod.yml ps`

**Do NOT use `docker compose up` (without `-f docker-compose.prod.yml`)** — that starts the dev compose which connects to a local MongoDB container and lacks Traefik routing labels, making the public URL return 404.

The `.env` file at `/opt/known-around-town/.env` holds Atlas credentials and other production secrets. The prod compose reads from this file via `${VAR:-}` expansion.
