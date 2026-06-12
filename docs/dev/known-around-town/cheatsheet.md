# Miami Knows Beauty — Developer Cheatsheet

## Quick Access

| Thing | Value |
|-------|-------|
| Production URL | https://miami.knowsbeauty.com |
| Dev/staging URL | https://miami.knowsbeauty.ai.devintensive.com |
| Server SSH | `ssh -p 2222 root@152.42.152.243` |
| Working dir | `/opt/known-around-town/` |
| GitHub repo | `david-wi/known-around-town` |
| Container image | `ghcr.io/david-wi/known-around-town:latest` |
| DB name | `who_knows_local` |
| Health endpoint | `/health` |
| Error logs | https://admin.ai.devintensive.com/error-logs |

## Most Common SSH Commands

```bash
# Connect
ssh -p 2222 root@152.42.152.243

# View live logs
docker compose -f docker-compose.prod.yml logs -f backend

# Restart after .env changes
docker compose -f docker-compose.prod.yml restart backend

# Check running containers
docker compose -f docker-compose.prod.yml ps

# Read .env (use python, not source — file has non-bash lines)
python3 -c "
with open('/opt/known-around-town/.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            print(line.strip())
"
```

## API Endpoints (Key Ones)

| Endpoint | Method | Auth | Purpose |
|---------|--------|------|---------|
| `/health` | GET | None | Health check |
| `/api/v1/businesses` | GET/POST | Admin key for writes | List/create businesses |
| `/api/v1/businesses/{slug}` | GET/PATCH/DELETE | Admin key for writes | Business detail |
| `/api/v1/owner/login/request-code` | POST | None | Request magic code |
| `/api/v1/owner/login/verify-code` | POST | None | Verify code, set cookie |
| `/api/v1/owner/profile` | GET/PATCH | Owner cookie | Owner dashboard data |
| `/api/v1/owner/photos` | POST/DELETE | Owner cookie | Photo management |
| `/api/v1/billing/checkout` | POST | Owner cookie | Create Stripe checkout |
| `/api/v1/billing/webhook` | POST | Stripe sig | Stripe webhook receiver |
| `/api/v1/billing/portal` | POST | Owner cookie | Stripe customer portal |
| `/api/v1/preview-login/request-code` | POST | None | Preview gate: request code |
| `/api/v1/preview-login/verify-code` | POST | None | Preview gate: verify code |
| `/sitemap.xml` | GET | None | XML sitemap |

## Admin API Auth

Write endpoints require `Authorization: Bearer {ADMIN_API_KEY}` header.

## Owner Cookie

Session cookie name: `kb_owner_session` (HttpOnly, Secure, 30-day)

## Preview Cookie

Cookie name: `preview_token` (HttpOnly, Secure, 30-day)

## Stripe Keys in Creds

```
STRIPE_SECRET_KEY_MIAMI_KNOWS_BEAUTY=rk_live_...  (in ~/.claude/gitignore/creds)
STRIPE_PRODUCT_ID_MIAMI_KNOWS_BEAUTY=prod_UgggS2CyiLgD52
STRIPE_PRICE_ID_MIAMI_KNOWS_BEAUTY_PRO=price_1ThJJFAIj5oq6xI8oejLDzvu
```

Production `.env` uses just `STRIPE_SECRET_KEY` (without the `_MIAMI_KNOWS_BEAUTY` suffix).

## Dynadot API

```python
import requests
# Read keys from ~/.claude/gitignore/creds
API_KEY = "..."
SECRET_KEY = "..."

# Set DNS (replaces ALL records for the domain)
r = requests.get("https://api.dynadot.com/api3.json", params={
    "key": API_KEY,
    "secret": SECRET_KEY,
    "command": "set_dns2",
    "domain": "knowsbeauty.com",  # root domain only, no subdomain
    "subdomain0": "miami",
    "sub_record_type0": "A",
    "sub_record0": "174.138.81.31",
    "ttl0": "300",
})

# Get domain list
r = requests.get("https://api.dynadot.com/api3.json", params={
    "key": API_KEY, "secret": SECRET_KEY, "command": "list_domain"
})
```

**Warning**: `set_dns2` replaces ALL DNS records for the domain. Always include all records in a single call.

## Test Suite

```bash
cd backend
python -m pytest tests/ -v              # all tests
python -m pytest tests/ -k "billing"   # billing tests only
python -m pytest tests/ -k "preview"   # preview gate tests only
```

372 tests total. CI runs all on push to main.
