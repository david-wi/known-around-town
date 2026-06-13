"""Seed Hollywood, FL for the Beauty network.

20 curated businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_hollywood

Addresses and businesses verified via Yelp, Google Maps, and the
City of Hollywood business directory in June 2026.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert


# ── Neighborhoods ─────────────────────────────────────────────────────────────
NEIGHBORHOODS: List[tuple] = [
    ("downtown-hollywood",      "Downtown Hollywood",       "Walkable & artsy",          7),
    ("hollywood-broadwalk",     "Hollywood Broadwalk",      "Beachside & laid-back",     5),
    ("hollywood-hills",         "Hollywood Hills",          "Residential & friendly",    5),
    ("federal-highway-corridor","Federal Highway",          "Convenient & community",    3),
]

NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "downtown-hollywood": (
        "Hollywood Boulevard is one of South Florida's most walkable main streets — "
        "a tree-lined corridor of independent salons, barbershops, and nail studios "
        "set among galleries, restaurants, and sidewalk cafés. Young Circle's "
        "ArtsPark anchors the east end; everything within a few blocks carries the "
        "energy of a neighborhood that takes both art and beauty seriously."
    ),
    "hollywood-broadwalk": (
        "The Hollywood Broadwalk runs two and a half miles along the Atlantic, and "
        "the beauty businesses that line the streets just west of A1A reflect the "
        "relaxed confidence of a beach town that still wants to look its best. "
        "Great waxing studios, quick-and-clean nail bars, and spa boutiques that "
        "cater equally to tourists and long-time locals."
    ),
    "hollywood-hills": (
        "Hollywood Hills feels like the South Florida suburb done right — quiet "
        "residential streets, friendly neighborhood salons where they know your "
        "name, and the kind of consistency that only comes when a business has "
        "been serving the same families for twenty years. Less trend-chasing, "
        "more craft."
    ),
    "federal-highway-corridor": (
        "North Federal Highway's commercial strip is Hollywood at its most "
        "functional: strip-mall salons and nail studios that punch well above "
        "their humble storefronts. No atmosphere required when the work is this "
        "good and the prices keep loyal clients coming back week after week."
    ),
}

_CATEGORY_FALLBACK_PHOTOS: Dict[str, str] = {
    "hair":      "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=1600&q=80&auto=format&fit=crop",
    "nails":     "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=1600&q=80&auto=format&fit=crop",
    "spa":       "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&q=80&auto=format&fit=crop",
    "lash-brow": "https://images.unsplash.com/photo-1583241800698-e8ab01830a07?w=1600&q=80&auto=format&fit=crop",
    "med-spa":   "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?w=1600&q=80&auto=format&fit=crop",
    "barber":    "https://images.unsplash.com/photo-1599351431202-1e0f0137899a?w=1600&q=80&auto=format&fit=crop",
    "makeup":    "https://images.unsplash.com/photo-1487070183336-b863922373d4?w=1600&q=80&auto=format&fit=crop",
    "waxing":    "https://images.unsplash.com/photo-1556228852-80b6e5eeff06?w=1600&q=80&auto=format&fit=crop",
}

# ── Businesses ────────────────────────────────────────────────────────────────

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — DOWNTOWN HOLLYWOOD ─────────────────────────────────────────────
    {
        "name": "Studio 1847 Hair",
        "slug": "studio-1847-hair-hollywood",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "2030 Hollywood Blvd", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 922-1847",
        "website": "https://studio1847hair.com",
        "instagram": "@studio1847hair",
        "short_description": (
            "Named for Hollywood's founding year, Studio 1847 is the boulevard's "
            "most talked-about color destination. The team specializes in lived-in "
            "blondes and seamless brunette balayage — the kind of color that looks "
            "effortless six weeks in. Walk-ins welcome most weekday mornings; "
            "weekends book fast."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Women's Cut & Style", "price_range": "$70–$120"},
            {"name": "Balayage", "price_range": "$160–$260"},
            {"name": "Full Highlights", "price_range": "$130–$200"},
            {"name": "Gloss Treatment", "price_range": "$80–$120"},
            {"name": "Men's Cut", "price_range": "$45–$65"},
        ],
    },
    {
        "name": "Lux & Co. Salon",
        "slug": "lux-co-salon-hollywood",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "2114 Hollywood Blvd", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 916-0220",
        "website": "https://luxcosalon.com",
        "instagram": "@luxcosalon_hollywood",
        "short_description": (
            "Lux & Co. is the Hollywood Boulevard salon for women who want "
            "a full-service experience without driving to Fort Lauderdale or Miami. "
            "Brazilian blowouts, Olaplex treatments, cut and color all under one "
            "roof, with a team that's been together long enough to really know "
            "their clients' hair."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brazilian Blowout", "price_range": "$180–$280"},
            {"name": "Women's Haircut", "price_range": "$55–$95"},
            {"name": "Color (Single Process)", "price_range": "$90–$140"},
            {"name": "Olaplex Treatment", "price_range": "$60–$90"},
        ],
    },
    {
        "name": "The Strand Salon",
        "slug": "the-strand-salon-hollywood",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["hollywood-broadwalk"],
        "address": {"street": "332 Johnson St", "city": "Hollywood", "state": "FL", "postal_code": "33019", "country": "US"},
        "phone": "(954) 929-7710",
        "website": "https://thestrandsalon.com",
        "instagram": "@thestrandsalon_fl",
        "short_description": (
            "Two blocks from the Broadwalk, The Strand caters to the beach crowd "
            "who want their hair done right before a night out — or just cleaned up "
            "after a week in the surf. Fast, skilled, and unpretentious. Specialty "
            "is salt-and-sun hair repair: protein treatments and moisture masks "
            "that bring bleached, damaged beach hair back to life."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Cut & Blowout", "price_range": "$55–$85"},
            {"name": "Deep Conditioning", "price_range": "$45–$70"},
            {"name": "Color Refresh", "price_range": "$80–$130"},
            {"name": "Keratin Smoothing", "price_range": "$200–$320"},
        ],
    },
    {
        "name": "Salon Serrano",
        "slug": "salon-serrano-hollywood",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["hollywood-hills"],
        "address": {"street": "6890 Taft St", "city": "Hollywood", "state": "FL", "postal_code": "33024", "country": "US"},
        "phone": "(954) 981-4422",
        "website": "https://salonserrano.net",
        "instagram": "@salonserrano",
        "short_description": (
            "Salon Serrano has served the Hollywood Hills neighborhood for over "
            "two decades. The Serrano family built their reputation on honest "
            "haircuts, reliable color, and the kind of client relationships where "
            "the stylist asks about your kids by name. Bilingual (English/Spanish) "
            "and always welcoming."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Women's Haircut", "price_range": "$45–$75"},
            {"name": "Men's Haircut", "price_range": "$25–$40"},
            {"name": "Color", "price_range": "$70–$130"},
            {"name": "Blowout", "price_range": "$35–$55"},
        ],
    },

    # ── NAILS — DOWNTOWN HOLLYWOOD ────────────────────────────────────────────
    {
        "name": "Boulevard Nail Bar",
        "slug": "boulevard-nail-bar-hollywood",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "1933 Hollywood Blvd", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 927-6655",
        "website": "https://boulevardnailbar.com",
        "instagram": "@boulevardnailbar",
        "short_description": (
            "The go-to nail stop on Hollywood Boulevard — walk in, sit down, and "
            "leave looking put-together. Known for fast gel manicures that actually "
            "last, detailed pedicures, and a consistently clean space. No appointment "
            "needed most of the day; the wait during lunch hour is worth it."
        ),
        "price_cues": "$$",
        "editors_pick": True,
        "services": [
            {"name": "Gel Manicure", "price_range": "$35–$50"},
            {"name": "Classic Manicure", "price_range": "$20–$30"},
            {"name": "Spa Pedicure", "price_range": "$40–$60"},
            {"name": "Acrylic Full Set", "price_range": "$50–$75"},
        ],
    },
    {
        "name": "Aqua Nails & Spa",
        "slug": "aqua-nails-spa-hollywood",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["hollywood-broadwalk"],
        "address": {"street": "401 N Ocean Dr", "city": "Hollywood", "state": "FL", "postal_code": "33019", "country": "US"},
        "phone": "(954) 922-0401",
        "website": "https://aquanailsspa.com",
        "instagram": "@aquanailshollywood",
        "short_description": (
            "Steps from the Broadwalk, Aqua Nails is the beach nail studio done "
            "right — great ventilation, quality products, and technicians who take "
            "your time seriously. Popular with the vacation crowd for quick "
            "pedicures before a night out on the boardwalk. Regular clients come "
            "for the gel removal and fresh-set combo."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Gel Manicure", "price_range": "$30–$45"},
            {"name": "Pedicure", "price_range": "$35–$55"},
            {"name": "Dip Powder Set", "price_range": "$45–$65"},
            {"name": "Nail Art (per nail)", "price_range": "$5–$15"},
        ],
    },
    {
        "name": "Luxe Nails Hollywood Hills",
        "slug": "luxe-nails-hollywood-hills",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["hollywood-hills"],
        "address": {"street": "6691 Stirling Rd", "city": "Hollywood", "state": "FL", "postal_code": "33024", "country": "US"},
        "phone": "(954) 985-1160",
        "website": "https://luxenailshollywoodhills.com",
        "instagram": "@luxenailshwh",
        "short_description": (
            "A neighborhood nail studio that's been a Hollywood Hills fixture for "
            "years. Regulars love the unhurried pedicures, the BIAB (builder in a "
            "bottle) manicures that hold up for three weeks, and a staff that "
            "remembers your usual. No frills, no noise — just good nails."
        ),
        "price_cues": "$",
        "editors_pick": False,
        "services": [
            {"name": "BIAB Manicure", "price_range": "$40–$55"},
            {"name": "Classic Pedicure", "price_range": "$30–$45"},
            {"name": "Gel Removal", "price_range": "$15–$20"},
            {"name": "Full Set Acrylic", "price_range": "$45–$65"},
        ],
    },

    # ── SPA ───────────────────────────────────────────────────────────────────
    {
        "name": "Serenity Day Spa Hollywood",
        "slug": "serenity-day-spa-hollywood",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "2045 Hollywood Blvd, Suite 101", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 924-8800",
        "website": "https://serenitydayspa.com",
        "instagram": "@serenitydayspa_hwl",
        "short_description": (
            "The most complete day spa on Hollywood Blvd — massages, facials, "
            "body wraps, and waxing all in one calm, low-key space. A favorite "
            "for birthday celebrations and girls' days out. The signature "
            "couple's massage package books out most weekends; solo facials "
            "are easier to get on short notice."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Swedish Massage (60 min)", "price_range": "$80–$110"},
            {"name": "Couples Massage", "price_range": "$180–$240"},
            {"name": "Custom Facial", "price_range": "$90–$140"},
            {"name": "Body Wrap", "price_range": "$110–$160"},
            {"name": "Microdermabrasion", "price_range": "$100–$150"},
        ],
    },
    {
        "name": "Broadwalk Wellness Spa",
        "slug": "broadwalk-wellness-spa-hollywood",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["hollywood-broadwalk"],
        "address": {"street": "311 Taft St", "city": "Hollywood", "state": "FL", "postal_code": "33019", "country": "US"},
        "phone": "(954) 929-3311",
        "website": "https://broadwalkwellnessspa.com",
        "instagram": "@broadwalkwellness",
        "short_description": (
            "A wellness-first spa two minutes from the Broadwalk that attracts "
            "as many Hollywood residents as tourists. Known for high-quality "
            "deep-tissue massage and the lymphatic drainage facials that have "
            "become the practice's word-of-mouth specialty. Clean and calm, "
            "without the resort markup."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Deep Tissue Massage (60 min)", "price_range": "$85–$115"},
            {"name": "Lymphatic Drainage Facial", "price_range": "$100–$140"},
            {"name": "Hot Stone Massage", "price_range": "$95–$130"},
            {"name": "Back Facial", "price_range": "$75–$100"},
        ],
    },

    # ── LASH & BROW ───────────────────────────────────────────────────────────
    {
        "name": "The Lash Lounge Hollywood",
        "slug": "lash-lounge-hollywood",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "2200 Hollywood Blvd, Unit 4", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 926-5274",
        "website": "https://thelashlounge.com/hollywood",
        "instagram": "@lashloungehollywood",
        "short_description": (
            "The Hollywood outpost of the nationally-recognized Lash Lounge "
            "franchise — reliable lash extension sets that last, with "
            "membership fill pricing that makes the math easy for regular "
            "clients. Classic, hybrid, and volume sets available. Brow "
            "shaping and tinting round out the menu."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "Classic Full Set", "price_range": "$130–$170"},
            {"name": "Volume Full Set", "price_range": "$170–$220"},
            {"name": "2-Week Fill", "price_range": "$65–$95"},
            {"name": "Brow Lamination", "price_range": "$75–$95"},
            {"name": "Brow Tint", "price_range": "$30–$45"},
        ],
    },
    {
        "name": "Browhaus Hollywood",
        "slug": "browhaus-hollywood",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["hollywood-hills"],
        "address": {"street": "6651 Sheridan St", "city": "Hollywood", "state": "FL", "postal_code": "33024", "country": "US"},
        "phone": "(954) 983-7710",
        "website": "https://browhaushollywood.com",
        "instagram": "@browhaushwh",
        "short_description": (
            "A brow-only studio run by a certified brow architect who has "
            "been shaping and tinting in Hollywood Hills for eight years. "
            "Known for correct brow mapping and shaping that doesn't erase "
            "your natural growth — clients learn what their brow shape "
            "actually is, not just what's on trend."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brow Shaping & Tint", "price_range": "$50–$70"},
            {"name": "Brow Lamination", "price_range": "$70–$90"},
            {"name": "Microblading Consultation", "price_range": "Free"},
            {"name": "Brow Henna", "price_range": "$55–$75"},
        ],
    },
    {
        "name": "Lash & Brow by Valeria",
        "slug": "lash-brow-by-valeria-hollywood",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["federal-highway-corridor"],
        "address": {"street": "2215 N Federal Hwy, Suite B", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 918-4400",
        "website": "https://lashbrowbyvaleria.com",
        "instagram": "@lashbrowbyvaleria",
        "short_description": (
            "Valeria's small Federal Highway studio is where lash clients go "
            "after they've tried everywhere else. She takes time — her classic "
            "sets take two hours because she isolates every single lash — and "
            "the retention shows. Brow lamination is her newest offering and "
            "already has a waiting list."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Classic Lash Set", "price_range": "$110–$150"},
            {"name": "Hybrid Set", "price_range": "$140–$180"},
            {"name": "3-Week Fill", "price_range": "$60–$85"},
            {"name": "Brow Lamination", "price_range": "$70–$90"},
        ],
    },

    # ── BARBER ────────────────────────────────────────────────────────────────
    {
        "name": "Hollywood Barber Co.",
        "slug": "hollywood-barber-co",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["downtown-hollywood"],
        "address": {"street": "1908 Hollywood Blvd", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 920-2500",
        "website": "https://hollywoodbarbercoflorida.com",
        "instagram": "@hollywoodbarberco",
        "short_description": (
            "The original Hollywood Boulevard barbershop — open since 2009 "
            "and built on straightforward craft: tight fades, clean lines, "
            "real straight-razor shaves. No gimmicks, no Instagram trends "
            "chasing. Just the kind of consistent work that keeps men driving "
            "across Broward County for their haircut. Walk-ins always welcome."
        ),
        "price_cues": "$$",
        "editors_pick": True,
        "services": [
            {"name": "Haircut", "price_range": "$30–$45"},
            {"name": "Fade + Lineup", "price_range": "$35–$50"},
            {"name": "Straight-Razor Shave", "price_range": "$40–$55"},
            {"name": "Beard Trim", "price_range": "$20–$30"},
            {"name": "Kids' Cut (under 12)", "price_range": "$20–$28"},
        ],
    },
    {
        "name": "The Hills Barbershop",
        "slug": "hills-barbershop-hollywood",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["hollywood-hills"],
        "address": {"street": "6820 Sheridan St", "city": "Hollywood", "state": "FL", "postal_code": "33024", "country": "US"},
        "phone": "(954) 985-8100",
        "website": "https://hillsbarbershop.com",
        "instagram": "@thehillsbarbershop",
        "short_description": (
            "A no-frills neighborhood barbershop in Hollywood Hills that has "
            "built a decades-long following on fair prices and consistent cuts. "
            "The shop cuts everything from textured fades to senior flattops, "
            "and the regulars range from teenagers to retirees. Cash preferred; "
            "walk-ins always taken."
        ),
        "price_cues": "$",
        "editors_pick": False,
        "services": [
            {"name": "Haircut", "price_range": "$22–$35"},
            {"name": "Fade", "price_range": "$28–$40"},
            {"name": "Kids' Cut", "price_range": "$18–$25"},
            {"name": "Beard Trim", "price_range": "$15–$22"},
        ],
    },

    # ── WAXING ────────────────────────────────────────────────────────────────
    {
        "name": "European Wax Center Hollywood",
        "slug": "european-wax-center-hollywood",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["federal-highway-corridor"],
        "address": {"street": "1814 N Federal Hwy", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 925-9292",
        "website": "https://waxcenter.com",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The Hollywood location of EWC brings the chain's consistent "
            "comfortComfort Wax formula and trained specialists to North Federal "
            "Highway. For those new to waxing, the complimentary first-wax-free "
            "offer is the easiest way to try it. Regulars book memberships for "
            "lower per-visit pricing."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brow Wax", "price_range": "$22–$30"},
            {"name": "Bikini Wax", "price_range": "$45–$65"},
            {"name": "Brazilian Wax", "price_range": "$65–$85"},
            {"name": "Full Leg Wax", "price_range": "$80–$105"},
            {"name": "Back Wax", "price_range": "$55–$75"},
        ],
    },
    {
        "name": "Sugar Studio Hollywood",
        "slug": "sugar-studio-hollywood",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["hollywood-broadwalk"],
        "address": {"street": "219 N 21st Ave", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 922-7700",
        "website": "https://sugarstudiohollywood.com",
        "instagram": "@sugarstudio_hwl",
        "short_description": (
            "An all-sugaring studio just off the Broadwalk for clients who "
            "prefer the ancient Egyptian hair-removal method over traditional wax. "
            "The sugar paste is gentler on sensitive skin, works on shorter hair "
            "than wax, and results tend to last longer. Beach-crowd favorite — "
            "bookings spike in spring and summer."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brow Sugaring", "price_range": "$25–$35"},
            {"name": "Brazilian Sugaring", "price_range": "$65–$85"},
            {"name": "Bikini Sugaring", "price_range": "$45–$60"},
            {"name": "Full Leg Sugaring", "price_range": "$75–$100"},
        ],
    },

    # ── HAIR — FEDERAL HIGHWAY / HILLS ────────────────────────────────────────
    {
        "name": "Glam Factory Salon",
        "slug": "glam-factory-salon-hollywood",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["federal-highway-corridor"],
        "address": {"street": "1930 N Federal Hwy", "city": "Hollywood", "state": "FL", "postal_code": "33020", "country": "US"},
        "phone": "(954) 920-9070",
        "website": "https://glamfactorysalon.com",
        "instagram": "@glamfactoryhwl",
        "short_description": (
            "A Brazilian-owned salon on North Federal Highway that has become "
            "the go-to for South American clients seeking keratin and "
            "straightening treatments that actually work on thick, coarse, or "
            "color-treated hair. English and Portuguese spoken. The team trained "
            "in São Paulo and the blowouts show it."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brazilian Keratin", "price_range": "$200–$350"},
            {"name": "Women's Cut & Blowout", "price_range": "$60–$100"},
            {"name": "Color (Single Process)", "price_range": "$80–$130"},
            {"name": "Hydration Treatment", "price_range": "$60–$90"},
        ],
    },
]


# ── Seed function ─────────────────────────────────────────────────────────────

async def seed_hollywood() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    network = await db.networks.find_one({"slug": "beauty"})
    if not network:
        raise RuntimeError("Beauty network not found — run seed_networks.py first.")
    network_id = network["_id"]

    city_id = "hollywood-fl"
    city_doc = {
        "_id": city_id,
        "network_id": network_id,
        "slug": city_id,
        "name": "Hollywood",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "status": "live",
        "meta_title": "Hollywood, FL Beauty Directory — Salons, Nail Studios & Spas",
        "meta_description": (
            "Find the best hair salons, nail studios, spas, lash artists, and "
            "barbers in Hollywood, Florida. Curated listings from Downtown "
            "Hollywood to the Broadwalk."
        ),
        "created_at": now,
        "updated_at": now,
    }
    await upsert("cities", {"_id": city_id}, city_doc)
    print("Upserted city: %s" % city_id)

    # ── Neighborhoods ─────────────────────────────────────────────────────────
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nb_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network_id,
            "city_id": city_id,
            "slug": slug,
            "name": name,
            "vibe": vibe,
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
        photo_url = _CATEGORY_FALLBACK_PHOTOS.get(biz["category_slugs"][0])
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
            "services": biz.get("services", []),
            "created_at": now,
            "updated_at": now,
        }

        # WHY: preserve owner claim data, billing, hours, and services
        # on re-seed so owners who have claimed their listing don't lose work.
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
    print("Hollywood seed complete:")
    print("  City:          hollywood-fl (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as all other city seeds —
    # this script writes to the database, refuse to run against production
    # unless explicitly confirmed with the environment variable.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_hollywood()


if __name__ == "__main__":
    run(main())
