"""Seed Miami across the Beauty, Wellness, and Health networks using the
exact rendered content from the reference site at
david.ai.devintensive.com/miami-knows-*.

Includes:
- City record with hero copy ("ISSUE NO. 01 · MIAMI · MAY 2026" eyebrow,
  hero subhead, search placeholder, stat counts)
- Neighborhoods (with vibe descriptions and the hardcoded "X LISTED"
  counts shown on the reference, NOT derived from the actual editorial
  pick count)
- City-scoped instances of the network's master categories
- Editor's Pick + trending businesses (every business has the exact name,
  category, neighborhood, short description and price shown on the
  reference home page)
- City-level copy blocks for stat counts, search-suggestion chips,
  section titles, footer "Also in..." cities, and the per-network
  "BY {axis}" label and owner CTA stats card.

Run inside the backend container, after seed_networks.py:
    python -m seed.seed_miami
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.database import ensure_indexes, get_db
from seed._helpers import run, upsert


# Neighborhoods PER NETWORK — each row is (slug, name, vibe, listed_count).
# `listed_count` is the number shown in the "X LISTED" pill on the reference
# neighborhood card. It is NOT derived from the visible editorial picks —
# Sunny Isles Beach for Beauty shows "14 LISTED" even though Beauty Bar Sunny
# is the only editorial pick from that neighborhood.

NEIGHBORHOODS = {
    "beauty": [
        ("wynwood",           "Wynwood",           "Creative & edgy",             2),
        ("brickell",          "Brickell",          "Sleek & corporate",           2),
        ("south-beach",       "South Beach",       "Glamorous & tropical",        1),
        ("coral-gables",      "Coral Gables",      "Refined & classic",           2),
        ("design-district",   "Design District",   "Editorial & luxe",            1),
        ("edgewater",         "Edgewater",         "Emerging & chic",             2),
        ("coconut-grove",     "Coconut Grove",     "Laid-back luxe",              1),
        ("little-havana",     "Little Havana",     "Vibrant & cultural",          2),
        ("sunny-isles-beach", "Sunny Isles Beach", "Tower luxury & multilingual", 14),
        ("aventura",          "Aventura",          "Polished & busy",             1),
        ("bal-harbour",       "Bal Harbour",       "Ultra-luxury",                1),
    ],
    "wellness": [
        ("wynwood",           "Wynwood",           "Creative & experimental", 2),
        ("brickell",          "Brickell",          "Sleek & corporate",       2),
        ("south-beach",       "South Beach",       "Glamorous & tropical",    2),
        ("coral-gables",      "Coral Gables",      "Refined & classic",       1),
        ("design-district",   "Design District",   "Editorial & luxe",        1),
        ("edgewater",         "Edgewater",         "Emerging & chic",         1),
        ("coconut-grove",     "Coconut Grove",     "Laid-back luxe",          1),
        ("sunny-isles-beach", "Sunny Isles Beach", "Tower luxury",            0),
        ("aventura",          "Aventura",          "Polished & busy",         1),
        ("bal-harbour",       "Bal Harbour",       "Ultra-luxury",            0),
        ("little-havana",     "Little Havana",     "Vibrant & cultural",      0),
        ("key-biscayne",      "Key Biscayne",      "Island residential",      1),
    ],
    "health": [
        ("wynwood",           "Wynwood",           "Creative & experimental", 2),
        ("brickell",          "Brickell",          "Sleek & corporate",       2),
        ("south-beach",       "South Beach",       "Glamorous & tropical",    2),
        ("coral-gables",      "Coral Gables",      "Refined & classic",       2),
        ("design-district",   "Design District",   "Editorial & luxe",        1),
        ("edgewater",         "Edgewater",         "Emerging & chic",         1),
        ("coconut-grove",     "Coconut Grove",     "Laid-back luxe",          0),
        ("sunny-isles-beach", "Sunny Isles Beach", "Tower luxury",            0),
        ("aventura",          "Aventura",          "Polished & busy",         1),
        ("bal-harbour",       "Bal Harbour",       "Ultra-luxury",            1),
        ("little-havana",     "Little Havana",     "Vibrant & cultural",      0),
        ("key-biscayne",      "Key Biscayne",      "Island residential",      0),
    ],
}


# Editorial businesses. Each tuple matches the reference card content
# verbatim: name, slug, category, neighborhood, price tier, editor's_pick
# flag, premium flag, short description.

BEAUTY_BUSINESSES = [
    {
        "slug": "beauty-bar-sunny", "name": "Beauty Bar Sunny",
        "category_slugs": ["hair"], "neighborhood_slugs": ["sunny-isles-beach"],
        "price_cues": "$$$", "editors_pick": True, "premium": True,
        "short_description": "A beauty coordination studio — hot-fusion extensions, Russian manicure, lash, brow, laser, and body work, often performed by two or three specialists at once.",
        "schema_org_type": "BeautySalon",
    },
    {
        "slug": "palmera-hair-house", "name": "Palmera Hair House",
        "category_slugs": ["hair"], "neighborhood_slugs": ["wynwood"],
        "price_cues": "$$$", "editors_pick": True, "premium": True,
        "short_description": "The color studio painting Miami's most copied highlights.",
        "schema_org_type": "HairSalon",
    },
    {
        "slug": "isla-nail-society", "name": "Isla Nail Society",
        "category_slugs": ["nails"], "neighborhood_slugs": ["brickell"],
        "price_cues": "$$$", "editors_pick": True, "premium": True,
        "short_description": "A clean-air nail studio for the Brickell lunch-hour crowd.",
        "schema_org_type": "NailSalon",
    },
    {
        "slug": "casa-luminara-spa", "name": "Casa Luminara Spa",
        "category_slugs": ["spa"], "neighborhood_slugs": ["coral-gables"],
        "price_cues": "$$$$", "editors_pick": True, "premium": True,
        "short_description": "A Mediterranean garden spa hidden in old Coral Gables.",
        "schema_org_type": "DaySpa",
    },
    {
        "slug": "el-rey-barberia", "name": "El Rey Barbería",
        "category_slugs": ["barber"], "neighborhood_slugs": ["little-havana"],
        "price_cues": "$$", "editors_pick": True, "premium": False,
        "short_description": "Three generations of Cuban barbering on Calle Ocho.",
        "schema_org_type": "BarberShop",
    },
    {
        "slug": "flutter-lash-lab", "name": "Flutter Lash Lab",
        "category_slugs": ["lash-brow"], "neighborhood_slugs": ["south-beach"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "Volume extensions and lash lifts, two blocks from the ocean.",
        "schema_org_type": "BeautySalon",
    },
    {
        "slug": "orchid-med-spa", "name": "Orchid Med Spa",
        "category_slugs": ["med-spa"], "neighborhood_slugs": ["design-district"],
        "price_cues": "$$$$", "editors_pick": False, "premium": True,
        "short_description": "Conservative, natural-looking injectables by a board-certified team.",
        "schema_org_type": "MedicalSpa",
    },
    {
        "slug": "luma-makeup-studio", "name": "Luma Makeup Studio",
        "category_slugs": ["makeup"], "neighborhood_slugs": ["edgewater"],
        "price_cues": "$$$", "editors_pick": False, "premium": False,
        "short_description": "Editorial-quality makeup for brides, events, and on-camera moments.",
        "schema_org_type": "BeautySalon",
    },
    {
        "slug": "wynwood-fades", "name": "Wynwood Fades",
        "category_slugs": ["barber"], "neighborhood_slugs": ["wynwood"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "A barbershop you'd Instagram. Streetwear, neon, and the cleanest fades.",
        "schema_org_type": "BarberShop",
    },
    {
        "slug": "brickell-brow-bar", "name": "Brickell Brow Bar",
        "category_slugs": ["lash-brow"], "neighborhood_slugs": ["brickell"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "Brow shaping, lamination, and tinting for the Brickell professional crowd.",
        "schema_org_type": "BeautySalon",
    },
]

WELLNESS_BUSINESSES = [
    {
        "slug": "salt-stone-recovery", "name": "Salt & Stone Recovery",
        "category_slugs": ["recovery"], "neighborhood_slugs": ["wynwood"],
        "price_cues": "$$$", "editors_pick": True, "premium": True,
        "short_description": "A members-style recovery floor: infrared sauna, 39°F cold plunge, compression, and a tea bar — built for athletes, founders, and post-flight resets.",
    },
    {
        "slug": "breathe-yoga-edgewater", "name": "Breathe Yoga Edgewater",
        "category_slugs": ["yoga-meditation"], "neighborhood_slugs": ["edgewater"],
        "price_cues": "$$", "editors_pick": True, "premium": False,
        "short_description": "A bayfront studio known for slow vinyasa, weekly sound baths on the deck, and an early-morning class that locals plan their week around.",
    },
    {
        "slug": "oceanic-day-spa", "name": "Oceanic Day Spa",
        "category_slugs": ["spa"], "neighborhood_slugs": ["south-beach"],
        "price_cues": "$$$$", "editors_pick": True, "premium": True,
        "short_description": "A 14,000-square-foot hotel spa with a Roman-style hammam, a saltwater plunge pool, and a couples' suite booked weeks ahead for anniversaries.",
    },
    {
        "slug": "glow-iv-brickell", "name": "Glow IV Brickell",
        "category_slugs": ["iv-hydration"], "neighborhood_slugs": ["brickell"],
        "price_cues": "$$$", "editors_pick": False, "premium": True,
        "short_description": "A clinical-grade IV lounge tucked into a Brickell tower — nurses on staff, drips reviewed by an MD, and an after-work crowd that comes in for hydration before flights.",
    },
    {
        "slug": "pulse-cryo", "name": "Pulse Cryo",
        "category_slugs": ["recovery"], "neighborhood_slugs": ["aventura"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "Whole-body cryotherapy, localized cryo, and infrared red-light beds — a fast in-and-out recovery stop for the post-gym Aventura crowd.",
    },
    {
        "slug": "green-roots-nutrition", "name": "Green Roots Nutrition",
        "category_slugs": ["nutrition"], "neighborhood_slugs": ["coconut-grove"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "A registered dietitian-led nutrition practice with a small Coconut Grove storefront, a juice bar in front, and 1:1 coaching upstairs.",
    },
    {
        "slug": "house-of-acupuncture", "name": "House of Acupuncture",
        "category_slugs": ["holistic"], "neighborhood_slugs": ["coral-gables"],
        "price_cues": "$$$", "editors_pick": False, "premium": False,
        "short_description": "A licensed acupuncture practice in a quiet Gables bungalow — sports recovery, fertility support, and chronic pain protocols.",
    },
    {
        "slug": "reset-retreats-miami", "name": "Reset Retreats Miami",
        "category_slugs": ["retreats"], "neighborhood_slugs": ["key-biscayne"],
        "price_cues": "$$$$", "editors_pick": False, "premium": True,
        "short_description": "A weekend wellness retreat run out of a Key Biscayne beach house — eight guests, two facilitators, breathwork, cold plunge, and a chef.",
    },
    {
        "slug": "sweat-haus-wynwood", "name": "Sweat Haus Wynwood",
        "category_slugs": ["recovery"], "neighborhood_slugs": ["wynwood"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "Three Finnish-style sauna rooms and a single cold tub in a brick warehouse — communal, sweaty, and very Wynwood.",
    },
]

HEALTH_BUSINESSES = [
    {
        "slug": "biscayne-longevity-medicine", "name": "Biscayne Longevity Medicine",
        "category_slugs": ["longevity"], "neighborhood_slugs": ["brickell"],
        "price_cues": "$$$$", "editors_pick": True, "premium": True,
        "short_description": "A physician-led longevity practice — comprehensive bloodwork panels, advanced imaging, and hormone therapy under MD supervision.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "gables-smile-studio", "name": "Gables Smile Studio",
        "category_slugs": ["dental"], "neighborhood_slugs": ["coral-gables"],
        "price_cues": "$$$", "editors_pick": True, "premium": True,
        "short_description": "A cosmetic and general dental practice known for veneers, Invisalign, and a quiet chair-side manner — six operatories, two dentists, one shared philosophy.",
        "schema_org_type": "Dentist",
    },
    {
        "slug": "design-district-aesthetics", "name": "Design District Aesthetics",
        "category_slugs": ["aesthetics"], "neighborhood_slugs": ["design-district"],
        "price_cues": "$$$$", "editors_pick": True, "premium": True,
        "short_description": "A physician-owned aesthetics practice — Botox, fillers, lasers, microneedling, all performed by MDs or RN injectors trained in-house.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "wynwood-mental-health-collective", "name": "Wynwood Mental Health Collective",
        "category_slugs": ["mental-health"], "neighborhood_slugs": ["wynwood"],
        "price_cues": "$$$", "editors_pick": False, "premium": False,
        "short_description": "A group practice of nine therapists and two psychiatrists — individual, couples, and family therapy, plus medication management when clinically appropriate.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "south-beach-physical-therapy", "name": "South Beach Physical Therapy",
        "category_slugs": ["pt-recovery"], "neighborhood_slugs": ["south-beach"],
        "price_cues": "$$", "editors_pick": False, "premium": False,
        "short_description": "A one-on-one physical therapy practice — every session is private, with the same PT for the full plan of care.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "aventura-concierge-md", "name": "Aventura Concierge MD",
        "category_slugs": ["primary-care"], "neighborhood_slugs": ["aventura"],
        "price_cues": "$$$$", "editors_pick": False, "premium": True,
        "short_description": "A concierge primary-care practice capped at 250 patients per physician — same-day appointments, direct phone access, and 60-minute visits.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "sunshine-fertility-center", "name": "Sunshine Fertility Center",
        "category_slugs": ["fertility"], "neighborhood_slugs": ["coral-gables"],
        "price_cues": "$$$$", "editors_pick": False, "premium": True,
        "short_description": "A reproductive endocrinology practice offering IVF, egg freezing, and fertility evaluation — three REI physicians, an on-site lab and embryology team.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "edgewater-metabolic-clinic", "name": "Edgewater Metabolic Clinic",
        "category_slugs": ["metabolic"], "neighborhood_slugs": ["edgewater"],
        "price_cues": "$$$", "editors_pick": False, "premium": False,
        "short_description": "A physician-supervised metabolic health practice — obesity medicine, GLP-1 management, and long-term care plans, not a short-term injection counter.",
        "schema_org_type": "MedicalBusiness",
    },
    {
        "slug": "brickell-direct-primary-care", "name": "Brickell Direct Primary Care",
        "category_slugs": ["primary-care"], "neighborhood_slugs": ["brickell"],
        "price_cues": "$$$", "editors_pick": False, "premium": False,
        "short_description": "A direct primary care practice — flat monthly fee, no insurance billing, unhurried visits, and a panel size that makes that possible.",
        "schema_org_type": "MedicalBusiness",
    },
]


# Per-network city-level configuration, all taken from the reference pages.
#
# Hero title structure: the editorial italic phrase is bracketed in
# `headline_html` with <em>...</em> so the template can render it directly
# (rather than guessing which words to italicize).
NETWORK_CITY_CONFIG = {
    "beauty": {
        "tagline": "Miami's best-kept beauty addresses.",
        "headline_html": "Miami's <em>best-kept</em> beauty addresses.",
        "hero_eyebrow": "ISSUE NO. 01 · MIAMI · MAY 2026",
        "hero_subhead": "An index of the stylists, colorists, esthetes, and barbers locals actually book — neighborhood by neighborhood.",
        "search_placeholder": "Balayage in Wynwood. Gel manicure in Brickell. Quiet barbershop near Coral Gables.",
        "stat_count_listings": "29",
        "stat_label_listings": "SALONS INDEXED",
        "stat_count_neighborhoods": "11",
        "stat_count_editor_picks": "5",
        "stat_label_owners": "FOR SALON OWNERS",
        "search_chips": ["balayage", "gel manicure", "lash extensions", "hydrafacial", "fade"],
        "header_nav": [
            ("hair",      "Hair"),
            ("nails",     "Nails"),
            ("spa",       "Spa"),
            ("lash-brow", "Lashes"),
            ("med-spa",   "Med Spa"),
            ("barber",    "Barber"),
        ],
        "header_owners_cta": "For Salon Owners",
        "browse_axis_label": "BY SERVICE",
        "map_culture_word": "beauty",
        "owners_eyebrow": "FOR SALON OWNERS",
        "owners_headline": "Own a salon in Miami?",
        "owners_italic": "Your listing's already here.",
        "owners_body": "We've pre-built a profile for every salon in Miami. Claim yours in 3 minutes, tell us your story by voice, and get found by people searching tonight.",
        "owners_cta": "Claim your salon · Free",
        "owners_card_business_slug": "beauty-bar-sunny",
        "owners_card_stats": {
            "views": "3,128",
            "calls": "112",
            "bookings": "+31",
            "bookings_label": "New bookings (Voice)",
        },
        "owners_card_action": "Post your golden-hour blowout reel to Instagram — draft ready",
        "spotlight_neighborhood_slug": "wynwood",
        "spotlight_eyebrow": "NEIGHBORHOOD SPOTLIGHT",
        "spotlight_lead_a": "What's",
        "spotlight_lead_b": "happening in",
        "spotlight_description": "Street-art murals meet experimental beauty studios.",
        "spotlight_business_slugs": ["palmera-hair-house", "wynwood-fades"],
        "footer_blurb": "The curated directory of Miami's best salons, spas, and beauty professionals. Discovered by locals, loved by visitors.",
        "footer_also_in": "Also in Lahore · Austin · Orlando",
        "footer_publication_label": "A Knows Beauty publication.",
        "footer_owners_label": "SALONS",
        "footer_owners_items": ["List your salon", "Owner login", "Pricing"],
        "footer_legal": "© 2026 Miami Knows Beauty · A local-first directory for beauty professionals.",
        "footer_made_in": "Made in Miami · Powered by Expertly",
        "seo_title": "Miami Knows Beauty",
        "trending_business_slugs": [
            "beauty-bar-sunny", "palmera-hair-house", "isla-nail-society",
            "casa-luminara-spa", "flutter-lash-lab", "orchid-med-spa",
            "el-rey-barberia", "luma-makeup-studio",
        ],
        "two_column_neighborhoods": [
            {"slug": "brickell",    "business_slugs": ["isla-nail-society", "brickell-brow-bar"]},
            {"slug": "south-beach", "business_slugs": ["flutter-lash-lab"]},
        ],
    },
    "wellness": {
        "tagline": "Where Miami recovers, resets, and breathes.",
        "headline_html": "Where Miami <em>recovers,</em> resets, and breathes.",
        "hero_eyebrow": "ISSUE NO. 01 · MIAMI · MAY 2026",
        "hero_subhead": "An index of the spas, saunas, recovery rooms, yoga studios, and IV lounges Miami locals actually book — between training blocks, after long flights, and before the week gets loud.",
        "search_placeholder": "Infrared sauna in Wynwood. Sunrise yoga in Edgewater. IV drip in Brickell.",
        "stat_count_listings": "418",
        "stat_label_listings": "STUDIOS INDEXED",
        "stat_count_neighborhoods": "12",
        "stat_count_editor_picks": "5",
        "stat_label_owners": "FOR OWNERS",
        "search_chips": ["infrared sauna", "cold plunge", "sunrise yoga", "IV drip", "reformer pilates"],
        "header_nav": [
            ("spa",             "Spa"),
            ("recovery",        "Recovery"),
            ("iv-hydration",    "IV & Hydration"),
            ("yoga-meditation", "Yoga & Meditation"),
            ("holistic",        "Holistic"),
            ("nutrition",       "Nutrition"),
        ],
        "header_owners_cta": "For Owners",
        "browse_axis_label": "BY WELLNESS",
        "map_culture_word": "wellness",
        "owners_eyebrow": "FOR WELLNESS OWNERS",
        "owners_headline": "Run a wellness practice in Miami?",
        "owners_italic": "Your listing's already here.",
        "owners_body": "We pre-built a profile for every studio, spa, and recovery room in Miami. Claim yours in three minutes — and get found by people searching tonight.",
        "owners_cta": "Claim your studio · Free",
        "owners_card_business_slug": "salt-stone-recovery",
        "owners_card_stats": {
            "views": "2,847",
            "calls": "94",
            "bookings": "+22",
            "bookings_label": "New bookings",
        },
        "owners_card_action": "Post your contrast-therapy reel — draft ready",
        "spotlight_neighborhood_slug": "wynwood",
        "spotlight_eyebrow": "NEIGHBORHOOD SPOTLIGHT",
        "spotlight_lead_a": "Where Miami's",
        "spotlight_lead_b": "recovery culture lives —",
        "spotlight_description": "A few converted warehouses and brick-walled studios are quietly leading the recovery scene. Here is who is doing it well.",
        "spotlight_business_slugs": ["salt-stone-recovery", "sweat-haus-wynwood"],
        "footer_blurb": "The curated guide to Miami spas, recovery, yoga, and wellness — discovered by locals, kept simple.",
        "footer_also_in": "Coming soon to Austin · Orlando · Dallas",
        "footer_publication_label": "A Knows Wellness publication.",
        "footer_owners_label": "WELLNESS",
        "footer_owners_items": ["Claim your listing", "Pricing", "Miami Knows Beauty →"],
        "footer_legal": "© 2026 Miami Knows Wellness · A local-first directory.",
        "footer_made_in": "Made in Miami · Powered by Expertly",
        "seo_title": "Miami Knows Wellness",
        "trending_business_slugs": [
            "salt-stone-recovery", "breathe-yoga-edgewater", "glow-iv-brickell",
            "oceanic-day-spa", "pulse-cryo", "green-roots-nutrition",
            "house-of-acupuncture", "reset-retreats-miami",
        ],
        "two_column_neighborhoods": [],
    },
    "health": {
        "tagline": "Miami's most-trusted doctors, dentists, and clinics.",
        "headline_html": "Miami's <em>most-trusted</em> doctors, dentists, and clinics.",
        "hero_eyebrow": "ISSUE NO. 01 · MIAMI · MAY 2026",
        "hero_subhead": "A neutral, locally curated guide to the longevity clinics, dental practices, mental health groups, fertility specialists, and concierge primary-care doctors Miami families and professionals trust.",
        "search_placeholder": "Concierge doctor in Brickell. Invisalign in Coral Gables. Couples therapist in Wynwood.",
        "stat_count_listings": "627",
        "stat_label_listings": "PRACTICES INDEXED",
        "stat_count_neighborhoods": "12",
        "stat_count_editor_picks": "4",
        "stat_label_owners": "FOR PRACTICES",
        "search_chips": ["concierge doctor", "invisalign", "pelvic floor PT", "hormone therapy", "couples therapy"],
        "header_nav": [
            ("aesthetics",     "Aesthetics"),
            ("metabolic",      "Metabolic"),
            ("longevity",      "Longevity"),
            ("dental",         "Dental"),
            ("mental-health",  "Mental Health"),
            ("fertility",      "Fertility"),
        ],
        "header_owners_cta": "For Owners",
        "browse_axis_label": "BY HEALTH",
        "map_culture_word": "health",
        "owners_eyebrow": "FOR PRACTICES",
        "owners_headline": "Run a practice in Miami?",
        "owners_italic": "Your listing's already here.",
        "owners_body": "We pre-built a profile for every clinic and practice in Miami-Dade. Claim yours, correct details, and add the things that matter — your training, your approach, your office.",
        "owners_cta": "Claim your practice · Free",
        "owners_card_business_slug": "biscayne-longevity-medicine",
        "owners_card_stats": {
            "views": "2,847",
            "calls": "94",
            "bookings": "+22",
            "bookings_label": "New bookings",
        },
        "owners_card_action": "Post your contrast-therapy reel — draft ready",
        "spotlight_neighborhood_slug": "brickell",
        "spotlight_eyebrow": "NEIGHBORHOOD SPOTLIGHT",
        "spotlight_lead_a": "Where Miami professionals",
        "spotlight_lead_b": "see their doctors —",
        "spotlight_description": "The tower-medicine corridor — concierge primary care, longevity clinics, and specialists who keep the same patients for decades.",
        "spotlight_business_slugs": ["biscayne-longevity-medicine", "brickell-direct-primary-care"],
        "footer_blurb": "A curated guide to Miami's clinics and providers — provider-focused, not outcome-promising.",
        "footer_also_in": "Coming soon to Austin · Orlando · Dallas",
        "footer_publication_label": "A Knows Health publication.",
        "footer_owners_label": "HEALTH",
        "footer_owners_items": ["Claim your listing", "Pricing", "Miami Knows Beauty →"],
        "footer_legal": "© 2026 Miami Knows Health · A local-first directory.",
        "footer_made_in": "Made in Miami · Powered by Expertly",
        "seo_title": "Miami Knows Health",
        "trending_business_slugs": [
            "biscayne-longevity-medicine", "gables-smile-studio",
            "wynwood-mental-health-collective", "south-beach-physical-therapy",
            "aventura-concierge-md", "sunshine-fertility-center",
            "edgewater-metabolic-clinic", "design-district-aesthetics",
        ],
        "two_column_neighborhoods": [],
    },
}


BUSINESSES_PER_NETWORK = {
    "beauty": BEAUTY_BUSINESSES,
    "wellness": WELLNESS_BUSINESSES,
    "health": HEALTH_BUSINESSES,
}


async def _set_copy(scope_type: str, scope_ref: Dict[str, str], key: str, value: str) -> None:
    """Upsert a single copy block."""
    db = get_db()
    now = datetime.now(timezone.utc)
    existing = await db.copy_blocks.find_one({
        "scope_type": scope_type, "scope_ref": scope_ref, "key": key, "locale": "en-US",
    })
    if existing:
        await db.copy_blocks.update_one(
            {"_id": existing["_id"]},
            {"$set": {"value": value, "updated_at": now}},
        )
    else:
        await db.copy_blocks.insert_one({
            "_id": str(uuid.uuid4()),
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "key": key,
            "value": value,
            "locale": "en-US",
            "active_from": None,
            "active_until": None,
            "created_at": now,
            "updated_at": now,
        })


async def seed_network(network_slug: str) -> None:
    db = get_db()
    network = await db.networks.find_one({"slug": network_slug})
    if not network:
        print(f"Network {network_slug} not found — run seed_networks.py first.")
        return

    cfg = NETWORK_CITY_CONFIG[network_slug]
    businesses = BUSINESSES_PER_NETWORK[network_slug]
    now = datetime.now(timezone.utc)

    # City
    city_doc = {
        "_id": str(uuid.uuid4()),
        "network_id": network["_id"],
        "slug": "miami",
        "name": "Miami",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": cfg["tagline"],
        "hero_description": cfg["hero_subhead"],
        "seo_title": cfg["seo_title"],
        "meta_description": cfg["hero_subhead"],
        "editorial_headlines": [{"headline": cfg["tagline"], "is_default": True}],
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network["_id"], "slug": "miami"}, city_doc)

    # Wipe and re-add neighborhoods so a re-seed cleanly matches the reference
    # (the upsert would otherwise leave behind older neighborhoods like
    # "Mid-Beach", "Downtown" etc. that aren't in the reference list).
    await db.neighborhoods.delete_many({
        "city_id": city["_id"],
        "slug": {"$nin": [n[0] for n in NEIGHBORHOODS[network_slug]]},
    })
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS[network_slug]):
        nb_doc = {
            "_id": str(uuid.uuid4()),
            "city_id": city["_id"],
            "slug": slug,
            "name": name,
            "description": vibe,
            "listed_count": listed_count,
            "order": i,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("neighborhoods", {"city_id": city["_id"], "slug": slug}, nb_doc)

    # Wipe and re-add categories the same way.
    master_slugs = [g["slug"] for g in (network.get("category_map") or [])]
    await db.categories.delete_many({
        "city_id": city["_id"],
        "slug": {"$nin": master_slugs},
    })
    for order, group in enumerate(network.get("category_map") or []):
        cat_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network["_id"],
            "city_id": city["_id"],
            "slug": group["slug"],
            "parent_slug": None,
            "name": group["name"],
            "description": group.get("description"),
            "examples": group.get("examples", []),
            "order": order,
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("categories", {"city_id": city["_id"], "slug": group["slug"]}, cat_doc)

    # Businesses
    for biz in businesses:
        featured = (
            {"enabled": True, "tier": "premium"} if biz.get("premium") else
            {"enabled": False, "tier": "free"}
        )
        biz_doc = {
            "_id": str(uuid.uuid4()),
            "network_id": network["_id"],
            "city_id": city["_id"],
            "slug": biz["slug"],
            "name": biz["name"],
            "category_slugs": biz["category_slugs"],
            "neighborhood_slugs": biz.get("neighborhood_slugs", []),
            "short_description": biz.get("short_description"),
            "known_for": biz.get("short_description"),
            "price_cues": biz.get("price_cues"),
            "featured": featured,
            "editors_pick": biz.get("editors_pick", False),
            "claim_status": "verified" if biz.get("editors_pick") or biz.get("premium") else "unclaimed",
            "schema_org_type": biz.get("schema_org_type", "LocalBusiness"),
            "data_source": "editorial",
            "quality_score": 90 if biz.get("editors_pick") else 60,
            "index_status": "indexed",
            "index_override": "auto",
            "status": "live",
            "address": {"city": "Miami", "state": "FL", "country": "US"},
            "socials": {}, "hours": [], "services": [], "photos": [],
            "created_at": now,
            "updated_at": now,
        }
        await upsert("businesses", {"city_id": city["_id"], "slug": biz["slug"]}, biz_doc)

    # City-level copy blocks for the structural strings that appear on the
    # home page (the same ones an editor would later tweak through the API).
    scope = {"city_id": city["_id"]}
    pairs = [
        ("home.hero.eyebrow",        cfg["hero_eyebrow"]),
        ("home.hero.subhead",        cfg["hero_subhead"]),
        ("home.hero.headline",       cfg["tagline"]),
        ("home.hero.headline_html",  cfg["headline_html"]),
        ("home.hero.search_placeholder", cfg["search_placeholder"]),
        ("home.stat.listings.count", cfg["stat_count_listings"]),
        ("home.stat.listings.label", cfg["stat_label_listings"]),
        ("home.stat.neighborhoods.count", cfg["stat_count_neighborhoods"]),
        ("home.stat.editor_picks.count",  cfg["stat_count_editor_picks"]),
        ("home.stat.owners.label",   cfg["stat_label_owners"]),
        ("home.browse.axis_label",   cfg["browse_axis_label"]),
        ("home.map.culture_word",    cfg["map_culture_word"]),
        ("home.editor_picks.eyebrow","★ EDITOR'S PICKS"),
        ("home.editor_picks.title",  "The ones we'd send a friend to"),
        ("home.trending.eyebrow",    "THIS WEEK"),
        ("home.trending.title",      "Trending in Miami"),
        ("home.spotlight.eyebrow",   cfg["spotlight_eyebrow"]),
        ("home.spotlight.lead_a",    cfg["spotlight_lead_a"]),
        ("home.spotlight.lead_b",    cfg["spotlight_lead_b"]),
        ("home.spotlight.description", cfg["spotlight_description"]),
        ("home.owners.eyebrow",      cfg["owners_eyebrow"]),
        ("home.owners.headline",     cfg["owners_headline"]),
        ("home.owners.italic",       cfg["owners_italic"]),
        ("home.owners.body",         cfg["owners_body"]),
        ("home.owners.cta",          cfg["owners_cta"]),
        ("home.owners.card_action",  cfg["owners_card_action"]),
        ("home.owners.card_stats.views",         cfg["owners_card_stats"]["views"]),
        ("home.owners.card_stats.calls",         cfg["owners_card_stats"]["calls"]),
        ("home.owners.card_stats.bookings",      cfg["owners_card_stats"]["bookings"]),
        ("home.owners.card_stats.bookings_label", cfg["owners_card_stats"]["bookings_label"]),
        ("header.owners_cta",        cfg["header_owners_cta"]),
        ("footer.about.body",        cfg["footer_blurb"]),
        ("footer.also_in",           cfg["footer_also_in"]),
        ("footer.publication_label", cfg["footer_publication_label"]),
        ("footer.owners.label",      cfg["footer_owners_label"]),
        ("footer.owners.items",      " | ".join(cfg["footer_owners_items"])),
        ("footer.legal",             cfg["footer_legal"]),
        ("footer.made_in",           cfg["footer_made_in"]),
    ]
    for key, value in pairs:
        await _set_copy("city", scope, key, value)

    # Configuration that's structural, not free text — keep on the city
    # doc itself so the route can read it without a copy-block lookup.
    await get_db().cities.update_one(
        {"_id": city["_id"]},
        {"$set": {
            "spotlight_neighborhood_slug": cfg["spotlight_neighborhood_slug"],
            "spotlight_business_slugs":    cfg["spotlight_business_slugs"],
            "owners_card_business_slug":   cfg["owners_card_business_slug"],
            "trending_business_slugs":     cfg["trending_business_slugs"],
            "two_column_neighborhoods":    cfg["two_column_neighborhoods"],
            "search_chips":                cfg["search_chips"],
            "header_nav":                  [{"slug": s, "label": l} for s, l in cfg["header_nav"]],
            "updated_at": now,
        }},
    )

    print(f"  Seeded {network_slug} / miami: "
          f"{len(NEIGHBORHOODS[network_slug])} neighborhoods, "
          f"{len(network.get('category_map') or [])} categories, "
          f"{len(businesses)} businesses.")


async def main() -> None:
    await ensure_indexes()
    for slug in ("beauty", "wellness", "health"):
        print(f"== Seeding Miami for {slug} ==")
        await seed_network(slug)


if __name__ == "__main__":
    run(main())
