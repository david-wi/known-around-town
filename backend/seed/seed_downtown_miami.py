"""Seed Downtown Miami for the Beauty network.

5 curated businesses across Downtown Miami neighborhoods.

Run inside the backend container after seed_networks.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_downtown_miami
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo


CITY_SLUG = "downtown-miami"
NETWORK_SLUG = "beauty"

# ── Neighborhoods ─────────────────────────────────────────────────────────────
NEIGHBORHOODS: List[tuple] = [
    ("brickell-city-centre",  "Brickell City Centre",   "Urban luxury",              2),
    ("arts-entertainment",    "Arts & Entertainment",   "Cultural & creative",        2),
    ("wynwood-adjacent",      "Wynwood Adjacent",       "Edgy & independent",         1),
]

NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "brickell-city-centre": (
        "The shopping and dining complex at the heart of Brickell draws a "
        "professional clientele who expect polished, efficient service. Beauty "
        "destinations here serve the lunch-hour and after-work crowd — quick, "
        "results-oriented, and never sacrificing quality."
    ),
    "arts-entertainment": (
        "The Arts & Entertainment District runs along Biscayne Boulevard from "
        "the Adrienne Arsht Center north toward Wynwood. The beauty studios "
        "here serve a diverse urban clientele — locals, visitors, and the arts "
        "crowd who value skill over brand recognition."
    ),
    "wynwood-adjacent": (
        "The blocks just south of Wynwood carry its creative energy without "
        "the weekend crowds. Independent studios and loft-style salons operate "
        "here, attracting a loyal neighborhood following."
    ),
}

# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing
# price_cues: $ | $$ | $$$ | $$$$

BUSINESSES: List[Dict[str, Any]] = [

    # ── BRICKELL CITY CENTRE ──────────────────────────────────────────────────
    {
        "name": "Ella Salon Brickell",
        "slug": "ella-salon-brickell",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "701 S Miami Ave, Suite 415", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 856-3525",
        "website": "https://ellasalonmiami.com",
        "instagram": "@ellasalonmiami",
        "short_description": (
            "Tucked inside Brickell City Centre, Ella has earned a devoted following "
            "among Brickell's professional class for its precise blowouts, balayage, "
            "and Brazilian keratin treatments — all delivered on a schedule that "
            "respects the lunch-hour window. With a 4.7-star reputation across 180+ "
            "reviews, it's the neighborhood's most trusted express-luxury hair address."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "Brickell City Centre's standout hair salon — a 4.7-star rating across "
            "180+ reviews, reliable same-week availability, and the kind of efficient, "
            "polished service that working professionals in Brickell actually need."
        ),
    },
    {
        "name": "SkinSpirit Brickell",
        "slug": "skinspirit-brickell",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "801 Brickell Ave, Suite 140", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 735-6610",
        "website": "https://www.skinspirit.com/locations/brickell",
        "instagram": "@skinspirit",
        "short_description": (
            "The national medical aesthetics brand's Brickell outpost brings "
            "physician-supervised injectables, CoolSculpting, laser resurfacing, and "
            "Botox to the heart of Miami's financial district. The clinic is staffed "
            "by board-certified nurse practitioners and consistently scores among the "
            "highest-rated med spas in the 33131 zip code."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── ARTS & ENTERTAINMENT ──────────────────────────────────────────────────
    {
        "name": "Damaris Salon",
        "slug": "damaris-salon-arts-district",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["arts-entertainment"],
        "address": {"street": "1901 Biscayne Blvd", "city": "Miami", "state": "FL", "postal_code": "33132", "country": "US"},
        "phone": "(305) 371-4770",
        "website": "https://damarissalon.com",
        "instagram": "@damarissalonmiami",
        "short_description": (
            "A downtown institution since the 1990s, Damaris Salon has shaped the "
            "hair of Miami's arts community from its Biscayne Boulevard studio for "
            "decades. The bilingual team specializes in curly and textured hair, "
            "lived-in color, and precision cuts — drawing a loyal urban clientele "
            "who appreciate real craft over trend-chasing."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Lush Lash & Brow Lounge",
        "slug": "lush-lash-brow-lounge-arts-district",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["arts-entertainment"],
        "address": {"street": "1637 N Bayshore Dr, Suite 102", "city": "Miami", "state": "FL", "postal_code": "33132", "country": "US"},
        "phone": "(786) 452-0318",
        "website": "https://lushlashlounge.com",
        "instagram": "@lushlashandbrownlounge",
        "short_description": (
            "A serene lash and brow specialist steps from the Adrienne Arsht Center, "
            "offering classic, hybrid, and volume lash extensions alongside microblading, "
            "ombre powder brows, and brow lamination. Its Bayshore Drive location pulls "
            "clients from both downtown residential towers and Edgewater, with 95+ "
            "five-star reviews praising the precise, long-lasting results."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── WYNWOOD ADJACENT ──────────────────────────────────────────────────────
    {
        "name": "Mane Theory Studio",
        "slug": "mane-theory-studio-wynwood-adjacent",
        "category_slugs": ["hair", "waxing"],
        "neighborhood_slugs": ["wynwood-adjacent"],
        "address": {"street": "2800 N Miami Ave, Suite 104", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 924-1187",
        "website": "https://manetheorystudio.com",
        "instagram": "@manetheorystudio",
        "short_description": (
            "An independent studio in the creative block just south of Wynwood, "
            "Mane Theory built its reputation on curly hair expertise and "
            "lived-in balayage before expanding into full waxing services. "
            "The loft-style space doubles as a local gathering point — stylists "
            "here know their regulars by name and their hair by memory."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_downtown_miami() -> None:
    now = datetime.now(tz=timezone.utc)
    db = get_db()

    network = await db.networks.find_one({"slug": NETWORK_SLUG})
    if not network:
        raise RuntimeError("Beauty network not found — run seed_networks.py first")
    network_id = str(network["_id"])

    # ── City ─────────────────────────────────────────────────────────────────
    city_doc: Dict[str, Any] = {
        "_id": str(uuid.uuid4()),
        "network_id": network_id,
        "slug": CITY_SLUG,
        "name": "Downtown Miami",
        "state": "FL",
        "country": "US",
        "metro": "miami",
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    await upsert("cities", {"slug": CITY_SLUG}, city_doc)
    city = await db.cities.find_one({"slug": CITY_SLUG})
    city_id = str(city["_id"])
    print("City upserted: %s (id=%s)" % (CITY_SLUG, city_id))

    # ── Neighborhoods ─────────────────────────────────────────────────────────
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nb_doc: Dict[str, Any] = {
            "_id": str(uuid.uuid4()),
            "network_id": network_id,
            "city_id": city_id,
            "slug": slug,
            "name": name,
            "description": vibe,
            "hero_description": NEIGHBORHOOD_DESCRIPTIONS.get(slug),
            "listed_count": listed_count,
            "photo_url": None,
            "order": i,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("neighborhoods", {"city_id": city_id, "slug": slug}, nb_doc)
    print("Upserted %d neighborhoods." % len(NEIGHBORHOODS))

    # ── Categories ────────────────────────────────────────────────────────────
    for order, group in enumerate(network.get("category_map") or []):
        cat_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network_id,
            "city_id": city_id,
            "slug": group["slug"],
            "parent_slug": None,
            "name": group["name"],
            "description": group.get("description"),
            "meta_description": group.get("meta_description"),
            "examples": group.get("examples", []),
            "order": order,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("categories", {"city_id": city_id, "slug": group["slug"]}, cat_doc)
    print("Upserted %d categories." % len(network.get("category_map") or []))

    # ── Businesses ────────────────────────────────────────────────────────────
    inserted = 0
    updated = 0
    for biz in BUSINESSES:
        photo_url = pick_category_photo(biz["slug"], biz["category_slugs"][0])
        photos = [{"url": photo_url, "alt": biz["name"], "order": 0, "is_hero": True}] if photo_url else []
        address = biz.get("address", {})
        socials: Dict[str, Any] = {}
        if biz.get("instagram"):
            socials["instagram"] = biz["instagram"]

        biz_doc: Dict[str, Any] = {
            "_id": str(uuid.uuid4()),
            "network_id": network_id,
            "city_id": city_id,
            "slug": biz["slug"],
            "name": biz["name"],
            "category_slugs": biz["category_slugs"],
            "neighborhood_slugs": biz.get("neighborhood_slugs", []),
            "address": address,
            "phone": biz.get("phone"),
            "website": biz.get("website"),
            "socials": socials,
            "short_description": biz.get("short_description"),
            "known_for": biz.get("short_description"),
            "price_cues": biz.get("price_cues"),
            "editors_pick": biz.get("editors_pick", False),
            "is_founding_partner": False,
            "featured": {"enabled": False, "tier": "free"},
            "claim_status": "unclaimed",
            "data_source": "editorial",
            "quality_score": 90 if biz.get("editors_pick") else 60,
            "index_status": "indexed",
            "index_override": "auto",
            "schema_org_type": "LocalBusiness",
            "status": "live",
            "photos": photos,
            "hours": [],
            "services": [],
            "created_at": now,
            "updated_at": now,
        }

        existing = await db.businesses.find_one({"city_id": city_id, "slug": biz["slug"]})
        if existing:
            for _preserve in (
                "claim_status", "claimed_email", "claimed_by_user_id",
                "claimed_at", "verified_at",
                "stripe_customer_id", "stripe_subscription_id",
                "is_founding_partner", "hours",
            ):
                if _preserve in existing:
                    biz_doc[_preserve] = existing[_preserve]
            existing_services = existing.get("services") or []
            if existing_services:
                biz_doc["services"] = existing_services
            biz_doc["_id"] = existing["_id"]
            biz_doc["created_at"] = existing.get("created_at", biz_doc["created_at"])
            await db.businesses.replace_one({"_id": existing["_id"]}, biz_doc)
            updated += 1
        else:
            await db.businesses.insert_one(biz_doc)
            inserted += 1

    print("Businesses: %d inserted, %d updated." % (inserted, updated))
    print("")
    print("Downtown Miami seed complete:")
    print("  City:          downtown-miami (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_downtown_miami()


if __name__ == "__main__":
    run(main())
