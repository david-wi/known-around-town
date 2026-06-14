"""One-time script: assign category_slugs to businesses that have none.

WHY: 8 cities (Doral, Hialeah, Miramar, Plantation, Weston, Pompano Beach,
Pembroke Pines, Hallandale Beach) were seeded with business names+addresses
but no categories. Without categories, listing cards appear blank and the
category filter returns no results for these cities.

This script infers categories from business names using keyword matching,
using the real category slugs from the DB categories collection:
  hair, nails, lash-brow, barber, spa, waxing, makeup, med-spa

Run once against production, then keep as reference.

Usage:
    MONGODB_URI="mongodb+srv://..." python3 backend/scripts/assign_categories.py
"""
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

# WHY: env var keeps credentials out of source code; fallback is empty so the
# script errors clearly rather than silently connecting to a wrong database.
MONGO_URI = os.environ.get("MONGODB_URI", os.environ.get("MONGODB_URL", ""))
DB_NAME = os.environ.get("MONGODB_DATABASE", "who_knows_local")

# Rules evaluated in order — first match wins.
# Slugs here are the REAL category slugs from the DB categories collection
# (hair, nails, lash-brow, barber, spa, waxing).
#
# WHY order matters:
#   "Barber & Spa"      → barber  (barber checked before spa)
#   "Nail & Lash Studio"→ nails   (nails checked before lash-brow)
#   "Massage Spa"       → spa     (no massage slug; spa is the right home)
#   "Skin Spa"          → spa     (skincare falls under spa)
#   "European Wax Center" → waxing (wax checked before spa)
#   "Beauty Salon"      → hair    (broad catch-all at the end)
RULES: list[tuple[list[str], list[str]]] = [
    (["barber", "barbershop"], ["barber"]),
    (["nail", "nails"], ["nails"]),
    (["lash", "brow", "eyebrow"], ["lash-brow"]),
    (["massage"], ["spa"]),          # no massage slug; spa is closest
    (["skin", "facial", "derma", "esthetic", "aesthet", "skincare"], ["spa"]),
    (["threading", "waxing", "wax"], ["waxing"]),
    (["tattoo", "piercing"], ["hair"]),  # no tattoo/piercing slug; default
    (["spa"], ["spa"]),
    (["hair", "salon", "studio", "coiffure", "beauty", "style", "cuts", "blowout", "color"], ["hair"]),
]

# WHY: hair is the default because this is a beauty directory — any uncategorised
# business is more likely a hair salon than anything else.
DEFAULT_CATEGORY = ["hair"]


def infer_category(name: str) -> list[str]:
    """Return the best-fit category list for a business name via keyword matching."""
    n = name.lower()
    for keywords, cats in RULES:
        if any(kw in n for kw in keywords):
            return cats
    return DEFAULT_CATEGORY


async def main() -> None:
    if not MONGO_URI:
        print("ERROR: set MONGODB_URI (or MONGODB_URL) env var to the Atlas connection string")
        return

    client = AsyncIOMotorClient(MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    # Find all live businesses with no category assignments.
    # WHY: $or covers three ways the field can be "missing":
    #   - field not present at all
    #   - field present but null
    #   - field present but empty array
    cursor = db.businesses.find(
        {
            "status": "live",
            "$or": [
                {"category_slugs": {"$exists": False}},
                {"category_slugs": None},
                {"category_slugs": []},
            ],
        },
        {"_id": 1, "name": 1, "city_id": 1},
    )

    updated = 0
    category_counts: dict[str, int] = {}

    async for b in cursor:
        cats = infer_category(b.get("name", ""))
        await db.businesses.update_one(
            {"_id": b["_id"]},
            {"$set": {"category_slugs": cats}},
        )
        updated += 1
        for c in cats:
            category_counts[c] = category_counts.get(c, 0) + 1
        if updated % 20 == 0:
            print(f"  updated {updated}...")

    print(f"\nDone. Updated {updated} businesses.")
    if category_counts:
        print("\nCategory breakdown:")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    client.close()


asyncio.run(main())
