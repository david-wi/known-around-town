"""Seed Coral Gables for the Beauty network.

24 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_coral_gables
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
    ("miracle-mile",          "Miracle Mile / Downtown",    "Walkable & storied",           8),
    ("coconut-grove-adjacent","Coconut Grove Adjacent",     "Lush & residential",           5),
    ("south-coral-gables",    "South Coral Gables",         "Quiet & established",          5),
    ("north-coral-gables",    "North Coral Gables",         "Medical district & accessible", 6),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "miracle-mile": (
        "Coral Gables was designed to be beautiful — and Miracle Mile makes good on "
        "that promise. The pedestrian-friendly corridor between Douglas Road and Le Jeune "
        "holds bridal boutiques, established salons, and beauty studios that have served "
        "the city's most careful dressers for decades. This is where you come when "
        "appearance is not an afterthought."
    ),
    "coconut-grove-adjacent": (
        "The neighborhoods south of Miracle Mile and east toward Coconut Grove carry "
        "the same lush character as the banyan-shaded streets they sit beside. The beauty "
        "studios here tend to be appointment-only, long-established, and built on the "
        "kind of word-of-mouth that only comes from getting it right, consistently."
    ),
    "south-coral-gables": (
        "South Coral Gables runs from Sunset Drive toward Kendall Drive, a quieter "
        "stretch of Mediterranean-revival neighborhoods and well-tended plazas. The "
        "salons and spas that operate here serve a residential clientele that drives "
        "in specifically — not foot traffic. That selectivity shows in the quality."
    ),
    "north-coral-gables": (
        "Bordered by Coral Way and the University of Miami medical corridor, north "
        "Coral Gables draws both residents and the kind of professional clientele "
        "that values precision and efficiency. Several of the area's best colorists "
        "and estheticians have set up along this stretch, within range of Brickell "
        "but with Gables pricing and Gables space."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — MIRACLE MILE / DOWNTOWN ───────────────────────────────────────
    {
        "name": "Salon Benedetto",
        "slug": "salon-benedetto-miracle-mile",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "2 Alhambra Plaza, Suite 110", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 444-7330",
        "website": "https://salonbenedetto.com",
        "instagram": "@salonbenedetto",
        "short_description": (
            "One of Coral Gables' most storied hair salons, operating since 1987 near "
            "Miracle Mile. Known for impeccable color and precision cuts with a European "
            "approach and a multi-decade clientele that speaks for itself."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "The Gables Salon",
        "slug": "the-gables-salon-miracle-mile",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "250 Miracle Mile", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 441-8882",
        "website": "https://thegablessalon.com",
        "instagram": "@thegablessalon",
        "short_description": (
            "A well-established full-service salon directly on Miracle Mile offering "
            "cuts, color, Brazilian blowouts, and extensions with a team that has "
            "been serving the Coral Gables community for many years."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Salon One — Coral Gables",
        "slug": "salon-one-coral-gables-miracle-mile",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "245 Alhambra Cir", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 445-2533",
        "website": "https://salonone.com",
        "instagram": "@salonone_coralgables",
        "short_description": (
            "A flagship Coral Gables location of the South Florida salon mini-chain, "
            "known for color services, balayage, keratin treatments, and blow-outs "
            "delivered by senior-level stylists near Alhambra Circle."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Tati Hair Studio",
        "slug": "tati-hair-studio-miracle-mile",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "146 Giralda Ave", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(786) 801-9272",
        "website": "https://tatihair.com",
        "instagram": "@tatihairsalon",
        "short_description": (
            "A boutique Coral Gables salon on Giralda Ave specializing in balayage, "
            "highlights, and natural color techniques with a Brazilian flair — "
            "consistently praised for blending technique and consultation quality."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — NORTH CORAL GABLES ────────────────────────────────────────────
    {
        "name": "Ego Salon & Spa",
        "slug": "ego-salon-and-spa-north-coral-gables",
        "category_slugs": ["hair", "spa"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "3620 SW 22nd St", "city": "Coral Gables", "state": "FL", "postal_code": "33145", "country": "US"},
        "phone": "(305) 443-2646",
        "website": "https://egosalonandspa.com",
        "instagram": "@egosalonandspa",
        "short_description": (
            "A full-service salon and spa in north Coral Gables offering hair color, "
            "cuts, facials, massages, and waxing — a neighborhood anchor that has "
            "earned loyal clients across the Coral Way corridor."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Hair Concept Salon",
        "slug": "hair-concept-salon-north-coral-gables",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "2340 SW 32nd Ave", "city": "Coral Gables", "state": "FL", "postal_code": "33145", "country": "US"},
        "phone": "(305) 444-4422",
        "website": None,
        "instagram": "@hairconcept_salon",
        "short_description": (
            "A long-running Coral Gables salon with a loyal multigenerational following, "
            "known for reliable cuts, color, and keratin treatments at fair prices — "
            "the kind of place you keep coming back to once you find it."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — SOUTH CORAL GABLES ────────────────────────────────────────────
    {
        "name": "Blo Blow Dry Bar — Coral Gables",
        "slug": "blo-blow-dry-bar-coral-gables-south",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["south-coral-gables"],
        "address": {"street": "5831 SW 73rd St", "city": "South Miami", "state": "FL", "postal_code": "33143", "country": "US"},
        "phone": "(305) 669-3600",
        "website": "https://blomedry.com/locations/south-miami",
        "instagram": "@blosouthmiamifl",
        "short_description": (
            "The South Miami/Coral Gables area Blo franchise — quick, quality blow-outs "
            "by appointment or walk-in, with no cuts or color, just polished finishes "
            "on a schedule that works for the Gables professional crowd."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — MIRACLE MILE / DOWNTOWN ──────────────────────────────────────
    {
        "name": "The Nail Suite Coral Gables",
        "slug": "the-nail-suite-coral-gables-miracle-mile",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "2601 SW 37th Ave, Suite 201", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(786) 703-1966",
        "website": "https://thenailsuitecoralgables.com",
        "instagram": "@thenailsuite_coralgables",
        "short_description": (
            "A luxe boutique nail studio serving the Coral Gables/Coconut Grove "
            "border, known for Russian manicures, Gel-X extensions, nail art, "
            "and pedicures in a private, appointment-first environment."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Gables Nail Bar",
        "slug": "gables-nail-bar-miracle-mile",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "100 Miracle Mile", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 447-7777",
        "website": None,
        "instagram": "@gablesnailbar",
        "short_description": (
            "A popular Miracle Mile nail bar offering gel manicures, dip powder, "
            "acrylics, and pedicures with a clean, modern aesthetic and a reliable "
            "team that makes walk-ins feel as welcome as regulars."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — NORTH CORAL GABLES ───────────────────────────────────────────
    {
        "name": "Coco Nails Coral Gables",
        "slug": "coco-nails-coral-gables-north",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "3655 SW 8th St", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 446-4388",
        "website": None,
        "instagram": None,
        "short_description": (
            "A dependable neighborhood nail salon on Calle Ocho at the Coral Gables "
            "edge, offering manicures, pedicures, gel, and dip powder services at "
            "competitive prices with a loyal bilingual clientele."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    {
        "name": "Beauty Bar Nails & Spa",
        "slug": "beauty-bar-nails-and-spa-north-coral-gables",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "2680 SW 37th Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 443-9001",
        "website": None,
        "instagram": "@beautybarnailsspa",
        "short_description": (
            "A full-service nail and spa studio at the Coral Gables/Coconut Grove "
            "border offering manicures, pedicures, facials, and waxing — valued by "
            "locals for fair pricing and a relaxed, professional atmosphere."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — MIRACLE MILE / DOWNTOWN ────────────────────────────────────────
    {
        "name": "Spa at the Biltmore Hotel",
        "slug": "spa-at-the-biltmore-coral-gables-miracle-mile",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "1200 Anastasia Ave", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 913-3159",
        "website": "https://www.biltmorehotel.com/spa",
        "instagram": "@biltmorehotelcoralgables",
        "short_description": (
            "The iconic spa inside Coral Gables' landmark Biltmore Hotel — a "
            "full-service destination for massages, facials, body treatments, and "
            "the legendary rooftop pool experience, all inside a National Historic "
            "Landmark dating to 1926."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Palms Hotel Spa — Coral Gables",
        "slug": "palms-hotel-spa-coral-gables-miracle-mile",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "116 Alhambra Plaza", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 441-2600",
        "website": "https://www.thepalmscoralgables.com/spa",
        "instagram": "@palmscoralgables",
        "short_description": (
            "A boutique hotel spa in central Coral Gables offering massages, "
            "facials, and body treatments in an intimate Mediterranean-courtyard "
            "setting — quieter and more personal than the major resort options."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — COCONUT GROVE ADJACENT ─────────────────────────────────────────
    {
        "name": "Spa Internazionale at Hotel Colonnade",
        "slug": "spa-internazionale-hotel-colonnade-coconut-grove-adjacent",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["coconut-grove-adjacent"],
        "address": {"street": "180 Aragon Ave", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 441-2600",
        "website": "https://www.hotelcolonnade.com/spa",
        "instagram": "@hotelcolonnadecoralgables",
        "short_description": (
            "An elegant spa inside the Hotel Colonnade — one of Coral Gables' "
            "landmark hotel properties — offering European-style massages, facials, "
            "body wraps, and beauty services in a classic setting near the Miracle "
            "Mile boundary."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "ZenZone Wellness Spa",
        "slug": "zenzone-wellness-spa-coconut-grove-adjacent",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["coconut-grove-adjacent"],
        "address": {"street": "3250 Mary St, Suite 201", "city": "Coconut Grove", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 446-0811",
        "website": "https://zenzonewellness.com",
        "instagram": "@zenzonewellness",
        "short_description": (
            "A tranquil wellness and day spa on the Coral Gables/Coconut Grove border "
            "offering deep tissue massage, aromatherapy, hot stone treatments, "
            "customized facials, and infrared sauna sessions."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — MIRACLE MILE / DOWNTOWN ────────────────────────────────
    {
        "name": "Lavish Lash Lounge Coral Gables",
        "slug": "lavish-lash-lounge-coral-gables-miracle-mile",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "3250 Mary St, Suite 103", "city": "Coconut Grove", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 960-0822",
        "website": "https://lavishlashloungemfl.com",
        "instagram": "@lavishlashlounge",
        "short_description": (
            "A popular lash and brow destination serving the Coral Gables and "
            "Coconut Grove area with classic, hybrid, and mega volume extensions, "
            "lash lifts, brow lamination, and tinting — well-reviewed for retention "
            "and natural-looking results."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Eye Candy Lash Studio",
        "slug": "eye-candy-lash-studio-north-coral-gables",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "2424 Ponce De Leon Blvd, Suite 102", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 774-9744",
        "website": "https://eyecandylashstudio.com",
        "instagram": "@eyecandylashstudio_cg",
        "short_description": (
            "A dedicated lash studio on Ponce De Leon Blvd specializing in custom "
            "lash sets — wispy, mega volume, classic, and hybrid — alongside "
            "microblading and brow design for Coral Gables and Brickell clients."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — MIRACLE MILE / DOWNTOWN ────────────────────────────────────
    {
        "name": "Meraki Medical Aesthetics",
        "slug": "meraki-medical-aesthetics-coral-gables-miracle-mile",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "169 Miracle Mile, Suite 206", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 424-7170",
        "website": "https://merakimedaesthetics.com",
        "instagram": "@merakimedaesthetics",
        "short_description": (
            "A boutique medical aesthetics practice on Miracle Mile offering Botox, "
            "dermal fillers, Sculptra, laser treatments, chemical peels, and "
            "HydraFacials — known in the Gables for personalized care and a "
            "natural-results philosophy."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Skin Science Soul",
        "slug": "skin-science-soul-coral-gables-miracle-mile",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "150 Alhambra Cir, Suite 1250", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 448-0083",
        "website": "https://skinscience.com",
        "instagram": "@skinscience_soul",
        "short_description": (
            "A well-established Coral Gables med spa and dermatology-adjacent "
            "practice offering laser resurfacing, IPL, Ultherapy, injectables, "
            "and medical-grade facials — a trusted skin health destination "
            "in the Alhambra business district."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — NORTH CORAL GABLES ─────────────────────────────────────────
    {
        "name": "Aesthetica Med Spa Coral Gables",
        "slug": "aesthetica-med-spa-coral-gables-north",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "2333 Ponce De Leon Blvd, Suite 314", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 448-6111",
        "website": "https://aestheticacoralgables.com",
        "instagram": "@aestheticacoralgables",
        "short_description": (
            "A medically directed aesthetic practice near the University of Miami "
            "health corridor offering injectables, PRP, Morpheus8, body contouring, "
            "and laser skin treatments with strong reviews from a professional clientele."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — MIRACLE MILE / DOWNTOWN ────────────────────────────────────
    {
        "name": "The Barbery Coral Gables",
        "slug": "the-barbery-coral-gables-miracle-mile",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "253 Miracle Mile", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 529-3030",
        "website": "https://thebarbery.com",
        "instagram": "@thebarberycoralgables",
        "short_description": (
            "A premium Coral Gables barbershop on Miracle Mile known for old-school "
            "precision cuts, straight razor shaves, beard sculpting, and a refined "
            "grooming experience that respects both the craft and the client's time."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Gables Classic Barber Shop",
        "slug": "gables-classic-barber-shop-miracle-mile",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "301 Miracle Mile", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 446-2770",
        "website": None,
        "instagram": None,
        "short_description": (
            "A no-frills Miracle Mile barbershop that has been cutting hair in Coral "
            "Gables for decades, earning loyalty through consistent work, reasonable "
            "prices, and the kind of old-school reliability that younger shops market "
            "and rarely deliver."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Arte Barber Studio",
        "slug": "arte-barber-studio-north-coral-gables",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "715 SW 27th Ave", "city": "Miami", "state": "FL", "postal_code": "33135", "country": "US"},
        "phone": "(305) 643-6588",
        "website": None,
        "instagram": "@artebarberstudio",
        "short_description": (
            "A skilled barber studio serving the north Coral Gables/Little Havana "
            "border with precision fades, line-ups, and beard shaping — known "
            "for exacting craft and a loyal bilingual community clientele."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── WAXING — NORTH CORAL GABLES ──────────────────────────────────────────
    {
        "name": "European Wax Center — Coral Gables",
        "slug": "european-wax-center-coral-gables-north",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["north-coral-gables"],
        "address": {"street": "3444 Main Hwy", "city": "Coconut Grove", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 444-4600",
        "website": "https://www.waxcenter.com/locations/fl/coral-gables-coconut-grove",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The Coral Gables/Coconut Grove European Wax Center, offering consistent "
            "comfort-wax services for brows, full-face, and full-body waxing in "
            "a clean, professional, efficiently run studio."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── WAXING — SOUTH CORAL GABLES ──────────────────────────────────────────
    {
        "name": "Wax Poetic Studio",
        "slug": "wax-poetic-studio-south-coral-gables",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["south-coral-gables"],
        "address": {"street": "5701 Sunset Dr, Suite 207", "city": "South Miami", "state": "FL", "postal_code": "33143", "country": "US"},
        "phone": "(786) 360-1147",
        "website": None,
        "instagram": "@waxpoeticstudio",
        "short_description": (
            "A boutique waxing studio in the South Miami/South Coral Gables area "
            "known for careful brow shaping, face and body waxing, and the kind of "
            "attentive technique that keeps clients coming back monthly."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MAKEUP — MIRACLE MILE / DOWNTOWN ─────────────────────────────────────
    {
        "name": "Sonia Roselli Beauty Studio",
        "slug": "sonia-roselli-beauty-studio-miracle-mile",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["miracle-mile"],
        "address": {"street": "358 Alhambra Cir, Suite 100", "city": "Coral Gables", "state": "FL", "postal_code": "33134", "country": "US"},
        "phone": "(305) 444-1900",
        "website": "https://soniaroselli.com",
        "instagram": "@soniarosellibeauty",
        "short_description": (
            "A prestige makeup and beauty studio near Miracle Mile built around the "
            "professional skincare and makeup line by celebrity artist Sonia Roselli — "
            "offering bridal, editorial, and special-event application alongside "
            "product consultations for skin-prep obsessives."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── HAIR — COCONUT GROVE ADJACENT ────────────────────────────────────────
    {
        "name": "Studio 5C Salon",
        "slug": "studio-5c-salon-coconut-grove-adjacent",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["coconut-grove-adjacent"],
        "address": {"street": "3390 Mary St, Suite 120", "city": "Coconut Grove", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 443-5080",
        "website": "https://studio5csalon.com",
        "instagram": "@studio5csalon",
        "short_description": (
            "A boutique salon serving the Coconut Grove/Coral Gables border with "
            "precision cuts, balayage, and Olaplex color treatments — known for "
            "a relaxed, private-suite atmosphere and stylists who prioritize "
            "hair health alongside aesthetics."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — SOUTH CORAL GABLES ─────────────────────────────────────────
    {
        "name": "Soul Aesthetics Medical Spa",
        "slug": "soul-aesthetics-medical-spa-south-coral-gables",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["south-coral-gables"],
        "address": {"street": "7272 SW 87th Ave, Suite 101", "city": "Miami", "state": "FL", "postal_code": "33173", "country": "US"},
        "phone": "(305) 595-1565",
        "website": "https://soulaestheticsspa.com",
        "instagram": "@soulaestheticsspa",
        "short_description": (
            "A physician-led medical spa in the South Coral Gables/Kendall corridor "
            "offering Botox, filler, Sculptra, laser hair removal, CoolSculpting, "
            "and HydraFacials — appreciated for competitive pricing and a "
            "results-focused approach with board-certified oversight."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — COCONUT GROVE ADJACENT ───────────────────────────────────────
    {
        "name": "Le Nails & Spa",
        "slug": "le-nails-and-spa-coconut-grove-adjacent",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["coconut-grove-adjacent"],
        "address": {"street": "3015 Grand Ave", "city": "Coconut Grove", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 461-5080",
        "website": None,
        "instagram": None,
        "short_description": (
            "A well-regarded nail salon in CocoWalk / Coconut Grove, steps from the "
            "Coral Gables border, offering gel manicures, acrylics, dip powder, "
            "and spa pedicures at consistent quality for a loyal neighborhood following."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — SOUTH CORAL GABLES ──────────────────────────────────────────────
    {
        "name": "Azul Body Therapy",
        "slug": "azul-body-therapy-south-coral-gables",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["south-coral-gables"],
        "address": {"street": "8323 SW 124th Ave, Suite 103", "city": "Miami", "state": "FL", "postal_code": "33183", "country": "US"},
        "phone": "(305) 596-3338",
        "website": "https://azulbodytherapy.com",
        "instagram": "@azulbodytherapy",
        "short_description": (
            "A therapeutic massage and body treatment studio serving South Coral "
            "Gables and Kendall clients with deep tissue, Swedish, hot stone, "
            "prenatal, and lymphatic drainage sessions — consistently praised "
            "for skilled therapists and a genuinely restorative environment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_coral_gables() -> None:
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
        "slug": "coral-gables",
        "name": "Coral Gables",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Coral Gables' most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, and nail stylists "
            "Coral Gables locals actually book — from Miracle Mile and the Biltmore "
            "to the quiet streets of South Gables and the Ponce De Leon corridor."
        ),
        "seo_title": "Coral Gables Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Coral Gables, Florida — salons, spas, "
            "lash studios, and nail bars discovered by locals. Covering Miracle Mile, "
            "Coconut Grove adjacent, South Coral Gables, and North Coral Gables."
        ),
        "editorial_headlines": [
            {"headline": "Coral Gables' most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "coral-gables"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: coral-gables (id=%s)" % city_id)

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
        # doesn't lose their work. Same pattern as Boca Raton and FTL seeds.
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
    print("Coral Gables seed complete:")
    print("  City:          coral-gables (id=%s)" % city_id)
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
    await seed_coral_gables()


if __name__ == "__main__":
    run(main())
