"""One-shot backfill: set `is_founding_partner` on the five demo businesses.

Why this exists:

Stage deploys share the production MongoDB and intentionally skip the full
seed re-run, so adding `is_founding_partner: true` to `_real_businesses.json`
alone is NOT enough to make the badge appear on the stage site. This
script flips the flag directly on the five chosen business documents and
leaves every other field untouched. Safe to re-run — repeated runs just
re-set the same flag.

Usage (from inside the container, after a stage deploy):

    python -m seed.backfill_founding_partners

Or via Docker on the deploy server:

    docker compose -p known-around-town -f docker-compose.prod.yml \\
        exec -T backend python -m seed.backfill_founding_partners

When the production seed runs (on a main deploy), the flag becomes part
of the seed itself, so this script becomes a no-op for those slugs.
"""

from __future__ import annotations

from app.database import get_db
from seed._helpers import run


# WHY: these five slugs match what was added to _real_businesses.json. Keep
# the two lists in sync — if you add or remove a founding partner there,
# update this list at the same time so the stage site reflects the change
# without a full re-seed.
FOUNDING_PARTNER_SLUGS = [
    "ayesha-beauty-studio-wynwood",
    "vanity-projects-miami-design-district",
    "igk-salon-south-beach",
    "blow-dry-bar-brickell",
    "nue-studio-wynwood",
]


async def main() -> None:
    db = get_db()
    result = await db.businesses.update_many(
        {"slug": {"$in": FOUNDING_PARTNER_SLUGS}},
        {"$set": {"is_founding_partner": True}},
    )
    print(
        f"Backfill complete: matched {result.matched_count} business documents, "
        f"modified {result.modified_count}."
    )

    # Helpful diagnostic — surface which slugs were NOT found so the operator
    # can investigate (e.g. typo in slug, business archived, fresh database).
    cursor = db.businesses.find(
        {"slug": {"$in": FOUNDING_PARTNER_SLUGS}}, {"slug": 1}
    )
    found = {doc["slug"] async for doc in cursor}
    missing = [s for s in FOUNDING_PARTNER_SLUGS if s not in found]
    if missing:
        print(f"WARNING: these slugs were not found in any business doc: {missing}")


if __name__ == "__main__":
    run(main())
