"""Seed Boca Raton for the Beauty network.

28 curated, web-verified businesses across 5 neighborhoods (+ Delray Beach).
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_boca_raton
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo


# ── Neighborhoods ─────────────────────────────────────────────────────────────
# (slug, display name, vibe description, listed_count)
NEIGHBORHOODS: List[tuple] = [
    ("downtown-boca",   "Downtown Boca / Mizner Park", "Walkable & upscale",        5),
    ("east-boca",       "East Boca",                   "Federal Hwy & intracoastal", 5),
    ("town-center",     "Town Center",                 "Mall district & beyond",     1),
    ("west-boca",       "West Boca",                   "Suburban & community",       5),
    ("delray-beach",    "Delray Beach",                "Atlantic Ave & beyond",      3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "downtown-boca": (
        "The cultural heart of Boca Raton — where Mizner Park meets Palmetto Park Road "
        "and the sidewalks fill with the kind of people who take their appearance seriously. "
        "The beauty studios here cater to a clientele that travels, entertains, and expects "
        "salon work to hold up whether they're at a gallery opening or on a boat."
    ),
    "east-boca": (
        "East Boca runs along Federal Highway from the Intracoastal inland, a corridor "
        "that mixes luxury condos, local boutiques, and some of Boca's most quietly impressive "
        "salons. The stylists here have built loyal practices through genuine skill — "
        "not just a prestigious Mizner Park address."
    ),
    "town-center": (
        "The mall district around Town Center at Boca Raton has more going for it than "
        "chain retail. A handful of serious independent salons have made their home here, "
        "drawing clients who want the convenience of the area without the cookie-cutter experience."
    ),
    "west-boca": (
        "West Boca Raton is where the full-service beauty appointment lives. Sprawling plazas "
        "along Glades Road, Yamato Road, and Military Trail hold salons and spas that serve "
        "the densely residential communities around them — often with veteran owners who've "
        "been here long enough to know their clients' children by name."
    ),
    "delray-beach": (
        "Just north of the Boca Raton city line, Delray Beach has developed a beauty scene "
        "that punches well above its size. Atlantic Avenue keeps a steady stream of visitors, "
        "but the best grooming spots here serve locals — regulars who drove past newer "
        "options to get back to someone who knows what they're doing."
    ),
}

# Fallback photos by category slug (shared with Miami and Fort Lauderdale seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — DOWNTOWN BOCA ─────────────────────────────────────────────────
    {
        "name": "Studio 10 Boca Raton",
        "slug": "studio-10-boca-raton-downtown-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "10 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 391-2992",
        "website": "https://studio10bocaraton.com",
        "instagram": "@studio10bocaraton",
        "short_description": (
            "A well-established downtown Boca salon on Palmetto Park Road, "
            "consistently ranked among the best in South Florida for precision "
            "cuts and color services."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Dapper & Divine",
        "slug": "dapper-and-divine-downtown-boca",
        "category_slugs": ["hair", "barber"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "199 W Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 376-1251",
        "website": "https://dapperanddivinestudio.com",
        "instagram": "@dapperanddivine",
        "short_description": (
            "A chic downtown Boca studio offering hair salon services, a luxury "
            "barbershop, and a makeup studio under one roof — popular with both "
            "men and women."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Hair, Lash & Brow Boca",
        "slug": "hair-lash-brow-boca-downtown-boca",
        "category_slugs": ["hair", "lash-brow"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "450 NE 20th St, Suite 117", "city": "Boca Raton", "state": "FL", "postal_code": "33431", "country": "US"},
        "phone": "(561) 391-3108",
        "website": "https://www.hairlashbrowboca.com",
        "instagram": "@hairlashandbrowboca",
        "short_description": (
            "A full-service boutique near downtown Boca offering blow-outs, cuts, "
            "color, hair extensions, lash extensions, waxing, and facials all in "
            "one relaxed studio setting."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — EAST BOCA ─────────────────────────────────────────────────────
    {
        "name": "Gramercy Hair Salon",
        "slug": "gramercy-hair-salon-east-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "2880 N Federal Hwy", "city": "Boca Raton", "state": "FL", "postal_code": "33431", "country": "US"},
        "phone": "(561) 600-9594",
        "website": "https://gramercyhairsalon.com",
        "instagram": "@gramercysalon",
        "short_description": (
            "A high-energy, full-service salon known for luxurious color work and "
            "a fun team atmosphere. Formerly in Mizner Park, now on Federal Hwy "
            "serving East Boca and beyond."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Salon Sora",
        "slug": "salon-sora-east-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "1675 N Military Trl, Suite 700", "city": "Boca Raton", "state": "FL", "postal_code": "33486", "country": "US"},
        "phone": "(561) 338-7597",
        "website": "https://salonsora.com",
        "instagram": "@salonsora",
        "short_description": (
            "A luxury hair salon with extended evening hours and weekend availability, "
            "known for high-end color, cuts, and a polished upscale experience."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Hair Bar NYC — Boca Raton",
        "slug": "hair-bar-nyc-east-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "4400 N Federal Hwy, Unit 184", "city": "Boca Raton", "state": "FL", "postal_code": "33431", "country": "US"},
        "phone": "(561) 717-3397",
        "website": "https://hairbarnyc.com/locations/boca-raton/",
        "instagram": "@hairbarnycbocaraton",
        "short_description": (
            "The Boca outpost of the NYC-born boutique chain, located in the Sanctuary "
            "Shoppes. Specializes in master stylists, formaldehyde-free keratin treatments, "
            "and editorial color."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Hairmess Salon",
        "slug": "hairmess-salon-east-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "7531 N Federal Hwy E3", "city": "Boca Raton", "state": "FL", "postal_code": "33487", "country": "US"},
        "phone": "(561) 372-9218",
        "website": "https://www.hairmesssalon.com",
        "instagram": "@hairmess.salon",
        "short_description": (
            "A creative independent boutique salon in north Boca known for bold color "
            "transformations, modern cuts, and a playful aesthetic that sets it apart "
            "from the typical South Florida salon."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — TOWN CENTER ───────────────────────────────────────────────────
    {
        "name": "Peter's Place Hair + Color",
        "slug": "peters-place-town-center",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["town-center"],
        "address": {"street": "5250 Town Center Cir, Suite 125", "city": "Boca Raton", "state": "FL", "postal_code": "33486", "country": "US"},
        "phone": "(561) 510-8100",
        "website": "https://www.petersplacesalon.com",
        "instagram": "@petersplacesalon",
        "short_description": (
            "Founded by celebrity colorist Peter Coppola, this Town Center salon is "
            "known as the #1 Boca Raton hair salon for precision color, cuts, and "
            "extensions near the mall."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── HAIR — WEST BOCA ─────────────────────────────────────────────────────
    {
        "name": "Bliss Salon and Spa",
        "slug": "bliss-salon-and-spa-west-boca",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "17940 N Military Trl, Suite 200", "city": "Boca Raton", "state": "FL", "postal_code": "33496", "country": "US"},
        "phone": "(561) 988-8989",
        "website": "https://www.blissinboca.com",
        "instagram": "@blissinboca",
        "short_description": (
            "A full-service west Boca salon and spa offering expert hair color, "
            "precision cuts, nails, facials, and waxing — a one-stop beauty "
            "destination for the community."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — DOWNTOWN BOCA ────────────────────────────────────────────────
    {
        "name": "Nail Depot",
        "slug": "nail-depot-downtown-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "157 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 347-7496",
        "website": "https://naildepotsalon.com",
        "instagram": None,
        "short_description": (
            "Voted #1 nail salon in Boca Raton for over 30 years, offering Dazzle Dry, "
            "hard gel, Russian manicures, acrylics, dip powder, and Gel-X in a trusted "
            "full-service setting on Palmetto Park Road."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Artisan Nail Studio & Spa",
        "slug": "artisan-nail-studio-downtown-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "59 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 416-1999",
        "website": None,
        "instagram": "@artisannailstudio",
        "short_description": (
            "A boutique nail studio in the heart of downtown Boca offering manicures, "
            "pedicures, spa treatments, and creative nail art — a local favorite with "
            "nearly 200 Yelp reviews."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — WEST BOCA ────────────────────────────────────────────────────
    {
        "name": "Boca Nail Bar",
        "slug": "boca-nail-bar-west-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "9841 W Glades Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33434", "country": "US"},
        "phone": "(561) 372-9226",
        "website": "https://bocanailbar.com",
        "instagram": "@bocanailbar",
        "short_description": (
            "A stylish west Boca nail bar known for quality gel manicures and pedicures "
            "in a clean, modern environment with strong local reviews and a loyal following."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Tipsy Nailbar Boca",
        "slug": "tipsy-nailbar-boca-west-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "9658 Glades Rd, Suite 220", "city": "Boca Raton", "state": "FL", "postal_code": "33434", "country": "US"},
        "phone": "(561) 990-1305",
        "website": None,
        "instagram": "@tipsynailbaratuptownboca",
        "short_description": (
            "A fun, social nail bar in Uptown Boca with a party-meets-pamper vibe. "
            "Popular for gel manis, acrylics, and pedicures with walk-in friendly "
            "hours seven days a week."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "BeautiLuxe Nail Spa",
        "slug": "beautiluxe-nail-spa-west-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "9882 Glades Rd, Suite E-7", "city": "Boca Raton", "state": "FL", "postal_code": "33434", "country": "US"},
        "phone": "(561) 465-5948",
        "website": "https://beautiluxenailspabocaraton.com",
        "instagram": None,
        "short_description": (
            "A top-rated west Boca nail spa offering high-end manicures, pedicures, "
            "waxing, and lash services in a clean, upscale environment with a 4.7-star "
            "average across review platforms."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Boca Beauty Nail Spa",
        "slug": "boca-beauty-nail-spa-west-boca",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "3013 Yamato Rd, Suite B13", "city": "Boca Raton", "state": "FL", "postal_code": "33434", "country": "US"},
        "phone": "(561) 998-0773",
        "website": "https://bocabeautynailspa.com",
        "instagram": None,
        "short_description": (
            "A dependable neighborhood nail salon on Yamato Road serving West Boca "
            "with manicures, pedicures, dip powder, and waxing services at "
            "approachable prices."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── SPA — DOWNTOWN BOCA ──────────────────────────────────────────────────
    {
        "name": "Eden Day Spa",
        "slug": "eden-day-spa-downtown-boca",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "213 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 447-7700",
        "website": "https://www.edendayspa.net",
        "instagram": "@edendayspabocaraton",
        "short_description": (
            "A serene day spa steps from downtown Boca with 9am–8pm daily hours, "
            "offering massages, facials, body treatments, and waxing in a lush, "
            "relaxing environment."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — EAST BOCA ──────────────────────────────────────────────────────
    {
        "name": "Katrinatique",
        "slug": "katrinatique-east-boca",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "807 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 931-2156",
        "website": "https://katrinatique.com",
        "instagram": "@katrinatique",
        "short_description": (
            "A boutique luxury facial spa founded in 1999 by a 30-year certified "
            "esthetician, known for personalized Biologique Recherche facials and "
            "high-touch skincare in an intimate appointment-only setting."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── SPA — WEST BOCA ──────────────────────────────────────────────────────
    {
        "name": "Skin Apeel Day Spa",
        "slug": "skin-apeel-day-spa-west-boca",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "21301 Powerline Rd, Suite 215", "city": "Boca Raton", "state": "FL", "postal_code": "33433", "country": "US"},
        "phone": "(561) 852-8081",
        "website": "https://skinapeel.com",
        "instagram": None,
        "short_description": (
            "A long-standing holistic day spa in west Boca known as one of South "
            "Florida's best, offering expert facials, massage, nail services, and "
            "Dermalogica skincare in a tranquil setting."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — DOWNTOWN BOCA ─────────────────────────────────────────
    {
        "name": "Beauty Glam Studio",
        "slug": "beauty-glam-studio-downtown-boca",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "303 S Federal Hwy", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(954) 507-4447",
        "website": "https://www.beautyglamstudio.com",
        "instagram": "@beautyglamstudio",
        "short_description": (
            "A chic luxury studio in the heart of downtown Boca specializing in "
            "permanent makeup, ombré brows, nano hair strokes, and lash extensions — "
            "known for the best PMU work in Boca Raton."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Boca Lash",
        "slug": "boca-lash-downtown-boca",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "422 E Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 544-7411",
        "website": None,
        "instagram": "@bocalashstudio",
        "short_description": (
            "A dedicated lash studio on Palmetto Park Road offering classic, hybrid, "
            "and volume eyelash extensions with a loyal local clientele and strong reviews."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — EAST BOCA ──────────────────────────────────────────────
    {
        "name": "Bella Lash & Beauty",
        "slug": "bella-lash-and-beauty-east-boca",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["east-boca"],
        "address": {"street": "1367 W Palmetto Park Rd", "city": "Boca Raton", "state": "FL", "postal_code": "33486", "country": "US"},
        "phone": "(561) 849-9813",
        "website": "https://www.bellalashandbeauty.net",
        "instagram": "@bellalashandbeautyy",
        "short_description": (
            "A top-rated boutique lash and beauty studio offering luxury eyelash "
            "extensions, lash lifts, brow lamination, brow shaping, waxing, and "
            "customized facials."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — WEST BOCA ──────────────────────────────────────────────
    {
        "name": "SBR Studio & Beauty Suites",
        "slug": "sbr-studio-beauty-suites-west-boca",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "9181 Glades Rd, Suite 125", "city": "Boca Raton", "state": "FL", "postal_code": "33433", "country": "US"},
        "phone": "(561) 314-5965",
        "website": "https://www.sbrboca.com",
        "instagram": "@sculptedbyrobin",
        "short_description": (
            "The only brow-focused salon and beauty suite in South Florida — "
            "an upscale, spa-like studio that specializes exclusively in brow "
            "waxing, shaping, and lamination using pearl wax for sensitive skin."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── MED-SPA — DOWNTOWN BOCA ──────────────────────────────────────────────
    {
        "name": "Peace Love Med",
        "slug": "peace-love-med-downtown-boca",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["downtown-boca"],
        "address": {"street": "151 SE Mizner Blvd, Suite 16A", "city": "Boca Raton", "state": "FL", "postal_code": "33432", "country": "US"},
        "phone": "(561) 270-4631",
        "website": "https://peacelovemed.com",
        "instagram": "@peacelovemedspa",
        "short_description": (
            "A highly popular med spa steps from Mizner Park with 138K Instagram "
            "followers, offering injectables, Botox, fillers, and aesthetic rejuvenation "
            "treatments in a welcoming boutique environment."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── MED-SPA — WEST BOCA ──────────────────────────────────────────────────
    {
        "name": "All About Aesthetics Med Spa",
        "slug": "all-about-aesthetics-med-spa-west-boca",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "21301 Powerline Rd, Suite 108", "city": "Boca Raton", "state": "FL", "postal_code": "33433", "country": "US"},
        "phone": "(561) 757-7391",
        "website": "https://allaboutaestheticsfl.com",
        "instagram": "@allaboutaestheticsfl",
        "short_description": (
            "Boca Raton's top-rated medical spa for Botox, dermal fillers, Morpheus8, "
            "laser treatments, and more — a well-reviewed destination for non-surgical "
            "aesthetic enhancement."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Glamor Medical",
        "slug": "glamor-medical-west-boca",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["west-boca"],
        "address": {"street": "7301 W Palmetto Park Rd, Suite 106B", "city": "Boca Raton", "state": "FL", "postal_code": "33433", "country": "US"},
        "phone": "(561) 990-8442",
        "website": "https://glamormedical.com",
        "instagram": None,
        "short_description": (
            "A boutique west Boca med spa offering anti-aging facials, injectables, "
            "Sculptra, Botox, and Instalift treatments with a focus on natural-looking "
            "rejuvenation results."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — DELRAY BEACH ────────────────────────────────────────────────
    {
        "name": "Lanzetta's Classic Barbershop",
        "slug": "lanzettas-barbershop-delray-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["delray-beach"],
        "address": {"street": "164 NE 2nd Ave", "city": "Delray Beach", "state": "FL", "postal_code": "33444", "country": "US"},
        "phone": "(561) 276-8601",
        "website": "https://www.lanzettas.com",
        "instagram": None,
        "short_description": (
            "A beloved Pineapple Grove institution with over 100 Yelp reviews, "
            "praised as the best barbershop in Delray Beach for its attention to detail, "
            "friendly atmosphere, and classic barbering skills."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Stark's Barbershop",
        "slug": "starks-barbershop-delray-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["delray-beach"],
        "address": {"street": "105 Avenue L", "city": "Delray Beach", "state": "FL", "postal_code": "33483", "country": "US"},
        "phone": "(561) 270-7296",
        "website": "https://www.starksbarbercofl.com",
        "instagram": "@starksbarbershopdelray",
        "short_description": (
            "Voted the best barbershop in Delray Beach, offering traditional scissor "
            "cuts, hot towel straight razor shaves, detailed fades, and a high-quality "
            "grooming experience for all ages."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "ManCave for Men — Delray Beach",
        "slug": "mancave-for-men-delray-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["delray-beach"],
        "address": {"street": "14851 Lyons Rd, Suite 108", "city": "Delray Beach", "state": "FL", "postal_code": "33446", "country": "US"},
        "phone": "(561) 429-4600",
        "website": "https://mancaveformen.com/locations/delray-marketplace-west-delray/",
        "instagram": None,
        "short_description": (
            "A premium men's grooming destination in Delray Marketplace with 150+ "
            "five-star reviews, offering precision haircuts, beard trims, hot towel "
            "straight razor shaves, and skin treatments."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
]


async def seed_boca_raton() -> None:
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
        "slug": "boca-raton",
        "name": "Boca Raton",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Boca Raton's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, lash artists, estheticians, and nail stylists "
            "Boca Raton locals actually book — from Mizner Park to West Boca and "
            "down the A1A corridor to Delray Beach."
        ),
        "seo_title": "Boca Raton Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Boca Raton — salons, spas, lash studios, "
            "and nail bars discovered by locals. Covering downtown Boca, East Boca, "
            "Town Center, West Boca, and Delray Beach."
        ),
        "editorial_headlines": [
            {"headline": "Boca Raton's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "boca-raton"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: boca-raton (id=%s)" % city_id)

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

        # WHY: preserve owner claim data, billing fields, hours, and services
        # on re-seed so that any owner who has already claimed their listing
        # doesn't lose their work. Same pattern as Miami and FTL seeds.
        existing = await db.businesses.find_one({"city_id": city_id, "slug": biz["slug"]})
        if existing:
            for _preserve in (
                "claim_status", "claimed_email", "claimed_by_user_id",
                "claimed_at", "verified_at",
                "stripe_customer_id", "stripe_subscription_id",
                "is_founding_partner", "hours", "google_place_id", "google_rating", "google_review_count", "google_rating_synced_at",
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
    print("Boca Raton seed complete:")
    print("  City:          boca-raton (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami and FTL seeds — this script
    # writes to the database. Refuse to run against production unless
    # explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_boca_raton()


if __name__ == "__main__":
    run(main())
