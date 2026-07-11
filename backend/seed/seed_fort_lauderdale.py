"""Seed Fort Lauderdale for the Beauty network.

32 curated, web-verified businesses across 10 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_fort_lauderdale
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


# ── Neighborhoods ────────────────────────────────────────────────────────────
# (slug, display name, vibe description, listed_count)
NEIGHBORHOODS: List[tuple] = [
    ("las-olas",              "Las Olas",                    "Walkable & upscale",           3),
    ("victoria-park",         "Victoria Park",               "Neighborhood & chic",          5),
    ("wilton-manors",         "Wilton Manors",               "Welcoming & creative",         4),
    ("flagler-village",       "Flagler Village",             "Arts district & emerging",     3),
    ("se-17th-street",        "SE 17th Street",              "Marina & residential",         2),
    ("downtown-fort-lauderdale", "Downtown Fort Lauderdale", "Urban & revitalizing",         3),
    ("north-fort-lauderdale", "North Fort Lauderdale",       "Coastal & accessible",         4),
    ("oakland-park",          "Oakland Park",                "Community & local",            5),
    ("lauderdale-by-the-sea", "Lauderdale-by-the-Sea",       "Beachy & laid-back",           3),
    ("pompano-beach",         "Pompano Beach",               "Coastal & growing",            0),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "las-olas": (
        "The main strip in Fort Lauderdale that locals and visitors actually use — "
        "Las Olas runs from downtown to the beach, lined with salons that know their "
        "clientele expects a polished finish whether they're heading to a yacht or a restaurant."
    ),
    "victoria-park": (
        "A quiet residential neighborhood just north of Las Olas where the beauty "
        "scene is built on loyalty. The studios here serve regulars who've been coming "
        "for years — worth the word-of-mouth search to find them."
    ),
    "wilton-manors": (
        "Fort Lauderdale's most welcoming neighborhood has cultivated a beauty scene "
        "that matches its character — thoughtful, creative, and genuinely skilled. "
        "Some of Broward's best colorists and massage therapists work along this corridor."
    ),
    "flagler-village": (
        "The arts-district neighborhood that's been drawing independent studios "
        "and boutique salons as the area redevelops. Early movers here tend to be "
        "the ones you'll be telling people about in two years."
    ),
    "se-17th-street": (
        "The marina corridor just south of Las Olas, where boat captains and hotel guests "
        "mix with locals. Salons here run tight schedules and know that a client on a "
        "yacht charter doesn't reschedule easily."
    ),
    "downtown-fort-lauderdale": (
        "A downtown that's been finding its footing — the beauty studios that opened "
        "here did so on conviction, and several have earned loyal followings from the "
        "professionals and residents filling the new towers."
    ),
    "north-fort-lauderdale": (
        "The stretch of N Federal Highway that runs through Lauderdale Lakes and "
        "into Pompano is dotted with specialist studios — lash artists, massage therapists, "
        "and colorists who chose space over a premium address and deliver on substance."
    ),
    "oakland-park": (
        "A working neighborhood east of Wilton Manors where Fort Lauderdale institutions "
        "have operated for decades, earning lifetime clients who drive past trendier "
        "options to get to someone they trust."
    ),
    "lauderdale-by-the-Sea": (
        "A small beach town that feels genuinely removed from South Florida's pace. "
        "The salons here are community staples — the kind of place where the stylist "
        "remembers your name and your color formula."
    ),
}

# Fallback photos by category slug (shared with Miami seed)
# ── Businesses ───────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing
#
# The seed data uses "hair-salons", "nail-salons", "spas-massage",
# "lash-brow", "facial-studios", "makeup-artists" as category names in the
# research file. We map them here to the correct network category slugs.

BUSINESSES: List[Dict[str, Any]] = [
    # ── HAIR ────────────────────────────────────────────────────────────────
    {
        "name": "Hair Las Olas Blvd Barbers",
        "slug": "hair-las-olas-barbers-las-olas",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["las-olas"],
        "address": {"street": "1312 E Las Olas Blvd", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(954) 522-7782",
        "website": "https://hairlasolas.com",
        "short_description": (
            "Master Barber Edgar Maisonet has been the go-to on Las Olas since 2002, "
            "offering razor-sharp cuts, hot-towel shaves, and beard sculpting that keep "
            "regulars coming back for decades."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "The Color Cove Salon",
        "slug": "color-cove-salon-wilton-manors",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wilton-manors"],
        "address": {"street": "3105 Bayview Dr", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33306", "country": "US"},
        "phone": "(754) 200-5218",
        "website": "https://thecolorcovehairsalon.com",
        "short_description": (
            "A boutique salon near Wilton Manors specializing in corrective color, "
            "balayage, and ombré — the kind of transformative work that takes a full "
            "consultation and a colorist who genuinely loves what they do."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Source Salon — Wilton Manors",
        "slug": "source-salon-wilton-manors",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wilton-manors"],
        "address": {"street": "1881 NE 26th St, Suite 30", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33305", "country": "US"},
        "phone": "(954) 283-9539",
        "website": "https://source-salon.com",
        "short_description": (
            "An Aveda flagship salon in Wilton Manors where every appointment opens "
            "with a stress-relief scalp massage. Known for clean color, personalized "
            "cuts, and a team that takes continuing education seriously."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Source Salon — Flagler Village",
        "slug": "source-salon-flagler-village",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["flagler-village"],
        "address": {"street": "525 N Federal Hwy, Suite 300", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(954) 880-1034",
        "website": "https://source-salon.com",
        "short_description": (
            "The downtown Flagler Village outpost of the beloved Aveda salon, "
            "drawing a creative neighborhood crowd for everything from precision cuts "
            "to full balayage transformations, with bridal styling a specialty."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Mavo Hair Lounge",
        "slug": "mavo-hair-lounge-victoria-park",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["victoria-park"],
        "address": {"street": "922 N Federal Hwy", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": "(954) 933-6010",
        "website": "https://mavohairlounge.com",
        "short_description": (
            "Founded in 2013 by Marina Vogel, this eight-chair coastal-chic lounge "
            "brings European precision blonding and Great Lengths extensions to "
            "Fort Lauderdale — a local favorite for natural-looking balayage."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "EuroHair Designs",
        "slug": "eurohair-designs-oakland-park",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["oakland-park"],
        "address": {"street": "1906 E Oakland Park Blvd", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33306", "country": "US"},
        "phone": "(954) 564-9633",
        "website": None,
        "short_description": (
            "A Fort Lauderdale institution for over 25 years, where skilled stylists "
            "have earned legions of lifetime clients — if you're new to the area and "
            "need a dependable colorist or cut, this is the first call to make."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Olivier Salon and Spa",
        "slug": "olivier-salon-spa-wilton-manors",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["wilton-manors"],
        "address": {"street": "2410 N Federal Hwy", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33305", "country": "US"},
        "phone": "(954) 900-1541",
        "website": "https://www.oliviersalon.com",
        "short_description": (
            "A full-service luxury salon and spa on the Wilton Manors corridor offering "
            "Milbon color, precision cuts, microblading, and lash tinting under one roof — "
            "plus a barbershop and an in-house retail boutique."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "The Wild Berry Salon",
        "slug": "wild-berry-salon-lauderdale-by-the-sea",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["lauderdale-by-the-sea"],
        "address": {"street": "262 Commercial Blvd, Suite B", "city": "Lauderdale-by-the-Sea", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(954) 268-4924",
        "website": "https://thewildberrysalon.com",
        "short_description": (
            "A beachy neighborhood gem steps from the ocean in Lauderdale-by-the-Sea "
            "offering hair, nails, makeup, and facials in a relaxed, friendly atmosphere "
            "that locals have been counting on for years."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS ────────────────────────────────────────────────────────────────
    {
        "name": "Archer Nail Studio",
        "slug": "archer-nail-studio-victoria-park",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["victoria-park"],
        "address": {"street": "1517 N Federal Hwy", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": "(954) 565-3151",
        "website": "https://archernailstudio.com",
        "short_description": (
            "A polished nail studio across from Trader Joe's using premium Volcano Spa "
            "products for manicures, pedicures, and gel services — consistently praised "
            "for clean technique and a welcoming, no-rush atmosphere."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },
    {
        "name": "Tipsy Salonbar",
        "slug": "tipsy-salonbar-las-olas",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["las-olas"],
        "address": {"street": "1503 E Las Olas Blvd", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(954) 779-2616",
        "website": "https://tipsyfortlauderdale.com",
        "short_description": (
            "A lively full-service beauty bar on Las Olas that pairs organic pedicures "
            "and gel manis with lash extensions, microblading, and hair services — "
            "the kind of place you pop in for nails and walk out with a whole new look."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Mod Nail Spa",
        "slug": "mod-nail-spa-sunrise-blvd",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["victoria-park"],
        "address": {"street": "1930 E Sunrise Blvd, Suite B-6", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": "(954) 306-6659",
        "website": "https://modnailsspa.com",
        "short_description": (
            "Established in 2016 and beloved by the neighborhood for meticulous chrome, "
            "cat-eye gel, and builder-gel work — Mod Nail Spa rewards regulars who book "
            "ahead with consistently creative results."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Harbor Nails",
        "slug": "harbor-nails-17th-street",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["se-17th-street"],
        "address": {"street": "1501 SE 17th St", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33316", "country": "US"},
        "phone": "(954) 256-6784",
        "website": "https://www.harbornailsftl.com",
        "short_description": (
            "Woman-owned and family-operated since 2008, Harbor Nails delivers "
            "meticulous gel, dip, and acrylic work alongside lash lifts and hot-stone "
            "pedicures — with multilingual staff and a spotlessly clean salon."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Venetian Nail Spa — Flagler Village",
        "slug": "venetian-nail-spa-flagler-village",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["flagler-village"],
        "address": {"street": "525 N Federal Hwy, Suite 200", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(954) 900-8799",
        "website": "https://venetiannailspaflagler.com",
        "short_description": (
            "Fort Lauderdale's most-reviewed nail destination in Flagler Village — "
            "a beautifully decorated space with cruelty-free, non-toxic products, "
            "a Latin-inspired aesthetic, and 347+ five-star reviews backing up the hype."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Nails Spa BK",
        "slug": "nails-spa-bk-victoria-park",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["victoria-park"],
        "address": {"street": "1145 N Federal Hwy", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": "(954) 289-8890",
        "website": "https://www.nailspabk.com",
        "short_description": (
            "A family-owned local nail salon with technicians who bring 20+ years of "
            "experience to Japanese gel, SNS dip, and luxury spa pedicures — "
            "personalized service at a price that keeps regulars loyal."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── OAKLAND PARK NAILS ──────────────────────────────────────────────────
    {
        "name": "K&K Nails and Spa",
        "slug": "kk-nails-and-spa-oakland-park",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["oakland-park"],
        "address": {"street": "169 E Oakland Park Blvd", "city": "Oakland Park", "state": "FL", "postal_code": "33334", "country": "US"},
        "phone": "(954) 530-0602",
        "website": None,
        "short_description": (
            "A dependable neighborhood nail salon on Oakland Park Blvd known for "
            "clean technique on manicures, pedicures, and gel services — "
            "the kind of place regulars return to without hesitation."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "D'Nails & Spa",
        "slug": "dnails-and-spa-oakland-park",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["oakland-park"],
        "address": {"street": "840 E Oakland Park Blvd, Suite 116", "city": "Oakland Park", "state": "FL", "postal_code": "33334", "country": "US"},
        "phone": "(954) 396-0860",
        "website": None,
        "short_description": (
            "A full-service nail salon and spa on Oakland Park Blvd offering "
            "manicures, pedicures, waxing, and facials — local staff with consistent "
            "reviews for care and cleanliness."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Paradise Nails & Spa",
        "slug": "paradise-nails-and-spa-oakland-park",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["oakland-park"],
        "address": {"street": "1323 E Commercial Blvd", "city": "Oakland Park", "state": "FL", "postal_code": "33334", "country": "US"},
        "phone": "(954) 999-0483",
        "website": None,
        "short_description": (
            "An Oakland Park nail spa on Commercial Blvd with a loyal local following — "
            "gel, acrylic, and spa pedicures in a clean, welcoming space where "
            "the staff remembers what you had last time."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    # ── OAKLAND PARK BARBER ─────────────────────────────────────────────────
    {
        "name": "Randy's Barbershop",
        "slug": "randys-barbershop-oakland-park",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["oakland-park"],
        "address": {"street": "3656 N Andrews Ave", "city": "Oakland Park", "state": "FL", "postal_code": "33309", "country": "US"},
        "phone": "(954) 317-7089",
        "website": None,
        "short_description": (
            "A trusted Oakland Park barbershop where fades, tapers, and beard "
            "work are done by barbers who've been at it long enough to have "
            "a waiting room full of familiar faces."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    # ── LAUDERDALE-BY-THE-SEA NAILS ──────────────────────────────────────────
    {
        "name": "Oceans Nail Spa",
        "slug": "oceans-nail-spa-lauderdale-by-the-sea",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["lauderdale-by-the-sea"],
        "address": {"street": "4741 N Ocean Dr", "city": "Lauderdale-by-the-Sea", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(954) 788-1891",
        "website": None,
        "short_description": (
            "A neighborhood nail spa steps from the beach in Lauderdale-by-the-Sea "
            "offering manicures, pedicures, and gel services with the unhurried "
            "pace the town is known for."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA & MASSAGE (maps to 'spa' category slug) ──────────────────────────
    {
        "name": "Majesty Day Spa",
        "slug": "majesty-day-spa-downtown",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["downtown-fort-lauderdale"],
        "address": {"street": "511 SE 5th Ave", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(754) 223-2669",
        "website": "https://www.yourmajestyspa.com",
        "short_description": (
            "A boho-luxury day spa in downtown Fort Lauderdale that opened in 2017 and "
            "quickly became the go-to for couples massages, customized body wraps, and "
            "therapeutic facials in a serene, candlelit setting."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Chi Spa",
        "slug": "chi-spa-wilton-manors",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["wilton-manors"],
        "address": {"street": "2415 N Dixie Hwy", "city": "Wilton Manors", "state": "FL", "postal_code": "33305", "country": "US"},
        "phone": "(954) 563-0001",
        "website": "https://chiwellness.org",
        "short_description": (
            "Wilton Manors' award-winning wellness sanctuary since 2007, offering "
            "rare modalities like ashiatsu barefoot massage, reiki, and cupping "
            "alongside classic facials and private yoga — a true mind-body retreat."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Planet Massage Urban Oasis",
        "slug": "planet-massage-urban-oasis-17th-street",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["se-17th-street"],
        "address": {"street": "500 SE 15th St, Suite 104", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33316", "country": "US"},
        "phone": "(954) 763-1619",
        "website": "https://planetmassage.com",
        "short_description": (
            "A massage-therapist-owned spa with an outdoor bamboo garden and mature "
            "mango groves — three-time TripAdvisor Certificate of Excellence winner "
            "and consistently rated Fort Lauderdale's best massage spa."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },
    {
        "name": "Zenko Spa & Massage",
        "slug": "zenko-spa-north-federal",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["north-fort-lauderdale"],
        "address": {"street": "6232 N Federal Hwy", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(954) 368-4888",
        "website": "https://www.zenkospa.com",
        "short_description": (
            "A luxury day spa on North Federal offering full-body massage, skin-rejuvenating "
            "facials, and waxing in a calm, beautifully appointed space — open seven days "
            "a week with extended evening hours."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LAUDERDALE-BY-THE-SEA SPA ────────────────────────────────────────────
    {
        "name": "Acqua Salon & Spa",
        "slug": "acqua-salon-and-spa-lauderdale-by-the-sea",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["lauderdale-by-the-sea"],
        "address": {"street": "218 Commercial Blvd, Unit 108", "city": "Lauderdale-by-the-Sea", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(754) 236-0597",
        "website": None,
        "short_description": (
            "A full-service salon and spa in the heart of Lauderdale-by-the-Sea "
            "offering hair, skin, and massage treatments steps from the beach — "
            "a complete beauty stop in a town that moves at its own relaxed pace."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW ──────────────────────────────────────────────────────────
    {
        "name": "KAI Beauty Co.",
        "slug": "kai-beauty-co-north-federal",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["north-fort-lauderdale"],
        "address": {"street": "4242 N Federal Hwy, Suite H", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(305) 510-0435",
        "website": "https://www.kaibeautyco.com",
        "short_description": (
            "A specialist studio for lash extensions, brow lamination, and microblading "
            "that also trains future lash artists — classic, hybrid, and mega-volume "
            "sets applied with pharmaceutical-grade Japanese adhesives."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "LASHISM",
        "slug": "lashism-fort-lauderdale",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["north-fort-lauderdale"],
        "address": {"street": "3455 NE 12th Terrace, Unit 1", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33334", "country": "US"},
        "phone": "(954) 866-3335",
        "website": "https://lashism.com",
        "short_description": (
            "A dedicated eyelash extension studio using anti-bacterial lashes and "
            "pharmaceutical-grade Japanese glue, with master technicians who offer "
            "personalized consultations to match extensions to your eye shape and lifestyle."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Fleeked Beauty",
        "slug": "fleeked-beauty-downtown",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["downtown-fort-lauderdale"],
        "address": {"street": "800 E Broward Blvd, Suite 400", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": "(954) 395-4294",
        "website": "https://fleekedbeauty.com",
        "short_description": (
            "A downtown studio offering the full spectrum of lash and brow work — "
            "from classic extensions to ombré powder brows and permanent eyeliner — "
            "alongside microblading and aesthetic injectables for a one-stop beauty fix."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Paradise Lashes",
        "slug": "paradise-lashes-downtown",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["downtown-fort-lauderdale"],
        "address": {"street": "315 NE 3rd Ave, Unit 101 – Spa G", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33301", "country": "US"},
        "phone": None,
        "website": "https://www.paradiselashes.com",
        "short_description": (
            "A focused lash extension and lash lift studio downtown dedicated to "
            "enhancing natural lashes with superior-quality extensions — "
            "precise, personalized application in a calm, spa-like setting."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MAKEUP ───────────────────────────────────────────────────────────────
    {
        "name": "Lawa Salon",
        "slug": "lawa-salon-las-olas",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["las-olas"],
        "address": {"street": "1684 SE 10th Ave", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33316", "country": "US"},
        "phone": "(954) 681-3939",
        "website": "https://lawa.salon",
        "short_description": (
            "A full-service beauty salon near Las Olas known for standout European "
            "lash and brow work, permanent makeup, and Russian manicures — "
            "stylists who combine old-world precision with a modern South Florida aesthetic."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Robbin Junnola Beauty",
        "slug": "robbin-junnola-beauty-north-fort-lauderdale",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["north-fort-lauderdale"],
        "address": {"street": "6278 N Federal Hwy, Suite 144", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33308", "country": "US"},
        "phone": "(954) 604-0602",
        "website": "https://www.robbinjunnolabeauty.com",
        "short_description": (
            "Former MAC artist Robbin Junnola has been creating flawless bridal and "
            "event looks since 2011 — she and her licensed team offer airbrush and "
            "traditional makeup, hair trials, and full on-location bridal-party services."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA/FACIAL (Skin Ritualist and Pure Skin map to 'spa' — closest fit) ─
    {
        "name": "Skin Ritualist",
        "slug": "skin-ritualist-victoria-park",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["victoria-park"],
        "address": {"street": "1948 E Sunrise Blvd, Unit 2", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": None,
        "website": "https://skinritualist.com",
        "short_description": (
            "Run by second-generation esthetician Susie, Skin Ritualist adapts every "
            "facial in real time to what your skin actually needs that day — acne "
            "treatments, microneedling, and chemical peels delivered with genuine expertise."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Pure Skin & Beauty",
        "slug": "pure-skin-beauty-flagler-village",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["flagler-village"],
        "address": {"street": "305 NE 7th St", "city": "Fort Lauderdale", "state": "FL", "postal_code": "33304", "country": "US"},
        "phone": "(954) 467-9733",
        "website": "https://pureskinandbeauty.com",
        "short_description": (
            "A clinical esthetics studio in Flagler Village with 20+ years of experience "
            "delivering medical-grade facials, body contouring, and brow care — "
            "same-day appointments available, with a satisfaction guarantee."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── POMPANO BEACH ────────────────────────────────────────────────────────
    {
        "name": "Artistic Hair & Nails",
        "slug": "artistic-hair-and-nails-pompano-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["pompano-beach"],
        "address": {"street": "732 E McNab Rd", "city": "Pompano Beach", "state": "FL", "postal_code": "33060", "country": "US"},
        "phone": "(954) 771-6245",
        "website": None,
        "short_description": (
            "A long-standing Pompano Beach salon on McNab Road offering haircuts, color, "
            "and nail services under one roof — the kind of reliable neighborhood spot "
            "that regulars have been returning to for years."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "The Studio Salon & Day Spa",
        "slug": "the-studio-salon-day-spa-pompano-beach",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["pompano-beach"],
        "address": {"street": "1403 S Federal Hwy", "city": "Pompano Beach", "state": "FL", "postal_code": "33062", "country": "US"},
        "phone": "(954) 788-2662",
        "website": None,
        "short_description": (
            "A full-service day spa on South Federal Highway bringing salon and spa "
            "services together — haircuts, coloring, facials, and massage for Pompano "
            "Beach residents who want everything in one appointment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Luxe Nail Spa",
        "slug": "luxe-nail-spa-pompano-beach",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["pompano-beach"],
        "address": {"street": "808 N Federal Hwy", "city": "Pompano Beach", "state": "FL", "postal_code": "33062", "country": "US"},
        "phone": "(954) 657-8375",
        "website": None,
        "short_description": (
            "A nail spa on North Federal Highway in Pompano Beach with a reputation "
            "for clean work and a calm atmosphere — manicures, pedicures, and gel "
            "sets done by a team that takes the time to get the details right."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "LS Nails & Spa",
        "slug": "ls-nails-and-spa-pompano-beach",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["pompano-beach"],
        "address": {"street": "2101 N Federal Hwy Ste D103", "city": "Pompano Beach", "state": "FL", "postal_code": "33062", "country": "US"},
        "phone": "(954) 960-2447",
        "website": None,
        "short_description": (
            "A well-reviewed nail spa in the North Federal Highway corridor, LS Nails "
            "offers manicures, pedicures, acrylic sets, and waxing in a comfortable "
            "shop that keeps a loyal Pompano Beach following."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "European Wax Center Pompano Beach",
        "slug": "european-wax-center-pompano-beach",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["pompano-beach"],
        "address": {"street": "1700 NE 23rd St Suite 104", "city": "Pompano Beach", "state": "FL", "postal_code": "33062", "country": "US"},
        "phone": "(954) 820-7086",
        "website": "https://www.waxcenter.com/locations/pompano-beach",
        "short_description": (
            "The Pompano Beach outpost of the national waxing specialist, using their "
            "proprietary Comfort Wax formula and a strip-free technique that regulars "
            "say is noticeably gentler than traditional waxing services."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_fort_lauderdale() -> None:
    db = get_db()

    # Look up the beauty network
    network = await db.networks.find_one({"slug": "beauty"})
    if not network:
        print("ERROR: beauty network not found — run seed_networks.py first.")
        return
    network_id = network["_id"]
    print("Found beauty network: id=%s" % network_id)

    now = datetime.now(timezone.utc)

    # ── City ─────────────────────────────────────────────────────────────────
    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network_id,
        "slug": "fort-lauderdale",
        "name": "Fort Lauderdale",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Fort Lauderdale's best-kept beauty addresses.",
        "hero_description": (
            "An index of the stylists, colorists, estheticians, and nail artists "
            "Fort Lauderdale locals actually book — from Las Olas to Wilton Manors."
        ),
        "seo_title": "Fort Lauderdale Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Fort Lauderdale — salons, spas, lash studios, "
            "and nail bars discovered by locals."
        ),
        "editorial_headlines": [
            {"headline": "Fort Lauderdale's best-kept beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "fort-lauderdale"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: fort-lauderdale (id=%s)" % city_id)

    # ── Neighborhoods ────────────────────────────────────────────────────────
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

    # ── Businesses ───────────────────────────────────────────────────────────
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

        # WHY: replacement writes share one live-state boundary so a satellite
        # reseed cannot drop owner, billing, voice, or analytics state.
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
    print("Fort Lauderdale seed complete:")
    print("  City:          fort-lauderdale (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami seed — this script writes to
    # the database. Refuse to run against production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_fort_lauderdale()


if __name__ == "__main__":
    run(main())
