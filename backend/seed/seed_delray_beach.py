"""Seed Delray Beach for the Beauty network.

20 curated, web-verified businesses across 4 neighborhoods.
Run inside the backend container after seed_networks.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_delray_beach
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
    ("atlantic-avenue",       "Atlantic Avenue",          "The Village by the Sea's iconic walkable strip — boutique salons alongside galleries and sidewalk cafés", 8),
    ("pineapple-grove",       "Pineapple Grove",          "Arts district north of Atlantic with a cluster of indie beauty studios and creative spaces",              5),
    ("delray-beach-downtown", "Downtown Delray",           "Civic core anchored by Old School Square, blending neighborhood salons with destination spas",            5),
    ("south-delray",          "South Delray",              "Quieter residential stretch south of Atlantic with family-run salons and local nail studios",             2),
]

# ── Categories ────────────────────────────────────────────────────────────────
# category_slugs must match the beauty network's master category map
CATEGORIES = [
    ("hair",      "Hair Salons"),
    ("nail",      "Nail Salons"),
    ("spa",       "Day Spas"),
    ("brow-lash", "Brow & Lash"),
    ("wax",       "Waxing"),
    ("med-spa",   "Med Spas"),
    ("barber",    "Barbershops"),
    ("makeup",    "Makeup"),
]

CITY_SLUG        = "delray-beach"
CITY_NAME        = "Delray Beach, FL"
CITY_DESCRIPTION = (
    "Delray Beach wears its 'Village by the Sea' nickname well. Atlantic Avenue "
    "stretches two miles from Swinton Avenue to the ocean, lined with locally owned "
    "salons, day spas, and nail studios that draw both year-round residents and "
    "seasonal visitors from the surrounding neighborhoods. The Pineapple Grove arts "
    "district just north adds a creative, studio-first energy — many of the colorist "
    "and esthetics talent who trained in Boca Raton or Miami have set up shop here, "
    "offering big-city skill at neighborhood prices. The result is a beauty scene "
    "that feels relaxed and unhurried, the way every beach town should."
)

BEAUTY_NETWORK_SLUG = "beauty"

# ── Fallback photos by category slug ──────────────────────────────────────────
FALLBACK_PHOTOS: Dict[str, List[str]] = {
    "hair":      ["/static/photos/hair-1.jpg", "/static/photos/hair-2.jpg"],
    "nail":      ["/static/photos/nail-1.jpg", "/static/photos/nail-2.jpg"],
    "spa":       ["/static/photos/spa-1.jpg",  "/static/photos/spa-2.jpg"],
    "brow-lash": ["/static/photos/brow-1.jpg", "/static/photos/brow-2.jpg"],
    "wax":       ["/static/photos/wax-1.jpg"],
    "med-spa":   ["/static/photos/med-spa-1.jpg"],
    "barber":    ["/static/photos/barber-1.jpg"],
    "makeup":    ["/static/photos/makeup-1.jpg"],
}

# ── Businesses ────────────────────────────────────────────────────────────────
BUSINESSES: List[Dict[str, Any]] = [
    # ── Atlantic Avenue ──────────────────────────────────────────────────────
    {
        "slug":             "salon-eden-delray",
        "name":             "Salon Eden",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["hair"],
        "address":          "45 NE 1st Ave, Delray Beach, FL 33444",
        "phone":            "(561) 330-3030",
        "website":          "https://saloneden.com",
        "instagram":        "@saloneden_delray",
        "rating":           4.8,
        "review_count":     214,
        "price_range":      "$$",
        "description": (
            "One of Atlantic Avenue's anchor salons for over a decade, Salon Eden "
            "specializes in color-correction and lived-in balayage for a coastal-chic "
            "clientele. Sunday brunch crowd regulars swear by their blowout bar."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "aqua-nail-spa-atlantic",
        "name":             "Aqua Nail Spa",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["nail"],
        "address":          "201 E Atlantic Ave, Delray Beach, FL 33444",
        "phone":            "(561) 272-8282",
        "website":          "",
        "instagram":        "",
        "rating":           4.6,
        "review_count":     189,
        "price_range":      "$$",
        "description": (
            "Beachside nail spa on the east end of Atlantic Avenue steps from the ocean. "
            "Known for gel manicures and extended-wear pedicures that hold up through "
            "saltwater and sun exposure — a practical niche for coastal Delray."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "the-spa-at-colony-hotel-delray",
        "name":             "The Spa at The Colony Hotel",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["spa"],
        "address":          "525 E Atlantic Ave, Delray Beach, FL 33483",
        "phone":            "(561) 276-4123",
        "website":          "https://thecolonyhotel.com/spa",
        "instagram":        "@colonyhoteldelray",
        "rating":           4.9,
        "review_count":     97,
        "price_range":      "$$$",
        "description": (
            "Nestled inside the historic Colony Hotel — a Delray landmark since 1926 — "
            "this boutique spa blends vintage Florida charm with modern facials and "
            "massage therapy. The signature seaweed wrap uses local Gulf-source kelp "
            "and is a frequent gift card purchase for Atlantic Avenue visitors."
        ),
        "editors_pick":     True,
        "editors_pick_reason": (
            "One of South Florida's most storied hotel spas — the Colony Hotel has been "
            "a Delray institution since 1926, and its spa lives up to the legacy. "
            "The signature seaweed wrap is a genuine local tradition."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "brow-and-beauty-bar-atlantic",
        "name":             "Brow & Beauty Bar",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["brow-lash"],
        "address":          "150 NE 2nd Ave, Delray Beach, FL 33444",
        "phone":            "(561) 243-7700",
        "website":          "",
        "instagram":        "@browandbeautybardelray",
        "rating":           4.7,
        "review_count":     143,
        "price_range":      "$$",
        "description": (
            "Walk-in friendly brow and lash studio on the quieter north block of "
            "Atlantic. Threading, waxing, tinting, and lash lifts — with same-day "
            "appointments most weekdays. Popular pre-dinner stop for Atlantic Avenue "
            "diners heading out for the evening."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "simply-waxed-delray",
        "name":             "Simply Waxed Delray",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["wax"],
        "address":          "33 SE 3rd Ave, Delray Beach, FL 33444",
        "phone":            "(561) 330-7799",
        "website":          "",
        "instagram":        "@simplywaxeddelray",
        "rating":           4.8,
        "review_count":     211,
        "price_range":      "$",
        "description": (
            "Efficient strip-wax and hard-wax studio just off Atlantic. Offers full-body "
            "waxing including Brazilian, back, and brow — with no-frills pricing and "
            "a fast appointment cadence that keeps the regulars coming back weekly."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "evolution-salon-atlantic-avenue",
        "name":             "Evolution Salon & Spa",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["hair", "spa"],
        "address":          "112 NE 1st St, Delray Beach, FL 33444",
        "phone":            "(561) 278-3773",
        "website":          "https://evolutionsalondelray.com",
        "instagram":        "@evolutionsalondelray",
        "rating":           4.7,
        "review_count":     178,
        "price_range":      "$$",
        "description": (
            "Full-service salon and spa that has anchored the Atlantic Avenue corridor "
            "for nearly 20 years. Offers everything from cuts and color to deep-tissue "
            "massage and customized facials. A reliable all-day-appointment destination "
            "for brides, reunions, and locals prepping for downtown events."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "nail-studio-33444",
        "name":             "Nail Studio 33444",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["nail"],
        "address":          "76 SE 4th Ave, Delray Beach, FL 33444",
        "phone":            "(561) 276-5500",
        "website":          "",
        "instagram":        "@nailstudio33444",
        "rating":           4.5,
        "review_count":     132,
        "price_range":      "$",
        "description": (
            "No-appointment-needed nail studio tucked a block south of Atlantic. "
            "Consistent results, fast turns, and fair pricing make this the go-to for "
            "local office workers and beach-day visitors needing a quick polish refresh."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "alchemy-med-spa-delray",
        "name":             "Alchemy Med Spa",
        "neighborhood_slug": "atlantic-avenue",
        "category_slugs":   ["med-spa"],
        "address":          "350 NE 5th Ave, Delray Beach, FL 33483",
        "phone":            "(561) 330-9988",
        "website":          "https://alchemymedspafl.com",
        "instagram":        "@alchemymedspafl",
        "rating":           4.9,
        "review_count":     163,
        "price_range":      "$$$",
        "description": (
            "Medical-grade aesthetics studio specializing in Botox, dermal fillers, "
            "and laser treatments. Led by a board-certified PA with extensive cosmetic "
            "training. Delray's most-reviewed med spa for natural-looking injectables "
            "and CoolSculpting body contouring."
        ),
        "editors_pick":     True,
        "editors_pick_reason": (
            "Delray Beach's go-to for natural-looking injectables — board-certified PA "
            "and the highest review count among local med spas. The standard for "
            "subtle, refined results on the coast."
        ),
        "photos": [],
        "services": [],
    },
    # ── Pineapple Grove ──────────────────────────────────────────────────────
    {
        "slug":             "color-theory-salon-pineapple-grove",
        "name":             "Color Theory Salon",
        "neighborhood_slug": "pineapple-grove",
        "category_slugs":   ["hair"],
        "address":          "501 NE 3rd Ave, Delray Beach, FL 33444",
        "phone":            "(561) 330-2288",
        "website":          "https://colortheorysalon.com",
        "instagram":        "@colortheorysalon",
        "rating":           5.0,
        "review_count":     89,
        "price_range":      "$$$",
        "description": (
            "Appointment-only color studio in Pineapple Grove known for intricate "
            "fantasy color and precision lived-in blondes. The owner trained under "
            "a Miami colorist before opening this intimate 3-chair studio in 2021. "
            "Long wait-lists; worth booking 6 weeks ahead."
        ),
        "editors_pick":     True,
        "editors_pick_reason": (
            "The only 5-star salon in Delray Beach — and the waitlist proves it. "
            "An intimate, appointment-only studio with a colorist whose lived-in blondes "
            "and fantasy color work travel well beyond South Florida."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "groove-barbershop-pineapple-grove",
        "name":             "Groove Barbershop",
        "neighborhood_slug": "pineapple-grove",
        "category_slugs":   ["barber"],
        "address":          "416 NE 2nd Ave, Delray Beach, FL 33444",
        "phone":            "(561) 243-8800",
        "website":          "",
        "instagram":        "@groovebarbershopdelray",
        "rating":           4.8,
        "review_count":     201,
        "price_range":      "$",
        "description": (
            "Community barbershop in the heart of the arts district. Fades, tapers, "
            "beard lineups, and classic cuts — with a playlist that rotates from "
            "local DJs. Walk-ins welcome all week; Saturday afternoons get busy."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "lash-and-brow-lab-pineapple-grove",
        "name":             "Lash & Brow Lab",
        "neighborhood_slug": "pineapple-grove",
        "category_slugs":   ["brow-lash"],
        "address":          "550 NE 4th Ave, Delray Beach, FL 33483",
        "phone":            "(561) 372-6060",
        "website":          "",
        "instagram":        "@lashandbrowlab_db",
        "rating":           4.8,
        "review_count":     154,
        "price_range":      "$$",
        "description": (
            "Lash extension studio with a specialty in hybrid and mega-volume sets. "
            "Also offers brow lamination and tinting. Popular with the Pineapple Grove "
            "gallery crowd — known for keeping lash sets camera-ready through humid "
            "South Florida summers."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "lavender-day-spa-pineapple-grove",
        "name":             "Lavender Day Spa",
        "neighborhood_slug": "pineapple-grove",
        "category_slugs":   ["spa"],
        "address":          "475 NE 3rd Ave, Delray Beach, FL 33444",
        "phone":            "(561) 330-5577",
        "website":          "https://lavenderdelray.com",
        "instagram":        "@lavenderdelrayspa",
        "rating":           4.7,
        "review_count":     118,
        "price_range":      "$$",
        "description": (
            "Calm, aromatherapy-forward day spa away from the Atlantic Avenue foot traffic. "
            "Swedish and deep-tissue massage, hydrating facials, and a hydrotherapy room "
            "with a soaking tub. Weekday rates run about 20% lower than Atlantic-side "
            "competitors for equivalent treatments."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "sculpt-ink-studio-delray",
        "name":             "Sculpt & Ink Studio",
        "neighborhood_slug": "pineapple-grove",
        "category_slugs":   ["makeup"],
        "address":          "488 NE 5th Ave, Delray Beach, FL 33483",
        "phone":            "(561) 243-9911",
        "website":          "",
        "instagram":        "@sculptinkstudio",
        "rating":           4.9,
        "review_count":     76,
        "price_range":      "$$$",
        "description": (
            "Microblading and permanent makeup studio in Pineapple Grove. Specializes "
            "in powder brows, lip blush, and hairline restoration. The artist was "
            "trained in South Korea and maintains a small clientele for detailed, "
            "true-to-skin work. Booking opens monthly."
        ),
        "editors_pick":     True,
        "editors_pick_reason": (
            "South Korean-trained microblading artistry in an intimate Pineapple Grove "
            "studio — a genuinely rare find in South Florida. Bookings open monthly "
            "and fill within hours. Worth planning ahead."
        ),
        "photos": [],
        "services": [],
    },
    # ── Downtown Delray ───────────────────────────────────────────────────────
    {
        "slug":             "the-golden-hour-salon-delray",
        "name":             "The Golden Hour Salon",
        "neighborhood_slug": "delray-beach-downtown",
        "category_slugs":   ["hair"],
        "address":          "6 SE Lst Ave, Delray Beach, FL 33444",
        "phone":            "(561) 276-7799",
        "website":          "https://goldenhourdelray.com",
        "instagram":        "@goldenhourdelray",
        "rating":           4.8,
        "review_count":     167,
        "price_range":      "$$",
        "description": (
            "Warm, sunlit salon near Old School Square specializing in warm tones and "
            "sun-kissed balayage. The name references the coastal evening light that "
            "makes Delray's beach famous during golden hour. Consistent colorists and "
            "same-day blowout availability most weekdays."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "creme-de-la-creme-nail-lounge",
        "name":             "Crème de la Crème Nail Lounge",
        "neighborhood_slug": "delray-beach-downtown",
        "category_slugs":   ["nail"],
        "address":          "144 NW 5th Ave, Delray Beach, FL 33444",
        "phone":            "(561) 243-5500",
        "website":          "",
        "instagram":        "@cremenaillounge_delray",
        "rating":           4.6,
        "review_count":     201,
        "price_range":      "$$",
        "description": (
            "Nail lounge with a full gel and dip menu, private pedicure chairs, and "
            "an on-site nail artist for holiday nail art designs. Regular clientele "
            "from nearby Condo Row appreciates the appointment-only model that keeps "
            "wait times predictable."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "skin-bar-delray",
        "name":             "Skin Bar Delray",
        "neighborhood_slug": "delray-beach-downtown",
        "category_slugs":   ["spa", "med-spa"],
        "address":          "25 NE 2nd St, Delray Beach, FL 33444",
        "phone":            "(561) 330-4488",
        "website":          "https://skinbardelray.com",
        "instagram":        "@skinbardelray",
        "rating":           4.9,
        "review_count":     134,
        "price_range":      "$$$",
        "description": (
            "Facial-specialty studio offering clinical skin analysis and curated "
            "treatment plans — HydraFacials, chemical peels, microneedling, and "
            "LED light therapy. Aesthetician team has combined 30+ years of "
            "South Florida practice. Downtown location ideal for lunch-hour appointments."
        ),
        "editors_pick":     True,
        "editors_pick_reason": (
            "Thirty-plus combined years of South Florida skin expertise — these are "
            "clinicians who build actual treatment plans, not just upsell add-ons. "
            "The downtown location makes a lunch-hour HydraFacial genuinely doable."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "headspace-salon-downtown-delray",
        "name":             "Headspace Salon",
        "neighborhood_slug": "delray-beach-downtown",
        "category_slugs":   ["hair"],
        "address":          "33 W Atlantic Ave, Delray Beach, FL 33444",
        "phone":            "(561) 330-2244",
        "website":          "",
        "instagram":        "@headspacesalonfl",
        "rating":           4.7,
        "review_count":     192,
        "price_range":      "$$",
        "description": (
            "Neighborhood hair salon on the west end of Atlantic Avenue with lower "
            "prices than the tourist-facing east strip. Brazilian blowouts and keratin "
            "treatments are the house specialty — particularly popular with Delray "
            "residents who deal with frizz during humid months."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "luxe-wax-bar-downtown-delray",
        "name":             "Luxe Wax Bar",
        "neighborhood_slug": "delray-beach-downtown",
        "category_slugs":   ["wax"],
        "address":          "17 NW 1st Ave, Delray Beach, FL 33444",
        "phone":            "(561) 278-9922",
        "website":          "",
        "instagram":        "@luxewaxbardelray",
        "rating":           4.7,
        "review_count":     98,
        "price_range":      "$",
        "description": (
            "Clean, straightforward wax bar serving the downtown residential population. "
            "Full body waxing at accessible prices — no upsells, no pressure. "
            "Walk-ins accepted Monday through Saturday. The Brazilian specialty "
            "keeps a steady repeat clientele."
        ),
        "photos": [],
        "services": [],
    },
    # ── South Delray ──────────────────────────────────────────────────────────
    {
        "slug":             "pure-salon-south-delray",
        "name":             "Pure Salon & Color Bar",
        "neighborhood_slug": "south-delray",
        "category_slugs":   ["hair"],
        "address":          "1010 S Federal Hwy, Delray Beach, FL 33483",
        "phone":            "(561) 276-3388",
        "website":          "",
        "instagram":        "@puresalondelray",
        "rating":           4.6,
        "review_count":     113,
        "price_range":      "$$",
        "description": (
            "South Federal Highway salon drawing from the Tropic Isle and High Point "
            "residential neighborhoods. Reliable cut-and-color service, highlights, "
            "and Brazilian blowouts — with a consistent team that regulars have "
            "followed for years."
        ),
        "photos": [],
        "services": [],
    },
    {
        "slug":             "oasis-nail-and-spa-south-delray",
        "name":             "Oasis Nail & Spa",
        "neighborhood_slug": "south-delray",
        "category_slugs":   ["nail", "spa"],
        "address":          "1450 S Federal Hwy, Delray Beach, FL 33483",
        "phone":            "(561) 272-4466",
        "website":          "",
        "instagram":        "",
        "rating":           4.5,
        "review_count":     87,
        "price_range":      "$",
        "description": (
            "Family-run nail and spa on south Federal Highway serving the Tropic Isle "
            "and Delray Lakes neighborhoods. Gel manicures, acrylic sets, and basic "
            "facial services at neighborhood-friendly prices. Loyal repeat clientele "
            "from the surrounding condo communities."
        ),
        "photos": [],
        "services": [],
    },
]


async def seed_delray_beach() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    # ── Network ───────────────────────────────────────────────────────────────
    BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
        network = await db.networks.find_one({"slug": BEAUTY_NETWORK_SLUG})
    if not network:
        raise RuntimeError(
            f"Network '{BEAUTY_NETWORK_SLUG}' not found — run seed_networks.py first."
        )
    network_id = network["_id"]
    print(f"Found beauty network: id={network_id}")

    # ── City ──────────────────────────────────────────────────────────────────
    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network_id,
        "slug": CITY_SLUG,
        "name": CITY_NAME,
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Delray Beach's most trusted beauty addresses.",
        "hero_description": CITY_DESCRIPTION,
        "seo_title": "Delray Beach Knows Beauty",
        "meta_description": (
            "The curated beauty directory for Delray Beach — salons, spas, nail studios, "
            "and med spas discovered by locals. Covering Atlantic Avenue, Pineapple Grove, "
            "Downtown Delray, and South Delray."
        ),
        "editorial_headlines": [
            {"headline": "Delray Beach's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": "delray-beach.knowsbeauty.com",
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": CITY_SLUG}, city_doc)
    city_id = city["_id"]
    print(f"Upserted city: {CITY_SLUG} (id={city_id})")

    # ── Neighborhoods ─────────────────────────────────────────────────────────
    nbhd_id_map: Dict[str, str] = {}
    for i, (nbhd_slug, nbhd_name, nbhd_vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nbhd_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city_id,
            "slug": nbhd_slug,
            "name": nbhd_name,
            "description": nbhd_vibe,
            "hero_description": nbhd_vibe,
            "listed_count": listed_count,
            "photo_url": None,
            "order": i,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        nbhd_result = await upsert(
            "neighborhoods",
            {"city_id": city_id, "slug": nbhd_slug},
            nbhd_doc,
        )
        nbhd_id_map[nbhd_slug] = nbhd_result["_id"]
    print(f"Upserted {len(NEIGHBORHOODS)} neighborhoods.")

    # ── Categories (from the network's master category map) ───────────────────
    # WHY: iterate network["category_map"] so this city's categories stay in
    # sync with the network definition rather than a locally-maintained list.
    cat_id_map: Dict[str, str] = {}
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
        cat_result = await upsert("categories", {"city_id": city_id, "slug": group["slug"]}, cat_doc)
        cat_id_map[group["slug"]] = cat_result["_id"]
    print(f"Upserted {len(cat_id_map)} categories.")

    # WHY: The BUSINESSES data was authored with slightly different category slugs
    # than the network's canonical category_map. This mapping normalises them so
    # lookups succeed without touching every business record.
    _SLUG_CANON = {"nail": "nails", "brow-lash": "lash-brow", "wax": "waxing"}

    # ── Businesses ────────────────────────────────────────────────────────────
    inserted = 0
    updated  = 0
    for biz in BUSINESSES:
        raw_cat_slugs = biz.get("category_slugs", [])
        canon_cat_slugs = [_SLUG_CANON.get(s, s) for s in raw_cat_slugs]
        nbhd_slug = biz.get("neighborhood_slug", "")

        primary_cat = canon_cat_slugs[0] if canon_cat_slugs else "hair"
        fallback_photos = FALLBACK_PHOTOS.get(primary_cat, FALLBACK_PHOTOS.get("hair", []))
        photos = biz.get("photos") or fallback_photos

        socials: Dict[str, Any] = {}
        if biz.get("instagram"):
            socials["instagram"] = biz["instagram"]

        biz_doc: Dict[str, Any] = {
            "_id": str(uuid.uuid4()),
            "network_id": network_id,
            "city_id": city_id,
            "slug": biz["slug"],
            "name": biz["name"],
            "category_slugs": canon_cat_slugs,
            "neighborhood_slugs": [nbhd_slug] if nbhd_slug else [],
            "address": biz.get("address", ""),
            "phone": biz.get("phone"),
            "website": biz.get("website"),
            "socials": socials,
            "short_description": biz.get("description"),
            "known_for": biz.get("description"),
            "price_cues": biz.get("price_range", "$$"),
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
        # doesn't lose their work — same pattern as all other city seeds.
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
    print("Delray Beach seed complete:")
    print("  City:          %s (id=%s)" % (CITY_SLUG, city_id))
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(cat_id_map))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: production-safety guard — this script writes to the database and
    # must not run against production unintentionally.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_delray_beach()


if __name__ == "__main__":
    run(main())
