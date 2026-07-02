"""Seed Beauty / Wellness / Health networks with the exact category lists
from the reference site at david.ai.devintensive.com/miami-knows-*.

Run inside the backend container:
    python -m seed.seed_networks
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.database import ensure_indexes
from seed._helpers import assert_seed_target_allowed, category_groups, run, upsert


# Categories: slug + display name + one-line description (matches the
# "01 / Hair / Color, cuts, blowouts, extensions →" item on the reference
# home page).

BEAUTY_CATEGORIES = [
    {
        "slug": "hair", "name": "Hair",
        "description": "Color, cuts, blowouts, extensions",
        "meta_description": "The best hair salons in Miami — color, cuts, blowouts, and extensions from Wynwood to Brickell. Browse Miami Knows Beauty.",
    },
    {
        "slug": "nails", "name": "Nails",
        "description": "Manicures, pedicures, nail art",
        "meta_description": "The best nail salons in Miami — manicures, pedicures, and nail art across every neighborhood. Browse Miami Knows Beauty.",
    },
    {
        "slug": "spa", "name": "Spa",
        "description": "Facials, massage, body treatments",
        "meta_description": "The best spas in Miami — facials, massage, and body treatments from luxury hotel spas to neighborhood favorites. Browse Miami Knows Beauty.",
    },
    {
        "slug": "lash-brow", "name": "Lash & Brow",
        "description": "Extensions, lifts, lamination",
        "meta_description": "The best lash and brow studios in Miami — extensions, lifts, and lamination by Miami's top technicians. Browse Miami Knows Beauty.",
    },
    {
        "slug": "med-spa", "name": "Med Spa",
        "description": "Botox, fillers, laser, microneedling",
        "meta_description": "The best medical spas in Miami — Botox, fillers, laser treatments, and microneedling from board-certified providers. Browse Miami Knows Beauty.",
    },
    {
        "slug": "barber", "name": "Barber",
        "description": "Mens cuts, fades, hot shaves",
        "meta_description": "The best barber shops in Miami — men's cuts, fades, and hot shaves from Wynwood to Brickell. Browse Miami Knows Beauty.",
    },
    {
        "slug": "makeup", "name": "Makeup",
        "description": "Bridal, editorial, lessons",
        "meta_description": "The best makeup artists in Miami — bridal, editorial, and private lessons from Miami's top professionals. Browse Miami Knows Beauty.",
    },
    {
        "slug": "waxing", "name": "Waxing",
        "description": "Brazilian, body waxing, threading",
        "meta_description": "The best waxing salons in Miami — Brazilian, full body waxing, and threading in every neighborhood. Browse Miami Knows Beauty.",
    },
]

WELLNESS_CATEGORIES = [
    {"slug": "spa",            "name": "Spa",              "description": "Day spas, hotel spas, massage, facials, body treatments"},
    {"slug": "recovery",       "name": "Recovery",         "description": "Infrared saunas, cold plunge, cryotherapy, compression"},
    {"slug": "iv-hydration",   "name": "IV & Hydration",   "description": "IV therapy, vitamin shots, hydration lounges"},
    {"slug": "yoga-meditation","name": "Yoga & Meditation","description": "Yoga studios, meditation, breathwork, sound baths"},
    {"slug": "holistic",       "name": "Holistic",         "description": "Acupuncture, reiki, Ayurveda, naturopathy"},
    {"slug": "nutrition",      "name": "Nutrition",        "description": "Coaches, wellness cafés, juice bars, supplements"},
    {"slug": "sleep-stress",   "name": "Sleep & Stress",   "description": "Sleep clinics, stress coaching, burnout recovery"},
    {"slug": "retreats",       "name": "Retreats",         "description": "Wellness retreats, day retreats, corporate wellness"},
]

HEALTH_CATEGORIES = [
    {"slug": "aesthetics",     "name": "Aesthetics",       "description": "Med spas, injectables, lasers, body contouring"},
    {"slug": "metabolic",      "name": "Metabolic",        "description": "Medical weight loss, GLP-1 clinics, obesity medicine"},
    {"slug": "longevity",      "name": "Longevity",        "description": "Hormone therapy, menopause care, functional medicine"},
    {"slug": "dental",         "name": "Dental",           "description": "Cosmetic dentistry, Invisalign, implants, orthodontics"},
    {"slug": "mental-health",  "name": "Mental Health",    "description": "Therapists, psychiatrists, couples & family therapy"},
    {"slug": "fertility",      "name": "Fertility",        "description": "Fertility clinics, OB/GYN, midwives, pelvic floor"},
    {"slug": "pt-recovery",    "name": "PT & Recovery",    "description": "Physical therapy, chiropractic, sports injury care"},
    {"slug": "primary-care",   "name": "Primary Care",     "description": "Concierge medicine, direct primary care, urgent care"},
]


NETWORK_DEFS = [
    {
        "slug": "beauty",
        "name": "Knows Beauty",
        "tagline": "The curated beauty directory, city by city.",
        "description": "The curated directory of the best salons, spas, and beauty professionals in every city we cover. Discovered by locals, loved by visitors.",
        "domains": [
            "knowsbeauty.ai.devintensive.com",
            "knowsbeauty.localhost",
            "knowsbeauty.com",
        ],
        "theme": {
            "primary_color": "#0e0e10",
            "accent_color": "#c89f5b",
        },
        "categories": BEAUTY_CATEGORIES,
        "sensitive_content_review": False,
    },
    {
        "slug": "wellness",
        "name": "Knows Wellness",
        "tagline": "Miami's curated wellness directory.",
        "description": "The curated guide to Miami spas, recovery, yoga, and wellness — discovered by locals, kept simple.",
        "domains": [
            "knowswellness.ai.devintensive.com",
            "knowswellness.localhost",
            "knowswellness.com",
        ],
        "theme": {
            "primary_color": "#1a2a23",
            "accent_color": "#9ac4a1",
        },
        "categories": WELLNESS_CATEGORIES,
        "sensitive_content_review": False,
    },
    {
        "slug": "health",
        "name": "Knows Health",
        "tagline": "Miami's curated health directory.",
        "description": "A curated guide to Miami's clinics and providers — provider-focused, not outcome-promising.",
        "domains": [
            "knowshealth.ai.devintensive.com",
            "knowshealth.localhost",
            "knowshealth.com",
        ],
        "theme": {
            "primary_color": "#0f2238",
            "accent_color": "#dfb27b",
        },
        "categories": HEALTH_CATEGORIES,
        "sensitive_content_review": True,
    },
]


async def main() -> None:
    # WHY: refuse to seed/reset a production database unless explicitly
    # confirmed. Runs before any DB access so a wrong-database run aborts with
    # nothing touched. See seed._helpers.assert_seed_target_allowed.
    assert_seed_target_allowed()
    await ensure_indexes()
    now = datetime.now(timezone.utc)
    for n in NETWORK_DEFS:
        doc = {
            "_id": str(uuid.uuid4()),
            "slug": n["slug"],
            "name": n["name"],
            "tagline": n["tagline"],
            "description": n["description"],
            "domains": n["domains"],
            "theme": n["theme"],
            "category_map": category_groups(n["categories"]),
            "badge_policy": {
                "editors_pick": "Editorially selected. Cannot be purchased.",
                "verified": "Core public details have been checked.",
                "claimed": "The business owner manages this profile.",
                "featured": "Paid placement.",
            },
            "sensitive_content_review": n["sensitive_content_review"],
            "status": "live",
            "created_at": now,
            "updated_at": now,
        }
        await upsert("networks", {"slug": n["slug"]}, doc)
        print(f"Seeded network: {n['slug']}")


if __name__ == "__main__":
    run(main())
