"""Seed Miami across the Beauty, Wellness, and Health networks.

Creates the city record, neighborhoods, city-scoped category instances (one
per master category in each network), and a small set of sample businesses
so the public pages have something real to render.

Run inside the backend container, after seed_networks.py:
    python -m seed.seed_miami
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import run, upsert


MIAMI_NEIGHBORHOODS = [
    {"slug": "south-beach", "name": "South Beach", "description": "Ocean Drive, Lincoln Road, and the Art Deco district — Miami's most photographed stretch.", "order": 1},
    {"slug": "mid-beach", "name": "Mid-Beach", "description": "Quieter, design-forward stretch of Collins between South Beach and Surfside.", "order": 2},
    {"slug": "brickell", "name": "Brickell", "description": "Miami's financial district — high-rises, hotels, and a constant flow of professionals.", "order": 3},
    {"slug": "downtown", "name": "Downtown", "description": "The civic and cultural heart of the city.", "order": 4},
    {"slug": "wynwood", "name": "Wynwood", "description": "Murals, galleries, breweries — Miami's creative neighborhood.", "order": 5},
    {"slug": "design-district", "name": "Design District", "description": "Luxury boutiques and showrooms north of Midtown.", "order": 6},
    {"slug": "midtown", "name": "Midtown", "description": "Between Wynwood and the Design District — residential mix with strong dining.", "order": 7},
    {"slug": "edgewater", "name": "Edgewater", "description": "Bayfront condos between downtown and the Design District.", "order": 8},
    {"slug": "coconut-grove", "name": "Coconut Grove", "description": "Lush, walkable, and historic — Miami's oldest neighborhood.", "order": 9},
    {"slug": "coral-gables", "name": "Coral Gables", "description": "Tree-lined, Mediterranean revival, anchored by Miracle Mile.", "order": 10},
    {"slug": "little-havana", "name": "Little Havana", "description": "Calle Ocho, ventanitas, and Cuban-American culture.", "order": 11},
    {"slug": "key-biscayne", "name": "Key Biscayne", "description": "Island living south of the city — beaches and the Cape Florida lighthouse.", "order": 12},
    {"slug": "aventura", "name": "Aventura", "description": "North Miami-Dade hub with the mall and family-oriented services.", "order": 13},
    {"slug": "bay-harbor-islands", "name": "Bay Harbor Islands", "description": "Quiet residential islands between the mainland and Bal Harbour.", "order": 14},
    {"slug": "surfside", "name": "Surfside", "description": "Walkable beach village north of Mid-Beach.", "order": 15},
    {"slug": "doral", "name": "Doral", "description": "Suburban west Miami-Dade with strong international community.", "order": 16},
]


# Sample businesses per network — small set so each page has real content.
BEAUTY_SAMPLE_BUSINESSES = [
    {
        "slug": "loft-647-miami",
        "name": "Loft 647 Miami",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wynwood"],
        "address": {"street": "647 NW 24th St", "city": "Miami", "state": "FL", "postal_code": "33127"},
        "phone": "+1-305-555-0117",
        "website": "https://example.com/loft647",
        "booking_url": "https://example.com/loft647/book",
        "socials": {"instagram": "loft647miami"},
        "short_description": "A Wynwood salon known for editorial color, lived-in blondes, and creative cuts.",
        "known_for": "Lived-in blonde, balayage, and creative cuts. The team is known for color corrections most other salons turn down.",
        "best_for": "People moving on from box dye, or anyone who wants their color to grow out without a hard line.",
        "before_booking_notes": "Color appointments require a consultation first. Book the consult two weeks ahead in season.",
        "price_cues": "$$$",
        "schema_org_type": "HairSalon",
        "editors_pick": True,
        "quality_score": 88,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "glamour-nails-brickell",
        "name": "Glamour Nails",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["brickell"],
        "address": {"street": "1101 Brickell Ave Suite 200", "city": "Miami", "state": "FL", "postal_code": "33131"},
        "phone": "+1-305-555-0142",
        "website": "https://example.com/glamour-nails",
        "booking_url": "https://example.com/glamour-nails/book",
        "socials": {"instagram": "glamournailsbrickell"},
        "short_description": "A Brickell nail studio known for detailed gel manicures and clean neutrals.",
        "known_for": "Detailed gel manicures, clean neutral looks, and appointment-friendly service for clients booking around work.",
        "best_for": "Clients who want a polished, reliable manicure without a full spa experience.",
        "before_booking_notes": "Walk-ins fill the same day. Book 48 hours ahead for weekend slots.",
        "price_cues": "$$",
        "schema_org_type": "NailSalon",
        "featured": {"enabled": True, "tier": "enhanced"},
        "quality_score": 82,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "skin-by-renata",
        "name": "Skin by Renata",
        "category_slugs": ["skin"],
        "neighborhood_slugs": ["coral-gables"],
        "address": {"street": "350 Miracle Mile Suite 4", "city": "Coral Gables", "state": "FL", "postal_code": "33134"},
        "phone": "+1-305-555-0168",
        "website": "https://example.com/skin-by-renata",
        "socials": {"instagram": "skinbyrenata"},
        "short_description": "Coral Gables skincare studio focused on acne, melasma, and barrier-friendly facials.",
        "known_for": "Acne protocols and melasma support for Miami sun and humidity. Pro-grade peels with realistic downtime.",
        "best_for": "Anyone treating melasma, persistent breakouts, or post-procedure rebuilding.",
        "before_booking_notes": "First visit is a consultation. Bring a list of current actives.",
        "price_cues": "$$$",
        "schema_org_type": "DaySpa",
        "claim_status": "verified",
        "quality_score": 90,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "lash-lab-mid-beach",
        "name": "Lash Lab Mid-Beach",
        "category_slugs": ["lashes-brows"],
        "neighborhood_slugs": ["mid-beach"],
        "address": {"street": "4441 Collins Ave Suite 12", "city": "Miami Beach", "state": "FL", "postal_code": "33140"},
        "phone": "+1-305-555-0186",
        "website": "https://example.com/lashlab",
        "socials": {"instagram": "lashlabmidbeach"},
        "short_description": "Mid-Beach studio known for classic and hybrid lash sets that survive humidity.",
        "known_for": "Long-wearing classic and hybrid sets engineered for ocean air. Brow shaping and lamination by appointment.",
        "best_for": "Travel-heavy clients who need lashes to hold up between fills.",
        "price_cues": "$$",
        "schema_org_type": "BeautySalon",
        "quality_score": 78,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "kala-makeup-collective",
        "name": "Kala Makeup Collective",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["design-district"],
        "address": {"street": "140 NE 39th St Suite 6", "city": "Miami", "state": "FL", "postal_code": "33137"},
        "phone": "+1-305-555-0210",
        "website": "https://example.com/kala",
        "socials": {"instagram": "kalamakeup"},
        "short_description": "On-site and studio makeup team for weddings, events, and editorial work.",
        "known_for": "Bridal and editorial makeup with skin that reads beautifully on camera without looking heavy.",
        "best_for": "Brides, anchor talent, and event clients who want makeup to last through humidity and dinner.",
        "price_cues": "$$$",
        "schema_org_type": "BeautySalon",
        "editors_pick": True,
        "quality_score": 84,
        "status": "live",
        "index_status": "indexed",
    },
]

WELLNESS_SAMPLE_BUSINESSES = [
    {
        "slug": "stillwater-spa-collins",
        "name": "Stillwater Spa",
        "category_slugs": ["spas-relaxation"],
        "neighborhood_slugs": ["mid-beach"],
        "address": {"street": "4525 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33140"},
        "phone": "+1-305-555-0301",
        "website": "https://example.com/stillwater",
        "short_description": "Mid-Beach hotel spa with a serious massage program and ocean-front treatment rooms.",
        "known_for": "Deep tissue and lymphatic massage with practitioners who actually adjust pressure to feedback.",
        "best_for": "Anyone with chronic tension who wants therapeutic — not just relaxing — bodywork.",
        "before_booking_notes": "Book 90 minutes if you've never been; the consultation eats the first 15.",
        "price_cues": "$$$$",
        "schema_org_type": "DaySpa",
        "editors_pick": True,
        "quality_score": 89,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "ember-cold-plunge",
        "name": "Ember Cold Plunge Club",
        "category_slugs": ["recovery-cold-plunge"],
        "neighborhood_slugs": ["wynwood"],
        "address": {"street": "250 NW 27th St", "city": "Miami", "state": "FL", "postal_code": "33127"},
        "phone": "+1-305-555-0322",
        "website": "https://example.com/ember",
        "socials": {"instagram": "emberplunge"},
        "short_description": "Wynwood members club for contrast therapy — infrared sauna, cold plunge, compression.",
        "known_for": "Contrast cycles run on a fixed clock so members can drop in without booking.",
        "best_for": "Athletes and travel-heavy professionals fitting recovery into morning routines.",
        "price_cues": "$$",
        "featured": {"enabled": True, "tier": "enhanced"},
        "quality_score": 80,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "north-room-yoga",
        "name": "North Room Yoga",
        "category_slugs": ["yoga-meditation"],
        "neighborhood_slugs": ["coconut-grove"],
        "address": {"street": "3201 Commodore Plaza", "city": "Coconut Grove", "state": "FL", "postal_code": "33133"},
        "phone": "+1-305-555-0345",
        "website": "https://example.com/northroom",
        "socials": {"instagram": "northroomyoga"},
        "short_description": "Coconut Grove studio with a steady morning practice and a strong restorative program.",
        "known_for": "Heat is controlled — not extreme. Teachers offer real cueing on alignment rather than playlists.",
        "best_for": "Practitioners coming back from injury or looking for a less performative studio.",
        "price_cues": "$$",
        "claim_status": "verified",
        "quality_score": 83,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "hydra-iv-brickell",
        "name": "Hydra IV Brickell",
        "category_slugs": ["iv-hydration"],
        "neighborhood_slugs": ["brickell"],
        "address": {"street": "1200 Brickell Ave", "city": "Miami", "state": "FL", "postal_code": "33131"},
        "phone": "+1-305-555-0359",
        "website": "https://example.com/hydraiv",
        "short_description": "Brickell IV lounge for hydration, post-flight recovery, and immunity drips.",
        "known_for": "Same-day drips with consultations conducted by registered nurses.",
        "best_for": "Travelers landing dehydrated, or anyone catching a cold the day before a big event.",
        "price_cues": "$$$",
        "quality_score": 74,
        "status": "live",
        "index_status": "indexed",
    },
]

HEALTH_SAMPLE_BUSINESSES = [
    {
        "slug": "gables-cosmetic-dentistry",
        "name": "Gables Cosmetic Dentistry",
        "category_slugs": ["dental-smile"],
        "neighborhood_slugs": ["coral-gables"],
        "address": {"street": "2811 Ponce de Leon Blvd", "city": "Coral Gables", "state": "FL", "postal_code": "33134"},
        "phone": "+1-305-555-0410",
        "website": "https://example.com/gables-cosmetic-dentistry",
        "short_description": "Coral Gables practice focused on veneers, Invisalign, and adult orthodontics.",
        "known_for": "Conservative veneer work and full smile-design consultations using digital previews before any tooth prep.",
        "best_for": "Adults considering cosmetic dentistry who want to see options before committing.",
        "price_cues": "$$$$",
        "schema_org_type": "Dentist",
        "claim_status": "verified",
        "editors_pick": True,
        "quality_score": 92,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "atlas-mental-health",
        "name": "Atlas Mental Health",
        "category_slugs": ["mental-health-therapy"],
        "neighborhood_slugs": ["brickell"],
        "address": {"street": "801 Brickell Ave Suite 1500", "city": "Miami", "state": "FL", "postal_code": "33131"},
        "phone": "+1-305-555-0428",
        "website": "https://example.com/atlas-mental-health",
        "short_description": "Brickell therapy group with psychiatrists, therapists, and family work.",
        "known_for": "In-network with major insurers. Practice mix includes anxiety, ADHD evaluation, and couples therapy.",
        "best_for": "Professionals and families looking for both medication management and weekly therapy under one practice.",
        "price_cues": "$$$",
        "schema_org_type": "MedicalBusiness",
        "quality_score": 86,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "metro-primary-care",
        "name": "Metro Primary Care",
        "category_slugs": ["primary-care-clinics"],
        "neighborhood_slugs": ["midtown"],
        "address": {"street": "3401 N Miami Ave Suite 2", "city": "Miami", "state": "FL", "postal_code": "33127"},
        "phone": "+1-305-555-0461",
        "website": "https://example.com/metro-primary",
        "short_description": "Direct primary care practice serving Midtown and Wynwood — same-day visits for members.",
        "known_for": "Membership model with same-day appointments and direct messaging access to a primary care physician.",
        "best_for": "Adults without insurance who want predictable monthly cost for primary care.",
        "price_cues": "$$",
        "schema_org_type": "MedicalBusiness",
        "quality_score": 81,
        "status": "live",
        "index_status": "indexed",
    },
    {
        "slug": "miami-fertility-collective",
        "name": "Miami Fertility Collective",
        "category_slugs": ["fertility-womens-health"],
        "neighborhood_slugs": ["aventura"],
        "address": {"street": "20801 Biscayne Blvd Suite 300", "city": "Aventura", "state": "FL", "postal_code": "33180"},
        "phone": "+1-305-555-0489",
        "website": "https://example.com/miami-fertility",
        "short_description": "Aventura fertility clinic offering IVF, egg freezing, and reproductive endocrinology.",
        "known_for": "Multidisciplinary fertility care with an in-house IVF lab and Spanish-speaking nurse navigators.",
        "best_for": "Patients exploring IVF or egg freezing who want a clinic with both clinical and emotional support.",
        "price_cues": "$$$$",
        "schema_org_type": "MedicalBusiness",
        "featured": {"enabled": True, "tier": "premium"},
        "quality_score": 87,
        "status": "live",
        "index_status": "indexed",
    },
]


NETWORK_SAMPLES = {
    "beauty": (
        "Miami's best-kept beauty addresses.",
        "A curated guide to the salons, med spas, nail artists, colorists, and glam pros Miami locals book before dinner, beach weekends, weddings, and big nights out.",
        "Miami Beauty Guide: Salons, Spas, Med Spas, Nails & Hair",
        BEAUTY_SAMPLE_BUSINESSES,
    ),
    "wellness": (
        "Miami's go-to wellness, beach to Brickell.",
        "Spas, recovery rooms, yoga studios, IV lounges, and wellness practices Miami locals trust between travel and big work weeks.",
        "Miami Wellness Guide: Spas, Recovery, Yoga, IV, Nutrition",
        WELLNESS_SAMPLE_BUSINESSES,
    ),
    "health": (
        "Miami's doctors, dentists, and clinics — chosen by neighborhood.",
        "A provider directory for cosmetic dentistry, mental health, fertility, primary care, and specialists across Greater Miami. We help you find the right provider; medical decisions remain between you and them.",
        "Miami Health Guide: Doctors, Dentists, Therapists & Clinics",
        HEALTH_SAMPLE_BUSINESSES,
    ),
}


async def seed_network(network_slug: str) -> None:
    db = get_db()
    network = await db.networks.find_one({"slug": network_slug})
    if not network:
        print(f"Network {network_slug} not found — run seed_networks.py first.")
        return

    tagline, hero, seo_title, businesses = NETWORK_SAMPLES[network_slug]
    now = datetime.now(timezone.utc)

    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network["_id"],
        "slug": "miami",
        "name": "Miami",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": tagline,
        "hero_description": hero,
        "seo_title": seo_title,
        "meta_description": hero,
        "editorial_headlines": [
            {"headline": tagline, "is_default": True},
            {"headline": "Where Miami gets ready before the week gets photographed.", "is_default": False},
            {"headline": "Miami, built for heat, humidity, and big nights out.", "is_default": False},
        ],
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network["_id"], "slug": "miami"}, city_doc)
    print(f"  City: {network_slug} / miami")

    for i, nb in enumerate(MIAMI_NEIGHBORHOODS):
        nb_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city["_id"],
            "slug": nb["slug"],
            "name": nb["name"],
            "description": nb["description"],
            "order": nb["order"],
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert(
            "neighborhoods",
            {"city_id": city["_id"], "slug": nb["slug"]},
            nb_doc,
        )
    print(f"  Neighborhoods: {len(MIAMI_NEIGHBORHOODS)}")

    # Categories: copy the network's master category list into city-scoped rows.
    for order, group in enumerate(network.get("category_map") or []):
        cat_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network["_id"],
            "city_id": city["_id"],
            "slug": group["slug"],
            "parent_slug": None,
            "name": group["name"],
            "description": group.get("description"),
            "examples": group.get("examples", []),
            "order": order,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert(
            "categories",
            {"city_id": city["_id"], "slug": group["slug"]},
            cat_doc,
        )
    print(f"  Categories: {len(network.get('category_map') or [])}")

    for biz in businesses:
        biz_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network["_id"],
            "city_id": city["_id"],
            "slug": biz["slug"],
            "name": biz["name"],
            "category_slugs": biz["category_slugs"],
            "neighborhood_slugs": biz.get("neighborhood_slugs", []),
            "address": biz.get("address", {}),
            "phone": biz.get("phone"),
            "website": biz.get("website"),
            "email": biz.get("email"),
            "booking_url": biz.get("booking_url"),
            "socials": biz.get("socials", {}),
            "hours": biz.get("hours", []),
            "services": biz.get("services", []),
            "photos": biz.get("photos", []),
            "short_description": biz.get("short_description"),
            "known_for": biz.get("known_for"),
            "best_for": biz.get("best_for"),
            "before_booking_notes": biz.get("before_booking_notes"),
            "price_cues": biz.get("price_cues"),
            "featured": biz.get("featured", {"enabled": False, "tier": "free"}),
            "editors_pick": biz.get("editors_pick", False),
            "claim_status": biz.get("claim_status", "unclaimed"),
            "schema_org_type": biz.get("schema_org_type", "LocalBusiness"),
            "data_source": biz.get("data_source", "editorial"),
            "quality_score": biz.get("quality_score", 50),
            "index_status": biz.get("index_status", "indexed"),
            "index_override": "auto",
            "status": biz.get("status", "live"),
            "created_at": now,
            "updated_at": now,
        }
        await upsert(
            "businesses",
            {"city_id": city["_id"], "slug": biz["slug"]},
            biz_doc,
        )
    print(f"  Businesses: {len(businesses)}")


async def main() -> None:
    await ensure_indexes()
    for slug in ("beauty", "wellness", "health"):
        print(f"== Seeding Miami for {slug} ==")
        await seed_network(slug)


if __name__ == "__main__":
    run(main())
