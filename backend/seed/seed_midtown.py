"""Seed Midtown Miami / Design District for the Beauty network.

18 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_midtown
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
    ("design-district-core",  "Design District Core",     "Luxury & prestige",       4),
    ("ne-2nd-ave-corridor",   "NE 2nd Ave Corridor",       "Gallery district beauty",  4),
    ("midtown-row",           "Midtown Row",               "Trendy & walkable",        6),
    ("edgewater-border",      "Edgewater Border",          "Award-winning independents", 4),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "design-district-core": (
        "Palm Court and the NE 39th–41st Street corridor set the design district's "
        "tone — a walkable luxury precinct where flagship boutiques, world-class "
        "art installations, and architecture firm up the backdrop for some of Miami's "
        "most prestigious beauty destinations. The clients who come here expect "
        "a certain level of experience, and the salons and spas on this block deliver it."
    ),
    "ne-2nd-ave-corridor": (
        "The gallery-lined spine of the Design District running along NE 2nd Avenue "
        "attracts independent beauty studios that match their surroundings — "
        "thoughtful, specialty-driven, and a cut above the chain experience. "
        "Medical spas, waxing boutiques, and hair studios share blocks with "
        "galleries and concept stores, drawing a creative, design-world clientele."
    ),
    "midtown-row": (
        "The commercial strip anchored by the Shops at Midtown Miami along N Miami "
        "Avenue and NE 1st Avenue is the neighborhood's most accessible beauty "
        "corridor — walkable, open late, and packed with nail bars, hair salons, "
        "brow studios, and barbers that serve the young creative professionals "
        "who live and work in Midtown's rapidly growing residential towers."
    ),
    "edgewater-border": (
        "The stretch of NE 1st and 2nd Avenues between Midtown and Edgewater along "
        "Biscayne Boulevard has quietly become one of Miami's most decorated indie "
        "beauty zones — home to Aurora Nails Bar, True Hair Miami, and a cluster "
        "of specialty studios that have built followings on craft and consistency "
        "rather than location or marketing."
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

    # ── DESIGN DISTRICT CORE ─────────────────────────────────────────────────
    {
        "name": "IGK Salon",
        "slug": "igk-salon-design-district",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["design-district-core"],
        "address": {"street": "56 NE 41st St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 573-5520",
        "website": "https://www.igkhair.com/pages/miami-salon",
        "instagram": "@igkhair",
        "short_description": (
            "Founded by celebrity colorists Franck and Leo Izquierdo, IGK is the "
            "Design District's defining hair destination — equal parts buzzy social "
            "scene and serious craft. The salon draws models, celebrities, and Miami's "
            "most fashion-forward locals for its signature effortless color work and "
            "beachy waves, holding a 4.8-star rating across 530+ reviews."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "Miami's most talked-about salon — co-founded by celebrity colorists, "
            "featured on Goop and in Vogue, with a 4.8 Google rating across 530+ "
            "reviews for transformative color work and an unmissable atmosphere."
        ),
    },
    {
        "name": "Dr. Barbara Sturm Boutique & Spa",
        "slug": "dr-barbara-sturm-boutique-spa-design-district",
        "category_slugs": ["spa", "med-spa"],
        "neighborhood_slugs": ["design-district-core"],
        "address": {"street": "140 NE 39th St, Suite 111", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": None,
        "website": "https://www.drsturm.com/miami-boutique-spa",
        "instagram": "@drbarbararstürm",
        "short_description": (
            "The skin guru to the stars brought her second U.S. location to Palm "
            "Court in 2021 — a minimalist two-level boutique and spa set beside "
            "Buckminster Fuller's iconic Fly's Eye Dome. Signature treatments include "
            "the STURMGLOW™ Facial and Exoso-metic Growth Factor Facial, rooted in "
            "Dr. Sturm's celebrated anti-inflammatory science."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "A globally recognized skincare icon with a bespoke Design District spa — "
            "the only South Florida outpost for Dr. Sturm's molecular skincare facials, "
            "covered by Vogue, Allure, and WWD."
        ),
    },
    {
        "name": "Valery Joseph Salon Miami",
        "slug": "valery-joseph-salon-design-district",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["design-district-core"],
        "address": {"street": "140 NE 39th St, Suite PC208", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 967-8352",
        "website": "https://valeryjoseph.com/pages/locations",
        "instagram": "@valeryjosephsalon",
        "short_description": (
            "The Miami outpost of the New York–born luxury hair brand occupies a "
            "refined suite in the Design District's signature building, specializing "
            "in precision cuts, balayage, hair extensions, and bridal styling. "
            "Clients describe it as one of the most quietly prestigious salon "
            "addresses in Miami."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },
    {
        "name": "Aesop Design District",
        "slug": "aesop-design-district",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["design-district-core"],
        "address": {"street": "160 NE 41st St, Suite 120", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 558-8965",
        "website": "https://www.aesop.com",
        "instagram": "@aesopskincare",
        "short_description": (
            "The Design District outpost of the cult Australian apothecary offers "
            "its full range of plant-based skin, hair, and body formulations in a "
            "beautifully appointed boutique. Trained consultants provide personalized "
            "product consultations — shopping here feels as much like a private "
            "skincare session as it does like retail."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NE 2ND AVE CORRIDOR ───────────────────────────────────────────────────
    {
        "name": "Aviva Medical Spa",
        "slug": "aviva-medical-spa-design-district",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["ne-2nd-ave-corridor"],
        "address": {"street": "4100 NE 2nd Ave, Suite 301", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": None,
        "website": "https://avivamedicalspa.com",
        "instagram": "@avivamedicalspa",
        "short_description": (
            "A full-service medical spa on the Design District's gallery corridor "
            "offering Morpheus8, Botox, dermal fillers, chemical peels, laser "
            "treatments, and IV therapy under physician supervision. Its 270+ Yelp "
            "reviews consistently praise the clinical results and the calm, "
            "luxury-spa atmosphere that sets it apart from clinical medspa chains."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "The Design District's standout medical spa — physician-supervised "
            "Morpheus8 and injectable treatments with 270+ verified reviews and "
            "a genuine luxury atmosphere rare in this category."
        ),
    },
    {
        "name": "Sugaring NYC — Design District",
        "slug": "sugaring-nyc-design-district",
        "category_slugs": ["waxing"],
        "neighborhood_slugs": ["ne-2nd-ave-corridor"],
        "address": {"street": "3635 NE 1st Ave, Unit 134", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": None,
        "website": "https://www.sugaringnyc.com",
        "instagram": "@sugaringnyc",
        "short_description": (
            "The Miami Design District outpost of the beloved New York sugaring "
            "studio brings its all-natural, three-ingredient sugar paste technique "
            "to the neighborhood — gentler on skin than traditional wax and equally "
            "effective. State-licensed estheticians also offer lash lifts and brow "
            "lamination alongside 40+ sugaring service options."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Maxel Beauty Lab",
        "slug": "maxel-beauty-lab-design-district",
        "category_slugs": ["hair", "makeup"],
        "neighborhood_slugs": ["ne-2nd-ave-corridor"],
        "address": {"street": "172 NE 29th St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 244-5110",
        "website": "https://maxelbeautylab.com",
        "instagram": "@maxelbeautylab",
        "short_description": (
            "A full-service beauty lab at the southern edge of the Design District "
            "specializing in hair color, balayage, and spa services alongside makeup "
            "artistry. The studio draws a creative, design-world clientele who "
            "appreciate the personalized approach and boutique scale."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Monaco MedSpa",
        "slug": "monaco-medspa-design-district",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["ne-2nd-ave-corridor"],
        "address": {"street": "2930 NE 2nd Ct", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 536-6117",
        "website": "https://www.monacomedspa.com",
        "instagram": "@monacomedspa",
        "short_description": (
            "A boutique medical spa at the Midtown/Design District border offering "
            "Botox, dermal fillers, laser treatments, and body contouring in a "
            "refined, personalized setting. Monaco's individualized approach and "
            "physician oversight make it one of the neighborhood's most recommended "
            "non-surgical aesthetic practices."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MIDTOWN ROW ───────────────────────────────────────────────────────────
    {
        "name": "Venetian Nail Spa — Midtown",
        "slug": "venetian-nail-spa-midtown",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "3401 N Miami Ave, Suite 110", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": "(786) 485-9999",
        "website": "https://venetiansalon.com/midtown-miami/",
        "instagram": "@venetiannailspa",
        "short_description": (
            "Anchoring the Shops at Midtown Miami with a spacious, hotel-lobby "
            "aesthetic and an extensive menu spanning gel, dip, acrylics, pedicures, "
            "and waxing. With nearly 500 Yelp reviews and an open, social-media-ready "
            "interior, it's become Midtown's go-to nail destination for walk-ins and "
            "regulars alike."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Hairports Miami",
        "slug": "hairports-miami-midtown",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "3470 E Coast Ave, Suite 112", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 798-3384",
        "website": "https://hairportsmiami.com",
        "instagram": "@hairportsmiami",
        "short_description": (
            "A full-service salon inside the Midtown Miami mixed-use complex offering "
            "precision cuts, balayage, keratin treatments, extensions, and "
            "special-occasion styling for women and men. Reviewers consistently "
            "highlight the skilled colorists and the warm, non-intimidating vibe "
            "that keeps locals coming back."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "The Outlet Barber Parlor",
        "slug": "outlet-barber-parlor-midtown",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "3201 N Miami Ave, Suite 109", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": "@theoutletbarberparlor",
        "short_description": (
            "Midtown's standout barbershop occupying a sleek studio off N Miami Ave, "
            "delivering precision fades, shape-ups, and beard work in a design-forward "
            "space that feels more like a creative studio than a traditional barber. "
            "It holds a perfect 5.0 Booksy rating with 183 client reviews — the "
            "highest-rated barber in the neighborhood."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Face. Brow & Beauty Bar",
        "slug": "face-brow-beauty-bar-midtown",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "110 NE 32nd St", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 703-5575",
        "website": "https://www.facebrowandbeautybar.com",
        "instagram": "@facebrowandbeautybar",
        "short_description": (
            "Since 2014, Face. Brow & Beauty Bar has been Midtown's dedicated "
            "brow studio — offering threading, waxing, tinting, lamination, and "
            "lash lifts alongside rejuvenating facials. With 311 Yelp reviews across "
            "its Miami locations, the team's reputation for precise, customized brow "
            "shaping has built one of the city's most loyal beauty followings."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "SkinLocal Midtown",
        "slug": "skinlocal-midtown",
        "category_slugs": ["med-spa", "lash-brow"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "3431 NE 1st Ave", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 384-6090",
        "website": "https://theskinlocal.com",
        "instagram": "@theskinlocal",
        "short_description": (
            "A boutique medical aesthetics clinic with a dedicated brow bar built in "
            "— SkinLocal handles everything from brow shaping, tinting, and lamination "
            "to injectables, chemical peels, and laser resurfacing under one roof. "
            "It's the Midtown destination for clients who want advanced skin treatments "
            "and everyday beauty services without making two separate trips."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Midtown Beauty Studio",
        "slug": "midtown-beauty-studio",
        "category_slugs": ["hair", "makeup"],
        "neighborhood_slugs": ["midtown-row"],
        "address": {"street": "46 NW 36th St", "city": "Miami", "state": "FL", "postal_code": "33127", "country": "US"},
        "phone": None,
        "website": None,
        "instagram": None,
        "short_description": (
            "A one-stop beauty hub at the northern edge of Midtown offering hair "
            "styling, makeup artistry, image consulting, hair extensions, custom "
            "eyebrow design, and eyelash extensions alongside a curated beauty "
            "supply section. Serves both walk-in clients and professional stylists "
            "sourcing products."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── EDGEWATER BORDER ──────────────────────────────────────────────────────
    {
        "name": "Aurora Nails Bar",
        "slug": "aurora-nails-bar-edgewater",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["edgewater-border"],
        "address": {"street": "2328 NE 2nd Ave", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 822-4844",
        "website": "https://auroranailsbar.com",
        "instagram": "@auroranailsbar",
        "short_description": (
            "Five-time Miami New Times 'Best Nail Bar' winner (2021–2025) and "
            "2026 Evergreen Awards honoree, Aurora Nails Bar is the most decorated "
            "nail salon in the Midtown/Edgewater corridor. Owner Mariana has built "
            "a reputation for immaculate nail art, non-toxic products, and a studio "
            "environment that feels as much like a gallery as a salon."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "Miami's most-awarded independent nail salon — five consecutive Best "
            "of Miami wins from New Times plus the 2026 Evergreen Award for Best "
            "Nail Salon in Miami. Non-toxic, art-forward, and fiercely locally beloved."
        ),
    },
    {
        "name": "True Hair Miami",
        "slug": "true-hair-miami-edgewater",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["edgewater-border"],
        "address": {"street": "3449 NE 1st Ave, Suite 107", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(305) 921-4238",
        "website": "https://truehairmiami.zoca.com",
        "instagram": "@truehairmiami",
        "short_description": (
            "One of Midtown's highest-rated hair salons with a 4.8-star reputation "
            "and 210+ Yelp reviews, True Hair Miami serves a loyal neighborhood "
            "clientele with cuts, color, and treatments in a relaxed, no-attitude "
            "studio atmosphere — a local favorite for salon-quality results without "
            "the Design District price tag."
        ),
        "price_cues": "$$",
        "editors_pick": True,
        "editors_pick_reason": (
            "A Midtown institution with a 4.8-star rating across 210+ reviews — "
            "consistently ranked among Miami's best independent hair salons for its "
            "personable approach and dependable color work."
        ),
    },
    {
        "name": "Mano Nail Studio",
        "slug": "mano-nail-studio-edgewater",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["edgewater-border"],
        "address": {"street": "3301 NE 1st Ave, Suite 110", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 697-7282",
        "website": "https://manonailstudio.com",
        "instagram": "@manonailstudio",
        "short_description": (
            "A refined, non-toxic nail studio specializing exclusively in Japanese "
            "soft gel — no acrylics, dip, or harsh enhancements. Mano's commitment "
            "to nail health and elevated artistry attracts clients who want beautiful, "
            "long-lasting results without damaging the natural nail, with 135+ "
            "verified reviews backing the approach."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Rosé Nail Lounge",
        "slug": "rose-nail-lounge-edgewater",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["edgewater-border"],
        "address": {"street": "3050 Biscayne Blvd, Suite 101", "city": "Miami", "state": "FL", "postal_code": "33137", "country": "US"},
        "phone": "(786) 502-3191",
        "website": "https://www.rosenailloungemiami.com",
        "instagram": "@rosenaillounge",
        "short_description": (
            "Effortlessly chic on Biscayne Boulevard at the gateway to the Design "
            "District, Rosé Nail Lounge delivers manicures, pedicures, and nail art "
            "in a rosy-hued, Instagram-worthy interior. Its 155+ Yelp reviews praise "
            "the friendly technicians and the salon's ability to execute everything "
            "from quick polish changes to intricate gel art with equal care."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
]


async def seed_midtown() -> None:
    db = get_db()
    assert_seed_target_allowed()

    # WHY: look up by known network ID first; fall back to slug in case the ID
    # differs across environments — same pattern as seed_brickell.py.
    BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
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
        "slug": "midtown",
        "name": "Midtown & Design District",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Midtown's most trusted beauty addresses.",
        "hero_description": (
            "Miami's art-and-design corridor stretches from the Design District's "
            "Palm Court luxury precinct south through Midtown Miami's walkable "
            "mixed-use blocks to the edge of Edgewater on Biscayne Bay. Beauty "
            "businesses here span the full spectrum — from the international prestige "
            "of IGK Salon and Dr. Barbara Sturm to the deeply local, award-winning "
            "craft of Aurora Nails Bar — all within walking distance of some of the "
            "best architecture and public art in the city."
        ),
        "seo_title": "Midtown Miami Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Midtown Miami and the Design District "
            "— salons, spas, lash studios, nail bars, and med spas discovered by "
            "locals. Covering Palm Court, NE 2nd Ave, Midtown Row, and the "
            "Edgewater border."
        ),
        "editorial_headlines": [
            {"headline": "Midtown's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": "midtown.knowsbeauty.com",
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "midtown"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: midtown (id=%s)" % city_id)

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
            "address": biz.get("address", {}),
            "phone": biz.get("phone"),
            "website": biz.get("website"),
            "socials": socials,
            "short_description": biz.get("short_description"),
            "known_for": biz.get("short_description"),
            "price_cues": biz.get("price_cues"),
            "editors_pick": biz.get("editors_pick", False),
            "editors_pick_reason": biz.get("editors_pick_reason"),
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
        # doesn't lose their work — same pattern as every other city seed.
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
    print("Midtown seed complete:")
    print("  City:          midtown (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    await ensure_indexes()
    await seed_midtown()


if __name__ == "__main__":
    run(main())
