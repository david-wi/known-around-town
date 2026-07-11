"""Seed Wynwood for the Beauty network.

18 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_wynwood
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
    ("nw-2nd-ave-wynwood-walls",  "NW 2nd Ave / Wynwood Walls",       "The heart of the arts district",     5),
    ("nw-25th-29th-corridor",     "NW 25th–29th Street Corridor",     "Deep Wynwood, studio-dense",         5),
    ("midtown-edge-district",     "Midtown / Edge District",          "NE 2nd Ave corridor, design-forward",5),
    ("buena-vista",               "Buena Vista",                      "Residential & quietly creative",     3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "nw-2nd-ave-wynwood-walls": (
        "The stretch of NW 2nd Ave below the Wynwood Walls is where the neighborhood's "
        "creative energy concentrates most visibly — murals on every block, galleries "
        "next to beauty studios, and a clientele that treats their hair color as "
        "seriously as the art on the walls outside. The salons here are the ones that "
        "understood Wynwood before Wynwood became a brand."
    ),
    "nw-25th-29th-corridor": (
        "The blocks between NW 25th and NW 29th Street are Wynwood's working interior — "
        "less tourist-facing than the walls, more studio and workshop. Beauty businesses "
        "here serve the people who actually live and work in the neighborhood: tattoo "
        "artists, photographers, DJs, and designers who want sharp fades and nail art "
        "without the wait."
    ),
    "midtown-edge-district": (
        "NE 2nd Ave from about 30th to 42nd Street is the Midtown corridor — where "
        "Wynwood's energy bleeds north into the Design District. The beauty landscape "
        "here is denser and more polished: flagship salons, precision barbershops, "
        "and nail studios that have built strong reputations with Miami's creative "
        "professional class."
    ),
    "buena-vista": (
        "East of N Miami Ave and north of Wynwood proper, Buena Vista is a tree-lined "
        "residential neighborhood that has quietly absorbed some of the area's most "
        "interesting smaller studios. Less foot traffic, more word-of-mouth — the "
        "beauty spots here earn loyalty through craft, not location."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — NW 2ND AVE / WYNWOOD WALLS ────────────────────────────────────
    {
        "name": "Stubborn Hair",
        "slug": "stubborn-hair-wynwood-walls",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["nw-2nd-ave-wynwood-walls"],
        "address": {"street": "2700 N Miami Ave, Unit 701", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 457-8272",
        "website": "https://www.stubbornhair.com",
        "instagram": "@stubbornhairmiami",
        "short_description": (
            "A Goldwell Master Colorist salon in the heart of Wynwood specializing in "
            "bold, high-shine color work — bright fashion shades, precision balayage, "
            "and edgy cuts for a clientele that treats their hair as a form of self-expression."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Wynwood Hair Co.",
        "slug": "wynwood-hair-co-nw-5th-ave",
        "category_slugs": ["hair", "barber"],
        "neighborhood_slugs": ["nw-2nd-ave-wynwood-walls"],
        "address": {"street": "2612 NW 5th Ave", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 399-0321",
        "website": "https://www.wynwoodhairco.com",
        "instagram": "@wynwoodhairco",
        "short_description": (
            "A full-service hair salon and barbershop rooted in the Wynwood Arts District "
            "— equal parts street-style and craft, offering cuts, color, and fades for "
            "the neighborhood's mixed creative community."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — NW 25TH–29TH CORRIDOR ─────────────────────────────────────────
    {
        "name": "Studio RauPO",
        "slug": "studio-raupo-wynwood-corridor",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "192 NW 36th St", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 677-6656",
        "website": "https://www.hairstylistmiami.com",
        "instagram": "@studioraupo",
        "short_description": (
            "An airy, artist-run salon in deep Wynwood co-founded by veteran stylists "
            "Wendy and Lhonette — the kind of studio that feels equal parts creative "
            "sanctuary and neighborhood salon, known for lived-in color and thoughtful "
            "consultations."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Bleach Hair Addiction",
        "slug": "bleach-hair-addiction-midtown",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "3101 N Miami Ave, Suite 120", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 372-0206",
        "website": "http://www.bleachhairaddiction.com",
        "instagram": "@bleachhairaddiction",
        "short_description": (
            "Miami's go-to destination for expert blonde work and vibrant fantasy color — "
            "a color-specialist salon inside the Shops at Midtown Miami that attracts "
            "clients from across South Florida for its precision bleach techniques and "
            "damage-conscious approach."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── HAIR — MIDTOWN / EDGE DISTRICT ────────────────────────────────────────
    {
        "name": "IGK Salon Miami",
        "slug": "igk-salon-miami-design-district",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "56 NE 41st St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 573-5520",
        "website": "https://www.igkhair.com/pages/miami-salon",
        "instagram": "@igkhair",
        "short_description": (
            "The Miami flagship of the celebrity-founded IGK brand — a high-energy "
            "Design District salon known for effortless color, textured cuts, and a "
            "rotating cast of top-tier stylists who draw clients from Wynwood to South "
            "Beach."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── NAILS — NW 2ND AVE / WYNWOOD WALLS ───────────────────────────────────
    {
        "name": "Brisa Nail Spa",
        "slug": "brisa-nail-spa-wynwood",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["nw-2nd-ave-wynwood-walls"],
        "address": {"street": "57 NW 24th St", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 209-6729",
        "website": "https://brisanailspa.com",
        "instagram": "@brisanailspa",
        "short_description": (
            "Wynwood's most aesthetically striking nail destination — a Tulum-inspired "
            "spa built from scratch for comfort and style, specializing in Russian and "
            "Japanese nail techniques with complimentary champagne and top-shelf products."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── NAILS — MIDTOWN / EDGE DISTRICT ──────────────────────────────────────
    {
        "name": "Nail Culture Wynwood",
        "slug": "nail-culture-wynwood-ne-2nd-ave",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "2400 NE 2nd Ave B", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 456-6974",
        "website": "https://nailculturewynwood.com",
        "instagram": "@nailculturewynwood",
        "short_description": (
            "A nail art-first studio on the NE 2nd Ave corridor dedicated to bringing "
            "gallery-level nail design to the arts district — intricate hand-painted "
            "art, gel extensions, and meticulous technique delivered alongside premium "
            "products."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Omni Nails and Lash Lounge",
        "slug": "omni-nails-and-lash-lounge-midtown",
        "category_slugs": ["nails", "lash-brow"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "139 NE 32nd St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 345-8098",
        "website": "https://omninailsmiami.com",
        "instagram": "@omninailsmiami",
        "short_description": (
            "A one-stop nail and lash studio in Midtown Miami with 500+ photos of work "
            "and 188 reviews — offering gel manicures, acrylics, dip powder, lash "
            "extensions, and permanent makeup in a well-lit, social-media-ready space."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Aurora Nails Bar",
        "slug": "aurora-nails-bar-edgewater",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "2328 NE 2nd Ave", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 822-4844",
        "website": "https://auroranailsbar.com",
        "instagram": "@auroranailsb",
        "short_description": (
            "Miami New Times Best Nail Bar five consecutive years (2021–2025) — the "
            "Edgewater/Midtown benchmark for manicure quality, nail art, and a "
            "welcoming atmosphere that keeps the creative community coming back."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — NW 25TH–29TH CORRIDOR ─────────────────────────────────
    {
        "name": "Solace Spa Miami",
        "slug": "solace-spa-miami-n-miami-ave",
        "category_slugs": ["spa", "lash-brow"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "3201 N Miami Ave, Suite 109", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 567-4843",
        "website": "https://www.solacespa.co",
        "instagram": "@solacespamia",
        "short_description": (
            "A skin and scalp wellness retreat on N Miami Ave best known for its "
            "signature Japanese Head Spa — a deeply therapeutic scalp ritual — alongside "
            "advanced facials, brow lamination, lash lifts, and Reiki healing."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — MIDTOWN / EDGE DISTRICT ────────────────────────────────
    {
        "name": "Face Brow & Beauty Bar — Midtown",
        "slug": "face-brow-beauty-bar-midtown",
        "category_slugs": ["lash-brow", "makeup"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "110 NE 32nd St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 703-5575",
        "website": "https://www.facebrowandbeautybar.com/locations/midtown",
        "instagram": "@facebrowbeautybar",
        "short_description": (
            "A multi-location Miami brow institution with its Midtown outpost serving "
            "the Wynwood corridor — known for expert brow shaping, microblading, brow "
            "lamination, and lash services in a clean, precision-focused environment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── BARBER — NW 2ND AVE / WYNWOOD WALLS ──────────────────────────────────
    {
        "name": "TruCutz — Midtown",
        "slug": "trucutz-midtown-ne-2nd-ave",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "3208 NE 2nd Ave", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 563-5779",
        "website": "https://www.trucutz.com",
        "instagram": "@trucutz",
        "short_description": (
            "Miami's premier barbershop destination with a flagship on NE 2nd Ave in "
            "the Midtown/Wynwood corridor — known for precision taper fades, line-ups, "
            "beard detailing, and straight razor shaves that have earned a loyal "
            "following in the creative community."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },
    {
        "name": "Barber & Co — Biscayne",
        "slug": "barber-and-co-biscayne-wynwood",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "2699 Biscayne Blvd", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 536-9064",
        "website": "https://www.barberandco.us/locations/biscayne",
        "instagram": "@barberandcomiami",
        "short_description": (
            "A luxury barbershop in Edgewater just steps from Wynwood's border — "
            "premium cuts, traditional hot towel shaves, and grooming services "
            "delivered with old-school precision in a well-appointed modern space."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — NW 25TH–29TH CORRIDOR ───────────────────────────────────────
    {
        "name": "Midtown Beauty Studio",
        "slug": "midtown-beauty-studio-nw-36th",
        "category_slugs": ["hair", "lash-brow", "makeup"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "46 NW 36th St, Suite 6", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 978-5307",
        "website": None,
        "instagram": "@midtownbeautystudio",
        "short_description": (
            "A versatile beauty studio in the heart of Wynwood offering hair styling, "
            "extensions, eyebrow design, lash extensions, and makeup artistry — "
            "a one-stop creative space for the neighborhood's working artists and "
            "image-conscious professionals."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — BUENA VISTA ────────────────────────────────────────────────────
    {
        "name": "Cata Luxury Barber Room",
        "slug": "cata-luxury-barber-room-wynwood",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["buena-vista"],
        "address": {"street": "174 NE 40th St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 717-7434",
        "website": "https://cataluxurybarber.com",
        "instagram": "@cataluxurybarber",
        "short_description": (
            "A premium barber room serving the Wynwood creative and professional "
            "community with trend-forward styles, bold textures, and modern edge — "
            "intimate by design, appointment-driven by demand."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — BUENA VISTA ──────────────────────────────────────────────────
    {
        "name": "Rosé Nail Lounge",
        "slug": "rose-nail-lounge-buena-vista",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["buena-vista"],
        "address": {"street": "149 NE 40th St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 576-9030",
        "website": None,
        "instagram": "@rosenaillounge",
        "short_description": (
            "A cheerful, well-reviewed nail lounge in the Design District/Buena Vista "
            "border offering gel manicures, dip powder, acrylics, and pedicures "
            "in a relaxed setting that attracts Wynwood's gallery crowd and "
            "neighborhood regulars alike."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — NW 2ND AVE / WYNWOOD WALLS ─────────────────────────────────────
    {
        "name": "Luv Nail Shop",
        "slug": "luv-nail-shop-wynwood",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["nw-2nd-ave-wynwood-walls"],
        "address": {"street": "2801 N Miami Ave", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 717-4636",
        "website": None,
        "instagram": "@luvnailshop",
        "short_description": (
            "A neighborhood nail shop in the NW 2nd Ave corridor popular with Wynwood "
            "locals for gel manicures, nail art, and pedicures at honest prices — "
            "the kind of spot that fills up by word of mouth."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── WAXING — NW 25TH–29TH CORRIDOR ──────────────────────────────────────
    {
        "name": "European Wax Center — Midtown Miami",
        "slug": "european-wax-center-midtown-miami",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "3301 NE 1st Ave, Suite 116", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 576-4400",
        "website": "https://www.waxcenter.com/locations/fl/miami-midtown",
        "instagram": "@europeanwaxcenter",
        "short_description": (
            "The Midtown Miami European Wax Center — consistent, comfort-wax services "
            "for brows, full-face, and full-body waxing from a franchise that sets "
            "the standard for clean technique and efficient scheduling."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH/BROW — BUENA VISTA ──────────────────────────────────────────────
    {
        "name": "The Pink Room Beauty Spa",
        "slug": "the-pink-room-beauty-spa-wynwood",
        "category_slugs": ["lash-brow", "spa"],
        "neighborhood_slugs": ["buena-vista"],
        "address": {"street": "4000 NE 2nd Ave, Suite 105", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 536-5677",
        "website": None,
        "instagram": "@thepinkroombeautyspa",
        "short_description": (
            "A boutique beauty spa on the Design District/Buena Vista border offering "
            "lash extensions, brow lamination, facials, and waxing in a "
            "feminine, carefully designed space that has built a devoted local following."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MED-SPA — MIDTOWN / EDGE DISTRICT ────────────────────────────────────
    {
        "name": "Skin Laser & Wellness Spa",
        "slug": "skin-laser-wellness-spa-midtown",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["midtown-edge-district"],
        "address": {"street": "3250 NE 1st Ave, Suite 305", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 539-9909",
        "website": "https://www.skinlaserandwellness.com",
        "instagram": "@skinlaserandwellness",
        "short_description": (
            "A medical spa inside the Midtown Miami tower offering laser hair removal, "
            "CoolSculpting, PRP facials, and injectables under physician oversight — "
            "one of the area's most reviewed clinical aesthetic practices serving "
            "the Wynwood and Midtown creative professional crowd."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — BUENA VISTA ────────────────────────────────────────────────────
    {
        "name": "Silvia's Hair Studio",
        "slug": "silvias-hair-studio-buena-vista",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["buena-vista"],
        "address": {"street": "180 NE 39th St, Suite 248", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 576-9944",
        "website": None,
        "instagram": "@silviashairsalon",
        "short_description": (
            "A long-established boutique salon tucked inside the Miami Design District "
            "building on NE 39th Street — Silvia specializes in precision cuts, "
            "keratin treatments, and color for a loyal Buena Vista and Design District "
            "clientele built over more than a decade."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── BARBER — NW 2ND AVE / WYNWOOD WALLS ──────────────────────────────────
    {
        "name": "Wynwood Barbershop",
        "slug": "wynwood-barbershop-nw-2nd-ave",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["nw-2nd-ave-wynwood-walls"],
        "address": {"street": "55 NW 25th St", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 401-5533",
        "website": None,
        "instagram": "@wynwoodbarbershop",
        "short_description": (
            "A street-level barbershop right in the Wynwood Walls district serving the "
            "neighborhood's artists, gallerists, and foot-traffic crowd with sharp fades, "
            "line-ups, and beard trims at accessible prices without sacrificing craft."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── MAKEUP — NW 25TH–29TH CORRIDOR ───────────────────────────────────────
    {
        "name": "Beauty Room Wynwood",
        "slug": "beauty-room-wynwood-nw-corridor",
        "category_slugs": ["makeup", "lash-brow"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "2610 N Miami Ave, Suite 5", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 605-4747",
        "website": None,
        "instagram": "@beautyroomwynwood",
        "short_description": (
            "A studio-style makeup and lash atelier on N Miami Ave focused on "
            "editorial and bridal makeup, individual and volume lash extensions, "
            "and brow design — drawing clients from across Miami who want "
            "a makeup artist's eye rather than a cookie-cutter lash chain."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — NW 25TH–29TH CORRIDOR ──────────────────────────────────────────
    {
        "name": "Wynwood Wellness Spa",
        "slug": "wynwood-wellness-spa-n-miami-ave",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["nw-25th-29th-corridor"],
        "address": {"street": "3140 N Miami Ave", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(305) 438-9010",
        "website": None,
        "instagram": "@wynwoodwellnessspa",
        "short_description": (
            "A neighborhood day spa on N Miami Ave offering deep-tissue massage, "
            "customized facials, body scrubs, and reflexology — a calm pocket of "
            "wellness tucked among the galleries and studios that defines the "
            "deep-Wynwood block between 25th and 29th Street."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_wynwood() -> None:
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
        "slug": "wynwood",
        "name": "Wynwood",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Wynwood's most creative beauty addresses.",
        "hero_description": (
            "An index of the colorists, nail artists, barbers, and lash stylists "
            "the Wynwood arts district actually books — from the mural-lined blocks "
            "of NW 2nd Ave to the Midtown corridor and the quieter studios of "
            "Buena Vista. This is Miami beauty with an edge."
        ),
        "seo_title": "Wynwood Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Wynwood, Miami — salons, nail studios, "
            "barbers, and lash bars chosen by the creative community. Covering "
            "NW 2nd Ave, the Wynwood Walls corridor, Midtown, and Buena Vista."
        ),
        "editorial_headlines": [
            {"headline": "Wynwood's most creative beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "wynwood"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: wynwood (id=%s)" % city_id)

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
    print("Wynwood seed complete:")
    print("  City:          wynwood (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Coral Gables, Miami, FTL, and Boca
    # Raton seeds — this script writes to the database. Refuse to run against
    # production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_wynwood()


if __name__ == "__main__":
    run(main())
