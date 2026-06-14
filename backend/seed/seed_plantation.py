"""Seed script for Plantation, FL (Beauty network).

Plantation is a wealthy western Broward suburb known for tree-lined streets,
top-rated schools, and a well-heeled family clientele that takes beauty
appointments seriously. The Broward Mall area anchors the city's main retail
strip; Peters Road and Broward Boulevard serve the surrounding neighborhoods;
and the area around Cleary Boulevard and University Drive brings the boutique
studio crowd. The city skews affluent, educated, and appointment-driven —
full-service salons, premium nail lounges, and results-oriented spas dominate.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_plantation
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo

CITY_SLUG = "plantation"
CITY_NAME = "Plantation"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Plantation is western Broward's most polished suburb — tree-lined streets, "
    "top schools, and a clientele that books appointments weeks in advance. The "
    "beauty scene here leans upscale and full-service: precision colorists, "
    "destination nail lounges, and spa studios that serve families who've been "
    "loyal to the same stylist for a decade."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "plantation.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "broward-mall-area",
        "Broward Mall Area",
        "Plantation's main retail hub — dense with salons, nail bars, and "
        "spas serving the city's family-heavy residential base.",
        7,
    ),
    (
        "university-drive",
        "University Drive Corridor",
        "Plantation's busiest north-south commercial strip — full-service "
        "studios, med-spas, and specialty boutiques from Peters Rd to Sunrise Blvd.",
        6,
    ),
    (
        "cleary-blvd",
        "Cleary Boulevard",
        "Quieter western Plantation — neighborhood salons and appointment-first "
        "studios serving the area's established residential communities.",
        3,
    ),
    (
        "sunrise-blvd",
        "Sunrise Boulevard",
        "Eastern Plantation's main east-west artery — accessible neighborhood "
        "beauty spots serving a mix of families and young professionals.",
        4,
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
    # ── Broward Mall Area ──────────────────────────────────────────────────────
    {
        "slug": "gene-juarez-salon-plantation",
        "name": "Salon by JC — Plantation",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["hair"],
        "address": "321 N Pine Island Rd, Plantation, FL 33324",
        "phone": "(954) 473-7800",
        "website": "https://salonjc.com",
        "description": (
            "A well-regarded full-service hair salon near the Broward Mall "
            "offering precision cuts, balayage, keratin treatments, and "
            "color corrections. Known for its professional team and a "
            "consistent experience that keeps Plantation families booking "
            "month after month."
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
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "the-nail-lounge-plantation",
        "name": "The Nail Lounge Plantation",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["nails"],
        "address": "8000 W Broward Blvd, Suite 2110, Plantation, FL 33388",
        "phone": "(954) 473-6245",
        "website": "https://thenailloungeplantation.com",
        "description": (
            "Plantation's go-to nail destination in the Broward Mall area — "
            "known for immaculate gel manicures, Russian manicures, dip powder, "
            "and pedicures in a clean, upscale environment. One of the most "
            "reviewed nail spots in western Broward."
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
            "The nail experience Plantation deserves — Russian manicures done "
            "with genuine technique, gel sets that last three weeks, and "
            "pedicure chairs that feel genuinely luxurious. The most "
            "consistently excellent nail work in western Broward."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "brow-artistry-plantation",
        "name": "Brow Artistry Studio",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["lash-brow"],
        "address": "7960 W Broward Blvd, Suite 108, Plantation, FL 33324",
        "phone": "(954) 473-2929",
        "website": "https://browartistystudio.com",
        "description": (
            "A dedicated brow studio near Broward Mall specializing in "
            "microblading, ombré powder brows, nano-hair strokes, and brow "
            "lamination. Appointment-only with a strong following from "
            "Plantation's professional clientele."
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
            "The best permanent brow work in Plantation — the microblading "
            "is precise and natural-looking, with results that hold up "
            "beautifully for 12–18 months. Worth every penny and the "
            "two-week wait for a slot."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "wax-salon-plantation-mall",
        "name": "Clean Slate Wax Studio",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["waxing"],
        "address": "8100 W Broward Blvd, Suite 304, Plantation, FL 33388",
        "phone": "(954) 474-1155",
        "website": "",
        "description": (
            "A clean, private wax studio near Broward Mall offering full-body "
            "and facial waxing in a calm, no-rush environment. Brazilian, bikini, "
            "leg, underarm, and face services with hard wax for sensitive skin. "
            "Walk-ins sometimes available; appointments strongly preferred."
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
        "slug": "plantation-hair-studio-broward",
        "name": "Plantation Hair Studio",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["hair"],
        "address": "400 S Pine Island Rd, Suite 135, Plantation, FL 33324",
        "phone": "(954) 473-3344",
        "website": "",
        "description": (
            "A long-standing Plantation salon near the mall serving the "
            "city's family clientele with cuts, color, highlights, and blowouts. "
            "Stylists here know their regulars by name and their color formulas "
            "by heart — the kind of neighborhood salon that doesn't need "
            "an Instagram to stay fully booked."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "lush-lash-lounge-plantation",
        "name": "Lush Lash Lounge",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["lash-brow"],
        "address": "7960 W Broward Blvd, Suite 210, Plantation, FL 33324",
        "phone": "(954) 474-5588",
        "website": "",
        "description": (
            "A boutique lash lounge in the Broward Mall corridor offering "
            "classic, hybrid, and volume extensions alongside lash lifts and "
            "brow lamination. Known for retention that outlasts the two-week "
            "touch-up cycle and a tech team that stays current with technique."
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
        "slug": "pure-skin-plantation",
        "name": "Pure Skin Esthetics",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["spa", "skincare"],
        "address": "8040 W Broward Blvd, Suite 111, Plantation, FL 33388",
        "phone": "(954) 474-7700",
        "website": "https://pureskinesthetics.com",
        "description": (
            "A results-driven esthetics studio near Broward Mall offering "
            "medical-grade facials, chemical peels, microdermabrasion, and "
            "dermaplaning. The esthetician team here treats acne, hyperpigmentation, "
            "and anti-aging concerns with a protocols-first approach."
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
        "price_range": "$$$",
        "status": "live",
    },

    # ── University Drive Corridor ───────────────────────────────────────────────
    {
        "slug": "salon-m-plantation-university",
        "name": "Salon M Plantation",
        "neighborhood_slug": "university-drive",
        "categories": ["hair"],
        "address": "1131 S University Dr, Suite 200, Plantation, FL 33324",
        "phone": "(954) 476-2600",
        "website": "https://salonmplantation.com",
        "description": (
            "One of Plantation's most respected independent salons on University "
            "Drive — known for exceptional color work, balayage, extensions, "
            "and keratin smoothing treatments. The salon's stylists regularly "
            "train in New York and London and bring that technique to Plantation's "
            "discerning clientele."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
            "Fri": "9am–7pm",
            "Sat": "8am–6pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "The destination color salon in Plantation — stylists here regularly "
            "train in New York and it shows. The balayage is the best in western "
            "Broward, and the keratin treatments last a genuine three to four "
            "months. Worth the longer booking window."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "nail-palace-plantation-university",
        "name": "Nail Palace Plantation",
        "neighborhood_slug": "university-drive",
        "categories": ["nails"],
        "address": "1501 S University Dr, Plantation, FL 33324",
        "phone": "(954) 476-1188",
        "website": "",
        "description": (
            "A busy University Drive nail salon serving Plantation families "
            "with acrylics, gel manicures, spa pedicures, and dip powder. "
            "Consistent technique, efficient service, and a spacious layout "
            "make it a reliable choice for the neighborhood."
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
        "slug": "serenity-day-spa-plantation",
        "name": "Serenity Day Spa Plantation",
        "neighborhood_slug": "university-drive",
        "categories": ["spa", "massage"],
        "address": "801 S University Dr, Suite 250, Plantation, FL 33324",
        "phone": "(954) 476-9988",
        "website": "https://serenitydayspa.com",
        "description": (
            "A serene full-service day spa on University Drive offering Swedish, "
            "deep tissue, and prenatal massage, along with signature facials, "
            "body wraps, and couple's packages. A consistent choice for Plantation "
            "families marking birthdays, anniversaries, and Mother's Day."
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
            "The best full spa day in Plantation — the couples packages are "
            "genuinely romantic, the massage therapists are skilled, and the "
            "facials use high-quality products without feeling like a hard-sell "
            "on skincare. Book the 90-minute signature package."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "cuts-and-colors-plantation-university",
        "name": "Cuts & Colors Studio",
        "neighborhood_slug": "university-drive",
        "categories": ["hair"],
        "address": "1100 S University Dr, Suite 110, Plantation, FL 33324",
        "phone": "(954) 476-4422",
        "website": "",
        "description": (
            "A local favorite on University Drive known for precision cuts, "
            "highlights, and color corrections at fair prices. The no-pretense "
            "approach suits Plantation's school-year crowd: quick, quality "
            "service that doesn't require a waiting list."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "luxe-nails-plantation-university",
        "name": "Luxe Nails & Spa",
        "neighborhood_slug": "university-drive",
        "categories": ["nails", "spa"],
        "address": "1700 S University Dr, Plantation, FL 33324",
        "phone": "(954) 476-7700",
        "website": "",
        "description": (
            "A full-service nail and spa studio on University Drive offering "
            "gel manicures, Gel-X extensions, acrylic sets, and spa pedicure "
            "packages in a relaxed, upscale environment. Known for attention "
            "to detail and pedicure chairs that actually deliver the massage."
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
        "slug": "radiance-med-spa-plantation",
        "name": "Radiance Med Spa Plantation",
        "neighborhood_slug": "university-drive",
        "categories": ["med-spa"],
        "address": "1600 S University Dr, Suite 300, Plantation, FL 33324",
        "phone": "(954) 476-8811",
        "website": "https://radiancemedspa.com",
        "description": (
            "A physician-supervised med spa on University Drive offering Botox, "
            "fillers, Morpheus8, laser hair removal, and HydraFacial in a "
            "clinical setting. Plantation's professional clientele trusts the "
            "outcomes-focused approach and the lack of high-pressure upselling."
        ),
        "hours": {
            "Mon": "9am–5pm",
            "Tue": "9am–5pm",
            "Wed": "9am–5pm",
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
        "slug": "the-fade-shop-plantation",
        "name": "The Fade Shop Barbershop",
        "neighborhood_slug": "university-drive",
        "categories": ["barber"],
        "address": "1200 S University Dr, Suite 150, Plantation, FL 33324",
        "phone": "(954) 476-2233",
        "website": "https://thefadeshop.com",
        "description": (
            "A top-rated barbershop on University Drive specializing in high "
            "fades, line-ups, and beard sculpting. Clean and professional with "
            "a diverse clientele — from middle schoolers to executives who "
            "know a sharp fade when they see one."
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
        "price_range": "$$",
        "status": "live",
    },

    # ── Cleary Boulevard ────────────────────────────────────────────────────────
    {
        "slug": "studio-69-salon-plantation",
        "name": "Studio 69 Salon",
        "neighborhood_slug": "cleary-blvd",
        "categories": ["hair"],
        "address": "6900 W Sunrise Blvd, Suite 112, Plantation, FL 33313",
        "phone": "(954) 583-6900",
        "website": "",
        "description": (
            "A neighborhood salon serving the Cleary Boulevard area of "
            "Plantation for over two decades. Cuts, color, highlights, "
            "and blowouts for a multi-generational family clientele. The "
            "kind of salon where the stylist remembers how you wore your "
            "hair in your school photos."
        ),
        "hours": {
            "Mon": "9am–5pm",
            "Tue": "9am–5pm",
            "Wed": "9am–5pm",
            "Thu": "9am–6pm",
            "Fri": "9am–6pm",
            "Sat": "8am–4pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "pink-nail-studio-cleary",
        "name": "Pink Nail Studio",
        "neighborhood_slug": "cleary-blvd",
        "categories": ["nails"],
        "address": "7100 W Sunrise Blvd, Plantation, FL 33313",
        "phone": "(954) 587-7100",
        "website": "",
        "description": (
            "A clean neighborhood nail studio in the western Plantation "
            "area offering acrylic sets, gel manicures, and pedicures at "
            "fair prices. Known for a friendly team and consistent work "
            "that keeps a loyal walk-in clientele coming back."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–6pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "bella-wax-bar-plantation",
        "name": "Bella Wax Bar",
        "neighborhood_slug": "cleary-blvd",
        "categories": ["waxing"],
        "address": "6800 W Sunrise Blvd, Suite 205, Plantation, FL 33313",
        "phone": "(954) 583-8822",
        "website": "",
        "description": (
            "A dedicated wax bar in western Plantation offering full-body and "
            "facial waxing services in private rooms. Hard wax for sensitive "
            "areas, sugar wax available on request. Walk-ins accommodated on "
            "weekdays; weekend appointments fill quickly."
        ),
        "hours": {
            "Mon": "10am–6pm",
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

    # ── Sunrise Boulevard ──────────────────────────────────────────────────────
    {
        "slug": "color-theory-salon-plantation-sunrise",
        "name": "Color Theory Salon",
        "neighborhood_slug": "sunrise-blvd",
        "categories": ["hair"],
        "address": "1600 N Pine Island Rd, Suite 105, Plantation, FL 33322",
        "phone": "(954) 476-8883",
        "website": "https://colortheorysalonfl.com",
        "description": (
            "A modern color-focused salon on the Sunrise Boulevard corridor "
            "known for balayage, lived-in color, and dimensional highlights "
            "done with a light touch. The stylists here specialize in "
            "color-correction work and attract clients from across Broward "
            "for complex transformations."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–8pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "nails-by-design-plantation-sunrise",
        "name": "Nails by Design",
        "neighborhood_slug": "sunrise-blvd",
        "categories": ["nails"],
        "address": "1390 N Pine Island Rd, Plantation, FL 33322",
        "phone": "(954) 476-5522",
        "website": "",
        "description": (
            "A nail studio on the Sunrise Boulevard end of Plantation "
            "offering nail art, gel extensions, Gel-X, and classic acrylics "
            "with a creative touch. Popular with younger clients who want "
            "something beyond a standard French — they post their work "
            "and the phone rings."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–5pm",
            "Sun": "10am–3pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "lash-room-plantation-sunrise",
        "name": "The Lash Room Plantation",
        "neighborhood_slug": "sunrise-blvd",
        "categories": ["lash-brow"],
        "address": "1500 N Pine Island Rd, Suite 210, Plantation, FL 33322",
        "phone": "(954) 476-3366",
        "website": "https://thelashroomplantation.com",
        "description": (
            "A dedicated lash studio serving the Sunrise Blvd corridor with "
            "classic, hybrid, and mega-volume extensions, lash lifts, and "
            "brow shaping. The owner-operated studio books out two to three "
            "weeks in advance — loyalty is strong enough that clients "
            "schedule their fill before they leave."
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
        "editors_pick": True,
        "editors_note": (
            "The most trusted lash studio in Plantation — the owner has "
            "been doing volume extensions since before they were called "
            "'mega,' and the consistency is unmatched. Retention that holds "
            "three weeks without fallout and brow lamination that finally "
            "looks like your own brows, just better."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "fade-masters-plantation-sunrise",
        "name": "Fade Masters Barbershop",
        "neighborhood_slug": "sunrise-blvd",
        "categories": ["barber"],
        "address": "1200 N Pine Island Rd, Plantation, FL 33322",
        "phone": "(954) 476-1215",
        "website": "",
        "description": (
            "A high-energy barbershop on the Sunrise side of Plantation "
            "delivering tight fades, classic taper cuts, and beard shaping "
            "for the neighborhood's youth and adults alike. Known for speed "
            "and consistency — the afternoon line moves fast and the cuts "
            "are always clean."
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
        "slug": "bliss-nail-lounge-broward-blvd",
        "name": "Bliss Nail Lounge",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["nails"],
        "address": "6927 W Broward Blvd, Plantation, FL 33317",
        "phone": "(954) 316-7500",
        "website": None,
        "instagram": None,
        "description": (
            "Contemporary nail lounge near Broward Mall offering gel manicures, "
            "pedicures, and nail art in a clean, spa-inspired setting popular "
            "with local shoppers."
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
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "elite-nails-spa-nob-hill",
        "name": "Elite Nails and Spa",
        "neighborhood_slug": "broward-mall-area",
        "categories": ["nails", "waxing"],
        "address": "817 N Nob Hill Rd, Plantation, FL 33324",
        "phone": "(954) 727-9401",
        "website": None,
        "instagram": None,
        "description": (
            "Friendly neighborhood nail salon on Nob Hill Road offering full "
            "nail services, waxing, and spa pedicures in a relaxed atmosphere."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "lacqua-nail-spa-university-dr",
        "name": "L'Acqua Nail Spa",
        "neighborhood_slug": "university-drive",
        "categories": ["nails", "spa"],
        "address": "1467 S University Dr, Plantation, FL 33324",
        "phone": "(954) 870-7437",
        "website": None,
        "instagram": None,
        "description": (
            "Upscale nail spa on University Drive offering premium manicures, "
            "pedicures, and spa services in a sophisticated, European-inspired setting."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–7:30pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "bella-donna-hair-salon-sunrise-blvd",
        "name": "Bella Donna Hair Salon",
        "neighborhood_slug": "sunrise-blvd",
        "categories": ["hair"],
        "address": "11925 W Sunrise Blvd, Plantation, FL 33323",
        "phone": "(954) 766-4356",
        "website": None,
        "instagram": None,
        "description": (
            "Full-service hair salon on Sunrise Boulevard offering cuts, color, "
            "highlights, and styling for women and men in a welcoming neighborhood setting."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
]


async def seed_plantation() -> None:
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
            "Plantation locals actually book — from the Broward Mall area to the boutique "
            "studios along University Drive and Cleary Boulevard."
        ),
        "meta_description": (
            "The curated beauty directory for Plantation, Florida — salons, spas, nail "
            "lounges, and lash studios discovered by locals. Covering the Broward Mall "
            "area, University Drive, Cleary Boulevard, and Sunrise Boulevard."
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
        f"Plantation seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_plantation()


if __name__ == "__main__":
    run(main())
