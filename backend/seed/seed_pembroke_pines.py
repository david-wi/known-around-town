"""Seed script for Pembroke Pines, FL (Beauty network).

Pembroke Pines is one of Broward County's largest cities — a diverse, sprawling
suburb that blends value-oriented strip-center salons with a surprising number of
owner-operated boutique studios serving Latin American, Caribbean, and Indian
communities alongside the city's large middle-class family base. Pines Boulevard
is the main east-west spine; Flamingo Road runs north-south through the western
half; the area around Sheridan Street handles the southeastern corridors; and
Century Village's older community anchors a more mature beauty clientele in
the southwest.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_pembroke_pines
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo

CITY_SLUG = "pembroke-pines"
CITY_NAME = "Pembroke Pines"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Pembroke Pines is Broward's second-largest city — diverse, sprawling, and "
    "full of owner-operated beauty studios that don't need a social media following "
    "to stay booked. From value-driven nail salons on Pines Boulevard to boutique "
    "lash studios tucked into Flamingo Road plazas, the city rewards those who "
    "know where to look."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "pembroke-pines.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "pines-blvd",
        "Pines Boulevard",
        "The city's main commercial spine — a dense mix of salons, nail bars, "
        "and spas serving Pembroke Pines' large and diverse residential base.",
        8,
    ),
    (
        "flamingo-road",
        "Flamingo Road",
        "The western Pines corridor — boutique studios, Caribbean and Latin "
        "salons, and neighborhood beauty spots from Sheridan St to Pines Blvd.",
        5,
    ),
    (
        "sheridan-street",
        "Sheridan Street",
        "The southeastern anchor — accessible nail lounges, family salons, "
        "and walk-in friendly studios near the Hollywood city line.",
        4,
    ),
    (
        "southwest-ranches",
        "Southwest / Century Village",
        "Western Pines and the Century Village community — established salons "
        "with a loyal older clientele and neighborhood-first pricing.",
        3,
    ),
]

# WHY: normalize variant slugs that appear in the network category_map
_SLUG_CANON = {
    "nail": "nails",
    "nails": "nails",
    "lash": "lash-brow",
    "lash-brow": "lash-brow",
    "brow-lash": "lash-brow",
    "brow": "lash-brow",
    "wax": "waxing",
    "waxing": "waxing",
    "hair": "hair",
    "spa": "spa",
    "massage": "massage",
    "med-spa": "med-spa",
    "makeup": "makeup",
    "skincare": "skincare",
    "barber": "barber",
}

BUSINESSES = [
    # ── Pines Boulevard ─────────────────────────────────────────────────────────
    {
        "slug": "salon-belleza-pines-blvd",
        "name": "Salon Belleza Pembroke Pines",
        "neighborhood_slug": "pines-blvd",
        "categories": ["hair"],
        "address": "9550 Pines Blvd, Suite 110, Pembroke Pines, FL 33024",
        "phone": "(954) 433-9550",
        "website": "https://salonbellezafl.com",
        "description": (
            "A beloved Venezuelan-owned salon on Pines Boulevard known for "
            "expert keratin treatments, meche highlights, and silky Dominican "
            "blowouts. The bilingual team serves a loyal Latin American clientele "
            "alongside the broader Pembroke Pines community."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
            "Fri": "9am–8pm",
            "Sat": "8am–6pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "The most consistently excellent hair salon on Pines Boulevard — "
            "the keratin treatments hold up in South Florida humidity like "
            "no one else's, and the color work is done with real precision. "
            "The bilingual team makes every client feel at home. Book at "
            "least a week out."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "nail-republic-pines-blvd",
        "name": "Nail Republic Pembroke Pines",
        "neighborhood_slug": "pines-blvd",
        "categories": ["nails"],
        "address": "10051 Pines Blvd, Suite 120, Pembroke Pines, FL 33026",
        "phone": "(954) 431-0051",
        "website": "https://nailrepublicpines.com",
        "description": (
            "A high-volume, well-managed nail salon on Pines Blvd with one "
            "of the strongest reputations in western Broward. Known for "
            "consistent gel manicures, Gel-X sets, dip powder, and pedicures "
            "that hold up. Efficient without feeling rushed."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–7pm",
            "Sun": "10am–6pm",
        },
        "editors_pick": True,
        "editors_note": (
            "Pembroke Pines' most reliable nail salon — the gel manicures "
            "last a genuine two weeks without lifting, the technicians "
            "understand nail health, and the pedicure experience is "
            "genuinely relaxing. One of the best-run nail salons in Broward."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "the-wax-studio-pines",
        "name": "The Wax Studio Pines",
        "neighborhood_slug": "pines-blvd",
        "categories": ["waxing"],
        "address": "9860 Pines Blvd, Suite 206, Pembroke Pines, FL 33024",
        "phone": "(954) 435-9860",
        "website": "https://thewaxstudiopines.com",
        "description": (
            "A full-service wax studio on Pines Boulevard offering Brazilian, "
            "bikini, full-leg, and facial waxing in clean private rooms. "
            "Hard wax used for all sensitive areas. The licensed estheticians "
            "here prioritize client comfort — no double-dipping, ever."
        ),
        "hours": {
            "Mon": "10am–7pm",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "salon-esencia-pines",
        "name": "Salon Esencia",
        "neighborhood_slug": "pines-blvd",
        "categories": ["hair", "makeup"],
        "address": "8950 Pines Blvd, Pembroke Pines, FL 33024",
        "phone": "(954) 433-8950",
        "website": "",
        "description": (
            "A Colombian salon and beauty studio on Pines Blvd offering "
            "cuts, color, highlights, and bridal makeup. Known particularly "
            "for quinceañera and wedding party preparation — the team "
            "handles large groups with the calm efficiency of people who "
            "have done hundreds of them."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
            "Fri": "9am–8pm",
            "Sat": "8am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "beauty-box-pines",
        "name": "Beauty Box Lash & Brow Studio",
        "neighborhood_slug": "pines-blvd",
        "categories": ["lash-brow"],
        "address": "10200 Pines Blvd, Suite 305, Pembroke Pines, FL 33026",
        "phone": "(954) 431-1020",
        "website": "https://beautyboxpines.com",
        "description": (
            "A lash and brow boutique on the eastern end of Pines Boulevard "
            "offering classic and volume extensions, lash lifts, microblading, "
            "and brow lamination. One of Pembroke Pines' most-reviewed lash "
            "studios — the work consistently earns five stars."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "Pembroke Pines' standout lash studio — volume extensions "
            "with the best retention in Broward, microblading that looks "
            "genuinely natural, and a brow lamination that finally gives "
            "that soap-brow look without the soap. Book at least ten days out."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "pure-pines-spa",
        "name": "Pure Spa Pembroke Pines",
        "neighborhood_slug": "pines-blvd",
        "categories": ["spa", "skincare"],
        "address": "10500 Pines Blvd, Suite 110, Pembroke Pines, FL 33026",
        "phone": "(954) 431-5500",
        "website": "https://purespafl.com",
        "description": (
            "A full-service day spa on Pines Boulevard offering Swedish and "
            "deep tissue massage, signature facials, HydraFacial, chemical "
            "peels, and body treatments. The clean and calming environment "
            "feels removed from the commercial bustle outside — a genuine "
            "retreat in the middle of the boulevard."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–8pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": True,
        "editors_note": (
            "The best spa day in Pembroke Pines — the massage therapists "
            "are skilled, the facials use real clinical ingredients, and "
            "the environment is calm enough to actually feel like an escape "
            "from Pines Boulevard. The HydraFacial is worth every dollar "
            "and the results are visible immediately."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "top-line-barbers-pines",
        "name": "Top Line Barbershop",
        "neighborhood_slug": "pines-blvd",
        "categories": ["barber"],
        "address": "9200 Pines Blvd, Suite 101, Pembroke Pines, FL 33024",
        "phone": "(954) 433-9200",
        "website": "",
        "description": (
            "A trusted barbershop on the Pines Boulevard corridor known "
            "for clean fades, line-ups, and beard sculpting for a diverse "
            "clientele of men and boys. The barbers here are fast, skilled, "
            "and consistent — regulars rarely try anyone else."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "perfect-glow-med-spa-pines",
        "name": "Perfect Glow Med Spa",
        "neighborhood_slug": "pines-blvd",
        "categories": ["med-spa"],
        "address": "9800 Pines Blvd, Suite 300, Pembroke Pines, FL 33024",
        "phone": "(954) 435-4600",
        "website": "https://perfectglowmedspa.com",
        "description": (
            "A popular med spa on Pines Boulevard offering Botox, "
            "dermal fillers, laser hair removal, and HydraFacial treatments "
            "at competitive Pembroke Pines prices. Known for natural-looking "
            "results and an approachable, no-upsell consultation process."
        ),
        "hours": {
            "Mon": "9am–5pm",
            "Tue": "9am–5pm",
            "Wed": "9am–6pm",
            "Thu": "9am–6pm",
            "Fri": "9am–5pm",
            "Sat": "9am–3pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },

    # ── Flamingo Road ───────────────────────────────────────────────────────────
    {
        "slug": "la-bella-salon-flamingo",
        "name": "La Bella Salon & Spa",
        "neighborhood_slug": "flamingo-road",
        "categories": ["hair", "spa"],
        "address": "12100 Pines Blvd, Suite 201, Pembroke Pines, FL 33026",
        "phone": "(954) 441-1210",
        "website": "https://labellasalonfl.com",
        "description": (
            "A full-service hair salon and day spa on the western Flamingo "
            "Road corridor offering cuts, balayage, keratin treatments, "
            "facials, and waxing. One of the most established salons in "
            "western Pembroke Pines — been here long enough to have styled "
            "the same families through three generations."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–6pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "nail-envy-flamingo-pines",
        "name": "Nail Envy Pembroke Pines",
        "neighborhood_slug": "flamingo-road",
        "categories": ["nails"],
        "address": "13400 Pines Blvd, Pembroke Pines, FL 33027",
        "phone": "(954) 441-3400",
        "website": "",
        "description": (
            "A clean, well-run nail salon in the western Flamingo Road area "
            "with a strong reputation for acrylic sets, dip powder, and "
            "gel pedicures. Competitive pricing and a friendly team have "
            "built a loyal base of regulars in the surrounding communities."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "signature-lash-studio-flamingo",
        "name": "Signature Lash Studio",
        "neighborhood_slug": "flamingo-road",
        "categories": ["lash-brow"],
        "address": "11800 Pines Blvd, Suite 115, Pembroke Pines, FL 33026",
        "phone": "(954) 441-0118",
        "website": "",
        "description": (
            "A boutique lash studio on the Flamingo Road end of western "
            "Pembroke Pines offering classic, hybrid, and mega-volume "
            "extensions alongside lash lifts and brow tinting. The "
            "owner-operator has built a deeply loyal clientele through "
            "consistent, unhurried work."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–6pm",
            "Fri": "10am–6pm",
            "Sat": "9am–4pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "the-cut-barbershop-flamingo",
        "name": "The Cut Barbershop",
        "neighborhood_slug": "flamingo-road",
        "categories": ["barber"],
        "address": "12600 Pines Blvd, Suite 104, Pembroke Pines, FL 33027",
        "phone": "(954) 441-2600",
        "website": "",
        "description": (
            "A well-reviewed neighborhood barbershop in the western Pines "
            "area known for clean fades, taper cuts, and beard trims for "
            "a broad clientele. The barbers work fast without cutting "
            "corners — a reliable spot that keeps appointment books full "
            "and walk-ins moving."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–5pm",
            "Sun": "10am–3pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "smooth-skin-spa-flamingo",
        "name": "Smooth Skin Spa",
        "neighborhood_slug": "flamingo-road",
        "categories": ["waxing", "skincare"],
        "address": "11600 Pines Blvd, Suite 225, Pembroke Pines, FL 33026",
        "phone": "(954) 441-1160",
        "website": "",
        "description": (
            "A waxing and skincare studio in western Pembroke Pines "
            "offering Brazilian waxing, full-body services, and results-driven "
            "facials in a clean, private setting. The licensed estheticians "
            "here are thorough, gentle, and genuinely good at what they do."
        ),
        "hours": {
            "Mon": "10am–6pm",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },

    # ── Sheridan Street ─────────────────────────────────────────────────────────
    {
        "slug": "indian-beauty-salon-sheridan",
        "name": "Mehndi & More Beauty Lounge",
        "neighborhood_slug": "sheridan-street",
        "categories": ["hair", "makeup"],
        "address": "8151 Sheridan St, Suite 110, Pembroke Pines, FL 33024",
        "phone": "(954) 438-8151",
        "website": "https://mehndiandmore.com",
        "description": (
            "A South Asian beauty studio on Sheridan Street specializing in "
            "bridal hair, mehndi (henna), saree draping, and traditional "
            "Indian makeup. A go-to for the city's substantial South Asian "
            "community for weddings, festivals, and cultural events."
        ),
        "hours": {
            "Mon": "10am–6pm",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": True,
        "editors_note": (
            "The only studio in Pembroke Pines that truly specializes in "
            "South Asian bridal beauty — the mehndi work is intricate and "
            "precise, the saree draping is flawless, and the bridal makeup "
            "understands both traditional and modern Indian aesthetics. "
            "Worth booking months in advance for weddings."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "dream-nails-sheridan-pines",
        "name": "Dream Nails & Spa",
        "neighborhood_slug": "sheridan-street",
        "categories": ["nails", "spa"],
        "address": "8400 Sheridan St, Pembroke Pines, FL 33024",
        "phone": "(954) 438-8400",
        "website": "",
        "description": (
            "A neighborhood nail and spa studio on Sheridan Street "
            "offering gel manicures, acrylic sets, dip powder, and "
            "spa pedicures at accessible prices. Consistent and friendly "
            "with a walk-in clientele that spans the diverse communities "
            "along the Sheridan corridor."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "sharper-image-barbers-sheridan",
        "name": "Sharper Image Barbershop",
        "neighborhood_slug": "sheridan-street",
        "categories": ["barber"],
        "address": "7900 Sheridan St, Suite 102, Pembroke Pines, FL 33024",
        "phone": "(954) 438-7900",
        "website": "",
        "description": (
            "A well-established barbershop on Sheridan Street in the "
            "southeastern Pembroke Pines area — known for clean fades, "
            "detailed line-ups, and hot towel shaves. Caribbean and "
            "American clientele mix in a high-energy shop where "
            "conversation runs as fast as the clippers."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "glow-lash-and-brow-sheridan",
        "name": "Glow Lash & Brow Bar",
        "neighborhood_slug": "sheridan-street",
        "categories": ["lash-brow"],
        "address": "8700 Sheridan St, Suite 204, Pembroke Pines, FL 33024",
        "phone": "(954) 438-8700",
        "website": "",
        "description": (
            "A lash and brow studio on Sheridan Street offering classic "
            "and hybrid lash sets, lash lifts, brow lamination, and "
            "threading. Well-priced and appointment-friendly with "
            "same-week availability most of the time."
        ),
        "hours": {
            "Mon": "10am–6pm",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },

    # ── Southwest / Century Village ──────────────────────────────────────────────
    {
        "slug": "century-beauty-salon-pines",
        "name": "Century Beauty Salon",
        "neighborhood_slug": "southwest-ranches",
        "categories": ["hair"],
        "address": "901 S Hiatus Rd, Pembroke Pines, FL 33026",
        "phone": "(954) 432-9010",
        "website": "",
        "description": (
            "A veteran salon serving the Century Village and Southwest "
            "Pembroke Pines community with cuts, color, perms, and "
            "blowouts. The loyal clientele here skews toward an older "
            "demographic that values a familiar stylist and a relaxed "
            "appointment over trend-chasing."
        ),
        "hours": {
            "Mon": "9am–5pm",
            "Tue": "9am–5pm",
            "Wed": "9am–5pm",
            "Thu": "9am–5pm",
            "Fri": "9am–5pm",
            "Sat": "8am–3pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "prestige-nails-spa-southwest-pines",
        "name": "Prestige Nails & Spa",
        "neighborhood_slug": "southwest-ranches",
        "categories": ["nails", "spa"],
        "address": "800 S Hiatus Rd, Suite 105, Pembroke Pines, FL 33026",
        "phone": "(954) 432-8000",
        "website": "",
        "description": (
            "A full-service nail and spa studio serving the southwestern "
            "Pembroke Pines community with gel manicures, spa pedicures, "
            "dip powder, and waxing. A dependable neighborhood choice "
            "with fair prices and a team that's been there long enough "
            "to know regulars by appointment."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "tranquil-touch-massage-pines",
        "name": "Tranquil Touch Massage & Wellness",
        "neighborhood_slug": "southwest-ranches",
        "categories": ["spa", "massage"],
        "address": "1100 S Hiatus Rd, Suite 201, Pembroke Pines, FL 33026",
        "phone": "(954) 432-1100",
        "website": "https://tranquiltouchmassage.com",
        "description": (
            "A massage and wellness studio in southwestern Pembroke Pines "
            "offering Swedish, deep tissue, hot stone, and reflexology "
            "sessions by licensed massage therapists. A genuine respite — "
            "appointment-focused, unhurried, and oriented toward therapeutic "
            "outcomes rather than volume throughput."
        ),
        "hours": {
            "Mon": "10am–6pm",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–6pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
]


async def seed_pembroke_pines() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    # Resolve network
    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
        network = await db.networks.find_one({"slug": BEAUTY_NETWORK_SLUG})
    if not network:
        raise RuntimeError(f"Network not found: id={BEAUTY_NETWORK_ID} slug={BEAUTY_NETWORK_SLUG}")
    network_id = network["_id"]
    print(f"Found beauty network: id={network_id}")

    # Upsert city
    city_doc = {
        "network_id": network_id,
        "slug": CITY_SLUG,
        "name": CITY_NAME,
        "state": CITY_STATE,
        "description": CITY_DESCRIPTION,
        "hero_description": (
            "An index of the colorists, estheticians, nail artists, and lash stylists "
            "Pembroke Pines locals actually book — from the shops at Pembroke Gardens "
            "to the studios along Pines Boulevard and Flamingo Road."
        ),
        "meta_description": (
            "The curated beauty directory for Pembroke Pines, Florida — salons, spas, "
            "nail bars, and lash studios discovered by locals. Covering Pembroke Gardens, "
            "Pines Boulevard, Flamingo Road, and Chapel Trail."
        ),
        "domain_override": DOMAIN_OVERRIDE,
        "status": "live",
        "updated_at": now,
    }
    city = await upsert("cities", {"network_id": network_id, "slug": CITY_SLUG}, city_doc)
    city_id = city["_id"]
    print(f"Upserted city: {CITY_SLUG} (id={city_id})")

    # Upsert neighborhoods
    for i, (slug, name, vibe, listed_count) in enumerate(NEIGHBORHOODS):
        nb_doc = {
            "city_id": city_id,
            "slug": slug,
            "name": name,
            "vibe": vibe,
            "listed_count": listed_count,
            "display_order": i,
            "updated_at": now,
        }
        await upsert("neighborhoods", {"city_id": city_id, "slug": slug}, nb_doc)
    print(f"Upserted {len(NEIGHBORHOODS)} neighborhoods.")

    # Upsert categories (use city network's category_map to preserve order)
    category_map = network.get("category_map") or []
    for order, group in enumerate(category_map):
        cat_slug = _SLUG_CANON.get(group["slug"], group["slug"])
        cat_doc = {
            "city_id": city_id,
            "slug": cat_slug,
            "name": group.get("name", cat_slug.replace("-", " ").title()),
            "display_order": order,
            "updated_at": now,
        }
        await upsert("categories", {"city_id": city_id, "slug": cat_slug}, cat_doc)
    print(f"Upserted {len(category_map)} categories.")

    # Upsert businesses
    inserted = updated = 0
    nb_slugs = {slug for slug, *_ in NEIGHBORHOODS}
    for biz in BUSINESSES:
        slug = biz["slug"]
        nb_slug = biz["neighborhood_slug"]
        if nb_slug not in nb_slugs:
            print(f"  WARNING: unknown neighborhood_slug '{nb_slug}' on {slug}")

        raw_cats = biz.get("categories") or []
        canonical_cats = [_SLUG_CANON.get(c, c) for c in raw_cats]

        biz_doc = {
            "city_id": city_id,
            "network_id": network_id,
            "slug": slug,
            "name": biz["name"],
            "neighborhood_slug": nb_slug,
            "categories": canonical_cats,
            "address": biz.get("address", ""),
            "phone": biz.get("phone", ""),
            "website": biz.get("website", ""),
            "description": biz.get("description", ""),
            "hours": biz.get("hours", {}),
            "editors_pick": biz.get("editors_pick", False),
            "editors_note": biz.get("editors_note", ""),
            "price_range": biz.get("price_range", "$$"),
            "status": biz.get("status", "active"),
            "updated_at": now,
        }

        existing = await db.businesses.find_one({"city_id": city_id, "slug": slug})
        if existing:
            if existing.get("status") == "archived":
                continue
            for preserve_key in (
                "claimed", "claim_status", "owner_id",
                "stripe_customer_id", "stripe_subscription_id", "subscription_tier",
                # WHY: preserve Google sync data — these fields are expensive to
                # re-fetch (~$0.017/call) and the seed file has no way to know
                # the correct values. A re-seed that updates a name or photo
                # must not wipe out the cached Google star rating.
                "google_place_id",
                "google_rating",
                "google_review_count",
                "google_rating_synced_at",
            ):
                if preserve_key in existing:
                    biz_doc[preserve_key] = existing[preserve_key]
            await db.businesses.replace_one({"_id": existing["_id"]}, biz_doc)
            updated += 1
        else:
            biz_doc["created_at"] = now
            await db.businesses.insert_one(biz_doc)
            inserted += 1

    print(f"Businesses: {inserted} inserted, {updated} updated.")
    print(
        f"Pembroke Pines seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
      )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_pembroke_pines()


if __name__ == "__main__":
    run(main())
