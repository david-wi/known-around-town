"""Seed script for Miramar, FL (Beauty network).

Miramar is a fast-growing city in southern Broward County with one of Florida's
most diverse populations — a vibrant mix of Caribbean, Latin American, and African
American communities with a strong Haitian, Jamaican, and Trinidadian presence
alongside a significant Colombian and Venezuelan base. The city's beauty scene
reflects this diversity: Dominican blowout bars, Afro-textured hair specialists,
Brazilian wax studios, Caribbean nail lounges, and Indian threading salons operate
alongside more traditional full-service spots. Miramar Town Center anchors the
upscale retail scene; Silver Lakes and Sunset Lakes serve the thriving planned
communities in western Miramar; Riviera Isles handles the southeastern residential
corridor near the Hollywood border.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_miramar
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert

CITY_SLUG = "miramar"
CITY_NAME = "Miramar"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Miramar is one of South Florida's most diverse cities — a Caribbean and Latin "
    "American melting pot where Dominican blowout bars, Afro-textured specialists, "
    "and Colombian colorists operate alongside luxury med spas. The beauty scene "
    "here reflects the community: technically skilled, culturally fluent, and "
    "deeply loyal to the studios that truly understand their clients."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "miramar.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "miramar-town-center",
        "Miramar Town Center",
        "Miramar's upscale retail and dining hub along Miramar Pkwy — home to "
        "full-service salons, luxury med spas, and boutique beauty studios "
        "serving the city's professional and family clientele.",
        8,
    ),
    (
        "silver-lakes",
        "Silver Lakes",
        "A large planned community in western Miramar — neighborhood salons, "
        "nail bars, and lash studios serving the diverse families and "
        "professionals who fill Silver Lakes' quiet streets.",
        5,
    ),
    (
        "sunset-lakes",
        "Sunset Lakes",
        "One of western Miramar's premier residential communities — boutique "
        "studios, Caribbean and Latin-owned salons, and appointment-first "
        "beauty spots catering to Sunset Lakes' active family base.",
        4,
    ),
    (
        "riviera-isles",
        "Riviera Isles",
        "Eastern Miramar's established residential corridor near the Hollywood "
        "border — accessible salons, nail lounges, and walk-in barbershops "
        "serving the community's diverse mix of families and young professionals.",
        5,
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
    # ── Miramar Town Center ─────────────────────────────────────────────────────
    {
        "slug": "salon-beaute-miramar-town-center",
        "name": "Salon Beauté Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["hair"],
        "address": "3150 SW 145th Ave, Suite 110, Miramar, FL 33027",
        "phone": "(954) 602-3150",
        "website": "https://salonbeautemiramar.com",
        "description": (
            "A well-established full-service salon in Miramar Town Center "
            "offering precision cuts, balayage, keratin treatments, and "
            "Dominican blowouts for Miramar's diverse clientele. The "
            "bilingual team is equally skilled in straight, wavy, and "
            "textured hair — a true neighborhood anchor that understands "
            "the full range of South Florida hair."
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
            "The most culturally fluent salon in Miramar Town Center — the "
            "team is as comfortable with Dominican blowouts and meche "
            "highlights as they are with keratin treatments and color "
            "corrections. Technically strong across all textures. Book "
            "the keratin at least a week out."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "luxe-nail-lounge-miramar",
        "name": "Luxe Nail Lounge Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["nails"],
        "address": "3100 SW 145th Ave, Suite 205, Miramar, FL 33027",
        "phone": "(954) 602-3100",
        "website": "https://luxenaillounge.com",
        "description": (
            "A premium nail lounge in Miramar Town Center known for "
            "meticulous gel manicures, Russian manicures, Gel-X extensions, "
            "and elaborate nail art in a clean, upscale environment. "
            "The lounge caters to Miramar's style-conscious community "
            "with a service menu that goes beyond the basics and a tech "
            "team that posts their work because it's worth posting."
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
            "Miramar's nail destination — the nail art here is genuinely "
            "creative, the Russian manicures are technically sound, and "
            "the Gel-X sets hold up for three weeks without lifting. "
            "The most consistent nail work in the Town Center area."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "vida-med-spa-miramar",
        "name": "Vida Med Spa Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["med-spa"],
        "address": "3200 SW 145th Ave, Suite 300, Miramar, FL 33027",
        "phone": "(954) 602-3200",
        "website": "https://vidamedspa.com",
        "description": (
            "A physician-supervised med spa in Miramar Town Center offering "
            "Botox, dermal fillers, Sculptra, laser hair removal, "
            "HydraFacial, and body contouring treatments. The clinical "
            "team serves Miramar's professional clientele with a nuanced "
            "understanding of diverse skin tones and a strong track record "
            "on deeper complexions."
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
        "editors_pick": True,
        "editors_note": (
            "Miramar's most trusted med spa — the injectors here understand "
            "diverse skin tones, the laser hair removal is calibrated for "
            "deeper complexions, and the HydraFacial results are visible "
            "immediately. The clinical approach without the clinical coldness."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "bella-lash-miramar-town-center",
        "name": "Bella Lash Studio Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["lash-brow"],
        "address": "3050 SW 145th Ave, Suite 115, Miramar, FL 33027",
        "phone": "(954) 602-3050",
        "website": "https://bellalashmiramar.com",
        "description": (
            "A boutique lash and brow studio in Miramar Town Center "
            "specializing in classic, hybrid, and volume lash extensions, "
            "lash lifts, microblading, and ombré powder brows. The studio "
            "books consistently and the owner's retention rate reflects "
            "the quality: clients come back every two to three weeks "
            "without being asked."
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
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "pure-skin-miramar",
        "name": "Pure Skin Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["skincare", "spa"],
        "address": "3350 SW 145th Ave, Suite 204, Miramar, FL 33027",
        "phone": "(954) 602-3350",
        "website": "https://pureskinmiramar.com",
        "description": (
            "A clinical esthetics studio in Miramar Town Center offering "
            "HydraFacials, chemical peels, microdermabrasion, and LED "
            "light therapy with a particular expertise in melanin-rich skin. "
            "The estheticians here understand hyperpigmentation, post-acne "
            "scarring, and texture concerns on deeper complexions with "
            "a protocols-first approach that gets results."
        ),
        "hours": {
            "Mon": "9am–5pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–6pm",
            "Fri": "9am–5pm",
            "Sat": "9am–3pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "miramar-wax-studio",
        "name": "Miramar Wax Studio",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["waxing"],
        "address": "3400 SW 145th Ave, Suite 108, Miramar, FL 33027",
        "phone": "(954) 602-3400",
        "website": "",
        "description": (
            "A clean, private waxing studio in the Town Center area "
            "offering Brazilian, bikini, full-body, and facial waxing "
            "with hard wax for all sensitive areas. The licensed "
            "estheticians here are efficient and comfortable — walk-ins "
            "welcome on weekdays, appointments strongly preferred on weekends."
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
        "slug": "crown-barbershop-miramar",
        "name": "Crown Barbershop Miramar",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["barber"],
        "address": "3250 SW 145th Ave, Suite 101, Miramar, FL 33027",
        "phone": "(954) 602-3250",
        "website": "https://crownbarbershopmiramar.com",
        "description": (
            "A high-energy barbershop in the Town Center area known for "
            "precise fades, line-ups, and beard sculpting for Miramar's "
            "diverse male clientele. The Caribbean-influenced crew here "
            "specializes in all textures — from tight coils to straight "
            "hair — and the shop has become a community fixture. "
            "Walk-ins welcome; appointments now available online."
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
        "editors_pick": True,
        "editors_note": (
            "The best barbershop in Miramar — the fades are precise, the "
            "line-ups are immaculate, and the crew works comfortably across "
            "all hair textures. The Caribbean influence shows in the "
            "attention to detail and the energy. Arrive early on Saturdays."
        ),
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "miramar-day-spa-town-center",
        "name": "Miramar Day Spa",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["spa", "massage"],
        "address": "3500 SW 145th Ave, Suite 312, Miramar, FL 33027",
        "phone": "(954) 602-3500",
        "website": "",
        "description": (
            "A full-service day spa in Miramar Town Center offering Swedish, "
            "deep tissue, and hot stone massage alongside signature facials, "
            "body wraps, and couples packages. A steady neighborhood anchor "
            "for Miramar families marking anniversaries, birthdays, and "
            "the occasional Tuesday afternoon that calls for a 90-minute escape."
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
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },

    # ── Silver Lakes ─────────────────────────────────────────────────────────────
    {
        "slug": "salon-caribe-silver-lakes",
        "name": "Salon Caribe Silver Lakes",
        "neighborhood_slug": "silver-lakes",
        "categories": ["hair"],
        "address": "11100 Miramar Pkwy, Suite 118, Miramar, FL 33025",
        "phone": "(954) 431-1110",
        "website": "",
        "description": (
            "A Caribbean and Latin-owned full-service salon in the Silver "
            "Lakes area offering Dominican blowouts, keratin treatments, "
            "braids, weaves, and color services. The team is expert in "
            "Afro-textured and natural hair alongside straight and wavy "
            "textures — one of the few shops in Broward that genuinely "
            "masters both worlds."
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
        "slug": "silver-lakes-nails-spa",
        "name": "Silver Lakes Nails & Spa",
        "neighborhood_slug": "silver-lakes",
        "categories": ["nails", "spa"],
        "address": "10900 Miramar Pkwy, Suite 103, Miramar, FL 33025",
        "phone": "(954) 431-1090",
        "website": "",
        "description": (
            "A clean, well-maintained nail and spa studio serving the "
            "Silver Lakes community with gel manicures, acrylic sets, "
            "dip powder, and spa pedicures at honest prices. The team "
            "here is efficient without rushing — and the pedicure "
            "chairs are consistently maintained and genuinely relaxing."
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
        "slug": "flawless-lash-bar-silver-lakes",
        "name": "Flawless Lash Bar",
        "neighborhood_slug": "silver-lakes",
        "categories": ["lash-brow"],
        "address": "11300 Miramar Pkwy, Suite 215, Miramar, FL 33025",
        "phone": "(954) 431-1130",
        "website": "",
        "description": (
            "A boutique lash bar in the Silver Lakes area offering classic "
            "and hybrid lash sets, mega-volume extensions, lash lifts, "
            "and brow lamination. The lash techs here are thorough and "
            "precise — clients in Silver Lakes have built a loyal "
            "following because the work speaks for itself."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–6pm",
            "Fri": "10am–6pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "fresh-cuts-barbershop-silver-lakes",
        "name": "Fresh Cuts Barbershop",
        "neighborhood_slug": "silver-lakes",
        "categories": ["barber"],
        "address": "10800 Miramar Pkwy, Suite 106, Miramar, FL 33025",
        "phone": "(954) 431-1080",
        "website": "",
        "description": (
            "A well-regarded community barbershop in the Silver Lakes "
            "area known for tight fades, line-ups, and beard work for "
            "men and boys of all ages. The diverse crew here handles "
            "all textures equally well and the shop has become a "
            "neighborhood staple — the kind of place where regulars "
            "refer their brothers, cousins, and eventually their kids."
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
        "slug": "smooth-glow-wax-silver-lakes",
        "name": "Smooth Glow Wax Studio",
        "neighborhood_slug": "silver-lakes",
        "categories": ["waxing", "skincare"],
        "address": "11000 Miramar Pkwy, Suite 308, Miramar, FL 33025",
        "phone": "(954) 431-1100",
        "website": "",
        "description": (
            "A waxing and skincare studio in the Silver Lakes corridor "
            "offering Brazilian, bikini, full-body, and facial waxing "
            "alongside results-focused skincare treatments. The licensed "
            "estheticians here prioritize skin health — gentle technique, "
            "proper aftercare guidance, and a genuine understanding of "
            "how waxing and skincare interact on melanin-rich skin."
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

    # ── Sunset Lakes ─────────────────────────────────────────────────────────────
    {
        "slug": "salon-tropical-sunset-lakes",
        "name": "Salon Tropical Miramar",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["hair"],
        "address": "12501 Miramar Pkwy, Suite 112, Miramar, FL 33027",
        "phone": "(954) 450-1250",
        "website": "https://salontropicalfl.com",
        "description": (
            "A full-service salon in the Sunset Lakes area of western "
            "Miramar with a diverse team fluent in Latin American, "
            "Caribbean, and natural hair textures. Known for expert "
            "keratin treatments that hold up in the South Florida "
            "humidity, meche highlights, and Dominican blowouts that "
            "keep their clients coming back every two weeks."
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
        "slug": "nail-boutique-sunset-lakes",
        "name": "Nail Boutique Sunset Lakes",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["nails"],
        "address": "12300 Miramar Pkwy, Suite 205, Miramar, FL 33027",
        "phone": "(954) 450-1230",
        "website": "",
        "description": (
            "A boutique nail studio in western Miramar's Sunset Lakes "
            "area known for creative nail art, gel extensions, and "
            "intricate designs alongside classic gel manicures and "
            "spa pedicures. The younger clientele here drives the "
            "demand for elaborate sets — and the techs deliver."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–6pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "lashes-by-simone-sunset-lakes",
        "name": "Lashes by Simone",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["lash-brow"],
        "address": "12700 Miramar Pkwy, Suite 118, Miramar, FL 33027",
        "phone": "(954) 450-1270",
        "website": "https://lashesbysimone.com",
        "description": (
            "A solo lash artist in the Sunset Lakes area of western "
            "Miramar with a loyal following built entirely on the quality "
            "of her work. Classic and volume extensions, lash lifts, "
            "and brow lamination done with the meticulous attention "
            "of someone who treats every set as a personal calling card. "
            "Books three weeks out; cancellations fill in under an hour."
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
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "tranquil-massage-sunset-lakes",
        "name": "Tranquil Massage & Wellness",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["massage", "spa"],
        "address": "12200 Miramar Pkwy, Suite 315, Miramar, FL 33027",
        "phone": "(954) 450-1220",
        "website": "",
        "description": (
            "A massage and wellness center in western Miramar offering "
            "Swedish, deep tissue, prenatal, and hot stone massage by "
            "licensed therapists. The unhurried, appointment-focused "
            "studio feels genuinely removed from the commercial strip "
            "outside — a real respite for Sunset Lakes families who "
            "prioritize self-care as a regular practice, not a special occasion."
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

    # ── Riviera Isles ────────────────────────────────────────────────────────────
    {
        "slug": "glam-house-salon-riviera-isles",
        "name": "Glam House Salon",
        "neighborhood_slug": "riviera-isles",
        "categories": ["hair"],
        "address": "6001 Miramar Pkwy, Suite 120, Miramar, FL 33023",
        "phone": "(954) 963-6001",
        "website": "https://glamhousesalon.com",
        "description": (
            "A full-service hair salon in the Riviera Isles area of eastern "
            "Miramar offering cuts, color, braids, natural hair styling, "
            "and weave installs for a diverse Caribbean and African American "
            "clientele. The salon is technically strong across all textures "
            "and the team genuinely loves what they do — which shows in the "
            "results and the energy."
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
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "nails-and-more-riviera-isles",
        "name": "Nails & More Miramar",
        "neighborhood_slug": "riviera-isles",
        "categories": ["nails", "spa"],
        "address": "5800 Miramar Pkwy, Suite 104, Miramar, FL 33023",
        "phone": "(954) 963-5800",
        "website": "",
        "description": (
            "A neighborhood nail and spa studio on the eastern Miramar "
            "corridor offering gel manicures, acrylic sets, dip powder, "
            "and spa pedicures at fair prices for the Riviera Isles "
            "community. Consistent, friendly, and always moving — "
            "walk-ins are welcome and the wait is rarely long."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "dynasty-barbers-riviera-isles",
        "name": "Dynasty Barbershop Miramar",
        "neighborhood_slug": "riviera-isles",
        "categories": ["barber"],
        "address": "6200 Miramar Pkwy, Suite 102, Miramar, FL 33023",
        "phone": "(954) 963-6200",
        "website": "",
        "description": (
            "A community barbershop staple in the Riviera Isles area of "
            "eastern Miramar known for sharp fades, precise line-ups, "
            "and beard sculpting for a predominantly Caribbean and "
            "African American clientele. The energy is welcoming, the "
            "cuts are consistent, and the barbers are genuinely skilled "
            "at the textured fades that define the shop's reputation."
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
        "slug": "island-glow-wax-riviera-isles",
        "name": "Island Glow Wax & Skincare",
        "neighborhood_slug": "riviera-isles",
        "categories": ["waxing", "skincare"],
        "address": "6100 Miramar Pkwy, Suite 218, Miramar, FL 33023",
        "phone": "(954) 963-6100",
        "website": "",
        "description": (
            "A waxing and skincare studio in eastern Miramar with "
            "Caribbean roots and a deep understanding of melanin-rich "
            "skin. Brazilian, bikini, body, and facial waxing alongside "
            "brightening facials and hyperpigmentation treatments. "
            "The licensed estheticians here have built a loyal clientele "
            "in the Riviera Isles community through genuinely knowledgeable "
            "and gentle work."
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
    {
        "slug": "queens-lash-studio-riviera-isles",
        "name": "Queens Lash Studio",
        "neighborhood_slug": "riviera-isles",
        "categories": ["lash-brow"],
        "address": "5900 Miramar Pkwy, Suite 210, Miramar, FL 33023",
        "phone": "(954) 963-5900",
        "website": "https://queenslashstudio.com",
        "description": (
            "A lash and brow studio in eastern Miramar with a strong "
            "following in the Riviera Isles community. Classic, hybrid, "
            "and mega-volume extensions, lash lifts, brow lamination, "
            "and microblading from a team that has built its reputation "
            "on retention, precision, and a clientele that never strays "
            "to another studio."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–6pm",
            "Fri": "10am–6pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "The most trusted lash studio in eastern Miramar — the mega-volume "
            "sets are full and precise without looking artificial, the lash lifts "
            "hold beautifully on all curl patterns, and the microblading is done "
            "with a steady hand and a natural eye. Worth the three-week wait."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "the-nail-lounge-sunset-lakes",
        "name": "The Nail Lounge Miramar",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["nails"],
        "address": "12717 Miramar Pkwy, Miramar, FL 33027",
        "phone": "(954) 432-6781",
        "website": None,
        "instagram": None,
        "description": (
            "Established nail art destination on western Miramar Pkwy with over "
            "a decade serving Broward County — specializing in intricate gel nail "
            "art and spa pedicures in a comfortable, spa-style setting."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "price_range": "$$",
        "editors_pick": True,
        "editors_note": (
            "Voted #1 nail art salon in South Florida by Miami New Times — "
            "a standout destination for intricate gel work."
        ),
        "status": "live",
    },
    {
        "slug": "toi-spa-miramar",
        "name": "Tôi Spa Miramar",
        "neighborhood_slug": "sunset-lakes",
        "categories": ["nails", "spa"],
        "address": "12647 Miramar Pkwy, Miramar, FL 33027",
        "phone": "(754) 551-2371",
        "website": None,
        "instagram": None,
        "description": (
            "Modern Vietnamese-owned nail and spa studio on Miramar Pkwy offering "
            "high-quality gel, acrylic, and spa services in a relaxing atmosphere."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "price_range": "$$",
        "editors_pick": False,
        "status": "live",
    },
    {
        "slug": "bliss-nails-spa-miramar-town-center",
        "name": "Bliss Nails & Spa",
        "neighborhood_slug": "miramar-town-center",
        "categories": ["nails", "waxing"],
        "address": "3131 SW 160th Ave, Miramar, FL 33027",
        "phone": "(954) 431-0221",
        "website": None,
        "instagram": None,
        "description": (
            "Full-service nail salon near Miramar Town Center offering manicures, "
            "pedicures, acrylics, and waxing in a comfortable neighborhood setting."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "price_range": "$",
        "editors_pick": False,
        "status": "live",
    },
]


async def seed_miramar() -> None:
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
        "meta_description": (
            "The curated beauty directory for Miramar, FL — salons, spas, lash studios, "
            "and nail bars discovered by locals. Covering Miramar Parkway, Silver Lakes, "
            "Sunset Lakes, and Miramar Town Center in Broward County."
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
        f"Miramar seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_miramar()


if __name__ == "__main__":
    run(main())
