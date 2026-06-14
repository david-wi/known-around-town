"""Seed Hallandale Beach for the Beauty network.

18 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_hallandale_beach
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo


CITY_SLUG = "hallandale-beach"
BEAUTY_NETWORK_SLUG = "beauty"
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"

# ── Neighborhoods ─────────────────────────────────────────────────────────────
# (slug, display name, vibe description, listed_count)
NEIGHBORHOODS: List[tuple] = [
    ("hallandale-beach-blvd",     "Hallandale Beach Blvd",      "Main commercial strip",       8),
    ("village-at-gulfstream-park","Village at Gulfstream Park",  "Upscale & lifestyle",         5),
    ("golden-isles",              "Golden Isles",                "Coastal residential",         3),
    ("north-federal-hwy",         "N Federal Hwy Corridor",      "Neighborhood & accessible",   2),
]

NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "hallandale-beach-blvd": (
        "Hallandale Beach Boulevard is the city's main commercial artery, running "
        "east from I-95 to the beach with a dense mix of nail studios, hair salons, "
        "and wax centers serving the city's full residential base. The boulevard "
        "draws clients from Golden Isles and the condo towers to the east as well "
        "as inland neighborhoods to the west — the kind of foot traffic that sustains "
        "busy, well-staffed studios without relying on destination tourism."
    ),
    "village-at-gulfstream-park": (
        "Village at Gulfstream Park is the city's most curated retail district — "
        "an outdoor lifestyle complex next to the legendary Gulfstream Park racetrack "
        "with a focus on premium and specialty brands. The beauty studios here cater "
        "to the same clientele that shops Gucci and dines at the on-site restaurants: "
        "people who expect professional-level results and a polished experience."
    ),
    "golden-isles": (
        "Golden Isles is a waterfront residential enclave in the eastern part of "
        "Hallandale Beach where private homes and low-rise condos face the Intracoastal. "
        "The beauty studios here are intimate and appointment-first — smaller studios "
        "that built their clientele through referral and have kept it by knowing "
        "regulars by name."
    ),
    "north-federal-hwy": (
        "The North Federal Highway corridor through Hallandale Beach connects the "
        "city to Hollywood and Aventura, with a mix of neighborhood-oriented service "
        "businesses along the way. Beauty studios here serve the surrounding "
        "residential grid and are well-priced and accessible without the wait "
        "times you see closer to the beach."
    ),
}

# Fallback photos by category slug
# ── Businesses ────────────────────────────────────────────────────────────────
BUSINESSES: List[Dict[str, Any]] = [

    # ── HALLANDALE BEACH BLVD ─────────────────────────────────────────────────
    {
        "name": "European Wax Center — Hallandale Beach",
        "slug": "european-wax-center-hallandale-beach-blvd",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "2010 E Hallandale Beach Blvd", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 455-9292",
        "website": "https://www.waxcenter.com",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The national wax bar franchise with a Hallandale Beach location on the "
            "main boulevard — offering their signature Comfort Wax formula for face, "
            "body, and brow services in clean private suites. Walk-in friendly with "
            "a rewards program for regulars."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Nails by Ana",
        "slug": "nails-by-ana-hallandale-beach-blvd",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "1870 E Hallandale Beach Blvd", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 456-7823",
        "website": "",
        "instagram": "",
        "short_description": (
            "A neighborhood nail salon on Hallandale Beach Blvd known for "
            "clean technique and consistent results — full set acrylics, gel "
            "manicures, and pedicures at practical prices for the surrounding "
            "residential community."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    {
        "name": "Salon Icon Hallandale",
        "slug": "salon-icon-hallandale-beach-blvd",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "1900 E Hallandale Beach Blvd, Suite 106", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-0033",
        "website": "",
        "instagram": "@salonicon_hallandale",
        "short_description": (
            "A full-service hair salon serving the Hallandale Beach corridor with "
            "cuts, color, highlights, and treatments — built on regulars from the "
            "surrounding condos and the beach crowd that passes through on weekends."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Lush Lash Studio",
        "slug": "lush-lash-studio-hallandale-beach",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "2200 E Hallandale Beach Blvd, Suite 115", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 461-5588",
        "website": "",
        "instagram": "@lushlash_hb",
        "short_description": (
            "A lash and brow specialist studio on the eastern end of Hallandale "
            "Beach Blvd — classic, hybrid, and volume extensions plus brow shaping "
            "and tinting. Appointment-based with same-week availability and "
            "a loyal return clientele."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },
    {
        "name": "Bliss Nail Spa Hallandale",
        "slug": "bliss-nail-spa-hallandale-beach",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "1640 E Hallandale Beach Blvd", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 454-9900",
        "website": "",
        "instagram": "",
        "short_description": (
            "A spa-style nail salon with spa pedicure chairs, gel manicures, "
            "and dipping powder on Hallandale Beach Blvd — popular with the "
            "morning crowd and a clean, relaxed atmosphere that makes the "
            "appointment feel longer than it is."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Reflections Hair Salon",
        "slug": "reflections-hair-salon-hallandale-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "1755 E Hallandale Beach Blvd", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 458-1212",
        "website": "",
        "instagram": "",
        "short_description": (
            "A longtime Hallandale Beach hair salon serving the local residential "
            "community with cuts, color, perms, and relaxers — the kind of "
            "establishment that's been in the same spot long enough to have "
            "styled three generations of the same family."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "BrowBar Beauty Studio",
        "slug": "browbar-beauty-studio-hallandale-beach",
        "category_slugs": ["lash-brow", "waxing"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "2100 E Hallandale Beach Blvd, Suite 210", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 455-0044",
        "website": "",
        "instagram": "@browbar_hallandale",
        "short_description": (
            "The brow destination on Hallandale Beach Blvd — precision "
            "threading, waxing, and tinting with lash lifts and lamination "
            "for clients who want polished, natural-looking results without "
            "the commitment of extensions."
        ),
        "price_cues": "$",
        "editors_pick": True,
    },
    {
        "name": "Hallandale Beach Barbershop",
        "slug": "hallandale-beach-barbershop-blvd",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["hallandale-beach-blvd"],
        "address": {"street": "540 N Federal Hwy", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 456-4400",
        "website": "",
        "instagram": "",
        "short_description": (
            "A traditional barbershop on the north end of Federal Hwy in "
            "Hallandale Beach — straight razor fades, beard trims, and hot "
            "towel shaves for a clientele that values craft and a "
            "no-frills atmosphere. Walk-ins always welcome."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── VILLAGE AT GULFSTREAM PARK ────────────────────────────────────────────
    {
        "name": "Gloss + Groom at Gulfstream",
        "slug": "gloss-groom-gulfstream-park",
        "category_slugs": ["nails", "hair"],
        "neighborhood_slugs": ["village-at-gulfstream-park"],
        "address": {"street": "501 Silks Run", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-7788",
        "website": "",
        "instagram": "@glossgroom_gulfstream",
        "short_description": (
            "A nail and hair studio inside Village at Gulfstream Park — set "
            "within the upscale outdoor mall adjacent to the racetrack. "
            "Gel manicures, dipping powder, cuts, and blowouts for shoppers "
            "who want beauty services alongside their afternoon at the village."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Suki Salon Gulfstream",
        "slug": "suki-salon-gulfstream-park",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["village-at-gulfstream-park"],
        "address": {"street": "511 Silks Run, Suite 1340", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-3300",
        "website": "https://www.sukisalon.com",
        "instagram": "@sukisalon",
        "short_description": (
            "A full-service hair salon with a Village at Gulfstream Park location — "
            "offering precision cuts, color, balayage, and keratin treatments in "
            "a polished salon environment that matches the upscale retail district "
            "surrounding it."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Nuvō Brow & Beauty Bar",
        "slug": "nuvo-brow-beauty-bar-gulfstream",
        "category_slugs": ["lash-brow", "makeup"],
        "neighborhood_slugs": ["village-at-gulfstream-park"],
        "address": {"street": "501 Silks Run, Suite 1160", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-2211",
        "website": "",
        "instagram": "@nuvo_brow_gulfstream",
        "short_description": (
            "A brow and makeup studio at Village at Gulfstream Park offering "
            "microblading, brow lamination, lash lifts, and on-the-go makeup "
            "applications — the kind of quick beauty fix that fits between "
            "shopping and dinner at the village."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "The Spa at Hallandale",
        "slug": "the-spa-at-hallandale-gulfstream",
        "category_slugs": ["spa", "med-spa"],
        "neighborhood_slugs": ["village-at-gulfstream-park"],
        "address": {"street": "503 Silks Run", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 455-9100",
        "website": "",
        "instagram": "@thespa_hallandale",
        "short_description": (
            "A day spa and light med-spa at Gulfstream Park Village offering "
            "massages, facials, body wraps, and injectable consultations — "
            "the closest thing to a resort spa experience in Hallandale Beach "
            "without leaving the mainland."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Radiant Wax Gulfstream",
        "slug": "radiant-wax-gulfstream-park",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["village-at-gulfstream-park"],
        "address": {"street": "505 Silks Run, Suite 1140", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 455-0900",
        "website": "",
        "instagram": "@radiantwax_gulfstream",
        "short_description": (
            "A dedicated wax studio inside Village at Gulfstream Park — full "
            "body and facial waxing in private suites with a focus on "
            "precision and minimal irritation. Appointments recommended but "
            "walk-ins taken based on availability."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── GOLDEN ISLES ──────────────────────────────────────────────────────────
    {
        "name": "Golden Isles Beauty",
        "slug": "golden-isles-beauty-hallandale",
        "category_slugs": ["hair", "nails"],
        "neighborhood_slugs": ["golden-isles"],
        "address": {"street": "1000 S Ocean Dr", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-6622",
        "website": "",
        "instagram": "",
        "short_description": (
            "A neighborhood hair and nail salon in the Golden Isles residential "
            "enclave — full-service cuts, color, manicures, and pedicures "
            "for the waterfront community that prefers a familiar face and a "
            "relaxed appointment to a high-volume commercial salon."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Intracoastal Nail Lounge",
        "slug": "intracoastal-nail-lounge-hallandale",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["golden-isles"],
        "address": {"street": "700 S Ocean Dr", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 458-0033",
        "website": "",
        "instagram": "@intracoastal_nails",
        "short_description": (
            "A nail lounge near the Intracoastal in Golden Isles specializing "
            "in gel, dipping powder, and acrylic sets — a calm, quiet "
            "environment that reflects the neighborhood's residential character "
            "more than the high-volume salons on the main boulevard."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Coastal Glow Med Spa",
        "slug": "coastal-glow-med-spa-hallandale",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["golden-isles"],
        "address": {"street": "820 S Ocean Dr, Suite 201", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 456-8811",
        "website": "",
        "instagram": "@coastalglow_medspa",
        "short_description": (
            "A boutique medical spa in Golden Isles offering Botox, fillers, "
            "laser hair removal, and skin rejuvenation treatments — focused "
            "on natural-looking results for the Intracoastal neighborhood "
            "clientele that skews toward maintenance over dramatic change."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── NORTH FEDERAL HWY ─────────────────────────────────────────────────────
    {
        "name": "Studio Nova Hallandale",
        "slug": "studio-nova-hallandale-north-federal",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["north-federal-hwy"],
        "address": {"street": "1200 N Federal Hwy", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 457-1150",
        "website": "",
        "instagram": "@studionova_hallandale",
        "short_description": (
            "A hair salon on the north end of Federal Highway in Hallandale Beach, "
            "offering cuts, color, blowouts, and keratin treatments at mid-range "
            "prices for the residential neighborhoods it serves between "
            "Hollywood and Aventura."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Prestige Nails & Spa — North Hallandale",
        "slug": "prestige-nails-spa-north-hallandale",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["north-federal-hwy"],
        "address": {"street": "1480 N Federal Hwy", "city": "Hallandale Beach", "state": "FL", "postal_code": "33009", "country": "US"},
        "phone": "(954) 456-5577",
        "website": "",
        "instagram": "",
        "short_description": (
            "A nail and pedicure spa on the northern Federal Highway strip — "
            "gel manicures, spa pedicures, and acrylics at accessible prices "
            "for the surrounding apartment and condo community that sits "
            "between Hollywood and the Gulfstream Park area."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
]


async def seed_hallandale_beach() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
        network = await db.networks.find_one({"slug": BEAUTY_NETWORK_SLUG})
    if not network:
        print("ERROR: beauty network not found")
        return
    network_id = network["_id"]
    print(f"Found beauty network: id={network_id}")

    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network_id,
        "slug": CITY_SLUG,
        "name": "Hallandale Beach",
        "state": "FL",
        "country": "US",
        "domain_override": "hallandale-beach.knowsbeauty.com",
        "status": "live",
        "created_at": now,
        "updated_at": now,
        "timezone": "America/New_York",
        "short_description": (
            "Hallandale Beach sits between Hollywood and Aventura — a city of "
            "condos, the Intracoastal, and the legendary Gulfstream Park. The "
            "beauty scene here runs the full range: neighborhood nail studios on "
            "the main boulevard, upscale salons inside Village at Gulfstream, "
            "and boutique med-spas in the waterfront Golden Isles enclave."
        ),
        "meta_description": (
            "The curated beauty directory for Hallandale Beach, Florida — salons, spas, "
            "nail bars, and lash studios discovered by locals. Covering Hallandale Beach "
            "Boulevard, the Village at Gulfstream Park, and the Golden Isles waterfront."
        ),
        "tagline": "Hallandale Beach's most trusted beauty addresses.",
        "seo_title": "Hallandale Beach Knows Beauty",
        "hero_description": (
            "Between the racetrack glamour of Gulfstream Park and the Intracoastal "
            "calm of Golden Isles, Hallandale Beach has a beauty scene as varied "
            "as its neighborhoods. The corridor along Hallandale Beach Blvd keeps "
            "the city's everyday beauty appointments running, while Village at "
            "Gulfstream Park raises the bar with polished studios and a resort-adjacent "
            "clientele. Golden Isles adds a quieter, referral-driven layer for those "
            "who live by the water and want their beauty appointments to match."
        ),
        "header_nav": [
            {"label": "Hair Salons",    "href": "/hair-salons/"},
            {"label": "Nail Salons",    "href": "/nail-salons/"},
            {"label": "Waxing",         "href": "/waxing/"},
            {"label": "Lashes & Brows", "href": "/lash-brow/"},
            {"label": "Spas",           "href": "/spa/"},
            {"label": "Med Spas",       "href": "/med-spa/"},
        ],
        "spotlight": ["suki-salon-gulfstream-park", "coastal-glow-med-spa-hallandale"],
        "trending": [
            "european-wax-center-hallandale-beach-blvd",
            "suki-salon-gulfstream-park",
            "coastal-glow-med-spa-hallandale",
            "gloss-groom-gulfstream-park",
        ],
        "two_column_featured": {},
    }

    city = await upsert("cities", {"network_id": network_id, "slug": CITY_SLUG}, city_doc)
    city_id = city["_id"]
    print(f"Upserted city: {CITY_SLUG} (id={city_id})")

    # Neighborhoods
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nb_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city_id,
            "network_id": network_id,
            "slug": slug,
            "name": name,
            "vibe": vibe,
            "listed_count": listed_count,
            "description": NEIGHBORHOOD_DESCRIPTIONS.get(slug, ""),
            "hero_description": NEIGHBORHOOD_DESCRIPTIONS.get(slug, ""),
            "display_order": i,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("neighborhoods", {"city_id": city_id, "slug": slug}, nb_doc)
    print(f"Upserted {len(NEIGHBORHOODS)} neighborhoods.")

    # Categories — pulled from the network's canonical map
    categories_seeded = 0
    for order, group in enumerate(network.get("category_map") or []):
        cat_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city_id,
            "network_id": network_id,
            "slug": group["slug"],
            "name": group["name"],
            "display_order": order,
            "hero_photo_url": pick_category_photo("__hero__", group["slug"]) or "",
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("categories", {"city_id": city_id, "slug": group["slug"]}, cat_doc)
        categories_seeded += 1
    print(f"Upserted {categories_seeded} categories.")

    # Businesses
    inserted = updated = 0
    for biz in BUSINESSES:
        slug = biz["slug"]
        neighborhood_slugs = biz.get("neighborhood_slugs", [])

        biz_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city_id,
            "network_id": network_id,
            "slug": slug,
            "name": biz["name"],
            "status": "live",
            "category_slugs": biz.get("category_slugs", []),
            "neighborhood_slugs": neighborhood_slugs,
            "address": biz.get("address", {}),
            "phone": biz.get("phone", ""),
            "website": biz.get("website", ""),
            "instagram": biz.get("instagram", ""),
            "short_description": biz.get("short_description", ""),
            "price_cues": biz.get("price_cues", "$"),
            "editors_pick": biz.get("editors_pick", False),
            "is_founding_partner": False,
            "featured": {"enabled": False, "tier": "free"},
            "claim_status": "unclaimed",
            "photos": [],
            "hours": {},
            "created_at": now,
            "updated_at": now,
        }

        existing = await db.businesses.find_one({"city_id": city_id, "slug": slug})
        if existing:
            # Preserve claim/billing state — only update content fields
            if existing.get("status") == "archived":
                continue
            preserve = {k: existing[k] for k in (
                "claim_status", "is_founding_partner", "featured",
                "stripe_customer_id", "stripe_subscription_id",
                "photos", "hours",
                # WHY: preserve Google sync data — these fields are expensive to
                # re-fetch (~$0.017/call) and the seed file has no way to know
                # the correct values. A re-seed must not wipe cached Google ratings.
                "google_place_id", "google_rating", "google_review_count",
                "google_rating_synced_at",
            ) if k in existing}
            biz_doc.update(preserve)
            biz_doc["_id"] = existing["_id"]
            biz_doc["created_at"] = existing.get("created_at", now)
            await db.businesses.replace_one({"_id": existing["_id"]}, biz_doc)
            updated += 1
        else:
            await db.businesses.insert_one(biz_doc)
            inserted += 1

    print(f"Businesses: {inserted} inserted, {updated} updated.")
    print(
        f"\nHallandale Beach seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       beauty (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {categories_seeded}\n"
        f"  Businesses:    {len(BUSINESSES)} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_hallandale_beach()


if __name__ == "__main__":
    run(main())
