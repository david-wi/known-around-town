"""Seed Brickell for the Beauty network.

18 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_brickell
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert


# ── Neighborhoods ─────────────────────────────────────────────────────────────
# (slug, display name, vibe description, listed_count)
NEIGHBORHOODS: List[tuple] = [
    ("brickell-ave-mary-brickell-village", "Brickell Ave / Mary Brickell Village", "Walkable & upscale",          7),
    ("brickell-city-centre",               "SW 8th St / Brickell City Centre",      "Sleek & central",             4),
    ("se-1st-ave-downtown-brickell",       "SE 1st Ave / Downtown Brickell",         "Financial district core",     4),
    ("alice-wainwright-sw-15th-rd",        "Alice Wainwright / SW 15th Rd",          "Residential & refined",       3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "brickell-ave-mary-brickell-village": (
        "Mary Brickell Village is the neighborhood's main commercial corridor — "
        "an open-air complex on South Miami Avenue where blow-dry bars, hair salons, "
        "and nail studios sit alongside the restaurants and shops that draw Brickell's "
        "professional crowd on lunch breaks and after work. The beauty businesses here "
        "run early and late because their clients do too."
    ),
    "brickell-city-centre": (
        "Brickell City Centre brought a new tier of retail to the neighborhood when "
        "it opened, and the beauty businesses inside it operate accordingly — "
        "appointment-first, well-staffed, and accustomed to clients who expect "
        "efficiency and quality in equal measure. This is Brickell's most "
        "concentrated block of polished beauty services."
    ),
    "se-1st-ave-downtown-brickell": (
        "The eastern edge of Brickell along Brickell Bay Drive and the avenues "
        "flanking it holds some of the neighborhood's most established beauty "
        "destinations — the kind of places that have served the same office towers "
        "for a decade and built their reputation on repeat business from people "
        "who notice when something is off."
    ),
    "alice-wainwright-sw-15th-rd": (
        "South of the main Brickell corridor, toward Alice Wainwright Park and the "
        "residential streets off SW 15th Road, the beauty studios are quieter and "
        "more neighborhood-focused. The clientele here lives nearby rather than "
        "commuting in — and the studios reflect that with a more personal, "
        "appointment-forward approach."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
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
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — BRICKELL AVE / MARY BRICKELL VILLAGE ──────────────────────────
    {
        "name": "Rik Rak Salon",
        "slug": "rik-rak-salon-brickell-ave",
        "category_slugs": ["hair", "nails"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "1061 Brickell Plaza", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 371-7324",
        "website": "http://www.rikrak.com",
        "instagram": "@rikraksalon",
        "short_description": (
            "A 6,000-square-foot flagship salon directly across from the Four Seasons "
            "on Brickell Plaza, offering full-service hair, nail care, and skin "
            "treatments in a setting that matches the neighborhood's ambition — "
            "open seven days with walk-ins welcome and late hours to suit the workday."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Studio-D Brickell",
        "slug": "studio-d-brickell-mary-brickell-village",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "900 S Miami Ave, Suite 266", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 349-4969",
        "website": "https://www.studio-dbrickell.com",
        "instagram": "@studiodmiami",
        "short_description": (
            "A boutique salon on the second floor of Mary Brickell Village with over "
            "20 years of combined Miami styling experience — specializing in cuts, "
            "balayage, extensions, blowouts, and keratin treatments for a professional "
            "clientele that values discretion and precision."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Trini Salon & Spa",
        "slug": "trini-salon-and-spa-brickell-ave",
        "category_slugs": ["hair", "nails", "spa"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "941 Brickell Ave", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(786) 220-7796",
        "website": "https://www.trinisalons.com",
        "instagram": "@trini_salons",
        "short_description": (
            "A French-influenced full-service salon in the heart of Brickell "
            "offering hair color, cuts, nails, and spa services — a genuine "
            "one-stop for the working professional who wants quality hair and "
            "nail work without bouncing between multiple studios."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Blo Blow Dry Bar — Brickell",
        "slug": "blo-blow-dry-bar-brickell-mary-brickell-village",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "900 S Miami Ave", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 374-2565",
        "website": "https://blomedry.com/blo-brickell/",
        "instagram": "@blobrickell",
        "short_description": (
            "North America's original blow-dry bar, with a Brickell outpost in "
            "Mary Brickell Village running early-to-late hours designed around "
            "the financial district schedule — wash, blo, and go, with no cuts "
            "or color, just polished finishes done efficiently."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — SE 1ST AVE / DOWNTOWN BRICKELL ────────────────────────────────
    {
        "name": "Sean Donaldson Hair — Brickell",
        "slug": "sean-donaldson-hair-brickell-city-centre",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "701 S Miami Ave", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(786) 646-9390",
        "website": "https://www.seandonaldsonhair.com",
        "instagram": "@seandonaldson_hair",
        "short_description": (
            "A high-end hair salon with a location inside Brickell City Centre "
            "known for precision color, balayage, and blowouts — the kind of "
            "appointment-first studio where senior stylists handle every client "
            "and the results justify the price."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── HAIR — ALICE WAINWRIGHT / SW 15TH RD ─────────────────────────────────
    {
        "name": "Armando Palacios Barber Studio — Brickell",
        "slug": "armando-palacios-barber-studio-brickell",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["alice-wainwright-sw-15th-rd"],
        "address": {"street": "1295 Coral Way, Suite 4", "city": "Miami", "state": "FL", "postal_code": "33145", "country": "US"},
        "phone": "(305) 400-1709",
        "website": "https://apbarberstudio.com",
        "instagram": "@ap.barberstudio",
        "short_description": (
            "A premium Brickell-area barbershop on Coral Way known for tailored "
            "haircuts, expert fades, straight razor shaves, and beard sculpting "
            "in a refined setting — the destination for professional men who "
            "treat a haircut as a considered appointment, not a chore."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── BARBER — SE 1ST AVE / DOWNTOWN BRICKELL ──────────────────────────────
    {
        "name": "The Spot Barbershop — Brickell Bay",
        "slug": "the-spot-barbershop-brickell-bay",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "1200 Brickell Bay Dr, Suite 104", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(786) 508-0405",
        "website": "https://thespotbarbershop.com/locations/brickell-bay/",
        "instagram": "@thespotbarbershop",
        "short_description": (
            "A sleek, modern barbershop on Brickell Bay Drive offering precision "
            "men's haircuts, hot towel shaves, beard sculpting, and straight razor "
            "finishes — with business-friendly hours (open weekdays from 8 AM) "
            "built around the Brickell financial district schedule."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "The Spot Barbershop — Brickell Heights",
        "slug": "the-spot-barbershop-brickell-heights",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "1300 S Miami Ave", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(786) 542-1234",
        "website": "https://thespotbarbershop.com/locations/brickell-heights/",
        "instagram": "@thespotbarbershop",
        "short_description": (
            "The Brickell Heights location of South Florida's well-regarded premium "
            "barbershop chain — a reliable option for executives who need a clean, "
            "consistent cut close to the Brickell Ave corridor without a long lead time."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — BRICKELL AVE / MARY BRICKELL VILLAGE ─────────────────────────
    {
        "name": "Neo Nails Brickell",
        "slug": "neo-nails-brickell",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "426 SW 8th St, Suite 7", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 306-8888",
        "website": "https://www.neo-nails.com",
        "instagram": "@neonailsbrickell",
        "short_description": (
            "Brickell's most-reviewed nail salon with over 3,000 Google reviews "
            "and a 4.6-star average — a luxury nail and day spa offering manicures, "
            "pedicures, gel, dip, acrylics, and massage services in a hotel-style "
            "environment that stands apart from the typical walk-in nail bar."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Top Beauty House",
        "slug": "top-beauty-house-brickell",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "777 Brickell Ave, Suite 170", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(786) 741-4076",
        "website": None,
        "instagram": "@topbeautyhouse",
        "short_description": (
            "A boutique nail studio inside a Brickell office tower specializing "
            "in Russian gel manicures, smart gel pedicures, and nail art — popular "
            "with the professional women who work in the buildings nearby and want "
            "precise, elevated nail work without leaving the neighborhood."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Brickell Nail Bar",
        "slug": "brickell-nail-bar-city-centre",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "701 S Miami Ave, Suite 377C", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 372-3888",
        "website": None,
        "instagram": "@brickellnailbar",
        "short_description": (
            "A convenient nail studio inside Brickell City Centre offering "
            "manicures, pedicures, gel, and dip powder in a clean, modern "
            "setting — well-positioned for city-centre shoppers and office "
            "workers looking for a reliable, no-fuss nail appointment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA / MED-SPA — SE 1ST AVE / DOWNTOWN BRICKELL ──────────────────────
    {
        "name": "Lux MedSpa Brickell",
        "slug": "lux-medspa-brickell",
        "category_slugs": ["med-spa", "spa"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "805 S Miami Ave, 9th Floor", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 988-9388",
        "website": "https://www.luxmedspabrickell.com",
        "instagram": "@luxmedspabrickell",
        "short_description": (
            "A top-rated luxury med spa and day spa on the 9th floor of the "
            "SLS LUX Hotel in Brickell — winner of multiple Miami Herald Gold "
            "Awards including Best Spa Day and Best Med Spa, with over 2,200 "
            "five-star reviews. Known for HydraFacials, microneedling, lymphatic "
            "drainage massage, and the Ultraformer MPT skin-tightening treatment."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Salon 701",
        "slug": "salon-701-brickell",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "701 Brickell Ave", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 372-0701",
        "website": None,
        "instagram": "@salon701miami",
        "short_description": (
            "A full-service salon inside the 701 Brickell tower offering nail "
            "care and beauty services to the building's professional tenants "
            "and nearby residents — a reliable option that earns its clientele "
            "through consistency and the convenience of its location."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — BRICKELL AVE / MARY BRICKELL VILLAGE ───────────────────
    {
        "name": "The Lash Lounge & Brow Bar — Brickell",
        "slug": "the-lash-lounge-brow-bar-brickell",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "1010 Brickell Ave, Unit 3504", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(786) 295-7720",
        "website": "https://www.nateelashes.com",
        "instagram": "@mysecretstudiolash",
        "short_description": (
            "A dedicated lash and brow studio inside 1010 Brickell offering "
            "classic, hybrid, and mega volume lash extensions alongside brow "
            "lamination, tinting, and microblading — a well-established "
            "Brickell option with a strong track record for retention and "
            "natural-looking results."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — ALICE WAINWRIGHT / SW 15TH RD ──────────────────────────────
    {
        "name": "Lash House Miami",
        "slug": "lash-house-miami-brickell",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "485 Brickell Ave", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": "@lashhousemiami",
        "short_description": (
            "An appointment-only lash studio on Brickell Ave offering a focused "
            "menu of custom lash sets in a private, unhurried setting — the kind "
            "of studio where the technician takes time to understand what you "
            "want before picking up a single lash."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── WAXING — BRICKELL CITY CENTRE ────────────────────────────────────────
    {
        "name": "Beauty and Bronze Lash Studio",
        "slug": "beauty-and-bronze-lash-studio-brickell",
        "category_slugs": ["lash-brow", "waxing"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "108 SW 9th St, Suite 5", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": "@beautyandbronce",
        "short_description": (
            "A boutique lash and brow studio on SW 9th Street founded by a "
            "technician who relocated to Brickell specifically to serve the "
            "neighborhood's beauty market — known for meticulous lash extensions, "
            "brow shaping, and face waxing in a clean, appointment-first studio."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — ALICE WAINWRIGHT / SW 15TH RD ──────────────────────────────────
    {
        "name": "ManCave For Men — Brickell",
        "slug": "mancave-for-men-brickell",
        "category_slugs": ["barber", "spa"],
        "neighborhood_slugs": ["alice-wainwright-sw-15th-rd"],
        "address": {"street": "1395 Brickell Ave, Suite 800", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 860-5011",
        "website": "https://mancaveformen.com",
        "instagram": "@mancaveformen",
        "short_description": (
            "South Florida's premier men's grooming destination with a Brickell "
            "location offering precision haircuts, kids' cuts, straight razor "
            "shaves, and grooming services in a comfortable, lounge-style setting "
            "designed specifically around the male client experience."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — BRICKELL CITY CENTRE ───────────────────────────────────────────
    {
        "name": "Studio-D Brickell — 1395 Location",
        "slug": "studio-d-brickell-1395-brickell-ave",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "1395 Brickell Ave, Suite 800", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 998-9082",
        "website": "https://www.studio-dbrickell.com",
        "instagram": "@studiodmiami",
        "short_description": (
            "The second Studio-D Brickell location, serving the northern end of "
            "the Brickell corridor with the same specialty in balayage, extensions, "
            "and precision cuts — a second option for the salon's growing Brickell "
            "clientele when the Mary Brickell Village studio is fully booked."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — SE 1ST AVE / DOWNTOWN BRICKELL ────────────────────────────────
    {
        "name": "Kelia Salon",
        "slug": "kelia-salon-brickell",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["se-1st-ave-downtown-brickell"],
        "address": {"street": "1221 Brickell Ave, Suite 900", "city": "Miami", "state": "FL", "postal_code": "33131", "country": "US"},
        "phone": "(305) 374-7333",
        "website": "https://www.keliasalon.com",
        "instagram": "@keliasalon",
        "short_description": (
            "A long-established Brickell salon known for precision cuts, highlights, "
            "and balayage serving the professional women who work in the Brickell Ave "
            "office towers — a consistent favorite with a loyal client base built "
            "over years of reliable color work and a welcoming, no-pressure environment."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BLOW DRY / HAIR — BRICKELL CITY CENTRE ───────────────────────────────
    {
        "name": "Primp & Blow",
        "slug": "primp-and-blow-brickell-city-centre",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "701 S Miami Ave, Suite 240", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 400-7250",
        "website": "https://primpandblow.com",
        "instagram": "@primpandblow",
        "short_description": (
            "A Miami-founded blow-dry bar and salon inside Brickell City Centre "
            "offering blowouts, braids, upstyles, and makeup services for clients "
            "heading straight from work to an event — known for stylists who actually "
            "listen and results that hold up in South Florida humidity."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — BRICKELL CITY CENTRE ────────────────────────────────────────────
    {
        "name": "Kure Spa — Brickell City Centre",
        "slug": "kure-spa-brickell-city-centre",
        "category_slugs": ["spa", "nails"],
        "neighborhood_slugs": ["brickell-city-centre"],
        "address": {"street": "701 S Miami Ave, Suite 375", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(305) 908-5873",
        "website": "https://kurespa.com",
        "instagram": "@kurespa",
        "short_description": (
            "A clean-beauty nail and body spa inside Brickell City Centre using "
            "non-toxic, 7-free polish and organic products throughout — manicures, "
            "pedicures, massages, and facials designed for clients who care what "
            "goes on their skin as much as how the finished result looks."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── WAXING — BRICKELL AVE / MARY BRICKELL VILLAGE ────────────────────────
    {
        "name": "European Wax Center — Brickell",
        "slug": "european-wax-center-brickell-mary-brickell-village",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["brickell-ave-mary-brickell-village"],
        "address": {"street": "900 S Miami Ave, Suite 150", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(786) 615-9155",
        "website": "https://www.waxcenter.com/locations/brickell",
        "instagram": "@ewcbrickell",
        "short_description": (
            "The Brickell outpost of the national waxing franchise known for its "
            "exclusive Comfort Wax formula — a proprietary wax that adheres to hair "
            "rather than skin to minimize discomfort. Located in Mary Brickell Village "
            "with flexible scheduling and a menu covering face, body, and Brazilian "
            "waxing for both women and men."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH — ALICE WAINWRIGHT / SW 15TH RD ─────────────────────────────────
    {
        "name": "Amazing Lash Studio — Brickell",
        "slug": "amazing-lash-studio-brickell",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["alice-wainwright-sw-15th-rd"],
        "address": {"street": "1451 S Miami Ave, Suite 103", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": "(786) 347-1818",
        "website": "https://amazinglashstudio.com/locations/florida/brickell",
        "instagram": "@amazinglashstudiobrickell",
        "short_description": (
            "A dedicated lash extension studio south of the main Brickell corridor "
            "offering classic, hybrid, and volume sets with a membership model "
            "designed for clients who want fresh lashes on a predictable schedule "
            "without the unpredictability of single-appointment pricing."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_brickell() -> None:
    db = get_db()

    # Look up the beauty network by the known network ID rather than slug,
    # since the slug alone may not be unique across environments.
    # WHY: using the exact network ID from the seed spec avoids any ambiguity
    # when multiple beauty networks are bootstrapped in the same DB.
    BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
        # Fallback: look up by slug in case the ID differs in this environment
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
        "slug": "brickell",
        "name": "Brickell",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Brickell's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, barbers, and "
            "nail studios that Brickell professionals actually book — from Mary "
            "Brickell Village and Brickell City Centre to Brickell Bay Drive and "
            "the residential streets south of the main corridor."
        ),
        "seo_title": "Brickell Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Brickell, Miami — salons, spas, "
            "lash studios, nail bars, and barbershops discovered by locals. "
            "Covering Mary Brickell Village, Brickell City Centre, SE 1st Ave, "
            "and the Alice Wainwright / SW 15th Rd corridor."
        ),
        "editorial_headlines": [
            {"headline": "Brickell's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": "brickell.knowsbeauty.com",
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "brickell"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: brickell (id=%s)" % city_id)

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
            "services": [],
            "created_at": now,
            "updated_at": now,
        }

        # WHY: preserve owner claim data, billing fields, hours, and services
        # on re-seed so that any owner who has already claimed their listing
        # doesn't lose their work. Same pattern as Coral Gables, Boca Raton,
        # and Fort Lauderdale seeds.
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
    print("Brickell seed complete:")
    print("  City:          brickell (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as all other city seeds — this script
    # writes to the database and must not run against production unintentionally.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_brickell()


if __name__ == "__main__":
    run(main())
