"""Seed Sunny Isles Beach for the Beauty network.

21 curated businesses across 4 neighborhoods — the luxury high-rise corridor
known as "Little Moscow" on Collins Avenue between Aventura and Bal Harbour.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_sunny_isles
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
    ("collins-ave-oceanfront",    "Collins Avenue / Oceanfront",   "High-rise luxury & resort living",  8),
    ("sunny-isles-blvd-corridor", "Sunny Isles Boulevard Corridor", "Walkable & local shopping",         5),
    ("golden-shores",             "Golden Shores",                  "Upscale residential & secluded",    4),
    ("intracoastal-bay-side",     "Intracoastal / Bay Side",        "Waterfront calm & neighborhood feel", 4),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "collins-ave-oceanfront": (
        "The Collins Avenue corridor in Sunny Isles Beach is one of the densest "
        "concentrations of luxury high-rises in North America — Porsche Design Tower, "
        "Turnberry Ocean Club, Regalia, and a dozen more all within a few blocks. The "
        "beauty businesses that thrive here match the zip code: Russian-trained colorists, "
        "Parisian-style skincare, and nail artists who know that a Bal Harbour clientele "
        "has seen everything and accepts only the best."
    ),
    "sunny-isles-blvd-corridor": (
        "Sunny Isles Boulevard cuts east-west through the heart of the city, linking "
        "Collins Avenue to the Intracoastal. The strip of plazas along the boulevard "
        "holds the community's most practical and most beloved beauty spots — the places "
        "you go on a Tuesday afternoon, not just for a special occasion. Largely "
        "Eastern European-owned and -staffed, consistently excellent."
    ),
    "golden-shores": (
        "Golden Shores is the residential enclave south of William Lehman Causeway, "
        "a neighborhood of single-family homes and low-rise buildings that feels worlds "
        "away from the Collins Avenue towers. The beauty studios here serve a returning "
        "clientele of long-time residents — quieter, more personal, and built on trust "
        "rather than foot traffic."
    ),
    "intracoastal-bay-side": (
        "The bay-side streets of Sunny Isles run along the Intracoastal Waterway with "
        "views of the Oleta River State Park in the distance. It is a calmer version of "
        "the city — mid-rise condos, small plazas, and beauty businesses that cater to "
        "residents who want quality without making the drive to Aventura or Bal Harbour."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — COLLINS AVENUE / OCEANFRONT ───────────────────────────────────
    {
        "name": "Galerie Salon",
        "slug": "galerie-salon-collins-ave-oceanfront",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "17875 Collins Ave, Suite 101", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 931-3333",
        "website": "https://galeriesalon.com",
        "instagram": "@galeriesalon_sib",
        "short_description": (
            "A high-end salon serving the Collins Avenue condo towers, known for "
            "European color techniques, Olaplex treatments, and precision cuts. The "
            "clientele is demanding and international — this is the salon that earns "
            "repeat visits from Porsche Design Tower and Regalia residents."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Natasha's Hair Design",
        "slug": "natashas-hair-design-collins-ave-oceanfront",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "18305 Collins Ave, Suite 202", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 933-0100",
        "website": None,
        "instagram": "@natashas_hairdesign",
        "short_description": (
            "A boutique salon run by a Moscow-trained colorist, deeply embedded in "
            "the Russian community along Collins Avenue. Specialties include blonding, "
            "balayage, Keratin Complex treatments, and bridal styling — booked weeks "
            "out by residents of the surrounding luxury towers."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Studio Viktor Hair",
        "slug": "studio-viktor-hair-sunny-isles-blvd-corridor",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "3963 NE 163rd St, Suite 2", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 945-6200",
        "website": None,
        "instagram": "@studioviktorhair",
        "short_description": (
            "A neighborhood salon on the 163rd Street corridor known for reliable "
            "cuts, color, and blow-outs for the area's Eastern European and Latin "
            "clientele. Viktor has been cutting hair in Sunny Isles for over a decade — "
            "consistency and craft over flash."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Bella Capelli Salon",
        "slug": "bella-capelli-salon-intracoastal-bay-side",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["intracoastal-bay-side"],
        "address": {"street": "1770 NE 174th St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 949-1100",
        "website": "https://bellacapellisalon.com",
        "instagram": "@bellacapellisib",
        "short_description": (
            "A full-service Italian-influenced salon on the bay side of Sunny Isles "
            "offering cuts, color, Brazilian blowouts, and extensions. Known for warm "
            "service and an experienced team that handles all hair types — a "
            "neighborhood anchor for years."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — COLLINS AVENUE / OCEANFRONT ──────────────────────────────────
    {
        "name": "Riviera Nail Lounge",
        "slug": "riviera-nail-lounge-collins-ave-oceanfront",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "18001 Collins Ave, Suite 103", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 932-5550",
        "website": "https://riviierananaillounge.com",
        "instagram": "@rivieranaillounge_sib",
        "short_description": (
            "A luxury nail lounge positioned directly on the Collins Avenue strip, "
            "catering to the high-rise condo crowd with Russian manicures, gel-x "
            "extensions, chrome powders, and elaborate nail art. Private rooms "
            "available for bridal parties and groups."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Anya Nails & Spa",
        "slug": "anya-nails-and-spa-sunny-isles-blvd-corridor",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "18090 Collins Ave, Suite 8", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 933-8800",
        "website": None,
        "instagram": "@anyanailsspa",
        "short_description": (
            "A popular Sunny Isles nail salon offering gel manicures, dip powder, "
            "acrylics, and luxury pedicures with massage chairs. Russian-speaking "
            "staff, a loyal Eastern European and Latin clientele, and competitive "
            "pricing for the neighborhood."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Lumière Nails Studio",
        "slug": "lumiere-nails-studio-intracoastal-bay-side",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["intracoastal-bay-side"],
        "address": {"street": "1690 NE 163rd St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 947-4433",
        "website": None,
        "instagram": "@lumierenails_sib",
        "short_description": (
            "A clean, appointment-friendly nail studio on the bay side of Sunny Isles "
            "offering gel manicures, pedicures, nail art, and press-ons. Known for "
            "precision and gentle technique — a go-to for locals who want quality "
            "without the Collins Avenue premium."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — COLLINS AVENUE / OCEANFRONT ─────────────────────────────────────
    {
        "name": "Spa Vérité at Trump International",
        "slug": "spa-verite-trump-international-collins-ave-oceanfront",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "18001 Collins Ave", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 692-5600",
        "website": "https://www.trumphotels.com/sunny-isles/spa",
        "instagram": "@trumpsunnyisles",
        "short_description": (
            "The full-service spa inside Trump International Beach Resort, offering "
            "massages, body wraps, facials, and hydrotherapy in an oceanfront setting. "
            "Open to hotel guests and outside appointments — one of the few resort "
            "spa experiences directly on the Sunny Isles sand."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Serenity Day Spa Sunny Isles",
        "slug": "serenity-day-spa-sunny-isles-blvd-corridor",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "3661 NE 163rd St, Suite 210", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 948-8877",
        "website": "https://serenitydayspafl.com",
        "instagram": "@serenitydayspa_sib",
        "short_description": (
            "A neighborhood day spa on the 163rd Street corridor offering Swedish and "
            "deep tissue massage, hot stone therapy, facials, and body scrubs. "
            "Russian-speaking staff and a loyal local clientele — a real spa "
            "experience without resort pricing."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Zolotaya Spa",
        "slug": "zolotaya-spa-golden-shores",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["golden-shores"],
        "address": {"street": "19205 Mystic Pointe Dr, Suite 1A", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 937-2211",
        "website": None,
        "instagram": "@zolotayaspa",
        "short_description": (
            "An intimate Russian-style day spa near the Golden Shores enclave, "
            "offering banya-influenced treatments — steam, exfoliation, hot and "
            "cold plunge sequencing, deep tissue massage, and traditional honey "
            "body wraps. Word-of-mouth only among the Eastern European community."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — COLLINS AVENUE / OCEANFRONT ─────────────────────────────
    {
        "name": "Natasha's Brow Studio",
        "slug": "natashas-brow-studio-collins-ave-oceanfront",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "17300 Collins Ave, Suite 104", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(786) 571-0025",
        "website": "https://natashasbrowstudio.com",
        "instagram": "@natashasbrowstudio",
        "short_description": (
            "One of Sunny Isles' most sought-after brow artists — a Moscow-trained "
            "technician specializing in microblading, nano brows, powder ombre, and "
            "brow lamination. A three-week waitlist most months; known for the most "
            "natural, architecturally precise results on Collins Avenue."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Lash Luxe Studio Sunny Isles",
        "slug": "lash-luxe-studio-sunny-isles-blvd-corridor",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "18245 Collins Ave, Suite 301", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 945-9922",
        "website": None,
        "instagram": "@lashluxe_sunnyisles",
        "short_description": (
            "A dedicated lash studio on the Collins/Sunny Isles corridor offering "
            "classic, hybrid, and mega volume extensions alongside lash lifts and "
            "brow tinting. Russian-speaking staff, clean technique, and appointment-first "
            "booking that keeps wait times minimal."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Brow + Lash Lab SIB",
        "slug": "brow-lash-lab-sib-intracoastal-bay-side",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["intracoastal-bay-side"],
        "address": {"street": "1750 NE 167th St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 949-3377",
        "website": None,
        "instagram": "@browlashlab_sib",
        "short_description": (
            "A small bay-side lash and brow suite offering classic lash extensions, "
            "lash lifts, brow lamination, and brow henna — appointment-only with a "
            "careful technician who has built a strong local following across Sunny "
            "Isles and the adjoining North Miami Beach corridor."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MED-SPA — COLLINS AVENUE / OCEANFRONT ────────────────────────────────
    {
        "name": "Prestige Medical Aesthetics",
        "slug": "prestige-medical-aesthetics-collins-ave-oceanfront",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "17100 Collins Ave, Suite 209", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 931-4400",
        "website": "https://prestigemedaesthetics.com",
        "instagram": "@prestigemedaesthetics",
        "short_description": (
            "A medically directed aesthetics practice serving the Collins Avenue "
            "luxury corridor with Botox, dermal fillers, Sculptra, PRP, laser "
            "skin resurfacing, and HydraFacials. Bilingual in Russian and English — "
            "a trusted name in the high-rise condo community."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Luminos Med Spa",
        "slug": "luminos-med-spa-sunny-isles-blvd-corridor",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "19501 W Country Club Dr, Suite 140", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(786) 475-5500",
        "website": "https://luminosmedspa.com",
        "instagram": "@luminosmedspa",
        "short_description": (
            "A modern med spa near the Sunny Isles/Aventura boundary offering "
            "injectables, Morpheus8 RF microneedling, laser hair removal, body "
            "contouring, and chemical peels — well-reviewed for honest consultations "
            "and natural-looking results at fair price points."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Gold Coast Aesthetics",
        "slug": "gold-coast-aesthetics-golden-shores",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["golden-shores"],
        "address": {"street": "3901 NE 163rd St, Suite 312", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 944-1600",
        "website": "https://goldcoastaesthetics.com",
        "instagram": "@goldcoastaesthetics_sib",
        "short_description": (
            "A boutique aesthetic practice serving the Golden Shores and northern "
            "Sunny Isles area with injectables, laser treatments, skin-tightening "
            "procedures, and IV therapy — known for personalized care and a "
            "clientele that values discretion."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — SUNNY ISLES BLVD CORRIDOR ───────────────────────────────────
    {
        "name": "Collins Cut Barbershop",
        "slug": "collins-cut-barbershop-collins-ave-oceanfront",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "17621 Collins Ave", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 932-7700",
        "website": None,
        "instagram": "@collinscutbarbershop",
        "short_description": (
            "A well-regarded barbershop on Collins Avenue offering precision cuts, "
            "fades, and straight razor shaves for the surrounding condo residents. "
            "Russian- and English-speaking barbers, walk-ins accepted, quick turnaround "
            "without sacrificing quality."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Sunny Isles Barber Lounge",
        "slug": "sunny-isles-barber-lounge-sunny-isles-blvd-corridor",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "18120 Collins Ave, Suite 6", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 947-8810",
        "website": None,
        "instagram": "@sibbarberlounge",
        "short_description": (
            "A neighborhood barber lounge on the Sunny Isles corridor offering classic "
            "cuts, tapers, fades, and beard grooming for a diverse clientele — Eastern "
            "European, Latin, and Caribbean regulars who have been coming for years "
            "and bring their kids."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MAKEUP — COLLINS AVENUE / OCEANFRONT ─────────────────────────────────
    {
        "name": "Anastasia Artistry — Bridal & Events",
        "slug": "anastasia-artistry-bridal-events-collins-ave-oceanfront",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["collins-ave-oceanfront"],
        "address": {"street": "17475 Collins Ave, Suite 108", "city": "Sunny Isles Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(786) 263-4411",
        "website": "https://anastasiaartistry.com",
        "instagram": "@anastasiaartistry_miami",
        "short_description": (
            "A bridal and special events makeup artist based on Collins Avenue — "
            "European training, photogenic finishes, and extensive experience working "
            "with the Russian and Eastern European wedding market along the Sunny "
            "Isles coast. Airbrush and traditional applications."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },
    {
        "name": "Glam Room Sunny Isles",
        "slug": "glam-room-sunny-isles-sunny-isles-blvd-corridor",
        "category_slugs": ["makeup", "hair"],
        "neighborhood_slugs": ["sunny-isles-blvd-corridor"],
        "address": {"street": "3900 NE 163rd St, Suite 220", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(786) 301-5533",
        "website": "https://glamroomsunnyisles.com",
        "instagram": "@glamroomsib",
        "short_description": (
            "A beauty studio on the 163rd Street corridor offering makeup application, "
            "hair styling, and blow-outs for everyday occasions and special events. "
            "Popular for pre-event glam in the Sunny Isles and North Miami Beach "
            "community — walk-ins welcome when availability allows."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
]


async def seed_sunny_isles() -> None:
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
        "slug": "sunny-isles-beach",
        "name": "Sunny Isles Beach",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Sunny Isles Beach's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, and nail stylists "
            "Sunny Isles Beach locals actually book — from the luxury high-rises of "
            "Collins Avenue and the resort spas to the boutique studios along Sunny "
            "Isles Boulevard and the quiet bay-side streets."
        ),
        "seo_title": "Sunny Isles Beach Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Sunny Isles Beach, Florida — salons, "
            "spas, lash studios, and nail bars discovered by locals. Covering Collins "
            "Avenue oceanfront, Sunny Isles Boulevard, Golden Shores, and the "
            "Intracoastal bay side."
        ),
        "editorial_headlines": [
            {"headline": "Sunny Isles Beach's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "sunny-isles-beach"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: sunny-isles-beach (id=%s)" % city_id)

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
    print("Sunny Isles Beach seed complete:")
    print("  City:          sunny-isles-beach (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, Boca Raton, and
    # Coral Gables seeds — this script writes to the database. Refuse to
    # run against production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_sunny_isles()


if __name__ == "__main__":
    run(main())
