from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorGridFSBucket,
)

from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        # WHY: refuse to start against a local MongoDB unless explicitly opted
        # in for development. Production must use the managed Atlas database;
        # a silent fall-back to a local Mongo is how the wrong (and once,
        # internet-exposed) database could be used without anyone noticing.
        # Validated here, at the single point where the client is created, so
        # it runs once on the first DB access at startup and fails loudly.
        settings.validate_mongodb_url()
        _client = AsyncIOMotorClient(settings.mongodb_url, tz_aware=True)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[get_settings().mongodb_database]


def get_gridfs_bucket() -> AsyncIOMotorGridFSBucket:
    # WHY: named bucket "business_photos" to keep owner photos isolated from
    # any other GridFS usage. The default bucket name is "fs", which is too
    # generic and could collide if GridFS is used elsewhere in the future.
    return AsyncIOMotorGridFSBucket(get_db(), bucket_name="business_photos")


async def ensure_indexes() -> None:
    db = get_db()

    await db.networks.create_index("slug", unique=True)
    await db.networks.create_index("domains")

    await db.cities.create_index([("network_id", 1), ("slug", 1)], unique=True)
    await db.cities.create_index([("network_id", 1), ("status", 1)])

    await db.neighborhoods.create_index([("city_id", 1), ("slug", 1)], unique=True)

    await db.categories.create_index([("city_id", 1), ("slug", 1)], unique=True)
    await db.categories.create_index([("network_id", 1), ("slug", 1)])
    await db.categories.create_index([("city_id", 1), ("parent_slug", 1)])

    await db.businesses.create_index([("city_id", 1), ("slug", 1)], unique=True)
    await db.businesses.create_index([("city_id", 1), ("status", 1)])
    await db.businesses.create_index([("city_id", 1), ("category_slugs", 1)])
    await db.businesses.create_index([("city_id", 1), ("neighborhood_slugs", 1)])
    await db.businesses.create_index([("city_id", 1), ("featured.enabled", 1)])
    await db.businesses.create_index([("city_id", 1), ("editors_pick", 1)])
    # WHY: Stripe webhooks and billing-portal creation identify the listing by
    # Stripe ids, and sparse unique indexes keep one Stripe object from being
    # accidentally attached to multiple businesses while allowing unsubscribed
    # businesses to leave the fields unset.
    await db.businesses.create_index("stripe_customer_id", unique=True, sparse=True)
    await db.businesses.create_index("stripe_subscription_id", unique=True, sparse=True)
    # WHY: owner portal looks up the business by the verified owner's email on
    # every page load and every profile-edit save. sparse=True because only
    # claimed+verified listings have this field; a non-sparse index would waste
    # space for the majority of documents.
    await db.businesses.create_index("claimed_email", sparse=True)

    await db.copy_blocks.create_index(
        [("scope_type", 1), ("scope_ref", 1), ("key", 1), ("locale", 1)],
        unique=True,
    )

    await db.editorial_guides.create_index([("city_id", 1), ("slug", 1)], unique=True)
    await db.editorial_guides.create_index([("city_id", 1), ("status", 1)])

    await db.business_claims.create_index([("business_id", 1), ("status", 1)])
    await db.business_inquiries.create_index([("business_id", 1), ("submitted_at", -1)])

    # Owner login (passwordless verification-code flow).
    # WHY: lookup pattern is "give me the most recent unused code for this
    # email", so we sort by (email, created_at desc). The same index also
    # answers the rate-limit count query that filters by email + a
    # created_at lower bound.
    await db.owner_magic_codes.create_index([("email", 1), ("created_at", -1)])
    # WHY: a Mongo TTL index garbage-collects rows after they've been around
    # well past their useful life. Codes expire in 15 minutes, but we keep
    # them for 24 hours as a short audit trail and to keep the rate-limit
    # math honest for the recent past.
    await db.owner_magic_codes.create_index("created_at", expireAfterSeconds=86400)

    # --- claim-and-pay: OwnerSession indexes (from stashed WIP) ---
    # WHY: code-entry lookups filter by email and an unexpired code.
    await db.owner_sessions.create_index([("email", 1), ("code_expires_at", 1)])
    # WHY: cookie-auth path looks the session up by the hashed token; the
    # token hash is unique because we issue one fresh per exchange.
    # `sparse=True` because not every row has a session token yet (a row
    # exists from the moment a code is requested).
    await db.owner_sessions.create_index(
        "session_token_hash", unique=True, sparse=True
    )
    # WHY: Mongo TTL indexes drop documents shortly after the named field's
    # timestamp. We piggyback on session_expires_at so spent sessions self-
    # expire from the collection 30 days after issue, keeping it small.
    await db.owner_sessions.create_index(
        "session_expires_at", expireAfterSeconds=0
    )
    # WHY: inquiry notifications look up the owner session by business_id;
    # without this index that lookup is a full collection scan per inquiry.
    # sparse=True because sessions without a bound business_id (pre-claim)
    # should not be indexed.
    await db.owner_sessions.create_index("business_id", sparse=True)

    # --- claim-and-pay: StripeEvent indexes (from stashed WIP) ---
    # WHY: webhook idempotency — we store the Stripe event id as _id.
    # Second delivery of the same event id causes a duplicate-key insert
    # error and we treat that as "already handled". No explicit index
    # needed — MongoDB's built-in _id index is already unique.

    # app_migrations: track which one-time data migrations have run.
    # WHY: a unique index on _id is built-in, but a secondary index on
    # `ran_at` lets ops quickly query migration history in order.
    await db.app_migrations.create_index("ran_at")


async def run_startup_migrations() -> None:
    """One-time data migrations, each guarded by a record in app_migrations."""
    import logging
    from datetime import datetime, timezone

    db = get_db()
    log = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Migration: reset editorially-seeded businesses from claim_status
    # "verified" back to "unclaimed" so the Claim CTA shows on their page.
    #
    # WHY: The seed script tagged every business with claim_status="verified"
    # to mean "editorial data quality approved". But the public listing
    # template reads "verified" as "owner has claimed this", and hides the
    # Claim CTA entirely. The result: every owner who clicks through from
    # outreach email sees a page with no way to claim their listing.
    #
    # The correct meaning of "verified": a real entry exists in
    # business_claims with status="verified". Businesses without that
    # entry should be "unclaimed" so the CTA is visible.
    # ------------------------------------------------------------------
    migration_id = "reset-editorial-verified-to-unclaimed-20260611"
    if not await db.app_migrations.find_one({"_id": migration_id}):
        reset_count = 0
        async for biz in db.businesses.find({"claim_status": "verified"}):
            has_real_claim = await db.business_claims.find_one(
                {"business_id": biz["_id"], "status": "verified"}
            )
            if not has_real_claim:
                await db.businesses.update_one(
                    {"_id": biz["_id"]},
                    {"$set": {"claim_status": "unclaimed"}},
                )
                reset_count += 1
        await db.app_migrations.insert_one(
            {
                "_id": migration_id,
                "ran_at": datetime.now(timezone.utc),
                "reset_count": reset_count,
            }
        )
        log.info(
            "Migration %s: reset %d businesses to unclaimed", migration_id, reset_count
        )

    # ------------------------------------------------------------------
    # Migration: publish all businesses still stuck on the default
    # "draft" status so they appear in public search and the sitemap.
    #
    # WHY: The Business model's default publish status is "draft", not
    # "live". Any business inserted via the admin API, an import script,
    # or a partial seed run (before the status field was explicitly set)
    # silently lands as draft and is invisible to the public: it won't
    # show up in search results, the sitemap, or the claim form directory.
    #
    # In production this affected 97 of 147 businesses — more than 2/3
    # of the directory was hidden. Owners of those salons would get
    # "couldn't find your business" if they tried to claim.
    #
    # All 147 businesses in the Miami seed data are intended to be
    # publicly visible. "Archived" is the intentional "hidden" status;
    # "draft" is just the model default that got stuck. This migration
    # promotes every non-live, non-archived business to "live" once.
    # ------------------------------------------------------------------
    migration_id = "publish-all-draft-businesses-20260611"
    if not await db.app_migrations.find_one({"_id": migration_id}):
        result = await db.businesses.update_many(
            {"status": {"$nin": ["live", "archived"]}},
            {"$set": {"status": "live"}},
        )
        published_count = result.modified_count
        await db.app_migrations.insert_one(
            {
                "_id": migration_id,
                "ran_at": datetime.now(timezone.utc),
                "published_count": published_count,
            }
        )
        log.info(
            "Migration %s: published %d draft businesses to live",
            migration_id,
            published_count,
        )

    # ------------------------------------------------------------------
    # Migration: clear is_founding_partner on businesses that never
    # legitimately earned it (no payment, no verified claim).
    #
    # WHY: is_founding_partner should only be set by the Stripe checkout
    # webhook (when an owner pays) or by the admin claim-verification flow.
    # During development the seed data and a backfill script incorrectly
    # set this flag on five demo businesses, causing the pricing page to
    # show "20 Founding Partner spots left" even before a single owner had
    # subscribed (5 fake slots consumed out of the 25-slot cap).
    # The backfill script has been deleted and the seed data cleaned up.
    # This migration clears any stale flags so a future seed accident can't
    # re-introduce them. The badge is permanent for real earners — see the
    # inline comment below for how legitimate holders are identified.
    # ------------------------------------------------------------------
    migration_id = "clear-seeded-founding-partner-flags-20260611"
    if not await db.app_migrations.find_one({"_id": migration_id}):
        cleared = 0
        async for biz in db.businesses.find({"is_founding_partner": True}):
            # WHY: the badge is permanent — it persists even after a subscriber
            # cancels (by design, stripe_billing.py line 221). So the guard is
            # "was this badge ever legitimately earned", not "is the sub active
            # today". Two legitimate paths:
            #   (a) stripe_customer_id is set — the business completed checkout
            #       at some point. stripe_customer_id is never cleared, even on
            #       cancellation (unlike stripe_subscription_id which IS cleared).
            #   (b) a verified business_claims record exists — admin-verified
            #       owners also receive the badge per the claims flow.
            # Seed/demo data has neither, so this safely targets only fake flags.
            has_paid = bool(biz.get("stripe_customer_id"))
            has_verified_claim = bool(
                await db.business_claims.find_one(
                    {"business_id": biz["_id"], "status": "verified"}
                )
            )
            if not has_paid and not has_verified_claim:
                await db.businesses.update_one(
                    {"_id": biz["_id"]},
                    {"$unset": {"is_founding_partner": ""}},
                )
                cleared += 1
        await db.app_migrations.insert_one(
            {
                "_id": migration_id,
                "ran_at": datetime.now(timezone.utc),
                "cleared_count": cleared,
            }
        )
        log.info(
            "Migration %s: cleared is_founding_partner from %d businesses with no payment history and no verified claim",
            migration_id,
            cleared,
        )
