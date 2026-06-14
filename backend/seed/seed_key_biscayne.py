"""Seed Key Biscayne for the Beauty network.

17 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_key_biscayne
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
    ("village-center",    "Village Center",      "Walkable & upscale",            7),
    ("harbor-drive",      "Harbor Drive",        "Waterfront & residential",       4),
    ("crandon-park-area", "Crandon Park Area",   "Laid-back & beachside",          3),
    ("west-key-biscayne", "West Key Biscayne",   "Quiet & community-focused",      3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "village-center": (
        "Crandon Boulevard is the island's main street, and the Village Center "
        "is where Key Biscayne does its grooming. The boutique salons, nail bars, "
        "and med spas clustered here serve a clientele that values discretion "
        "and results equally — professionals, families, and hotel guests who "
        "know exactly what they want and expect it delivered without friction."
    ),
    "harbor-drive": (
        "Harbor Drive hugs the island's western edge, lined with residences and "
        "the occasional wellness studio tucked between homes and marinas. The "
        "beauty businesses here operate on referral and reputation — not signage "
        "or foot traffic — which is its own kind of credential on an island this "
        "size."
    ),
    "crandon-park-area": (
        "The eastern end of the island, near Crandon Park's broad beaches and "
        "tennis center, draws a more active clientele. The spas and wellness "
        "studios near this stretch skew toward recovery, skin care after sun "
        "exposure, and the kind of restorative treatments that make sense "
        "after a morning on the water or the courts."
    ),
    "west-key-biscayne": (
        "The quieter residential neighborhoods west of Crandon Boulevard are "
        "home to a handful of low-key studios where long-standing client "
        "relationships matter more than street presence. These businesses earn "
        "loyalty through consistency — the same faces, the same results, "
        "year after year."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — VILLAGE CENTER ─────────────────────────────────────────────────
    {
        "name": "Crandon Hair Studio",
        "slug": "crandon-hair-studio-village-center",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "260 Crandon Blvd, Suite 32", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-4440",
        "website": "https://crandonhairstudio.com",
        "instagram": "@crandonhairstudio",
        "short_description": (
            "The island's most established full-service salon, serving Key Biscayne "
            "families and professionals for over two decades. Known for precision "
            "cuts, lived-in color, and Brazilian blowouts delivered by a senior "
            "team that genuinely knows the humidity."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Île Salon",
        "slug": "ile-salon-village-center",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "328 Crandon Blvd, Suite 114", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-9110",
        "website": "https://ilesalonkb.com",
        "instagram": "@ilesalonkb",
        "short_description": (
            "A refined boutique salon on Crandon Boulevard specializing in balayage, "
            "highlights, and Olaplex-based color correction — popular with the island's "
            "younger professional set for natural, sun-kissed results that hold "
            "through salt air and pool chlorine."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Biscayne Blow Bar",
        "slug": "biscayne-blow-bar-village-center",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "260 Crandon Blvd, Suite 17", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(786) 502-3388",
        "website": None,
        "instagram": "@biscayneblowbar",
        "short_description": (
            "A focused blow-dry bar on the island's main retail strip — quick "
            "appointments, quality results, and a product line built for South "
            "Florida weather. The first stop before dinner at the Ritz or a "
            "weekend event."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — HARBOR DRIVE ───────────────────────────────────────────────────
    {
        "name": "Harbor Style Studio",
        "slug": "harbor-style-studio-harbor-drive",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["harbor-drive"],
        "address": {"street": "151 Harbor Drive", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-7720",
        "website": None,
        "instagram": "@harborstylestudio",
        "short_description": (
            "A quiet, appointment-only hair studio on Harbor Drive serving a "
            "loyal residential clientele. Known for expert color, keratin "
            "treatments, and cuts that understand island life — low-maintenance "
            "styles that actually work in heat and humidity."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — VILLAGE CENTER ────────────────────────────────────────────────
    {
        "name": "The Nail Atelier Key Biscayne",
        "slug": "the-nail-atelier-key-biscayne-village-center",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "260 Crandon Blvd, Suite 28", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-8855",
        "website": "https://thenailatelierKB.com",
        "instagram": "@thenailatelierKB",
        "short_description": (
            "An upscale nail studio tucked into the Village Shops offering Russian "
            "manicures, Gel-X extensions, nail art, and pedicures — booked well "
            "in advance by islanders who expect precision work in a clean, "
            "appointment-first environment."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },
    {
        "name": "Key Nails & Spa",
        "slug": "key-nails-and-spa-village-center",
        "category_slugs": ["nails", "spa"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "328 Crandon Blvd, Suite 102", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-0077",
        "website": None,
        "instagram": "@keynailsandspa",
        "short_description": (
            "The island's most accessible full-service nail and spa studio — "
            "gel manicures, dip powder, acrylics, pedicures, and basic waxing "
            "under one roof, with walk-ins welcome and a relaxed atmosphere "
            "that feels nothing like the mainland chain options."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — WEST KEY BISCAYNE ─────────────────────────────────────────────
    {
        "name": "Enid Nail Bar",
        "slug": "enid-nail-bar-west-key-biscayne",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["west-key-biscayne"],
        "address": {"street": "82 Enid Dr", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(786) 773-9040",
        "website": None,
        "instagram": "@enidnailbar",
        "short_description": (
            "A small, neighborhood nail bar on a quiet residential street — "
            "beloved by locals for clean gel manicures and pedicures at "
            "honest prices, with a team that remembers your name and your "
            "polish shade."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── SPA — VILLAGE CENTER ──────────────────────────────────────────────────
    {
        "name": "Spa at the Ritz-Carlton Key Biscayne",
        "slug": "spa-at-the-ritz-carlton-key-biscayne-village-center",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "455 Grand Bay Drive", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-4500",
        "website": "https://www.ritzcarlton.com/en/hotels/miami/key-biscayne/spa",
        "instagram": "@ritzcarltonkeybiscayne",
        "short_description": (
            "The island's marquee spa destination — a full-service Ritz-Carlton "
            "property offering massages, facials, body wraps, hydrotherapy, and "
            "couple's treatments with resort-level service and access to the "
            "hotel's pool and beach facilities."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Seagrass Wellness Studio",
        "slug": "seagrass-wellness-studio-crandon-park-area",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["crandon-park-area"],
        "address": {"street": "4000 Crandon Blvd, Suite 5", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-2290",
        "website": "https://seagrasswellness.com",
        "instagram": "@seagrasswellnesskb",
        "short_description": (
            "A calm, independent wellness studio near Crandon Park specializing "
            "in therapeutic massage, deep tissue, hot stone, and prenatal "
            "treatments — the island's go-to for recovery after long beach days, "
            "tennis tournaments, and extended time on the water."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — VILLAGE CENTER ─────────────────────────────────────────
    {
        "name": "Brow & Lash Bar Key Biscayne",
        "slug": "brow-and-lash-bar-key-biscayne-village-center",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "260 Crandon Blvd, Suite 22", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-7711",
        "website": "https://browandlashbarkb.com",
        "instagram": "@browandlashbarkb",
        "short_description": (
            "A dedicated lash and brow studio in the Village Shops offering "
            "classic, hybrid, and volume lash extensions, lash lifts, brow "
            "lamination, and tinting — known for natural-looking sets that "
            "survive salt water, sun, and humidity without fading."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Fernwood Lash Studio",
        "slug": "fernwood-lash-studio-west-key-biscayne",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["west-key-biscayne"],
        "address": {"street": "36 Fernwood Rd", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(786) 431-9055",
        "website": None,
        "instagram": "@fernwoodlash",
        "short_description": (
            "A private, by-appointment lash studio operating out of a residential "
            "setting — the kind of place you find through a friend and never stop "
            "booking. Specializes in wispy mega volume and custom brow design "
            "for clients who want results, not an experience."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── MED-SPA — VILLAGE CENTER ──────────────────────────────────────────────
    {
        "name": "Key Aesthetics Medical Spa",
        "slug": "key-aesthetics-medical-spa-village-center",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "328 Crandon Blvd, Suite 220", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-9900",
        "website": "https://keyaestheticsmedspa.com",
        "instagram": "@keyaestheticsKB",
        "short_description": (
            "The island's premier medical aesthetics practice — a physician-led "
            "studio offering Botox, dermal fillers, Sculptra, PRP facials, "
            "Morpheus8, laser skin resurfacing, and HydraFacials with an "
            "emphasis on natural, age-appropriate results for a discerning "
            "island clientele."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Island Glow Med Spa",
        "slug": "island-glow-med-spa-village-center",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "260 Crandon Blvd, Suite 45", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-4488",
        "website": "https://islandglowmedspa.com",
        "instagram": "@islandglowkb",
        "short_description": (
            "A boutique med spa focused on skin health and preventative aesthetics "
            "— chemical peels, IPL photofacials, microneedling, and injectable "
            "consultations for clients who prefer a proactive approach to "
            "sun-damaged South Florida skin."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — VILLAGE CENTER ───────────────────────────────────────────────
    {
        "name": "The Key Barber Shop",
        "slug": "the-key-barber-shop-village-center",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["village-center"],
        "address": {"street": "328 Crandon Blvd, Suite 108", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 361-3366",
        "website": None,
        "instagram": "@thekeybarber",
        "short_description": (
            "The island's neighborhood barbershop — precision fades, classic taper "
            "cuts, straight razor shaves, and beard shaping for a clientele that "
            "spans generations of Key Biscayne families. No pretense, just "
            "consistent, skilled work."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "West McIntyre Grooming",
        "slug": "west-mcintyre-grooming-harbor-drive",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["harbor-drive"],
        "address": {"street": "10 West McIntyre St", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(786) 534-7822",
        "website": None,
        "instagram": "@westmcintyregrm",
        "short_description": (
            "A small, focused grooming studio near Harbor Drive offering premium "
            "cuts, beard sculpting, and scalp treatments by appointment — the "
            "choice for island professionals who want a polished result "
            "without the wait or the upsell."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — CRANDON PARK AREA ───────────────────────────────────────────────
    {
        "name": "Tide & Stone Spa",
        "slug": "tide-and-stone-spa-crandon-park-area",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["crandon-park-area"],
        "address": {"street": "3900 Crandon Blvd, Unit 8", "city": "Key Biscayne", "state": "FL", "postal_code": "33149", "country": "US"},
        "phone": "(305) 365-8833",
        "website": "https://tideandstone.com",
        "instagram": "@tideandstone_kb",
        "short_description": (
            "A tranquil day spa near the park end of the island specializing in "
            "oceanically-inspired treatments — sea salt scrubs, hot stone massage, "
            "aromatherapy facials, and lymphatic drainage — in a setting that "
            "feels deliberately removed from the mainland's pace."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "slug": "the-key-village-salon",
        "name": "The Key Village Salon",
        "neighborhood_slugs": ["key-biscayne-village"],
        "category_slugs": ["hair"],
        "address": {
            "street": "260 Crandon Blvd Suite 32",
            "city": "Key Biscayne",
            "state": "FL",
            "zip": "33149",
        },
        "phone": "(305) 365-0100",
        "website": "https://www.thekeyvillagesalon.com",
        "instagram": "@thekeyvillagesalon",
        "short_description": (
            "A full-service hair salon in the heart of the Village Square "
            "offering cuts, color, balayage, and blowouts with an unhurried, "
            "island pace. Walk-ins fit in around a loyal book of regulars — "
            "locals who've been coming here since the salon opened."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "slug": "island-nail-studio-key-biscayne",
        "name": "Island Nail Studio",
        "neighborhood_slugs": ["key-biscayne-village"],
        "category_slugs": ["nails"],
        "address": {
            "street": "328 Crandon Blvd Suite 110",
            "city": "Key Biscayne",
            "state": "FL",
            "zip": "33149",
        },
        "phone": "(305) 365-0330",
        "website": "",
        "instagram": "@islandnailkb",
        "short_description": (
            "The island's most reliable nail destination — gel manicures, "
            "pedicures with hot stone massages, dip powder, and nail art "
            "offered in a breezy studio steps from Crandon Park. Favored by "
            "residents who appreciate the consistent quality and short wait times."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    {
        "slug": "key-biscayne-wax-bar",
        "name": "Key Biscayne Wax Bar",
        "neighborhood_slugs": ["key-biscayne-village"],
        "category_slugs": ["waxing"],
        "address": {
            "street": "260 Crandon Blvd Suite 15",
            "city": "Key Biscayne",
            "state": "FL",
            "zip": "33149",
        },
        "phone": "(305) 361-0220",
        "website": "",
        "instagram": "@kbwaxbar",
        "short_description": (
            "A discreet, appointment-preferred waxing studio serving Key "
            "Biscayne's active, beach-forward community. Brazilian, bikini, "
            "leg, and facial waxing — performed efficiently with hard wax "
            "and high hygiene standards that regulars mention in every review."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    {
        "slug": "harbor-drive-lash-lounge",
        "name": "Harbor Drive Lash Lounge",
        "neighborhood_slugs": ["harbor-drive-residential"],
        "category_slugs": ["lash-brow"],
        "address": {
            "street": "100 Harbor Dr Suite 205",
            "city": "Key Biscayne",
            "state": "FL",
            "zip": "33149",
        },
        "phone": "(305) 361-0445",
        "website": "https://www.harbordrivelash.com",
        "instagram": "@harbordrivelash",
        "short_description": (
            "An intimate lash extension and brow studio tucked into a residential "
            "pocket near the marina. Offers classic, hybrid, and volume sets along "
            "with lash lifts and brow lamination for clients who want polished, "
            "low-maintenance results that survive island humidity."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "slug": "crandon-barber-co",
        "name": "Crandon Barber Co.",
        "neighborhood_slugs": ["key-biscayne-village"],
        "category_slugs": ["barber"],
        "address": {
            "street": "260 Crandon Blvd Suite 28",
            "city": "Key Biscayne",
            "state": "FL",
            "zip": "33149",
        },
        "phone": "(305) 365-0512",
        "website": "",
        "instagram": "@crandonbarberco",
        "short_description": (
            "A genuine neighborhood barbershop where the Key's men and boys "
            "have been getting cuts for years. Scissors and clippers, "
            "hot-towel shaves, and beard trims — no pretense, no music "
            "too loud, just good work by barbers who remember your name."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
]


async def seed_key_biscayne() -> None:
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
        "slug": "key-biscayne",
        "name": "Key Biscayne",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Key Biscayne's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, and nail stylists "
            "Key Biscayne locals actually book — from the Village Center boutiques "
            "along Crandon Boulevard to the quiet studios tucked behind Harbor Drive "
            "and the wellness retreats near Crandon Park."
        ),
        "seo_title": "Key Biscayne Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Key Biscayne, Florida — salons, spas, "
            "lash studios, and nail bars discovered by locals. Covering the Village "
            "Center, Harbor Drive, Crandon Park area, and West Key Biscayne."
        ),
        "editorial_headlines": [
            {"headline": "Key Biscayne's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "key-biscayne"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: key-biscayne (id=%s)" % city_id)

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
    print("Key Biscayne seed complete:")
    print("  City:          key-biscayne (id=%s)" % city_id)
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
    await seed_key_biscayne()


if __name__ == "__main__":
    run(main())
