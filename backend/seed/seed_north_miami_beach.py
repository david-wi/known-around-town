"""Seed North Miami Beach for the Beauty network.

11 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_north_miami_beach

NOTE: Several NMB-address businesses were already seeded under the Sunny Isles
seed (seed_sunny_isles.py) and live in the DB under city "sunny-isles-beach":
  - Studio Viktor Hair (3963 NE 163rd St)
  - Bella Capelli Salon (1770 NE 174th St)
  - Lumière Nails Studio (1690 NE 163rd St)
  - Serenity Day Spa Sunny Isles (3661 NE 163rd St)
  - Brow + Lash Lab SIB (1750 NE 167th St)
  - Glam Room Sunny Isles (3900 NE 163rd St)
  - Gold Coast Aesthetics (3901 NE 163rd St)
The businesses below are all distinct from those.
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
    ("163rd-street-corridor",  "163rd Street Corridor",   "Urban & accessible",          4),
    ("biscayne-blvd-corridor", "Biscayne Blvd Corridor",  "Workhorse strip & well-served", 5),
    ("ne-167th-district",      "NE 167th Street District", "Neighborhood & local",         4),
    ("biscayne-gardens",       "Biscayne Gardens",         "Residential & community",      2),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "163rd-street-corridor": (
        "NE 163rd Street is North Miami Beach's main east-west artery — the place where "
        "the city does its everyday business. Strip plazas line both sides of the road "
        "between Biscayne Boulevard and the Intracoastal, and the beauty studios here "
        "reflect the neighborhood's practical character: well-priced, reliable, and built "
        "on returning clients rather than walk-in foot traffic. The 163rd corridor serves "
        "a genuinely diverse clientele — Latin, Haitian, Caribbean, and Eastern European — "
        "and the best spots here have learned to serve all of them well."
    ),
    "biscayne-blvd-corridor": (
        "Biscayne Boulevard runs the length of North Miami Beach from the Ojus area in the "
        "north to the Sunny Isles boundary in the south, and the plazas along it hold some "
        "of the city's most polished beauty addresses. The corridor sits at the western edge "
        "of NMB, close enough to Aventura's pull to attract studios that would be "
        "comfortable in that zip code — but with the unpretentious pricing that comes from "
        "genuinely serving a neighborhood rather than a mall. The 15800-block strip in "
        "particular has become a quiet concentration of quality."
    ),
    "ne-167th-district": (
        "NE 167th Street is the city's secondary commercial corridor — a dense stretch of "
        "small plazas and storefronts running east from Biscayne. It lacks the Biscayne "
        "Boulevard traffic but makes up for it in character: this is where multi-decade "
        "operators run their practices, where nail salons built on word-of-mouth thrive, "
        "and where the city's working community actually books their appointments. The "
        "clientele is diverse and the quality is real — just without the Instagram aesthetic."
    ),
    "biscayne-gardens": (
        "Biscayne Gardens is the residential neighborhood that fills the western interior "
        "of North Miami Beach — single-family homes, low-rise apartment complexes, and the "
        "kind of community fabric that sustains neighborhood barbershops and local studios "
        "for decades. The beauty businesses here don't advertise much. They don't need to. "
        "Regulars come back, and regulars bring their families."
    ),
}

# Fallback photos by category slug (shared with other city seeds)
# ── Businesses ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map:
#   hair | nails | spa | lash-brow | med-spa | barber | makeup | waxing
#
# All businesses verified via Yelp, Google Maps, Fresha, and/or official websites
# as of June 2026. Phone numbers are real — no 555-XXXX placeholders.

BUSINESSES: List[Dict[str, Any]] = [

    # ── HAIR — BISCAYNE BLVD CORRIDOR ────────────────────────────────────────
    {
        "name": "ONE11 Hair Studio",
        "slug": "one11-hair-studio-biscayne-blvd",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "15805 Biscayne Blvd, Suite 111", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(786) 657-3526",
        "website": "https://one11hairstudio.co",
        "instagram": "@one11hairstudio",
        "short_description": (
            "A contemporary salon in the 15805 Biscayne strip offering balayage, color, "
            "cuts, extensions, and barber services from a team that follows the newest "
            "trends without abandoning the classics. Clean, well-reviewed, and appointment-first "
            "with a diverse clientele that spans the surrounding residential blocks."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── HAIR — NE 167TH DISTRICT ──────────────────────────────────────────────
    {
        "name": "Auguste Beauty",
        "slug": "auguste-beauty-ne-167th",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["ne-167th-district"],
        "address": {"street": "365 NE 167th St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(786) 269-6758",
        "website": "https://augustebeauty.com",
        "instagram": None,
        "short_description": (
            "A luxury hair extensions studio on NE 167th Street specializing in 100% human "
            "hair extensions — tape-in, sew-in, keratin, and weft — alongside expert cutting "
            "and styling. The interior was designed by the same creative team behind Louis "
            "Vuitton and Dior retail spaces; the technique matches the ambition."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── NAILS — 163RD STREET CORRIDOR ────────────────────────────────────────
    {
        "name": "Queen Nails",
        "slug": "queen-nails-163rd-corridor",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["163rd-street-corridor"],
        "address": {"street": "1334 NE 163rd St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 947-7178",
        "website": "https://queennailsspanorthmiamibeach.com",
        "instagram": None,
        "short_description": (
            "A long-running neighborhood nail salon on the 163rd Street corridor offering "
            "manicures, pedicures, gel, dip powder, and acrylics with dependable quality "
            "and pricing that keeps a loyal local following coming back week after week."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },

    # ── NAILS — NE 167TH DISTRICT ─────────────────────────────────────────────
    {
        "name": "NG's Nails Spa",
        "slug": "ngs-nails-spa-ne-167th",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["ne-167th-district"],
        "address": {"street": "738 NE 167th St", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(786) 657-2567",
        "website": "https://ngsnailsspa.com",
        "instagram": None,
        "short_description": (
            "A well-reviewed nail salon on NE 167th Street known for clean technique, "
            "meticulous gel manicures, dip powder, pedicures, and lash services. NG's "
            "draws a consistent clientele from across NMB who prize precision and hygiene "
            "above flash — and come back for the results, not the décor."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "name": "Encore Nail Bar",
        "slug": "encore-nail-bar-ne-167th",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["ne-167th-district"],
        "address": {"street": "978 N Miami Beach Blvd", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 705-2388",
        "website": "https://encorenailbarnorthmiami.com",
        "instagram": "@encore_nailbar",
        "short_description": (
            "A modern nail bar in North Miami Beach offering gel manicures, dip powder, "
            "acrylics, Gel-X extensions, nail art, and luxury pedicures. Encore has built "
            "a strong local following with extended hours and a clean, welcoming environment "
            "that accommodates both walk-ins and booked appointments."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── NAILS — BISCAYNE BLVD CORRIDOR ───────────────────────────────────────
    {
        "name": "Soft Touch Nail & Spa",
        "slug": "soft-touch-nail-spa-biscayne-blvd",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "15979 Biscayne Blvd, Suite 4605", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 749-6006",
        "website": "https://softtouchnailspa.com",
        "instagram": "@softtouchnail.spa",
        "short_description": (
            "A polished nail salon on Biscayne Boulevard offering gel manicures, pedicures, "
            "dip powder, acrylics, and nail art in a comfortable, appointment-friendly "
            "setting. Soft Touch earns repeat visits for consistent quality and the kind "
            "of attentive service that keeps a Biscayne Blvd clientele coming back."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — BISCAYNE BLVD CORRIDOR ─────────────────────────────────
    {
        "name": "Yuny Studio Brows & Lashes",
        "slug": "yuny-studio-brows-lashes-biscayne-blvd",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "15805 Biscayne Blvd, Suite 109", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 602-5544",
        "website": "https://yuny-studio-brows-lashes.square.site",
        "instagram": "@yblashestudio",
        "short_description": (
            "A boutique lash and brow studio run by Yuniska Bonilla, a master lash artist "
            "specializing in classic, volume, and hybrid extensions alongside lash lifts, "
            "brow lamination, and brow tinting. Located in the same 15805 Biscayne building "
            "as ONE11 and Nava, Yuny has earned a loyal appointment-only clientele through "
            "meticulous technique and beautiful, lasting results."
        ),
        "price_cues": "$$",
        "editors_pick": True,
    },

    # ── MED-SPA — BISCAYNE BLVD CORRIDOR ─────────────────────────────────────
    {
        "name": "Nava Wellness & Med Spa",
        "slug": "nava-wellness-med-spa-biscayne-blvd",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "15805 Biscayne Blvd, Suite 102", "city": "North Miami Beach", "state": "FL", "postal_code": "33160", "country": "US"},
        "phone": "(305) 705-2300",
        "website": "https://navawellnessmedspa.com",
        "instagram": "@navawellnessandmedspa",
        "short_description": (
            "A Vogue-featured med spa with over 25 years on Biscayne Boulevard, specializing "
            "in post-operative care, customized facials, non-surgical body sculpting, hair "
            "loss treatments, and lymphatic drainage. Nava has built a reputation for "
            "medically grounded technique and the kind of discretion that post-surgery "
            "clients specifically seek out — a genuine institution on the corridor."
        ),
        "price_cues": "$$$",
        "editors_pick": True,
    },

    # ── WAXING — 163RD STREET CORRIDOR ───────────────────────────────────────
    {
        "name": "Wax Spa",
        "slug": "wax-spa-163rd-corridor",
        "category_slugs": ["waxing", "lash-brow"],
        "neighborhood_slugs": ["163rd-street-corridor"],
        "address": {"street": "1590 NE 162nd St, Suite 200", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 940-5141",
        "website": "https://www.waxspa.net",
        "instagram": None,
        "short_description": (
            "A dedicated waxing and brow studio on the 163rd Street corridor offering "
            "authentic Brazilian wax, full-body waxing, lash extensions, and permanent "
            "makeup including ombré brows and microblading. Wax Spa serves a loyal NMB "
            "clientele with extended weekday hours and a tidy, professional environment."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },

    # ── BARBER — BISCAYNE BLVD CORRIDOR ──────────────────────────────────────
    {
        "name": "Lavish Barber Studio",
        "slug": "lavish-barber-studio-biscayne-blvd",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["biscayne-blvd-corridor"],
        "address": {"street": "14382 Biscayne Blvd", "city": "North Miami Beach", "state": "FL", "postal_code": "33181", "country": "US"},
        "phone": "(786) 338-6099",
        "website": "https://lavishbarberstudio.com/miami-lavish-barber-studio",
        "instagram": None,
        "short_description": (
            "The Miami outpost of a premium Canadian barbershop brand, landing on Biscayne "
            "Boulevard with precision fades, scissor cuts, straight razor shaves, and beard "
            "sculpting that live up to the Lavish name. A deliberate step up from "
            "neighborhood shops — this is the kind of barber you clear an hour for."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── BARBER — BISCAYNE GARDENS ─────────────────────────────────────────────
    {
        "name": "Stay Fresh Barbershop",
        "slug": "stay-fresh-barbershop-biscayne-gardens",
        "category_slugs": ["barber"],
        "neighborhood_slugs": ["biscayne-gardens"],
        "address": {"street": "16768 NE 2nd Ave", "city": "North Miami Beach", "state": "FL", "postal_code": "33162", "country": "US"},
        "phone": "(305) 515-6994",
        "website": None,
        "instagram": None,
        "short_description": (
            "A neighborhood barbershop in the heart of Biscayne Gardens offering fades, "
            "tapers, skin fades, line-ups, and beard grooming with extended hours seven "
            "days a week. Stay Fresh is the kind of shop that fills up on a Saturday "
            "morning with regulars who've been coming since it opened — consistent, "
            "skilled, and unpretentious."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
]


async def seed_north_miami_beach() -> None:
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
        "slug": "north-miami-beach",
        "name": "North Miami Beach",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "North Miami Beach's most trusted beauty addresses.",
        "hero_description": (
            "An index of the nail artists, colorists, lash technicians, barbers, and "
            "estheticians that North Miami Beach locals actually book — from the Biscayne "
            "Boulevard corridor to NE 163rd, NE 167th, and the Biscayne Gardens "
            "neighborhood."
        ),
        "seo_title": "North Miami Beach Knows Beauty",
        "meta_description": (
            "The curated beauty directory for North Miami Beach, Florida — salons, nail bars, "
            "lash studios, med spas, and barbershops discovered by locals. Covering the "
            "163rd Street corridor, Biscayne Boulevard, NE 167th District, and Biscayne "
            "Gardens."
        ),
        "editorial_headlines": [
            {"headline": "North Miami Beach's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "north-miami-beach"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: north-miami-beach (id=%s)" % city_id)

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
    print("North Miami Beach seed complete:")
    print("  City:          north-miami-beach (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, Boca Raton, Aventura, and
    # Sunny Isles seeds — this script writes to the database. Refuse to run
    # against production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_north_miami_beach()


if __name__ == "__main__":
    run(main())
