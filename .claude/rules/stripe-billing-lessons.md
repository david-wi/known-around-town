# Stripe Billing — Lessons Learned (Miami Knows Beauty Integration)

Lessons captured during the Stripe subscription billing integration for Miami Knows Beauty. Apply these before touching billing, subscription, or webhook code.

## 1. MongoDB Sparse+Unique Index: Use `$unset`, Not `$set: null`

The `stripe_subscription_id` field on business documents has a `unique: true, sparse: true` index. A common belief is that sparse indexes skip `null` values — **this is wrong**. MongoDB sparse indexes DO index `null`, so two documents with `stripe_subscription_id: null` violate the unique constraint and throw a duplicate-key error.

**The broken pattern (causes DuplicateKeyError on the second cancellation):**
```python
# WRONG — sets the field to null, which IS indexed under the sparse index
await db.businesses.update_one({"_id": biz_id}, {"$set": {"stripe_subscription_id": None}})
```

**The correct pattern:**
```python
# RIGHT — removes the field entirely, keeping the document out of the index
await db.businesses.update_one({"_id": biz_id}, {"$unset": {"stripe_subscription_id": ""}})
```

Whenever clearing a field covered by a sparse+unique index, always `$unset` the field rather than setting it to `None`/`null`.

## 2. Docker Compose Env Var Wiring: `.env` Values Are NOT Passed Automatically

When adding new environment variables to a FastAPI app running in Docker, the values in the host `.env` file are **not** automatically passed into the container. They must be explicitly listed in the `environment:` block of `docker-compose.prod.yml`.

The Stripe keys were set in `.env` and appeared to be configured, but the running container could not see them because the compose file did not list them — causing silent auth failures inside the app.

**Required for every new env var:**

1. Add to the host `.env` file (and `.env.example` for documentation)
2. Add to the `environment:` block in `docker-compose.prod.yml`:
   ```yaml
   environment:
     - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
     - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
   ```

Never assume the host environment bleeds through to containers automatically.

## 3. Session Cookie Name: `kb_owner_session`, Not `owner_session`

The owner authentication session cookie is named **`kb_owner_session`**. Tests and any code that reads or sets the session cookie must use this exact name. Using `owner_session` or any other variant will result in 401 Unauthorized responses with no helpful error message about the mismatch.

**In tests:**
```python
# WRONG
client.cookies.set("owner_session", token)

# RIGHT
client.cookies.set("kb_owner_session", token)
```

## 4. `lru_cache` and Settings in Tests: Clear the Cache After Patching

`get_settings()` is decorated with `@lru_cache`. If a test patches environment variables (e.g., with `monkeypatch.setenv` or `unittest.mock.patch.dict(os.environ, ...)`), the cache must be explicitly cleared afterward — otherwise the patched values never reach the `Settings` object because the old cached instance is returned.

**Pattern for every test that patches env vars:**
```python
from app.config import get_settings

def test_something(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_...")
    get_settings.cache_clear()  # WHY: lru_cache returns stale settings without this
    try:
        # ... test body ...
    finally:
        get_settings.cache_clear()  # clean up so subsequent tests get fresh settings
```

The `finally` block matters: if the test raises before cleanup, the next test inherits the patched (and now wrong) cached settings.

## 5. Webhook Idempotency: Insert-First Pattern

To guarantee idempotent Stripe webhook handling, insert the Stripe `event.id` as the document `_id` in a `stripe_events` collection **before** taking any action. If the event was already processed, the insert raises `DuplicateKeyError`, which is caught and returns `already_processed` immediately.

This is safer than a check-then-act pattern, which has a race window between the existence check and the insert.

**The pattern:**
```python
from pymongo.errors import DuplicateKeyError

async def handle_webhook(event: stripe.Event) -> str:
    # WHY: insert-first idempotency — no race window vs select-then-insert
    try:
        await db.stripe_events.insert_one({
            "_id": event["id"],
            "type": event["type"],
            "processed_at": datetime.utcnow(),
        })
    except DuplicateKeyError:
        return "already_processed"

    # Safe to take action — we own this event exclusively
    await _handle_event_body(event)
    return "processed"
```

The `stripe_events` collection requires no explicit unique index because `_id` is always unique in MongoDB. No TTL or cleanup is strictly necessary for correctness, but a TTL index of 90 days keeps the collection from growing unbounded.

## 6. Jinja2 Block Balance: Verify Parse After Any Structural Template Refactor

Moving a template section outside a conditional is a silent crash risk. Jinja2 does NOT catch mismatched blocks until a request actually renders the template — and some routes return early (e.g., auth redirects) before rendering, masking the error from smoke tests.

**The failure mode (found in owner_me.html, PR #131):** A missing `{% endif %}` caused `TemplateSyntaxError: Encountered unknown tag 'else'` for every signed-in owner visiting `/owners/me`. Unauthenticated requests redirect before rendering, so the error was invisible in smoke tests.

**After any structural template change, always verify parse:**
```bash
cd backend
python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('owner_me.html')
print('Template parses OK')
"
```

**Label block boundaries** with comments to make structure unambiguous:
```jinja
{% if owner_business.stripe_subscription_id %}
  ...subscription content...
</section>
{% endif %}{# /if stripe_subscription_id #}

{% if owner_business.get('is_founding_partner') %}
```

The `{# /if <condition> #}` suffix is searchable and makes block boundaries unambiguous.

## 7. Founding Partner Badge: Place OUTSIDE the Subscription Conditional

The `is_founding_partner` flag is permanent — it is never cleared, not even on subscription cancellation. The dashboard badge must live **outside** `{% if stripe_subscription_id %}` so founding partners see it regardless of current subscription state.

The same principle applies to the post-subscribe success toast: show "You're a Founding Partner!" when the flag is already set at render time (webhook typically fires before the browser redirect lands), and fall back to "You're Featured!" if the webhook hasn't written the flag yet.

## 8. mongomock_motor: Use Empty `mock_db` for `count_documents` Tests

`mongomock_motor`'s `count_documents({"is_founding_partner": True})` returns inflated counts against `seeded_db` because the 147 seed businesses include documents where the field is absent — and mongomock treats absent fields as matching. Tests that assert on founding partner counts must use `mock_db` (empty DB), not `seeded_db`.

```python
# WRONG — seeded_db has 147 documents; mongomock inflates the count
async def test_count(seeded_db):
    count = await seeded_db.businesses.count_documents({"is_founding_partner": True})
    assert count == 0  # fails; mongomock returns inflated number

# RIGHT — mock_db starts empty; counts are deterministic
async def test_count(mock_db):
    await mock_db.businesses.insert_one({"is_founding_partner": True, ...})
    count = await mock_db.businesses.count_documents({"is_founding_partner": True})
    assert count == 1
```
