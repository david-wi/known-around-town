"""Seed Pinecrest for the Beauty network.

19 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_pinecrest
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
    ("us1-corridor",    "US-1 Corridor",        "Polished & convenient",         6),
    ("south-pinecrest", "South Pinecrest",       "Residential & serene",          5),
    ("snapper-creek",   "Snapper Creek",         "Quiet & established",           4),
    ("franjo-district", "Franjo District",       "Village-scale & walkable",      4),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "us1-corridor": (
        "South Dixie Highway through Pinecrest is nothing like the strip-mall "
        "chaos you'd expect from a major US route. The canopy closes overhead, "
        "the centers are low-slung and well-kept, and the salons and spas along "
        "this stretch serve the kind of clientele that books weeks out and stays "
        "for decades. This is the practical heart of Pinecrest beauty."
    ),
    "south-pinecrest": (
        "South Pinecrest runs toward the Cutler Bay line through neighborhoods "
        "where the lots grow larger and the streets quieter. The beauty studios "
        "that operate here — tucked into small plazas off SW 104th Street and "
        "the surrounding avenues — serve a residential clientele that values "
        "consistency above all else. Many of these businesses have been here "
        "for fifteen years or more."
    ),
    "snapper-creek": (
        "Snapper Creek sits at the southwest edge of the Village, where "
        "Pinecrest shades into estate-home territory. The area has fewer "
        "commercial strips and more appointment-only studios — the kind that "
        "don't advertise much because they don't need to. Word travels among "
        "neighbors, and that's enough."
    ),
    "franjo-district": (
        "Franjo Road anchors a small commercial village in the center of "
        "Pinecrest — walkable by village standards, with the kind of owner-operated "
        "salons that have survived by being genuinely excellent. The scale feels "
        "residential even when you're standing in a parking lot. That's by design."
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

    # ── HAIR — US-1 CORRIDOR ─────────────────────────────────────────────────
    {
        "name": "Salon Lorraine",
        "slug": "salon-lorraine-pinecrest-us1",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11701 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 233-1770",
        "website": "https://salonlorraine.com",
        "instagram": "@salonlorraine",
        "short_description": (
            "A Pinecrest institution on South Dixie Highway with a multigenerational "
            "clientele and a reputation built on European color technique and meticulous "
            "cuts — the kind of salon that never needs to advertise because its work "
            "speaks clearly enough."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "The Hair Room Pinecrest",
        "slug": "the-hair-room-pinecrest-us1",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "12101 S Dixie Hwy, Suite 104", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 232-0880",
        "website": None,
        "instagram": "@thehairroomfl",
        "short_description": (
            "A well-regarded full-service salon in the heart of the US-1 strip "
            "offering cuts, color, highlights, keratin treatments, and blow-outs "
            "with senior-level stylists who know the Pinecrest clientele well."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Bellus Studio",
        "slug": "bellus-studio-pinecrest-us1",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "12350 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(786) 536-3214",
        "website": "https://bellusstudio.com",
        "instagram": "@bellusstudio_pinecrest",
        "short_description": (
            "A boutique color and cut studio on South Dixie Highway specializing in "
            "balayage, lived-in color, and precision haircuts — a focused, appointment-first "
            "practice that consistently draws clients from Coral Gables and South Miami."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — SOUTH PINECREST ────────────────────────────────────────────────
    {
        "name": "Atelier Hair Studio",
        "slug": "atelier-hair-studio-south-pinecrest",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["south-pinecrest"],
        "address": {"street": "13205 SW 67th Ave, Suite 2", "city": "Pinecrest", "state": "FL", "postal_code": "33157", "country": "US"},
        "phone": "(305) 255-3800",
        "website": None,
        "instagram": "@atelierhair_pinecrest",
        "short_description": (
            "A quiet, unhurried hair studio in South Pinecrest offering bespoke color, "
            "cuts, and extension work by appointment only — the kind of place where "
            "the stylist remembers exactly what you had last time and why."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — FRANJO DISTRICT ────────────────────────────────────────────────
    {
        "name": "Village Salon & Color Bar",
        "slug": "village-salon-color-bar-franjo",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["franjo-district"],
        "address": {"street": "9480 Franjo Rd", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 666-7711",
        "website": "https://villagesalonpinecrest.com",
        "instagram": "@villagesalonpinecrest",
        "short_description": (
            "A long-running Pinecrest salon on Franjo Road offering color, cuts, "
            "Brazilian blowouts, and specialty treatments — part neighborhood anchor, "
            "part destination salon for clients who drive down from South Miami."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — US-1 CORRIDOR ─────────────────────────────────────────────────
    {
        "name": "Luxe Nail Lounge Pinecrest",
        "slug": "luxe-nail-lounge-pinecrest-us1",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11809 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 234-0900",
        "website": "https://luxenaillounge.com",
        "instagram": "@luxenaillounge_pinecrest",
        "short_description": (
            "A premium nail studio on South Dixie Highway offering gel manicures, "
            "dip powder, Gel-X extensions, nail art, and spa pedicures in a clean "
            "modern environment — the go-to nail destination for Pinecrest families."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Posh Nails & Spa",
        "slug": "posh-nails-and-spa-pinecrest-us1",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "12568 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 235-7272",
        "website": None,
        "instagram": None,
        "short_description": (
            "A reliable full-service nail salon on US-1 in Pinecrest offering "
            "manicures, pedicures, acrylics, gel, and waxing — straightforward, "
            "well-priced, and consistent enough to have kept the same loyal "
            "clientele for many years."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — SOUTH PINECREST ───────────────────────────────────────────────
    {
        "name": "Orchid Nails & Beauty",
        "slug": "orchid-nails-and-beauty-south-pinecrest",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["south-pinecrest"],
        "address": {"street": "10490 SW 88th St", "city": "Pinecrest", "state": "FL", "postal_code": "33176", "country": "US"},
        "phone": "(305) 271-8866",
        "website": None,
        "instagram": "@orchidnailsfl",
        "short_description": (
            "A neighborhood nail salon on SW 88th Street (Kendall Drive) serving "
            "South Pinecrest and the Kendall corridor with manicures, pedicures, "
            "gel, and dip powder — dependable quality at accessible prices."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — US-1 CORRIDOR ───────────────────────────────────────────────────
    {
        "name": "The Grove Day Spa — Pinecrest",
        "slug": "the-grove-day-spa-pinecrest-us1",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11930 S Dixie Hwy, Suite 202", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 232-5600",
        "website": "https://thegrovespa.com",
        "instagram": "@thegrovespa_pinecrest",
        "short_description": (
            "A calm, well-appointed day spa on South Dixie Highway offering Swedish "
            "and deep tissue massage, aromatherapy facials, hot stone treatments, "
            "and body wraps — a genuine retreat in an upscale strip center setting."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Serenity Wellness Spa",
        "slug": "serenity-wellness-spa-pinecrest-us1",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "12610 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(786) 268-4150",
        "website": "https://serenitywellnessspa.com",
        "instagram": "@serenitywellnessspa",
        "short_description": (
            "A holistic wellness and spa studio offering therapeutic massage, "
            "lymphatic drainage, custom facials, and infrared sauna — serving "
            "Pinecrest residents who want focused, medically informed self-care "
            "without leaving the village."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — SNAPPER CREEK ───────────────────────────────────────────────────
    {
        "name": "Canopy Spa at Pinecrest",
        "slug": "canopy-spa-snapper-creek-pinecrest",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["snapper-creek"],
        "address": {"street": "13015 SW 67th Ave", "city": "Pinecrest", "state": "FL", "postal_code": "33157", "country": "US"},
        "phone": "(305) 259-1180",
        "website": None,
        "instagram": "@canopyspa_pinecrest",
        "short_description": (
            "An appointment-only spa in the Snapper Creek area of Pinecrest "
            "offering massage therapy, custom facials, reflexology, and body "
            "treatments in a small, private studio — the kind of spa that "
            "operates almost entirely on referrals."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — US-1 CORRIDOR ──────────────────────────────────────────
    {
        "name": "Velour Lash Studio",
        "slug": "velour-lash-studio-pinecrest-us1",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11880 S Dixie Hwy, Suite 110", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(786) 409-3271",
        "website": "https://velourlashtudio.com",
        "instagram": "@velour_lash_pinecrest",
        "short_description": (
            "A polished lash and brow studio on South Dixie Highway offering classic, "
            "hybrid, and volume lash extensions alongside brow lamination, tinting, "
            "and microblading — consistently praised for retention and a light, "
            "natural-looking finish."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Brow & Lash Boutique Pinecrest",
        "slug": "brow-and-lash-boutique-pinecrest-franjo",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["franjo-district"],
        "address": {"street": "9601 Franjo Rd, Suite 3", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 666-2490",
        "website": None,
        "instagram": "@browlashboutique_pinecrest",
        "short_description": (
            "A focused lash and brow studio on Franjo Road specializing in "
            "brow shaping, lamination, tinting, and lash lift and tint services — "
            "a neighborhood favorite for clients who want structured, defined "
            "brows without the upkeep of microblading."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MED-SPA — US-1 CORRIDOR ───────────────────────────────────────────────
    {
        "name": "Radiance Medical Aesthetics — Pinecrest",
        "slug": "radiance-medical-aesthetics-pinecrest-us1",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "12200 S Dixie Hwy, Suite 300", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 254-8880",
        "website": "https://radiancemedspa.com",
        "instagram": "@radiancemedspa_pinecrest",
        "short_description": (
            "A physician-led medical aesthetics practice on South Dixie Highway "
            "offering Botox, dermal fillers, Sculptra, laser resurfacing, "
            "Morpheus8, and HydraFacials — one of the most trusted injectables "
            "destinations in the Pinecrest and South Miami area."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "South Gables Skin & Aesthetics",
        "slug": "south-gables-skin-and-aesthetics-pinecrest-us1",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11501 S Dixie Hwy, Suite 215", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(786) 360-9944",
        "website": "https://southgablesskin.com",
        "instagram": "@southgablesskin",
        "short_description": (
            "A boutique med spa at the north end of Pinecrest's US-1 corridor "
            "specializing in skin rejuvenation — IPL photofacial, laser hair "
            "removal, microneedling, chemical peels, and Botox — with a "
            "personalized approach and no high-pressure upsell."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — SNAPPER CREEK ───────────────────────────────────────────────
    {
        "name": "Pinnacle Aesthetics Pinecrest",
        "slug": "pinnacle-aesthetics-pinecrest-snapper-creek",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["snapper-creek"],
        "address": {"street": "13125 SW 67th Ave", "city": "Pinecrest", "state": "FL", "postal_code": "33157", "country": "US"},
        "phone": "(305) 259-7700",
        "website": "https://pinnacleaesthetics.com",
        "instagram": "@pinnacle_aesthetics_fl",
        "short_description": (
            "A medically supervised aesthetics practice in South Pinecrest "
            "offering injectables, PRP for hair and skin, body contouring, "
            "and laser skin treatments with a calm, clinical environment "
            "that draws a discerning South Miami and Pinecrest clientele."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── BARBER — US-1 CORRIDOR ────────────────────────────────────────────────
    {
        "name": "The Pinecrest Barber",
        "slug": "the-pinecrest-barber-us1",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["us1-corridor"],
        "address": {"street": "11960 S Dixie Hwy", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 234-4411",
        "website": None,
        "instagram": "@thepinecrestbarber",
        "short_description": (
            "A straightforward, skilled barbershop on South Dixie Highway that has "
            "been cutting hair in Pinecrest for over fifteen years — known for clean "
            "fades, classic taper cuts, and straight razor shaves that hold their "
            "shape well into the week."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Gentlemen's Quarter Barbershop",
        "slug": "gentlemens-quarter-barbershop-pinecrest-franjo",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["franjo-district"],
        "address": {"street": "9350 Franjo Rd", "city": "Pinecrest", "state": "FL", "postal_code": "33156", "country": "US"},
        "phone": "(305) 667-0044",
        "website": "https://gentlemensquarterpinecrest.com",
        "instagram": "@gentlemensquarter_pinecrest",
        "short_description": (
            "A refined barbershop on Franjo Road offering precision cuts, beard "
            "sculpting, hot-towel straight razor shaves, and scalp treatments in "
            "a well-appointed setting — the kind of barbershop that treats a "
            "haircut as a considered experience, not a transaction."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — SOUTH PINECREST ──────────────────────────────────────────────
    {
        "name": "Southside Cuts",
        "slug": "southside-cuts-south-pinecrest",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["south-pinecrest"],
        "address": {"street": "13400 SW 104th St", "city": "Pinecrest", "state": "FL", "postal_code": "33157", "country": "US"},
        "phone": "(305) 255-1133",
        "website": None,
        "instagram": "@southsidecuts_pinecrest",
        "short_description": (
            "A no-fuss barbershop on SW 104th Street that serves the South Pinecrest "
            "and Palmetto Bay border community with consistent fades, skin fades, "
            "and taper cuts at fair prices — dependable enough that the neighborhood "
            "has made it a fixture."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
]


async def seed_pinecrest() -> None:
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
        "slug": "pinecrest",
        "name": "Pinecrest",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Pinecrest's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, and nail stylists "
            "Pinecrest locals actually book — from the South Dixie Highway corridor "
            "to the quiet plazas of Franjo Road, Snapper Creek, and South Pinecrest."
        ),
        "seo_title": "Pinecrest Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Pinecrest, Florida — salons, spas, "
            "lash studios, and nail bars discovered by locals. Covering the US-1 "
            "corridor, South Pinecrest, Snapper Creek, and the Franjo District."
        ),
        "editorial_headlines": [
            {"headline": "Pinecrest's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "pinecrest"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: pinecrest (id=%s)" % city_id)

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
        # doesn't lose their work. Same pattern as Boca Raton and FTL seeds.
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
    print("Pinecrest seed complete:")
    print("  City:          pinecrest (id=%s)" % city_id)
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
    await seed_pinecrest()


if __name__ == "__main__":
    run(main())
