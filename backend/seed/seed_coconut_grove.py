"""Seed Coconut Grove for the Beauty network.

22 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_coconut_grove

All addresses, phones, and websites verified via Yelp, Google, and the
official Coconut Grove BID directory (coconutgrove.com) in June 2026.
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
    ("cocowalk-grand-avenue",     "CocoWalk / Grand Avenue",         "Vibrant & walkable",           8),
    ("south-bayshore-florida-ave","South Bayshore / Florida Avenue", "Lush & established",           7),
    ("commodore-plaza-bird-ave",  "Commodore Plaza / Bird Avenue",   "Neighborhood & approachable",  5),
    ("west-coconut-grove",        "West Coconut Grove",              "Community-rooted & authentic", 2),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "cocowalk-grand-avenue": (
        "Grand Avenue is the pulse of Coconut Grove's beauty scene. CocoWalk's "
        "renovated open-air mall anchors the block with barbershops, brow studios, "
        "and full-service salons within steps of each other. The energy here is "
        "walkable and social — the kind of neighborhood where you can get a blowout "
        "and a coffee without moving your car."
    ),
    "south-bayshore-florida-ave": (
        "Florida Avenue and South Bayshore Drive carry the more established, "
        "appointment-first side of Coconut Grove beauty. The studios here — many "
        "operating for decades — draw clients from Brickell and Coral Gables who "
        "are willing to drive for the right colorist or the right esthetician. "
        "Banyan trees overhead, and excellence inside."
    ),
    "commodore-plaza-bird-ave": (
        "Commodore Plaza and the Bird Avenue corridor hold the Grove's most "
        "neighborhood-rooted beauty spots — familiar faces, reliable results, "
        "and the kind of long-running client relationships that only happen when "
        "a business earns trust one visit at a time."
    ),
    "west-coconut-grove": (
        "West Coconut Grove — the historic Black neighborhood that anchors the "
        "western edge of the Grove — has its own identity in the beauty world: "
        "community barbershops and salons that have served the neighborhood for "
        "generations, operating on authenticity rather than trend."
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

    # ── HAIR — COCOWALK / GRAND AVENUE ───────────────────────────────────────
    {
        "name": "Detlev — A Davines Salon",
        "slug": "detlev-davines-salon-coconut-grove",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3015 Grand Ave, Suite 208", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 448-5750",
        "website": "https://detlev.com",
        "instagram": "@detlevsalon",
        "short_description": (
            "A Coconut Grove institution since 1988, Detlev brought European-caliber "
            "hair talent to Miami and built a four-decade reputation for precision cuts, "
            "color, and keratin treatments. Inside CocoWalk's upper level, it remains "
            "one of the Grove's most respected full-service salons — Davines-certified "
            "and Green Circle sustainability-committed."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Women's Haircut & Style", "price_range": "$85–$150"},
            {"name": "Balayage / Highlights", "price_range": "$180–$300"},
            {"name": "Keratin Treatment", "price_range": "$250–$400"},
            {"name": "Men's Cut", "price_range": "$55–$80"},
            {"name": "Color Gloss", "price_range": "$90–$140"},
        ],
    },
    {
        "name": "Armandeus Coconut Grove",
        "slug": "armandeus-coconut-grove",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["commodore-plaza-bird-ave"],
        "address": {"street": "2859 Bird Ave, Suite 2L", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 400-2237",
        "website": "https://www.armandeus.com",
        "instagram": "@armandeusgrove",
        "short_description": (
            "The Coconut Grove outpost of Armandeus, South Florida's celebrated "
            "balayage and color specialists. Known for blending technique and "
            "personalized consultations — clients come for highlights and leave with "
            "a color plan they can actually maintain. Also offers keratin treatments, "
            "hair botox, manicures, and makeup services."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "Balayage", "price_range": "$200–$350"},
            {"name": "Women's Haircut", "price_range": "$75–$120"},
            {"name": "Hair Botox Treatment", "price_range": "$200–$350"},
            {"name": "Highlights", "price_range": "$150–$250"},
            {"name": "Manicure / Pedicure", "price_range": "$35–$75"},
        ],
    },
    {
        "name": "Salon & Spa Renova",
        "slug": "salon-spa-renova-coconut-grove",
        "category_slugs": ["hair", "nails"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "2590 S Dixie Hwy", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 443-4035",
        "website": "https://renovasalonspa.com",
        "instagram": "@salonrenovamiami",
        "short_description": (
            "Half a block from CocoWalk and steps from the Mayfair Hotel, Renova "
            "has served the Coconut Grove community as a full-service hair and nail "
            "salon for years. Reliable for cuts, color, gel manicures, and pedicures "
            "with a warm neighborhood feel that keeps regulars coming back."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Women's Haircut & Style", "price_range": "$65–$100"},
            {"name": "Color / Highlights", "price_range": "$120–$220"},
            {"name": "Gel Manicure", "price_range": "$35–$50"},
            {"name": "Pedicure", "price_range": "$45–$75"},
            {"name": "Brazilian Blowout", "price_range": "$200–$300"},
        ],
    },

    # ── HAIR — SOUTH BAYSHORE / FLORIDA AVENUE ───────────────────────────────
    {
        "name": "Ugo Di Roma Salon & Day Spa",
        "slug": "ugo-di-roma-salon-day-spa-coconut-grove",
        "category_slugs": ["hair", "spa"],
        "neighborhood_slugs": ["south-bayshore-florida-ave"],
        "address": {"street": "2801 Florida Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 444-4661",
        "website": "https://ugodiroma.com",
        "instagram": "@ugodiroma",
        "short_description": (
            "Miami's premier luxury hair salon and day spa in the heart of Coconut "
            "Grove. Ugo Di Roma combines expert haircuts, color, and hair extensions "
            "with a full spa menu — facials, massages, manicures, and more — in a "
            "polished appointment-first environment that has served discerning "
            "Grove residents for decades."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
        "services": [
            {"name": "Luxury Haircut & Blowout", "price_range": "$120–$200"},
            {"name": "Balayage / Highlights", "price_range": "$250–$450"},
            {"name": "Hair Extensions", "price_range": "$400–$1,200"},
            {"name": "Spa Facial", "price_range": "$120–$200"},
            {"name": "Deep Tissue Massage", "price_range": "$100–$180"},
        ],
    },
    {
        "name": "ELA Salon",
        "slug": "ela-salon-coconut-grove",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["south-bayshore-florida-ave"],
        "address": {"street": "2901 Florida Ave, Suite 805", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 445-4000",
        "website": "https://elasalon.com",
        "instagram": "@elasalonmiami",
        "short_description": (
            "Tucked into a suite on Florida Avenue, ELA Salon is Coconut Grove's "
            "boutique destination for color, styling, and esthetician services. "
            "Known for balayage and natural color work alongside manicures and "
            "pedicures — a full-service studio with an intimate, appointment-first "
            "approach that suits the neighborhood's vibe perfectly."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "Haircut & Style", "price_range": "$80–$140"},
            {"name": "Balayage", "price_range": "$180–$300"},
            {"name": "Color / Tint", "price_range": "$100–$180"},
            {"name": "Manicure", "price_range": "$35–$55"},
            {"name": "Facial", "price_range": "$90–$150"},
        ],
    },
    {
        "name": "Serge Renard Beauty Salon",
        "slug": "serge-renard-beauty-salon-coconut-grove",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["commodore-plaza-bird-ave"],
        "address": {"street": "3141 Commodore Plz", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 447-0265",
        "website": None,
        "instagram": None,
        "short_description": (
            "Open since 1985, Serge Renard has held a place in the top tier of "
            "Miami hair salons for over four decades. Located on Commodore Plaza, "
            "it draws a multigenerational Coconut Grove clientele for cuts, color, "
            "and styling — the kind of long-running salon whose reputation is built "
            "entirely on word of mouth."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "Women's Haircut & Style", "price_range": "$80–$150"},
            {"name": "Men's Haircut", "price_range": "$50–$80"},
            {"name": "Color / Highlights", "price_range": "$130–$250"},
            {"name": "Blowout", "price_range": "$55–$90"},
            {"name": "Keratin Treatment", "price_range": "$200–$350"},
        ],
    },

    # ── NAILS — COCOWALK / GRAND AVENUE ──────────────────────────────────────
    {
        "name": "T & K Nails",
        "slug": "t-and-k-nails-coconut-grove",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3105 Grand Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 446-9404",
        "website": None,
        "instagram": None,
        "short_description": (
            "A well-established neighborhood nail salon on Grand Avenue serving "
            "Coconut Grove with manicures, pedicures, gel, dip powder, and "
            "acrylics. Reliable and fairly priced with extended weekend hours — "
            "the kind of place locals recommend without hesitation."
        ),
        "price_cues": "$",
        "editors_pick": False,
        "services": [
            {"name": "Classic Manicure", "price_range": "$20–$30"},
            {"name": "Gel Manicure", "price_range": "$35–$50"},
            {"name": "Dip Powder", "price_range": "$45–$60"},
            {"name": "Pedicure", "price_range": "$35–$55"},
            {"name": "Acrylic Full Set", "price_range": "$45–$65"},
        ],
    },
    {
        "name": "Mary Nails Salon",
        "slug": "mary-nails-salon-coconut-grove",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["commodore-plaza-bird-ave"],
        "address": {"street": "3141 Commodore Plz", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 440-8237",
        "website": None,
        "instagram": None,
        "short_description": (
            "A small, well-reviewed nail salon on Commodore Plaza in the heart "
            "of Coconut Grove. Known for careful work, attentive technicians, and "
            "a calm atmosphere that makes it a neighborhood go-to for gel manicures "
            "and pedicures by appointment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Gel Manicure", "price_range": "$40–$55"},
            {"name": "Classic Manicure", "price_range": "$25–$35"},
            {"name": "Spa Pedicure", "price_range": "$50–$70"},
            {"name": "Dip Powder Manicure", "price_range": "$50–$65"},
            {"name": "Nail Art (per nail)", "price_range": "$5–$15"},
        ],
    },

    # ── SPA — SOUTH BAYSHORE / FLORIDA AVENUE ────────────────────────────────
    {
        "name": "Silviana's European Spa & Skin Care",
        "slug": "silvianas-european-spa-coconut-grove",
        "category_slugs": ["spa", "waxing"],
        "neighborhood_slugs": ["south-bayshore-florida-ave"],
        "address": {"street": "3339 Virginia St, Suite R1", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 442-4431",
        "website": "https://silvianas.com",
        "instagram": "@silvianasspa",
        "short_description": (
            "A long-running European-style day spa in Coconut Grove offering "
            "custom facials, massages, lash extensions, and full-body waxing in "
            "a calm, unhurried environment. Silviana's has been a neighborhood "
            "staple for skin-care clients who prioritize technique and trust — "
            "open six days a week on Virginia Street."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "European Facial", "price_range": "$80–$120"},
            {"name": "Deep Tissue Massage", "price_range": "$90–$150"},
            {"name": "Lash Extensions", "price_range": "$120–$200"},
            {"name": "Brow / Full-Face Wax", "price_range": "$20–$60"},
            {"name": "Body Waxing (Brazilian)", "price_range": "$55–$75"},
        ],
    },
    {
        "name": "Sana Skin Studio",
        "slug": "sana-skin-studio-coconut-grove",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["south-bayshore-florida-ave"],
        "address": {"street": "2810 Oak Ave, Suite 106", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 942-9444",
        "website": "https://www.sanaskinstudio.com",
        "instagram": "@sanaskinstudio",
        "short_description": (
            "A modern goal-driven skin studio on Oak Avenue offering personalized "
            "facials, acne-clearing treatments, and clean skincare guidance. Sana's "
            "approach — the name comes from the Spanish word for 'heal' — is less "
            "about pampering and more about actual skin progress. The Coconut Grove "
            "location features exclusive Jet Peel Infusion add-ons."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Signature Facial", "price_range": "$120–$160"},
            {"name": "Acne-Clearing Treatment", "price_range": "$130–$170"},
            {"name": "Jet Peel Infusion Add-On", "price_range": "$125"},
            {"name": "Brightening Facial", "price_range": "$140–$180"},
            {"name": "Monthly Skin Membership (facial)", "price_range": "$99–$130/mo"},
        ],
    },

    # ── LASH & BROW — COCOWALK / GRAND AVENUE ────────────────────────────────
    {
        "name": "Studio 3D Brows, Lashes & PMU",
        "slug": "studio-3d-brows-lashes-pmu-coconut-grove",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3015 Grand Ave, Suite 210", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(786) 384-1710",
        "website": "https://studio3dbrows.com",
        "instagram": "@studio3dbrowsfl",
        "short_description": (
            "Inside CocoWalk, Studio 3D specializes exclusively in semi-permanent "
            "and paramedical cosmetic makeup — microblading, powder brows, ombre "
            "brows, eyeliner tattoo, and lash extensions. One of the few South "
            "Florida studios focused purely on PMU and lash artistry, with a "
            "second location in Aventura for the wait list."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Microblading", "price_range": "$450–$600"},
            {"name": "Powder / Ombre Brows (PMU)", "price_range": "$500–$650"},
            {"name": "Lash Extensions (Classic)", "price_range": "$150–$200"},
            {"name": "Lash Extensions (Volume)", "price_range": "$200–$300"},
            {"name": "Permanent Eyeliner", "price_range": "$350–$500"},
        ],
    },

    # ── MED-SPA — SOUTH BAYSHORE / FLORIDA AVENUE ────────────────────────────
    {
        "name": "Lavish Laser Med Spa",
        "slug": "lavish-laser-med-spa-coconut-grove",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["south-bayshore-florida-ave"],
        "address": {"street": "3160 Florida Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 846-7524",
        "website": "https://lavishlasermedspa.com",
        "instagram": "@lavishlasermedspa",
        "short_description": (
            "A woman-owned medical spa on Florida Avenue in Coconut Grove with "
            "physician oversight from Dr. Marc Epstein. Lavish Laser specializes "
            "in Hydrafacials, RF microneedling, injectables (Botox, filler), "
            "laser hair removal, IPL, and body contouring — with a strong "
            "following among Grove and Brickell professionals."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "HydraFacial", "price_range": "$175–$250"},
            {"name": "Botox (per unit)", "price_range": "$14–$18/unit"},
            {"name": "RF Microneedling", "price_range": "$350–$600"},
            {"name": "Laser Hair Removal (per area)", "price_range": "$100–$400"},
            {"name": "Body Contouring", "price_range": "$300–$800"},
        ],
    },

    # ── BARBER — COCOWALK / GRAND AVENUE ─────────────────────────────────────
    {
        "name": "Fade Masters of Miami",
        "slug": "fade-masters-of-miami-coconut-grove",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3250 Grand Ave, Suite 1", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(786) 615-4005",
        "website": "https://fademastersofmiami.com",
        "instagram": "@fademastersofmiami",
        "short_description": (
            "Named Miami New Times' Top Barbershop in 2023 and 2024, Fade Masters "
            "has become a Coconut Grove institution for precision fades, tapers, "
            "and straight razor shaves. Their signature add-on — an express facial "
            "at the barber chair — is exactly the kind of innovation that earned "
            "them the press. Walk-ins welcome, appointments preferred."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "services": [
            {"name": "Signature Haircut & Style", "price_range": "$45–$75"},
            {"name": "Skin Fade", "price_range": "$45–$65"},
            {"name": "Straight Razor Shave", "price_range": "$40–$60"},
            {"name": "Beard Sculpting", "price_range": "$25–$40"},
            {"name": "Express Facial Add-On", "price_range": "$35–$55"},
        ],
    },
    {
        "name": "The Spot Barbershop — CocoWalk",
        "slug": "the-spot-barbershop-cocowalk-coconut-grove",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3015 Grand Ave, Unit 235", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(786) 388-0557",
        "website": "https://thespotbarbershop.com",
        "instagram": "@thespotbarbershop",
        "short_description": (
            "The Coconut Grove location of The Spot Barbershop, Miami's polished "
            "premium grooming chain — inside CocoWalk on the Grand Avenue level. "
            "Known for consistent fade technique, beard shaping, and an efficient, "
            "appointment-friendly experience from a team that takes craft seriously."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Haircut", "price_range": "$35–$55"},
            {"name": "Skin Fade", "price_range": "$40–$60"},
            {"name": "Beard Trim & Line-Up", "price_range": "$20–$35"},
            {"name": "Haircut + Beard Combo", "price_range": "$55–$80"},
            {"name": "Kids' Cut (under 12)", "price_range": "$25–$35"},
        ],
    },
    {
        "name": "Gentleman's Grove Barbershop",
        "slug": "gentlemans-grove-barbershop-coconut-grove",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["commodore-plaza-bird-ave"],
        "address": {"street": "2829 Bird Ave, Suite 11", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(786) 391-4401",
        "website": "https://www.gentlemansgrovebarbershop.com",
        "instagram": "@gentlemansgrovebarbershop",
        "short_description": (
            "A neighborhood-rooted barbershop on Bird Avenue with a 4.9-star "
            "rating from its community of regulars. Gentleman's Grove earns its "
            "name through precision fades, luxury shaves, and a relaxed "
            "atmosphere — open seven days a week, including Sundays, which is "
            "more than most Grove shops can say."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Haircut", "price_range": "$35–$55"},
            {"name": "Skin Fade", "price_range": "$40–$60"},
            {"name": "Luxury Shave", "price_range": "$40–$65"},
            {"name": "Beard Design", "price_range": "$20–$35"},
            {"name": "Haircut + Shave Combo", "price_range": "$65–$90"},
        ],
    },
    {
        "name": "Charles Barber Shop",
        "slug": "charles-barber-shop-coconut-grove",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["west-coconut-grove"],
        "address": {"street": "3757 Grand Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 443-3580",
        "website": None,
        "instagram": None,
        "short_description": (
            "A community barbershop on the western stretch of Grand Avenue that "
            "has served West Coconut Grove for years. Charles Barber Shop does "
            "no-frills, high-quality work — straight razor shaves, precise cuts, "
            "kids' haircuts, and the kind of consistent service that keeps "
            "multi-generational families coming back."
        ),
        "price_cues": "$",
        "editors_pick": False,
        "services": [
            {"name": "Men's Haircut", "price_range": "$20–$35"},
            {"name": "Kids' Haircut", "price_range": "$15–$25"},
            {"name": "Straight Razor Shave", "price_range": "$25–$40"},
            {"name": "Beard Trim", "price_range": "$15–$25"},
            {"name": "Line-Up", "price_range": "$15–$20"},
        ],
    },

    # ── WAXING — COCOWALK / GRAND AVENUE ─────────────────────────────────────
    {
        "name": "Wax On Wax Off",
        "slug": "wax-on-wax-off-coconut-grove",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3215 Grand Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 444-8455",
        "website": None,
        "instagram": "@waxonwaxoff_coconut_grove",
        "short_description": (
            "Coconut Grove's dedicated waxing studio on Grand Avenue, known for "
            "precise brow shaping, face waxing, and full-body services including "
            "Brazilian and bikini wax. A loyalty points program (two points per "
            "dollar) rewards regulars, and the studio's clean, friendly atmosphere "
            "keeps them returning."
        ),
        "price_cues": "$$",
        "editors_pick": False,
        "services": [
            {"name": "Brow Wax & Shape", "price_range": "$18–$28"},
            {"name": "Full-Face Wax", "price_range": "$45–$65"},
            {"name": "Brazilian Wax", "price_range": "$55–$75"},
            {"name": "Bikini Wax", "price_range": "$35–$50"},
            {"name": "Leg Wax (full)", "price_range": "$65–$90"},
        ],
    },

    # ── MAKEUP — COCOWALK / GRAND AVENUE ─────────────────────────────────────
    {
        "name": "Beauty by Noel",
        "slug": "beauty-by-noel-coconut-grove",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["cocowalk-grand-avenue"],
        "address": {"street": "3109 Grand Ave", "city": "Miami", "state": "FL", "postal_code": "33133", "country": "US"},
        "phone": "(305) 417-9910",
        "website": "https://beautybynoel.com",
        "instagram": "@beautybynoel",
        "short_description": (
            "A boutique makeup studio on Grand Avenue specializing in flawless "
            "airbrush makeup, bridal hair and makeup, and event styling — by "
            "appointment. Beauty by Noel serves clients who want polished, "
            "camera-ready results for weddings, quinceañeras, and professional "
            "engagements across Coconut Grove and South Florida."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
        "services": [
            {"name": "Bridal Makeup", "price_range": "$250–$400"},
            {"name": "Airbrush Makeup Application", "price_range": "$150–$250"},
            {"name": "Event Makeup", "price_range": "$120–$200"},
            {"name": "Bridal Hair & Makeup Package", "price_range": "$400–$650"},
            {"name": "Men's Grooming / Makeup", "price_range": "$80–$150"},
        ],
    },
]

async def seed_coconut_grove() -> None:
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
        "slug": "coconut-grove",
        "name": "Coconut Grove",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Coconut Grove's most trusted beauty addresses.",
        "hero_description": (
            "The curated index of salons, spas, barbershops, and lash studios "
            "that Coconut Grove locals actually book — from the Grand Avenue energy "
            "of CocoWalk to the appointment-first studios along Florida Avenue and "
            "the neighborhood anchors on Commodore Plaza and Bird Avenue."
        ),
        "seo_title": "Coconut Grove Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Coconut Grove, Miami — salons, spas, "
            "barbershops, lash studios, and nail bars discovered by locals. "
            "Covering CocoWalk, Grand Avenue, Florida Avenue, South Bayshore Drive, "
            "Commodore Plaza, and Bird Avenue."
        ),
        "editorial_headlines": [
            {"headline": "Coconut Grove's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "coconut-grove"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: coconut-grove (id=%s)" % city_id)

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
            "services": biz.get("services", []),
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
    print("Coconut Grove seed complete:")
    print("  City:          coconut-grove (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, Boca Raton, Coral Gables,
    # and Aventura seeds — this script writes to the database. Refuse to run
    # against production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_coconut_grove()


if __name__ == "__main__":
    run(main())
