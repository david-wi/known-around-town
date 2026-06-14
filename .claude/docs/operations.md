
## Deployment — how to push new code to production

Deployment is fully automatic: merging a PR to `main` triggers the GitHub Actions "Build and push image" workflow, which pushes a new Docker image to GHCR. Watchtower (running on the server) polls GHCR every 5 minutes and pulls + restarts the container automatically. No manual SSH steps needed.

To verify a deploy landed: `ssh -p 2222 root@152.42.152.243 "docker ps | grep known-around-town"` — the "Up X minutes" time will reset to a low value right after Watchtower pulls the new image.

The `.env` file at `/opt/known-around-town/.env` holds Atlas credentials and other production secrets.

**Do NOT use `docker compose up` (without `-f docker-compose.prod.yml`)** — that starts the dev compose which connects to a local MongoDB container and lacks Traefik routing labels.

## Preview gate — bypassing for internal verification

The staging site (`*.knowsbeauty.ai.devintensive.com`) is behind a preview gate (`PREVIEW_MODE_ENABLED=true` in the server `.env`). Requests without a valid preview cookie get redirected to `/preview-login`.

To bypass the gate for curl/script verification, use the admin API key as an `X-API-Key` header:

```bash
ADMIN_KEY=$(ssh -p 2222 root@152.42.152.243 "grep ADMIN_API_KEY /opt/known-around-town/.env | cut -d= -f2-")
ssh -p 2222 root@152.42.152.243 "docker exec known-around-town-backend-1 curl -s \
  -H 'Host: miami.knowsbeauty.ai.devintensive.com' \
  -H 'X-API-Key: $ADMIN_KEY' \
  'http://localhost:8000/b/SLUG'"
```

The admin key is in `/opt/known-around-town/.env` under `ADMIN_API_KEY`.
