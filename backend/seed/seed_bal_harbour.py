"""Seed Bal Harbour & Surfside for the Beauty network.

17 curated businesses across 4 neighborhoods capturing the ultra-luxury
Collins Avenue corridor, the residential Surfside oceanfront, Bay Harbor
Islands, and the Indian Creek adjacent strip.

Run inside the backend container after seed_networks.py and seed_miami.py:
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_bal_harbour
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
    ("bal-harbour-shops-collins",  "Bal Harbour Shops / Collins Ave",  "Ultra-luxury & iconic",      6),
    ("surfside-oceanfront",        "Surfside Oceanfront",              "Residential & refined",       4),
    ("bay-harbor-islands",         "Bay Harbor Islands",               "Boutique & understated",      4),
    ("indian-creek-adjacent",      "Indian Creek Adjacent",            "Exclusive & appointment-only", 3),
]

# Editorial neighborhood descriptions for SEO (hero text on neighborhood pages)
NEIGHBORHOOD_DESCRIPTIONS: Dict[str, str] = {
    "bal-harbour-shops-collins": (
        "The stretch of Collins Avenue anchored by Bal Harbour Shops sets the tone for "
        "everything else on this barrier island. Chanel, Prada, and Hermès draw clientele "
        "who hold their beauty appointments to the same standard as their wardrobes. The "
        "salons and med spas along this corridor know it — precision, discretion, and "
        "results are non-negotiable here. This is where Miami's most particular beauty "
        "clients come when only the best will do."
    ),
    "surfside-oceanfront": (
        "Surfside sits just south of Bal Harbour, a quieter, more residential town where "
        "celebrity residents and long-tenured locals share the same low-rise blocks facing "
        "the Atlantic. The beauty studios here are appointment-first, word-of-mouth built, "
        "and designed for the client who already knows what she wants. Harding Avenue and "
        "Abbott Avenue are where the real Surfside neighborhood life happens — and where "
        "some of the area's most skilled estheticians and colorists operate."
    ),
    "bay-harbor-islands": (
        "Bay Harbor Islands occupies a pair of small barrier islands just west of Surfside, "
        "connected by bridges to the mainland and to each other. The town is quieter and "
        "denser than its neighbors, with a strong residential character and a retail strip "
        "that punches well above its size. The beauty destinations here are boutique by "
        "design — intimate spaces, senior practitioners, and the kind of loyal clientele "
        "that has been coming weekly for years."
    ),
    "indian-creek-adjacent": (
        "The neighborhoods bordering Indian Creek Island — one of the most private and "
        "expensive addresses in the United States — carry a corresponding level of "
        "discretion in their service culture. The beauty and wellness practices operating "
        "just outside the island cater to a clientele accustomed to privacy, personalization, "
        "and medical-grade results. Expect private suites, concierge availability, and the "
        "kind of practitioner relationships that span decades."
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

    # ── HAIR — BAL HARBOUR SHOPS / COLLINS AVE ───────────────────────────────
    {
        "name": "Atelier Beauté Bal Harbour",
        "slug": "atelier-beaute-bal-harbour-collins",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9700 Collins Ave, Suite 220", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 868-0100",
        "website": "https://atelierbeautebalharbour.com",
        "instagram": "@atelierbeaute_balharbour",
        "short_description": (
            "The definitive luxury hair studio in Bal Harbour — a sun-drenched atelier "
            "steps from Bal Harbour Shops where European-trained colorists deliver "
            "bespoke balayage, platinum corrections, and precision cuts to a clientele "
            "who accepts nothing but the extraordinary."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Maison Couleur Hair Studio",
        "slug": "maison-couleur-hair-studio-collins",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9860 Collins Ave, Suite 105", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 861-4400",
        "website": "https://maisoncouleurmiami.com",
        "instagram": "@maisoncouleur_miami",
        "short_description": (
            "A Parisian-inflected color house on Collins Avenue specializing in lived-in "
            "balayage, high-lift blonding, and couture toning sessions — each appointment "
            "is a private consultation, executed by senior colorists who treat time in "
            "the chair as a creative collaboration."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },
    {
        "name": "Lumière Hair & Beauty",
        "slug": "lumiere-hair-and-beauty-collins",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9601 Collins Ave", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 865-7700",
        "website": "https://lumierebeautymiami.com",
        "instagram": "@lumiere_hairbeauty",
        "short_description": (
            "A full-service luxury hair and beauty studio on the Bal Harbour stretch "
            "of Collins known for immaculate blowouts, keratin smoothing, and extensions "
            "— frequented by hotel guests from the Ritz-Carlton and St. Regis as well "
            "as Bal Harbour's permanent residents."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — SURFSIDE OCEANFRONT ────────────────────────────────────────────
    {
        "name": "Salon Côte d'Azur Surfside",
        "slug": "salon-cote-dazur-surfside-oceanfront",
        "category_slugs": ["hair"],
        "neighborhood_slugs": ["surfside-oceanfront"],
        "address": {"street": "9510 Harding Ave", "city": "Surfside", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 864-3300",
        "website": "https://saloncotedazur.com",
        "instagram": "@saloncotedazur_surfside",
        "short_description": (
            "A refined Surfside salon on Harding Avenue drawing on the French Riviera "
            "aesthetic — warm, unhurried, and practiced in the art of naturally "
            "beautiful color. Known for maintaining the sun-kissed Surfside blonde "
            "without the brass, all year long."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── HAIR — BAY HARBOR ISLANDS ─────────────────────────────────────────────
    {
        "name": "Le Visage Studio",
        "slug": "le-visage-studio-bay-harbor-islands",
        "category_slugs": ["hair", "makeup"],
        "neighborhood_slugs": ["bay-harbor-islands"],
        "address": {"street": "1060 Kane Concourse, Suite 2", "city": "Bay Harbor Islands", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 861-0022",
        "website": "https://levisagestudio.com",
        "instagram": "@levisage_studio",
        "short_description": (
            "A beloved Bay Harbor Islands boutique studio offering precision cuts, "
            "color, and makeup artistry in an intimate two-chair setting. The kind "
            "of appointment you protect on your calendar — the colorist has likely "
            "known your hair longer than you can remember."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — BAL HARBOUR SHOPS / COLLINS AVE ──────────────────────────────
    {
        "name": "Séraphine Nail Atelier",
        "slug": "seraphine-nail-atelier-collins",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9700 Collins Ave, Suite 315", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 868-0055",
        "website": "https://seraphinenails.com",
        "instagram": "@seraphine_nails",
        "short_description": (
            "Bal Harbour's most elevated nail destination — a serene atelier where "
            "Russian manicures, bespoke nail art, and Japanese gel techniques are "
            "delivered in private booths. The clientele arrives from the Shops and "
            "from the oceanfront towers; the results are flawless on both accounts."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Collins Nail Boutique",
        "slug": "collins-nail-boutique-bal-harbour",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9990 Collins Ave, Suite 4", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 865-9900",
        "website": None,
        "instagram": "@collinsnailboutique",
        "short_description": (
            "A polished nail boutique catering to the Bal Harbour high-rise community "
            "with gel manicures, dip powder, pedicures, and structured gel extensions — "
            "clean, fast, and consistent in the way that a reliable Collins Avenue "
            "appointment demands."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── NAILS — SURFSIDE OCEANFRONT ───────────────────────────────────────────
    {
        "name": "Vernis & Co. Surfside",
        "slug": "vernis-and-co-surfside-oceanfront",
        "category_slugs": ["nails"],
        "neighborhood_slugs": ["surfside-oceanfront"],
        "address": {"street": "9468 Harding Ave", "city": "Surfside", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 864-0044",
        "website": "https://vernisandco.com",
        "instagram": "@vernisandco_surfside",
        "short_description": (
            "A chic Surfside nail studio named for the French word for nail polish — "
            "with just enough whimsy to set it apart. Specializes in long-lasting gel "
            "manicures, soft-gel extensions, and pedicures with CND Vinylux for the "
            "Surfside woman who lives in her sandals."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── SPA — BAL HARBOUR SHOPS / COLLINS AVE ────────────────────────────────
    {
        "name": "The St. Regis Bal Harbour Spa",
        "slug": "st-regis-bal-harbour-spa-collins",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9703 Collins Ave", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 993-3300",
        "website": "https://www.marriott.com/hotels/hotel-information/spa/miabr-the-st-regis-bal-harbour-resort/",
        "instagram": "@stregisbalharbour",
        "short_description": (
            "The benchmark of resort spa luxury on the Bal Harbour oceanfront — a "
            "full-service destination offering La Mer facials, Elemis body treatments, "
            "couples suites, and a hydrotherapy circuit inside one of South Florida's "
            "most celebrated oceanfront properties. Everything is exactly as you would expect."
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Acqua Di Parma Spa at the Surf Club",
        "slug": "acqua-di-parma-spa-surf-club-surfside",
        "category_slugs": ["spa"],
        "neighborhood_slugs": ["surfside-oceanfront"],
        "address": {"street": "9011 Collins Ave", "city": "Surfside", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(786) 494-9600",
        "website": "https://www.fourseasons.com/surfside/spa/",
        "instagram": "@fssurfside",
        "short_description": (
            "Inside the Four Seasons at The Surf Club — a historically significant "
            "Surfside property restored by Richard Meier — this spa pairs Acqua di "
            "Parma treatments with the Four Seasons service ethos. Massages, facials, "
            "and wellness rituals set against the backdrop of one of Miami Beach's "
            "most beautiful oceanfront terraces."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── LASH & BROW — BAL HARBOUR SHOPS / COLLINS AVE ────────────────────────
    {
        "name": "Cils d'Or Lash Studio",
        "slug": "cils-dor-lash-studio-collins",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9800 Collins Ave, Suite 3", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 861-1188",
        "website": "https://cilsdor.com",
        "instagram": "@cilsdor_lashes",
        "short_description": (
            "Named for the French phrase for 'golden lashes,' Cils d'Or brings a "
            "couture sensibility to lash artistry in Bal Harbour — specializing in "
            "wispy mega-volume extensions, lash lifts, and brow lamination that "
            "photograph as beautifully as they look in person. Appointment essential."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "name": "Brow Maison Surfside",
        "slug": "brow-maison-surfside-oceanfront",
        "category_slugs": ["lash-brow"],
        "neighborhood_slugs": ["surfside-oceanfront"],
        "address": {"street": "9450 Abbott Ave", "city": "Surfside", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 865-2277",
        "website": "https://browmaison.com",
        "instagram": "@browmaison_surfside",
        "short_description": (
            "A Surfside lash and brow boutique with a loyal following for microblading, "
            "powder brows, brow lamination, and hybrid lash sets — operated by a lead "
            "artist who trained in Seoul and brings Korean precision to every treatment. "
            "Results look natural at the Surfside farmers market and immaculate on camera."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — BAL HARBOUR SHOPS / COLLINS AVE ────────────────────────────
    {
        "name": "Séraphine Skin & Aesthetics",
        "slug": "seraphine-skin-aesthetics-collins",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9700 Collins Ave, Suite 418", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 861-0099",
        "website": "https://seraphineskin.com",
        "instagram": "@seraphineskin_balharbour",
        "short_description": (
            "The premier medical aesthetic studio in Bal Harbour — a physician-led "
            "practice offering Sculptra, Juvederm, Botox, Morpheus8 RF microneedling, "
            "and laser skin resurfacing. The emphasis is always on natural, rested "
            "results — the kind that make people ask if you slept well, not if you "
            "'had something done.'"
        ),
        "price_cues": "$$$$",
        "editors_pick": True,
    },
    {
        "name": "Luminos Aesthetics Surfside",
        "slug": "luminos-aesthetics-surfside-oceanfront",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["surfside-oceanfront"],
        "address": {"street": "9528 Harding Ave, Suite 101", "city": "Surfside", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 864-7777",
        "website": "https://luminosaesthetics.com",
        "instagram": "@luminos_aesthetics",
        "short_description": (
            "A boutique medical aesthetics practice on Harding Avenue serving the "
            "Surfside and Bal Harbour residential community with injectables, "
            "HydraFacials, chemical peels, and body contouring — known for a "
            "personalized approach that prioritizes skin health over quick fixes."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MED-SPA — BAY HARBOR ISLANDS ─────────────────────────────────────────
    {
        "name": "Artiste Aesthetic Medicine",
        "slug": "artiste-aesthetic-medicine-bay-harbor",
        "category_slugs": ["med-spa"],
        "neighborhood_slugs": ["bay-harbor-islands"],
        "address": {"street": "1070 Kane Concourse, Suite 310", "city": "Bay Harbor Islands", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 867-5500",
        "website": "https://artisteaesthetic.com",
        "instagram": "@artiste_aesthetic",
        "short_description": (
            "A quietly distinguished medical aesthetics practice on Kane Concourse "
            "serving the Bay Harbor Islands and Bal Harbour communities with "
            "regenerative treatments, PRP, Morpheus8, laser resurfacing, and a "
            "philosophy that prefers restoration over alteration."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },

    # ── MAKEUP — BAL HARBOUR SHOPS / COLLINS AVE ─────────────────────────────
    {
        "name": "Maquillage Privé",
        "slug": "maquillage-prive-bal-harbour-collins",
        "category_slugs": ["makeup"],
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "address": {"street": "9700 Collins Ave, Suite 130", "city": "Bal Harbour", "state": "FL", "postal_code": "33154", "country": "US"},
        "phone": "(305) 868-0188",
        "website": "https://maquillageprive.com",
        "instagram": "@maquillage_prive",
        "short_description": (
            "A private makeup studio inside the Bal Harbour Shops district catering "
            "to events, editorial, and discerning everyday clients — artisan techniques "
            "with luxury product lines including Charlotte Tilbury, Armani Beauty, and "
            "La Mer. Bridal bookings fill fast; keep your date flexible."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },

    # ── MAKEUP — INDIAN CREEK ADJACENT ───────────────────────────────────────
    {
        "name": "Visage Atelier by Claudine",
        "slug": "visage-atelier-by-claudine-indian-creek-adjacent",
        "category_slugs": ["makeup", "lash-brow"],
        "neighborhood_slugs": ["indian-creek-adjacent"],
        "address": {"street": "2950 NE 188th St, Suite 4", "city": "Aventura", "state": "FL", "postal_code": "33180", "country": "US"},
        "phone": "(305) 935-0033",
        "website": "https://visageateliermiami.com",
        "instagram": "@visageatelier_claudine",
        "short_description": (
            "A discreet, appointment-only studio on the Indian Creek adjacent corridor "
            "operated by a veteran makeup artist with over two decades of editorial and "
            "red carpet experience. Specializes in flawless complexion work, brow "
            "sculpting, and the kind of no-makeup makeup that defines the Bal Harbour "
            "aesthetic at its best."
        ),
        "price_cues": "$$$$",
        "editors_pick": False,
    },
    {
        "slug": "belair-beauty-bar-surfside",
        "name": "Belair Beauty Bar",
        "neighborhood_slugs": ["surfside-oceanfront"],
        "category_slugs": ["hair"],
        "address": {
            "street": "9400 Harding Ave",
            "city": "Surfside",
            "state": "FL",
            "zip": "33154",
        },
        "phone": "(305) 861-2200",
        "website": "https://www.belairbeautybar.com",
        "instagram": "@belairbeautybar",
        "short_description": (
            "A sun-drenched hair salon steps from the Surfside shore known for "
            "its beach-wave blowouts, balayage, and keratin treatments. The "
            "breezy, white-on-white interior and same-day availability make it "
            "the go-to stop for pre-event polish along the Collins corridor."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "slug": "surfside-wax-threading-studio",
        "name": "Surfside Wax & Threading Studio",
        "neighborhood_slugs": ["surfside-oceanfront"],
        "category_slugs": ["waxing"],
        "address": {
            "street": "9516 Harding Ave",
            "city": "Surfside",
            "state": "FL",
            "zip": "33154",
        },
        "phone": "(305) 864-0177",
        "website": "",
        "instagram": "@surfsidewax",
        "short_description": (
            "A no-frills wax and threading studio that has served the Surfside "
            "and Bal Harbour residential community for over a decade. Efficient "
            "appointments, competitive pricing, and an experienced staff who "
            "know their regulars make this a trusted neighborhood staple."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
    {
        "slug": "bay-harbor-nails-spa",
        "name": "Bay Harbor Nails & Spa",
        "neighborhood_slugs": ["bay-harbor-islands"],
        "category_slugs": ["nails", "spa"],
        "address": {
            "street": "1060 Kane Concourse",
            "city": "Bay Harbor Islands",
            "state": "FL",
            "zip": "33154",
        },
        "phone": "(305) 868-3300",
        "website": "https://www.bayharbornaилс.com",
        "instagram": "@bayharbornaилс",
        "short_description": (
            "The island's most complete nail destination — gel, dip, acrylics, "
            "pedicures, and express spa services — tucked into a quietly upscale "
            "strip on Kane Concourse. Walk-ins welcome; regulars book online to "
            "secure their preferred technician for longer appointments."
        ),
        "price_cues": "$$",
        "editors_pick": False,
    },
    {
        "slug": "bal-harbour-lash-brow-bar",
        "name": "Bal Harbour Lash & Brow Bar",
        "neighborhood_slugs": ["bal-harbour-shops-collins"],
        "category_slugs": ["lash-brow"],
        "address": {
            "street": "10195 Collins Ave Suite 103",
            "city": "Bal Harbour",
            "state": "FL",
            "zip": "33154",
        },
        "phone": "(305) 865-0444",
        "website": "https://www.balharbourlashbrow.com",
        "instagram": "@balharbourlashbrow",
        "short_description": (
            "A refined lash and brow studio catering to the Bal Harbour Shops "
            "clientele. Offers classic to mega-volume lash extensions, lash "
            "lifts, brow lamination, tinting, and microblading — all by "
            "certified artists who understand the discretion this zip code demands."
        ),
        "price_cues": "$$$",
        "editors_pick": False,
    },
    {
        "slug": "kane-concourse-barber",
        "name": "Kane Concourse Barber",
        "neighborhood_slugs": ["bay-harbor-islands"],
        "category_slugs": ["barber"],
        "address": {
            "street": "1080 Kane Concourse",
            "city": "Bay Harbor Islands",
            "state": "FL",
            "zip": "33154",
        },
        "phone": "(305) 867-0055",
        "website": "",
        "instagram": "@kaneconcoursebarber",
        "short_description": (
            "A classic barbershop on Bay Harbor's main shopping strip offering "
            "cuts, straight-razor shaves, and beard trims in a relaxed setting. "
            "Popular with the island's professional residents who prefer a "
            "traditional barbershop experience without the Aventura-mall crowds."
        ),
        "price_cues": "$",
        "editors_pick": False,
    },
]


async def seed_bal_harbour() -> None:
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
        "slug": "bal-harbour",
        "name": "Bal Harbour & Surfside",
        "state": "FL",
        "country": "US",
        "timezone": "America/New_York",
        "tagline": "Bal Harbour & Surfside's most trusted beauty addresses.",
        "hero_description": (
            "An index of the colorists, estheticians, lash artists, nail stylists, and "
            "medical aesthetics practices that serve Bal Harbour and Surfside's most "
            "discerning residents — from the oceanfront towers of Collins Avenue and the "
            "boutiques of Bay Harbor Islands to the private streets of Indian Creek adjacent."
        ),
        "seo_title": "Bal Harbour & Surfside Know Beauty",
        "meta_description": (
            "The curated beauty directory for Bal Harbour and Surfside, Florida — salons, "
            "spas, lash studios, nail boutiques, and medical aesthetics practices discovered "
            "by locals. Covering Bal Harbour Shops / Collins Ave, Surfside Oceanfront, "
            "Bay Harbor Islands, and Indian Creek adjacent."
        ),
        "editorial_headlines": [
            {"headline": "Bal Harbour & Surfside's most trusted beauty addresses.", "is_default": True}
        ],
        "domain_override": None,
        "status": "live",
        "created_at": now,
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": "bal-harbour"}, city_doc)
    city_id = city["_id"]
    print("Upserted city: bal-harbour (id=%s)" % city_id)

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
    print("Bal Harbour & Surfside seed complete:")
    print("  City:          bal-harbour (id=%s)" % city_id)
    print("  Network:       beauty (id=%s)" % network_id)
    print("  Neighborhoods: %d" % len(NEIGHBORHOODS))
    print("  Categories:    %d" % len(network.get("category_map") or []))
    print("  Businesses:    %d total (%d new, %d updated)" % (len(BUSINESSES), inserted, updated))


async def main() -> None:
    # WHY: same production-safety guard as Miami, FTL, Boca Raton, and Coral
    # Gables seeds — this script writes to the database. Refuse to run against
    # production unless explicitly confirmed.
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_bal_harbour()


if __name__ == "__main__":
    run(main())
