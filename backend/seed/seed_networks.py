"""Seed the three flagship networks: Beauty, Wellness, Health.

Run inside the backend container:
    python -m seed.seed_networks
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.database import ensure_indexes
from seed._helpers import category_groups, run, upsert


BEAUTY_CATEGORIES = [
    {"slug": "hair", "name": "Hair", "description": "Salons, colorists, blowouts, extensions, keratin, curly hair specialists, men's grooming, barbers.",
     "examples": ["Hair salons", "colorists", "blowouts", "extensions", "keratin treatments", "curly hair specialists", "men's grooming", "barbers"]},
    {"slug": "nails", "name": "Nails", "description": "Nail salons, gel, acrylics, Russian manicures, pedicures, nail art.",
     "examples": ["Nail salons", "gel manicures", "acrylics", "Russian manicures", "pedicures", "nail art"]},
    {"slug": "skin", "name": "Skin", "description": "Facials, skincare studios, estheticians, acne, peels, microneedling, hydrafacials.",
     "examples": ["Facials", "skincare studios", "estheticians", "acne treatments", "peels", "microneedling", "hydrafacials"]},
    {"slug": "lashes-brows", "name": "Lashes & Brows", "description": "Lash extensions, lash lifts, brow shaping, brow lamination, microblading.",
     "examples": ["Lash extensions", "lash lifts", "brow shaping", "brow lamination", "microblading"]},
    {"slug": "makeup", "name": "Makeup", "description": "Makeup artists for bridal, event, and permanent makeup.",
     "examples": ["Makeup artists", "bridal makeup", "event makeup", "permanent makeup"]},
    {"slug": "med-beauty", "name": "Med Beauty", "description": "Med spas, Botox, fillers, lasers, skin tightening, body contouring.",
     "examples": ["Med spas", "Botox", "fillers", "lasers", "skin tightening", "body contouring"]},
    {"slug": "cosmetic-surgery", "name": "Cosmetic Surgery", "description": "Plastic surgeons for facial, breast, body, rhinoplasty.",
     "examples": ["Plastic surgeons", "facial plastic surgery", "breast surgery", "body surgery", "rhinoplasty"]},
    {"slug": "tanning-glow", "name": "Tanning & Glow", "description": "Spray tans, tanning salons, body shimmer, event prep.",
     "examples": ["Spray tans", "tanning salons", "body shimmer", "event prep"]},
    {"slug": "beauty-at-home", "name": "Beauty at Home", "description": "Mobile hair, makeup, nails, and glam squads.",
     "examples": ["Mobile hair", "mobile makeup", "mobile nails", "glam squads"]},
    {"slug": "beauty-shopping", "name": "Beauty Shopping", "description": "Beauty boutiques, skincare shops, perfume, clean beauty, pro beauty supply.",
     "examples": ["Beauty boutiques", "skincare shops", "perfume", "clean beauty", "pro beauty supply"]},
]


WELLNESS_CATEGORIES = [
    {"slug": "spas-relaxation", "name": "Spas & Relaxation", "description": "Day spas, hotel spas, massage, facials, body treatments.",
     "examples": ["Day spas", "hotel spas", "massage", "facials", "body treatments"]},
    {"slug": "recovery-cold-plunge", "name": "Sauna, Cold Plunge & Recovery", "description": "Infrared saunas, cold plunge, cryotherapy, compression, recovery lounges.",
     "examples": ["Infrared saunas", "cold plunge", "cryotherapy", "compression therapy", "recovery lounges"]},
    {"slug": "iv-hydration", "name": "IV & Hydration", "description": "IV therapy, vitamin shots, hydration lounges.",
     "examples": ["IV therapy", "vitamin shots", "hydration lounges"]},
    {"slug": "yoga-meditation", "name": "Yoga, Meditation & Breathwork", "description": "Yoga studios, meditation, breathwork, sound baths, mindfulness.",
     "examples": ["Yoga studios", "meditation", "breathwork", "sound baths", "mindfulness"]},
    {"slug": "holistic-alternative", "name": "Holistic & Alternative Wellness", "description": "Acupuncture, reiki, energy work, Ayurveda, naturopathy, Chinese medicine.",
     "examples": ["Acupuncture", "reiki", "energy work", "Ayurveda", "naturopathy", "Chinese medicine"]},
    {"slug": "nutrition-clean-living", "name": "Nutrition & Clean Living", "description": "Nutrition coaches, wellness cafés, juice bars, supplements, detox programs.",
     "examples": ["Nutrition coaches", "wellness cafés", "juice bars", "supplements", "detox programs"]},
    {"slug": "sleep-stress", "name": "Sleep & Stress", "description": "Sleep clinics, stress coaching, relaxation therapy, burnout recovery.",
     "examples": ["Sleep clinics", "stress coaching", "relaxation therapy", "burnout recovery"]},
    {"slug": "retreats-experiences", "name": "Retreats & Experiences", "description": "Wellness retreats, day retreats, spa getaways, corporate wellness.",
     "examples": ["Wellness retreats", "day retreats", "spa getaways", "corporate wellness"]},
]


HEALTH_CATEGORIES = [
    {"slug": "aesthetics-medical-beauty", "name": "Aesthetics & Medical Beauty", "description": "Med spas, Botox, fillers, lasers, body contouring, cosmetic dermatology, plastic surgery, hair restoration.",
     "examples": ["Med spas", "Botox", "fillers", "lasers", "body contouring", "cosmetic dermatology", "plastic surgery", "hair restoration"]},
    {"slug": "weight-loss-metabolic", "name": "Weight Loss & Metabolic Health", "description": "GLP-1 clinics, medical weight loss, nutrition doctors, obesity medicine, diabetes prevention, body composition testing.",
     "examples": ["GLP-1 clinics", "medical weight loss", "nutrition doctors", "obesity medicine", "diabetes prevention", "body composition testing"]},
    {"slug": "longevity-hormones", "name": "Longevity, Hormones & Optimization", "description": "Longevity clinics, testosterone therapy, hormone therapy, menopause care, peptide clinics, functional medicine, executive physicals.",
     "examples": ["Longevity clinics", "testosterone therapy", "hormone therapy", "menopause care", "peptide clinics", "functional medicine", "executive physicals", "preventive testing"]},
    {"slug": "dental-smile", "name": "Dental & Smile", "description": "Cosmetic dentistry, veneers, Invisalign, dental implants, teeth whitening, orthodontics, pediatric dentistry, oral surgery.",
     "examples": ["Cosmetic dentistry", "veneers", "Invisalign", "dental implants", "teeth whitening", "orthodontics", "pediatric dentistry", "oral surgery"]},
    {"slug": "mental-health-therapy", "name": "Mental Health & Therapy", "description": "Therapists, psychiatrists, couples therapy, family therapy, teen therapy, ADHD, anxiety, ketamine, addiction.",
     "examples": ["Therapists", "psychiatrists", "couples therapy", "family therapy", "teen therapy", "ADHD evaluation", "anxiety specialists", "ketamine therapy", "addiction treatment"]},
    {"slug": "fertility-womens-health", "name": "Fertility, Pregnancy & Women's Health", "description": "Fertility clinics, IVF, egg freezing, OB/GYN, midwives, doulas, pelvic floor therapy, lactation consultants.",
     "examples": ["Fertility clinics", "IVF", "egg freezing", "OB/GYN", "midwives", "doulas", "pelvic floor therapy", "lactation consultants"]},
    {"slug": "physical-therapy-pain", "name": "Physical Therapy, Pain & Recovery", "description": "Physical therapy, chiropractic, pain management, sports injury, orthopedics, acupuncture, massage, regenerative medicine.",
     "examples": ["Physical therapy", "chiropractic", "pain management", "sports injury care", "orthopedics", "acupuncture", "massage therapy", "regenerative medicine"]},
    {"slug": "primary-care-clinics", "name": "Primary Care & Clinics", "description": "Concierge medicine, direct primary care, urgent care, family medicine, pediatrics, internal medicine, house-call doctors, telehealth.",
     "examples": ["Concierge medicine", "direct primary care", "urgent care", "family medicine", "pediatrics", "internal medicine", "house-call doctors", "telehealth"]},
    {"slug": "nutrition-healthy-living", "name": "Nutrition & Healthy Living", "description": "Dietitians, nutritionists, meal planning, gut health, healthy meal prep, wellness coaching.",
     "examples": ["Dietitians", "nutritionists", "meal planning", "gut health", "healthy meal prep", "wellness coaching"]},
    {"slug": "medical-specialists", "name": "Medical Specialists", "description": "Dermatology, cardiology, gastroenterology, ENT, neurology, rheumatology, urology, ophthalmology, allergy.",
     "examples": ["Dermatology", "cardiology", "gastroenterology", "ENT", "neurology", "rheumatology", "urology", "ophthalmology", "allergy and immunology"]},
]


NETWORK_DEFS = [
    {
        "slug": "beauty",
        "name": "Knows Beauty",
        "tagline": "The local beauty guide locals book from.",
        "description": "A curated guide to the salons, med spas, nail artists, colorists, and glam pros locals book before the moment.",
        "domains": [
            "knowsbeauty.ai.devintensive.com",
            "knowsbeauty.localhost",
            "knowsbeauty.com",
        ],
        "theme": {
            "primary_color": "#0e0e10",
            "accent_color": "#c89f5b",
            "body_font": "Inter, system-ui, sans-serif",
            "display_font": "Playfair Display, Georgia, serif",
            "hero_treatment": "dark",
        },
        "categories": BEAUTY_CATEGORIES,
        "sensitive_content_review": False,
    },
    {
        "slug": "wellness",
        "name": "Knows Wellness",
        "tagline": "Where locals go to feel better.",
        "description": "A curated guide to the spas, recovery lounges, yoga studios, nutritionists, and wellness experiences locals trust.",
        "domains": [
            "knowswellness.ai.devintensive.com",
            "knowswellness.localhost",
            "knowswellness.com",
        ],
        "theme": {
            "primary_color": "#1a2a23",
            "accent_color": "#9ac4a1",
            "body_font": "Inter, system-ui, sans-serif",
            "display_font": "Playfair Display, Georgia, serif",
            "hero_treatment": "dark",
        },
        "categories": WELLNESS_CATEGORIES,
        "sensitive_content_review": False,
    },
    {
        "slug": "health",
        "name": "Knows Health",
        "tagline": "Find the right doctor, dentist, or clinic.",
        "description": "A curated provider directory for cosmetic dentistry, mental health, fertility, primary care, and specialists. We promote the provider, not the medical outcome.",
        "domains": [
            "knowshealth.ai.devintensive.com",
            "knowshealth.localhost",
            "knowshealth.com",
        ],
        "theme": {
            "primary_color": "#0f2238",
            "accent_color": "#dfb27b",
            "body_font": "Inter, system-ui, sans-serif",
            "display_font": "Playfair Display, Georgia, serif",
            "hero_treatment": "dark",
        },
        "categories": HEALTH_CATEGORIES,
        # Health requires extra editorial review for medical claims.
        "sensitive_content_review": True,
    },
]


async def main() -> None:
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
