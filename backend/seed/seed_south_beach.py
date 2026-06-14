"""Seed South Beach for the Beauty network.

20 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_south_beach
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
    ("ocean-drive-collins",  "Ocean Drive / Collins Ave",      "Art Deco & oceanfront",        5),
    ("lincoln-road-alton",   "Lincoln Road / Alton Road",      "Shopping & local staples",     8),
    ("espanola-way-mid",     "Española Way / Mid-Beach",       "Bohemian & residential",       4),
    ("south-of-fifth-sofi",  "South of Fifth / SoFi",          "Quiet & upscale",              3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "ocean-drive-collins": (
        "Ocean Drive and the Collins Avenue corridor are what the world pictures when it "
        "pictures Miami Beach — the Art Deco hotels, the ocean light, the relentless "
        "energy. The beauty businesses that survive here do so because they're exceptional: "
        "hotel spas with international reputations, storied salons that predate the "
        "neighborhood's latest reinvention, and destination names that draw clients from "
        "across South Florida and beyond."
    ),
    "lincoln-road-alton": (
        "Lincoln Road is South Beach's living room — a pedestrian mall lined with palms "
        "and packed with locals, visitors, and professionals who live within walking "
        "distance. Alton Road runs parallel, quieter and more neighborhood-facing, home "
        "to the nail bars and hair studios that serve the actual residents of the zip code. "
        "Together they hold the deepest concentration of beauty services on the island."
    ),
    "espanola-way-mid": (
        "Española Way's cobblestoned Mediterranean-revival block was built in 1925 as an "
        "artists' colony and has kept a bohemian spirit ever since. The stretch north "
        "toward Arthur Godfrey Road is more residential, with longtime studios that rely "
        "on word-of-mouth rather than foot traffic. This is where Miami Beach's beauty "
        "professionals come to work without the chaos of the tourist core."
    ),
    "south-of-fifth-sofi": (
        "South of Fifth Street — SoFi to everyone who lives there — is the quietest and "
        "most affluent corner of Miami Beach. The streets are leafy, the buildings are "
        "newer, and the handful of beauty studios that operate here serve a clientele "
        "that drives in deliberately, not by accident. Expect precision, privacy, and "
        "the kind of unhurried attention that the busier corridors rarely afford."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — LINCOLN ROAD / ALTON ROAD ─────────────────────────────────────
    {
        "name": "Danny Jelaca Salon",
        "slug": "danny-jelaca-salon-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["south-of-fifth-sofi"],
        "address": {"street": "300 Alton Rd, Suite 100A", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 604-9696",
        "website": "https://dannyjelaca.com",
        "instagram": "@dannyjelacasalon",
        "short_description": (
            "One of South Beach's most celebrated salons, founded by award-winning "
            "stylist Danny Jelaca at the Miami Beach Marina. Known for over two decades "
            "of impeccable color, cuts, and hair wellness treatments that have earned "
            "a devoted following across South Florida and beyond."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Valerio Perfetti Hair Salon",
        "slug": "valerio-perfetti-hair-salon-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1239 Alton Rd, Suite 5", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": "https://valerioperfetti.com",
        "instagram": "@valerioperfetti",
        "short_description": (
            "A boutique Italian hair salon on Alton Road with a loyal South Beach "
            "clientele and consistently top-rated reviews. Specializes in precision "
            "cuts, lived-in color, and balayage techniques with a European touch that "
            "stands out in a crowded market."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Kaan Hair Design Miami",
        "slug": "kaan-hair-design-miami-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1800 Bay Rd, Suite 101", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 536-2444",
        "website": "https://kaanhairdesign.com",
        "instagram": "@kaansevinch",
        "short_description": (
            "A highly rated boutique salon on Bay Road serving the Alton Road "
            "neighborhood with precision cuts, color, balayage, and Brazilian blowouts. "
            "Praised across multiple platforms for technique, consultation, and the "
            "kind of consistent results that build a loyal repeat clientele."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — OCEAN DRIVE / COLLINS AVE ─────────────────────────────────────
    {
        "name": "Rossano Ferretti — Faena Hotel",
        "slug": "rossano-ferretti-faena-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "3201 Collins Ave, 3rd Floor", "city": "Miami Beach", "state": "FL", "postal_code": "33140", "country": "US"},
        "phone": "(786) 877-7306",
        "website": "https://rossanoferretti.com/our-salons/miami-faena-hotel-salon",
        "instagram": "@rossanoferretti",
        "short_description": (
            "The only Miami outpost of world-renowned Italian master stylist Rossano "
            "Ferretti, located inside the iconic Faena Hotel on Collins Avenue. "
            "Known for his signature 'Method' cutting technique — heralded as one of "
            "the most important hairstyling innovations of the past 40 years."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },

    # ── HAIR — ESPAÑOLA WAY / MID-BEACH ──────────────────────────────────────
    {
        "name": "Italian Concept Hair Salon — Johnny Almagno",
        "slug": "italian-concept-hair-salon-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["espanola-way-mid"],
        "address": {"street": "227 9th St", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": "@johnnyalmagno",
        "short_description": (
            "Stylist Johnny Almagno brings Italian elegance to South Beach with "
            "precision cuts, sophisticated color, and expert styling — all using "
            "100% Made-in-Italy professional products. A boutique studio that earns "
            "consistent five-star reviews for personalized, unhurried service."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — LINCOLN ROAD / ALTON ROAD ────────────────────────────────────
    {
        "name": "Sky Nails & Spa of South Beach",
        "slug": "sky-nails-spa-south-beach",
        "category_slugs": ["nails", "waxing"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1611 Alton Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 275-6666",
        "website": "https://skynailsofsouthbeach.com",
        "instagram": "@skynailssouthbeach",
        "short_description": (
            "A full-service nail and spa destination on Alton Road with over 300 "
            "Yelp reviews and a loyal local following. Offers manicures, pedicures, "
            "gel, acrylics, eyelash extensions, waxing, facials, and massage — "
            "one of the Lincoln Road area's most consistently praised nail studios."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Sobe Nails & Spa",
        "slug": "sobe-nails-and-spa-south-beach",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1650 Alton Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 534-2998",
        "website": "https://sobenailspamiamibeach.com",
        "instagram": "@sobenailsspa",
        "short_description": (
            "A well-established neighborhood nail salon on Alton Road with nearly "
            "200 reviews and a well-earned reputation for consistent quality. Specializes "
            "in gel manicures, dip powder, nail art, and pedicures with a clean, "
            "professional environment that keeps South Beach locals coming back."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "McAllister Spa",
        "slug": "mcallister-spa-south-beach",
        "category_slugs": ["hair", "nails", "spa", "waxing", "lash-brow"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1301 Alton Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 604-0550",
        "website": "https://spamiamibeach.com",
        "instagram": "@mcallisterspa",
        "short_description": (
            "South Beach's most comprehensive full-service beauty destination, voted "
            "Best Salon and Best Nail Salon in Miami Beach. Steps from Lincoln Road, "
            "McAllister houses a Goldwell hair salon, nail salon, esthetic suite, "
            "eyelash bar, barbershop, and waxing services under one roof."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },

    # ── SPA — OCEAN DRIVE / COLLINS AVE ──────────────────────────────────────
    {
        "name": "The Ritz-Carlton Spa, South Beach",
        "slug": "ritz-carlton-spa-south-beach",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "1 Lincoln Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 276-4090",
        "website": "https://ritzcarlton.com/en/hotels/miasb-the-ritz-carlton-south-beach/spa",
        "instagram": "@ritzcarltonmiamib",
        "short_description": (
            "A landmark oceanfront spa at the Ritz-Carlton South Beach, known for "
            "Miami-inspired treatments including the signature 'Miami Glow' exfoliation "
            "and wrap, hot stone massage, and custom facials — delivered with the "
            "white-glove service expected of the Ritz brand, steps from the Atlantic."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "K'alma Spa at Hotel Victor",
        "slug": "kalma-spa-hotel-victor-south-beach",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "1144 Ocean Dr", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": "https://kalmaspas.com/victor-hotel",
        "instagram": "@kalmaspas",
        "short_description": (
            "A luxury spa on Ocean Drive in the historic Hotel Victor, offering "
            "massages, facials, and body treatments alongside amenities including a "
            "couples suite, hamam, co-ed sauna, steam room, and a meditation room "
            "that provides genuine escape from the Ocean Drive energy outside."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — LINCOLN ROAD / ALTON ROAD ──────────────────────────────────────
    {
        "name": "Bamford Wellness Spa at 1 Hotel South Beach",
        "slug": "bamford-wellness-spa-1-hotel-south-beach",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "2341 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 604-6792",
        "website": "https://1hotels.com/south-beach/do/bamford-wellness-spa",
        "instagram": "@bamfordwellness",
        "short_description": (
            "The first U.S. location of the celebrated British Bamford Wellness Spa, "
            "housed inside the sustainably-minded 1 Hotel South Beach. Offers holistic "
            "treatments using organic and natural formulations — from lymphatic drainage "
            "and reflexology to signature body rituals and ocean-view massages."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── SPA — ESPAÑOLA WAY / MID-BEACH ───────────────────────────────────────
    {
        "name": "The Standard Spa, Miami Beach",
        "slug": "the-standard-spa-miami-beach",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["espanola-way-mid"],
        "address": {"street": "40 Island Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": "https://standardhotels.com/miami/properties/miami-beach",
        "instagram": "@standardmiami",
        "short_description": (
            "A beloved South Beach institution on Belle Isle in Biscayne Bay — "
            "less a hotel than an adults-only wellness playground. The Standard's spa "
            "campus includes mud baths, a hammam, a cold plunge, rooftop sundeck, and "
            "an unhurried ethos that has made it a local favorite for over two decades."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── LASH & BROW — ESPAÑOLA WAY / MID-BEACH ───────────────────────────────
    {
        "name": "Sultry Eyes Lash Studio",
        "slug": "sultry-eyes-lash-studio-south-beach",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["espanola-way-mid"],
        "address": {"street": "820 Arthur Godfrey Rd, Suite 308", "city": "Miami Beach", "state": "FL", "postal_code": "33140", "country": "US"},
        "phone": "(305) 535-6887",
        "website": "https://sultryeyeslashstudio.com",
        "instagram": "@sultryeyeslashstudio",
        "short_description": (
            "A Miami Beach institution for lash and brow services since 2007 — one of "
            "the longest-running lash studios in South Florida. Known for Xtreme Lashes "
            "extensions, lash lifts, lash and brow tinting, and brow threading in a "
            "calm, spa-like environment praised across hundreds of reviews."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — LINCOLN ROAD / ALTON ROAD ──────────────────────────────
    {
        "name": "Face Card Miami",
        "slug": "face-card-miami-south-beach",
        "category_slugs": ["lash-brow", "makeup"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1400 Alton Rd, Suite 101", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": "https://facecardmiami.com",
        "instagram": "@facecardmiami",
        "short_description": (
            "A premier South Beach beauty studio on Alton Road offering luxury lash "
            "extensions, brow lamination and design, facials, chemical peels, permanent "
            "makeup, and airbrush services. Known for combining multiple treatments "
            "into efficient combo appointments with high-quality results."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — SOUTH OF FIFTH / SOFI ──────────────────────────────────────
    {
        "name": "South Florida Face and Body",
        "slug": "south-florida-face-and-body-sofi",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["south-of-fifth-sofi"],
        "address": {"street": "1000 5th St", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": "https://southfloridafaceandbody.com",
        "instagram": "@southfloridafaceandbody",
        "short_description": (
            "A boutique owner-operated medical aesthetics and functional medicine "
            "practice in SoFi, founded by board-certified nurse practitioner Kelly "
            "Wolfe, FNP-BC. Specializes in Botox, dermal fillers, microneedling, "
            "Kybella, and integrative wellness for a personalized, unhurried experience."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — OCEAN DRIVE / COLLINS AVE ──────────────────────────────────
    {
        "name": "GlowVita Med Spa",
        "slug": "glowvita-med-spa-south-beach",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "110 Washington Ave, Suite CU-7", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 767-6023",
        "website": "https://glowvitamedspa.com",
        "instagram": "@glowvitamedspa",
        "short_description": (
            "A South Beach medical spa on Washington Avenue offering Botox, cosmetic "
            "fillers, PRP, laser treatments, hormone replacement therapy, and IV "
            "wellness therapy. Known for a clinical approach to aesthetic care "
            "with results-driven protocols and transparent pricing."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — LINCOLN ROAD / ALTON ROAD ───────────────────────────────────
    {
        "name": "The Spot Barbershop — South Beach",
        "slug": "the-spot-barbershop-south-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1000 17th St, Unit 1-B", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 485-2250",
        "website": "https://thespotbarbershop.com/locations/south-beach",
        "instagram": "@thespotbarbershop",
        "short_description": (
            "The South Beach location of a well-regarded Miami grooming chain, offering "
            "precision haircuts, fades, beard sculpting, and straight razor shaves in "
            "a sleek contemporary space near Lincoln Road. Open six days a week with "
            "early hours that work for professionals and early risers alike."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── BARBER — ESPANOLA WAY / MID-BEACH ────────────────────────────────────
    {
        "name": "McAllister Spa Barbershop",
        "slug": "mcallister-spa-barbershop-south-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1301 Alton Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 604-0550",
        "website": "https://spamiamibeach.com/products/barber-shop",
        "instagram": "@mcallisterspa",
        "short_description": (
            "The barbershop inside the acclaimed McAllister Spa complex — voted Best "
            "Barber Shop in Miami and South Beach. Offers classic cuts, fades, beard "
            "shaping, and hot-towel shaves within a full-service beauty destination "
            "that gives it a polish most standalone shops can't match."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── WAXING — LINCOLN ROAD / ALTON ROAD ───────────────────────────────────
    {
        "name": "South Beach Body Waxing Company",
        "slug": "south-beach-body-waxing-company",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1521 Alton Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": "@southbeachwaxing",
        "short_description": (
            "A dedicated waxing studio on Alton Road with a strong TripAdvisor "
            "reputation, specializing in body and face waxing services for both "
            "men and women. Known for a clean, efficient, and judgment-free "
            "environment that has earned repeat clients across South Beach."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MAKEUP — SOUTH OF FIFTH / SOFI ────────────────────────────────────────
    {
        "name": "Browmetrics",
        "slug": "browmetrics-south-beach",
        "category_slugs": ["makeup", "lash-brow"],
        "neighborhood_slugs": ["south-of-fifth-sofi"],
        "address": {"street": "900 SW 1st St, Suite 210", "city": "Miami", "state": "FL", "postal_code": "33130", "country": "US"},
        "phone": None,
        "website": "https://browmetrics.com",
        "instagram": "@browmetrics",
        "short_description": (
            "Led by PMU Master Artist Yadi Martinez, Browmetrics is a permanent makeup "
            "studio focused on beauty symmetry and precision — specializing in ombre "
            "powder brows, microblading, lip blush, and lash-line enhancement for "
            "natural, long-lasting results that complement South Beach's sun-drenched lifestyle."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — OCEAN DRIVE / COLLINS AVE ─────────────────────────────────────
    {
        "name": "Salon Ramses",
        "slug": "salon-ramses-south-beach",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "650 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 538-8300",
        "website": None,
        "instagram": "@salonramses",
        "short_description": (
            "A South Beach veteran on Collins Avenue with decades of history in the "
            "neighborhood, offering cuts, color, highlights, and blowouts for both men "
            "and women. Known for dependable, no-fuss service and a loyal local clientele "
            "that has kept the salon busy through multiple waves of Miami Beach reinvention."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — OCEAN DRIVE / COLLINS AVE ────────────────────────────────────
    {
        "name": "Nails at the Setai",
        "slug": "nails-at-the-setai-south-beach",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "2001 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 520-6900",
        "website": "https://thesetaihotel.com/spa-and-wellness/spa",
        "instagram": "@thesetaihotel",
        "short_description": (
            "The nail and spa services at The Setai's award-winning spa offer some of "
            "the most refined manicure and pedicure experiences on South Beach — "
            "performed in an atmosphere of hushed Asian-inspired elegance with top-tier "
            "products and practitioners, inside one of Collins Avenue's most prestigious hotels."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── WAXING — ESPAÑOLA WAY / MID-BEACH ────────────────────────────────────
    {
        "name": "European Wax Center — Miami Beach",
        "slug": "european-wax-center-miami-beach-espanola",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["espanola-way-mid"],
        "address": {"street": "757 Arthur Godfrey Rd", "city": "Miami Beach", "state": "FL", "postal_code": "33140", "country": "US"},
        "phone": "(305) 397-8770",
        "website": "https://waxcenter.com/locations/miami-beach-fl",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The Miami Beach location of the national wax-specialist chain, situated on "
            "Arthur Godfrey Road in the Mid-Beach residential corridor. Offers full-body "
            "waxing for men and women using their proprietary Comfort Wax formula, with "
            "consistent technique and online booking that appeals to busy South Beach locals."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── BARBER — OCEAN DRIVE / COLLINS AVE ───────────────────────────────────
    {
        "name": "Art Deco Barbershop",
        "slug": "art-deco-barbershop-south-beach",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["ocean-drive-collins"],
        "address": {"street": "820 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(305) 672-4247",
        "website": None,
        "instagram": None,
        "short_description": (
            "A no-frills classic barbershop in the heart of South Beach's Art Deco "
            "Historic District, offering straight-razor shaves, traditional cuts, and "
            "beard trims at honest prices. A grounding counterpoint to the flashier "
            "salons on the strip, frequented by both locals and hotel guests since the 1990s."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── MED-SPA — LINCOLN ROAD / ALTON ROAD ──────────────────────────────────
    {
        "name": "Skin Laundry — South Beach",
        "slug": "skin-laundry-south-beach-lincoln",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["lincoln-road-alton"],
        "address": {"street": "1601 Collins Ave", "city": "Miami Beach", "state": "FL", "postal_code": "33139", "country": "US"},
        "phone": "(786) 664-0920",
        "website": "https://skinlaundry.com/locations/south-beach",
        "instagram": "@skinlaundry",
        "short_description": (
            "The South Beach outpost of the cult-favorite laser facial brand, offering "
            "their signature 15-minute Laser & Light Facial alongside microdermabrasion, "
            "chemical peels, LED therapy, and Hydrafacials. Beloved for making clinical "
            "skin treatments fast, accessible, and affordable without sacrificing results."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_south_beach() -> None:
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
        "slug": "south-beach",
        "name": "South Beach",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "South Beach's most trusted beauty addresses.",
        "hero_description": (
            "An index of the stylists, estheticians, lash artists, and nail techs "
            "that South Beach locals actually book — from Ocean Drive and the Faena "
            "to the Lincoln Road corridor, Española Way, and the quiet streets of "
            "South of Fifth."
        ),
        "seo_title": "South Beach Knows Beauty",
        "meta_description": (
            "The curated beauty directory for South Beach, Miami Beach, Florida — "
            "salons, spas, lash studios, and nail bars discovered by locals. Covering "
            "Ocean Drive, Lincoln Road, Española Way, and South of Fifth."
        ),
        "editorial_headlines": [
            {"headline": "South Beach's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "south-beach"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: south-beach (id=%s)" % city_id)

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
        # doesn't lose their work. Same pattern as Coral Gables and FTL seeds.
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
    print("South Beach seed complete:")
    print("  City:          south-beach (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, Coral Gables, and Boca
    # Raton seeds — this script writes to the database. Refuse to run against
    # production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_south_beach()


if __name__ == "__main__":
    run(main())
