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
