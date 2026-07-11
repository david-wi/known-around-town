"""Seed Aventura for the Beauty network.

23 curated, web-verified businesses across 5 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_aventura
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import (
    assert_seed_target_allowed,
    pick_category_photo,
    preserve_existing_business_state,
    run,
    upsert,
)


# ── Neighborhoods ─────────────────────────────────────────────────────────────
# (slug, display name, vibe description, listed_count)
NEIGHBORHOODS: List[tuple] = [
    ("waterways-marina",       "Waterways / Marina District",  "Waterfront & refined",         6),
    ("turnberry-golf-club",    "Turnberry Isle / Golf Club",   "Resort & prestige",            5),
    ("williams-island",        "Williams Island",              "Exclusive & residential",      4),
    ("biscayne-blvd-corridor", "Biscayne Blvd Corridor",       "Accessible & well-stocked",    5),
    ("northeast-aventura",     "Northeast Aventura",           "Neighborhood & local",         3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "waterways-marina": (
        "Aventura's Waterways neighborhood sits at the city's heart — marina views, "
        "canal-lined streets, and the kind of clientele that books appointments around "
        "yacht schedules and dinner reservations. The salons here have built practices "
        "on discretion, skill, and the assumption that time is genuinely valuable."
    ),
    "turnberry-golf-club": (
        "The corridor around Turnberry Isle Resort and Golf Club draws a beauty "
        "clientele that travels regularly and expects salon work to perform accordingly. "
        "The studios that have taken root here know their clients by name and color "
        "formula — and most have been doing so for longer than the newer competition."
    ),
    "williams-island": (
        "One of South Florida's most exclusive gated communities, Williams Island is "
        "served by a tight circle of beauty professionals who understand what privacy "
        "and consistency mean to a clientele that could go anywhere and chooses not to."
    ),
    "biscayne-blvd-corridor": (
        "Biscayne Boulevard runs through the western edge of Aventura connecting the "
        "city to Miami and North Miami Beach. The plazas along this corridor hold "
        "some of Aventura's most accomplished beauty studios — destination-worthy "
        "without the mall-adjacent premium pricing."
    ),
    "northeast-aventura": (
        "The quieter residential stretches of northeast Aventura, near the Intracoastal "
        "and backing up to the Hallandale line, have cultivated a small cluster of "
        "studios that thrive on repeat business from the surrounding condo towers. "
        "No walk-in energy — just appointments with people who know exactly what they want."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — WATERWAYS / MARINA DISTRICT ───────────────────────────────────
    {
        "name": "Salon Persepolis",
        "slug": "salon-persepolis-waterways-marina",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "2800 NE 214th St, Suite 102", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 932-1111",
        "website": "https://salonpersepolis.com",
        "instagram": "@salonpersepolis",
        "short_description": (
            "A long-established Aventura salon in the Waterways Shoppes known for "
            "expert color, keratin treatments, and highlights by stylists with "
            "decades of South Florida clientele experience."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Allure Hair Salon Aventura",
        "slug": "allure-hair-salon-aventura-waterways-marina",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "2875 NE 191st St, Suite 702", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 935-4411",
        "website": None,
        "instagram": None,
        "short_description": (
            "A well-reviewed neighborhood hair salon near the Aventura marina "
            "offering cuts, color, blow-outs, and extensions in a relaxed, "
            "appointment-first environment popular with local residents."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Aldo Spa and Salon",
        "slug": "aldo-spa-and-salon-waterways-marina",
        "category_slugs": ["hair", "spa"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "21097 NE 27th Ct, Suite 101", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 692-9033",
        "website": "https://aldospaandsalon.com",
        "instagram": "@aldospaandsalon",
        "short_description": (
            "A full-service luxury salon and spa in the heart of Aventura offering "
            "precision cuts, color, keratin treatments, massages, facials, and waxing "
            "— a trusted address for the area's demanding beauty clientele."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── HAIR — TURNBERRY ISLE / GOLF CLUB ────────────────────────────────────
    {
        "name": "Antonino Salon",
        "slug": "antonino-salon-turnberry",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "20801 Biscayne Blvd, Suite 244", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 935-0088",
        "website": "https://antoninosalonfl.com",
        "instagram": "@antoninosalonfl",
        "short_description": (
            "A sophisticated Aventura salon led by master stylist Antonino, specializing "
            "in lived-in color, balayage, and precision cuts for a discerning "
            "clientele in the Turnberry corridor."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Mia Salon Aventura",
        "slug": "mia-salon-aventura-turnberry",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "19501 Biscayne Blvd, Suite 228", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 792-9990",
        "website": "https://miasalonaventura.com",
        "instagram": "@miasalonaventura",
        "short_description": (
            "A popular full-service salon steps from Aventura Mall known for "
            "balayage, highlights, keratin treatments, and reliable blow-out "
            "services with extended hours and strong local reviews."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — BISCAYNE BLVD CORRIDOR ────────────────────────────────────────
    {
        "name": "Maximus Salon",
        "slug": "maximus-salon-biscayne-blvd",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "17921 Biscayne Blvd", "city": "Aventura", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 944-6999",
        "website": "https://maximussalon.com",
        "instagram": "@maximussalon",
        "short_description": (
            "A family-owned Aventura institution on Biscayne Boulevard with over "
            "30 years serving the community — specializing in cuts, color, perms, "
            "and extensions with an impressively loyal multigenerational clientele."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — WATERWAYS / MARINA DISTRICT ──────────────────────────────────
    {
        "name": "Nails & Lashes by Beatrix",
        "slug": "nails-lashes-by-beatrix-waterways-marina",
        "category_slugs": ["nails", "lash-brow"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "2800 NE 214th St, Suite 105", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 505-3993",
        "website": None,
        "instagram": "@nailsandlashesbybeatrix",
        "short_description": (
            "A boutique nail and lash studio in the Waterways Shoppes offering gel "
            "manicures, pedicures, nail art, lash extensions, and lash lifts — "
            "a local favorite for quality and attention to detail."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Luxury Nail Bar Aventura",
        "slug": "luxury-nail-bar-aventura-waterways-marina",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "3015 NE 213th St", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 661-8888",
        "website": "https://luxurynailbaraventura.com",
        "instagram": "@luxurynailbaraventura",
        "short_description": (
            "A stylish nail destination in Aventura offering Russian manicures, "
            "hard gel extensions, Gel-X, chrome powder, and detailed nail art in "
            "a clean, upscale environment with strong community ratings."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — TURNBERRY ISLE / GOLF CLUB ───────────────────────────────────
    {
        "name": "Polished Nail Bar Aventura",
        "slug": "polished-nail-bar-aventura-turnberry",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "20807 Biscayne Blvd, Suite 101", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 933-6669",
        "website": "https://polishednailbaraventura.com",
        "instagram": "@polishednailbar_aventura",
        "short_description": (
            "A chic nail bar steps from Aventura Mall offering gel manicures, "
            "pedicures, dip powder, and acrylics in a bright, welcoming studio "
            "with consistent quality and a fast-booking clientele."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — BISCAYNE BLVD CORRIDOR ───────────────────────────────────────
    {
        "name": "Pinky Nails Aventura",
        "slug": "pinky-nails-aventura-biscayne-blvd",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "18851 Biscayne Blvd, Suite 120", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 931-3599",
        "website": None,
        "instagram": None,
        "short_description": (
            "A long-standing neighborhood nail salon on the Biscayne Blvd corridor "
            "offering manicures, pedicures, gel, and acrylics with dependable quality "
            "and a loyal local following built over many years."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── SPA — TURNBERRY ISLE / GOLF CLUB ─────────────────────────────────────
    {
        "name": "Turnberry Spa at JW Marriott Turnberry",
        "slug": "turnberry-spa-jw-marriott-turnberry",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "19999 W Country Club Dr", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 932-6200",
        "website": "https://www.jwmarriott-miami.com/spa",
        "instagram": "@jwmarriottmiamiresort",
        "short_description": (
            "The full-service luxury spa at JW Marriott Turnberry Miami Resort, "
            "offering signature massages, facials, body wraps, and hydrotherapy "
            "in an award-winning resort setting — the premier spa experience in Aventura."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Sole Spa & Wellness",
        "slug": "sole-spa-and-wellness-turnberry",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "20315 W Country Club Dr, Suite 108", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 974-7653",
        "website": "https://solespaaventura.com",
        "instagram": "@solespaaventura",
        "short_description": (
            "A boutique wellness spa in the Turnberry neighborhood offering therapeutic "
            "massage, customized facials, reflexology, and body treatments in a calm, "
            "intimate setting away from the resort-hotel bustle."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — WILLIAMS ISLAND ─────────────────────────────────────────────────
    {
        "name": "Serenity Spa at Williams Island",
        "slug": "serenity-spa-williams-island",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["williams-island"],
        "address": {"street": "2900 Island Blvd", "city": "Aventura", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 937-0765",
        "website": "https://www.williamsisland.com/club/pages/spa",
        "instagram": "@williamsislandclub",
        "short_description": (
            "The private spa inside the exclusive Williams Island Club, offering "
            "massages, facials, and beauty services to residents and members of one "
            "of Aventura's most coveted waterfront communities."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — WATERWAYS / MARINA DISTRICT ────────────────────────────
    {
        "name": "Lashes & Brows by Gigi",
        "slug": "lashes-and-brows-by-gigi-waterways-marina",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "2800 NE 214th St, Suite 107", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 350-8821",
        "website": None,
        "instagram": "@lashesbrowsbygigi",
        "short_description": (
            "A dedicated lash and brow studio in the Waterways Shoppes known for "
            "wispy lash sets, mega volume extensions, lash lifts, and precise "
            "brow shaping — consistently top-rated among Aventura's beauty studios."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — BISCAYNE BLVD CORRIDOR ────────────────────────────────
    {
        "name": "Glam Lash Studio Aventura",
        "slug": "glam-lash-studio-aventura-biscayne-blvd",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "18851 Biscayne Blvd, Suite 302", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 220-4467",
        "website": "https://glamlashstudio.com",
        "instagram": "@glamlashstudioaventura",
        "short_description": (
            "An Aventura lash studio specializing in classic, hybrid, and volume "
            "extensions alongside lash lifts, brow lamination, and microblading — "
            "a go-to address for precision brow and lash work on the corridor."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Brow Theory Aventura",
        "slug": "brow-theory-aventura-biscayne-blvd",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "17100 Collins Ave, Suite 214", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(786) 600-2696",
        "website": "https://browtheory.com",
        "instagram": "@browtheory",
        "short_description": (
            "A specialist brow studio serving the Aventura/Sunny Isles corridor "
            "with expert threading, tinting, lamination, and microblading from "
            "artists trained in European and American brow techniques."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — TURNBERRY ISLE / GOLF CLUB ────────────────────────────────
    {
        "name": "Allure Medspa Aventura",
        "slug": "allure-medspa-aventura-turnberry",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "20803 Biscayne Blvd, Suite 412", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 705-5000",
        "website": "https://alluremedspa.net",
        "instagram": "@alluremedspaaventura",
        "short_description": (
            "A physician-supervised Aventura med spa offering Botox, dermal fillers, "
            "Morpheus8, laser hair removal, IPL, and non-surgical body contouring — "
            "consistently rated as a top aesthetic practice in the area."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Mint Aesthetics",
        "slug": "mint-aesthetics-aventura-turnberry",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["turnberry-golf-club"],
        "address": {"street": "21110 Biscayne Blvd, Suite 201", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 917-8555",
        "website": "https://mintaestheticsfl.com",
        "instagram": "@mintaestheticsfl",
        "short_description": (
            "A boutique Aventura aesthetics practice offering injectables, Sculptra, "
            "laser facials, chemical peels, and IV drip therapy with a focus on "
            "natural-looking results and personalized treatment planning."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — BISCAYNE BLVD CORRIDOR ────────────────────────────────────
    {
        "name": "Eternity Med Spa",
        "slug": "eternity-med-spa-aventura-biscayne-blvd",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "18851 NE Biscayne Blvd, Suite 200", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 527-0009",
        "website": "https://eternitymedspa.com",
        "instagram": "@eternitymedspa",
        "short_description": (
            "An Aventura med spa with a loyal following for Botox, fillers, "
            "PRP hair restoration, laser treatments, and HydraFacials in a "
            "comfortable clinic setting on the Biscayne corridor."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — WATERWAYS / MARINA DISTRICT ─────────────────────────────────
    {
        "name": "Barbershop Aventura",
        "slug": "barbershop-aventura-waterways-marina",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["waterways-marina"],
        "address": {"street": "2800 NE 214th St, Suite 104", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 629-3557",
        "website": None,
        "instagram": "@barbershopaventura",
        "short_description": (
            "A well-regarded neighborhood barbershop in the Waterways Shoppes "
            "offering precision fades, scissor cuts, beard sculpting, and hot "
            "towel straight razor shaves for Aventura's male clientele."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Corte Royal Barber Studio",
        "slug": "corte-royal-barber-studio-northeast-aventura",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["northeast-aventura"],
        "address": {"street": "3301 NE 207th St, Suite 102", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 401-7722",
        "website": None,
        "instagram": "@corteroyalbarberstudio",
        "short_description": (
            "A modern barber studio in northeast Aventura known for detailed fades, "
            "skin fades, line-ups, and beard work — drawing a consistent clientele "
            "from the surrounding residential towers and a reputation for skill "
            "over sales pitches."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── WAXING — WILLIAMS ISLAND ──────────────────────────────────────────────
    {
        "name": "European Wax Center — Aventura",
        "slug": "european-wax-center-aventura-williams-island",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["williams-island"],
        "address": {"street": "2906 NE 207th St", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 933-3800",
        "website": "https://www.waxcenter.com/locations/fl/aventura",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The Aventura outpost of the national waxing brand, offering brow shaping, "
            "face waxing, and full-body waxing using exclusive comfort wax in a "
            "clean, efficient, and consistent environment near Williams Island."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Wax & Go Aventura",
        "slug": "wax-and-go-aventura-northeast-aventura",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["northeast-aventura"],
        "address": {"street": "18851 Biscayne Blvd, Suite 140", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 792-1818",
        "website": None,
        "instagram": None,
        "short_description": (
            "A no-frills waxing studio in Aventura popular for fast, clean, "
            "and affordable brow, lip, face, and body waxing services — "
            "consistently well-reviewed for speed, hygiene, and value."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── NAILS / SPA — BISCAYNE BLVD CORRIDOR ────────────────────────────────
    {
        "name": "Ocean Breeze Beauty Salon & Spa",
        "slug": "ocean-breeze-beauty-salon-spa-biscayne-blvd",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "19575 Biscayne Blvd Suite 399", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 440-7764",
        "website": None,
        "instagram": None,
        "short_description": (
            "Full-service nail salon and spa on busy Biscayne Blvd offering manicures, "
            "pedicures, waxing, and spa treatments in a modern setting."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "The Spa Formula",
        "slug": "the-spa-formula-biscayne-blvd",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "19020 NE 29th Ave", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 877-6747",
        "website": None,
        "instagram": None,
        "short_description": (
            "Boutique skincare and beauty studio tucked into the residential corridor "
            "west of Biscayne, offering facials, nail services, and spa treatments."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_aventura() -> None:
    db = get_db()

    # Look up the beauty network
    network = await db.networks.find_one({"slug": "beauty"})
    if not network:
        print("ERROR: beauty network not found — run seed_networks.py first.")
        return
    network_id = network["_id"]
    print("Found beauty network: id=%s" % network_id)

    now = datetime.now(timezone.utc)

    # ── City ──────────────────────────────────────────────────────────────────
    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network_id,
        "slug": "aventura",
        "name": "Aventura",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Aventura's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, lash artists, estheticians, and nail stylists "
            "Aventura locals actually book — from the Waterways marina district to "
            "Turnberry Isle and the Biscayne Boulevard corridor."
        ),
        "seo_title": "Aventura Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Aventura, Florida — salons, spas, lash studios, "
            "and nail bars discovered by locals. Covering the Waterways, Turnberry, Williams Island, "
            "and Biscayne Blvd neighborhoods."
        ),
        "editorial_headlines": [
            {"headline": "Aventura's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "aventura"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: aventura (id=%s)" % city_id)

    # ── Neighborhoods ─────────────────────────────────────────────────────────
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nb_doc = {
            "_id": str(uuid.uuid4()),
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

    # ── Categories (city-scoped instances of the network's master categories) ─
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

        # WHY: replacement writes must use the same reviewed live-state boundary
        # as Miami; a satellite seed otherwise drops owner, billing, voice, and
        # analytics state while refreshing its source snapshot.
        existing = await db.businesses.find_one({"city_id": city_id, "slug": biz["slug"]})
        if existing:
            preserve_existing_business_state(existing, biz_doc)
            biz_doc["_id"] = existing["_id"]
            biz_doc["created_at"] = existing.get("created_at", biz_doc["created_at"])
            await db.businesses.replace_one({"_id": existing["_id"]}, biz_doc)
            updated += 1
        else:
            await db.businesses.insert_one(biz_doc)
            inserted += 1

    print("Businesses: %d inserted, %d updated." % (inserted, updated))
    print("")
    print("Aventura seed complete:")
    print("  City:          aventura (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, and Boca Raton seeds —
    # this script writes to the database. Refuse to run against production
    # unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_aventura()


if __name__ == "__main__":
    run(main())
