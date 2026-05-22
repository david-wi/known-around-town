from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_url, tz_aware=True)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[get_settings().mongodb_database]


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
