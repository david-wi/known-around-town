"""Seed script for Weston, FL (Beauty network).

Weston is one of South Florida's most affluent planned communities — a master-
planned city in western Broward County developed in the 1990s that has grown
into one of the region's most desirable suburban addresses. The city is defined
by its gated neighborhoods, top-ranked schools, and a large Latin American
professional class (particularly Venezuelan and Colombian) with high disposable
income and strong beauty-service loyalty. Weston Town Center anchors the
community's retail life; the surrounding neighborhoods feed a salon and spa
scene that skews high-end, appointment-driven, and deeply loyal.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_weston
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo

CITY_SLUG = "weston"
CITY_NAME = "Weston"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Weston is one of South Florida's most affluent planned communities — a "
    "master-planned city where Venezuelan and Colombian professionals have built "
    "a beauty scene that rivals Coral Gables in quality and Boca Raton in loyalty. "
    "The salons and spas here serve clients who book weeks out, tip generously, "
    "and have been with the same stylist since they moved to the city."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "weston.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "weston-town-center",
        "Weston Town Center",
        "Weston's vibrant retail and dining hub — a walkable open-air district "
        "anchored by high-end salons, med spas, and boutique beauty studios "
        "serving the city's affluent professional community.",
        8,
    ),
    (
        "emerald-estates",
        "Emerald Estates",
        "One of Weston's most prestigious gated communities — appointment-first "
        "studios and full-service salons serving a loyal, affluent clientele "
        "who expect exceptional results and discretion.",
        5,
    ),
    (
        "savanna",
        "Savanna",
        "A large planned neighborhood in central Weston — neighborhood beauty "
        "spots and full-service salons on Weston Road serving families who "
        "treat beauty appointments as part of the weekly routine.",
        4,
    ),
    (
        "indian-trace",
        "Indian Trace",
        "Eastern Weston's established residential community — accessible salons "
        "and nail studios along Indian Trace Boulevard serving families and "
        "professionals in one of Broward's most sought-after zip codes.",
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
    # ── Weston Town Center ─────────────────────────────────────────────────────
    {
        "slug": "salon-del-sol-weston",
        "name": "Salon Del Sol Weston",
        "neighborhood_slug": "weston-town-center",
        "categories": ["hair"],
        "address": "1675 Market St, Suite 101, Weston, FL 33326",
        "phone": "(954) 384-7700",
        "website": "https://salondelsol.com",
        "description": (
            "One of Weston's most established full-service hair salons in the "
            "heart of Weston Town Center. Known for exceptional balayage, keratin "
            "treatments, and color work that holds up in South Florida's humidity. "
            "The bilingual team serves Weston's large Latin American professional "
            "community with the kind of personalized attention that keeps clients "
            "loyal for years."
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
        "editors_pick": True,
        "editors_note": (
            "The anchor salon of Weston Town Center — the keratin treatments "
            "here genuinely last four months in South Florida humidity, the "
            "balayage is done with real artistry, and the bilingual team makes "
            "every client feel at home. The most trusted hair salon in Weston."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "weston-nail-bar",
        "name": "Weston Nail Bar",
        "neighborhood_slug": "weston-town-center",
        "categories": ["nails"],
        "address": "1625 Market St, Suite 206, Weston, FL 33326",
        "phone": "(954) 384-5522",
        "website": "https://westonnailbar.com",
        "description": (
            "A premium nail destination in Weston Town Center known for "
            "meticulous gel manicures, Russian manicures, Gel-X extensions, "
            "and spa pedicures in an upscale, spa-like environment. The team "
            "here maintains nail health as a priority — no damage, no lifting, "
            "no compromising the integrity of the natural nail."
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
            "Weston's best nail studio — the Russian manicures are done with "
            "genuine technique, the gel sets last a real three weeks, and the "
            "spa pedicure chairs actually deliver the massage. The most "
            "consistently excellent nail work in western Broward."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "glow-med-spa-weston",
        "name": "Glow Med Spa Weston",
        "neighborhood_slug": "weston-town-center",
        "categories": ["med-spa"],
        "address": "2055 Town Center Blvd, Suite 300, Weston, FL 33326",
        "phone": "(954) 385-4500",
        "website": "https://glowmedspa.com",
        "description": (
            "A physician-supervised med spa in Weston Town Center offering "
            "Botox, dermal fillers, Morpheus8 radiofrequency microneedling, "
            "laser hair removal, and HydraFacial MD. Weston's professional "
            "clientele trusts the outcomes-focused approach and the clinical "
            "staff who deliver natural-looking results without the upsell pressure."
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
            "Weston's most trusted med spa — the Botox and filler work is "
            "natural-looking and the Morpheus8 results are genuinely visible. "
            "The clinical staff explains every treatment without pushing add-ons. "
            "Worth the longer booking window for the injectors."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "lash-studio-weston-town-center",
        "name": "The Lash Studio Weston",
        "neighborhood_slug": "weston-town-center",
        "categories": ["lash-brow"],
        "address": "1700 Market St, Suite 115, Weston, FL 33326",
        "phone": "(954) 384-8833",
        "website": "https://thelashstudioweston.com",
        "description": (
            "A boutique lash and brow studio in Weston Town Center offering "
            "classic, hybrid, and mega-volume lash extensions, lash lifts, "
            "microblading, ombré powder brows, and brow lamination. "
            "The owner-operated studio books two to three weeks out and "
            "has a retention rate that reflects the quality of the work."
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
            "The best lash work in Weston — volume extensions with retention "
            "that consistently outlasts the two-week fill, microblading that "
            "looks genuinely natural at 18 months, and a brow lamination that "
            "actually tames and sculpts. Book as far out as they'll let you."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "arte-y-color-salon-weston",
        "name": "Arte y Color Salon",
        "neighborhood_slug": "weston-town-center",
        "categories": ["hair"],
        "address": "1910 Town Center Blvd, Suite 102, Weston, FL 33326",
        "phone": "(954) 385-1910",
        "website": "",
        "description": (
            "A Venezuelan-owned color salon in Weston Town Center known for "
            "meche highlights, balayage, and dimensional color work for the "
            "city's large Latin American clientele. The team is technically "
            "skilled and the consultation is thorough — they understand hair "
            "texture, porosity, and the unique challenges of South Florida color."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
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
        "slug": "bliss-wax-studio-weston",
        "name": "Bliss Wax Studio",
        "neighborhood_slug": "weston-town-center",
        "categories": ["waxing"],
        "address": "2025 Town Center Blvd, Suite 204, Weston, FL 33326",
        "phone": "(954) 385-2025",
        "website": "",
        "description": (
            "A clean, private wax studio in Weston Town Center offering "
            "Brazilian, bikini, full-leg, and facial waxing in calm, "
            "single-treatment rooms. Hard wax for all sensitive areas, "
            "licensed estheticians only, and a no-double-dipping policy "
            "enforced without exception. Appointment-recommended but "
            "weekday walk-ins are usually accommodated."
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
        "slug": "weston-serenity-spa",
        "name": "Serenity Spa & Wellness Weston",
        "neighborhood_slug": "weston-town-center",
        "categories": ["spa", "massage"],
        "address": "2100 Town Center Blvd, Suite 400, Weston, FL 33326",
        "phone": "(954) 385-2100",
        "website": "https://serenityspafl.com",
        "description": (
            "A full-service day spa and massage studio in Weston Town Center "
            "offering Swedish, deep tissue, prenatal, and hot stone massage, "
            "along with signature facials, body treatments, and couple's packages. "
            "The environment is calm and appointment-focused — built for "
            "Weston's dual-income families who need a real escape."
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
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "prestige-cuts-weston",
        "name": "Prestige Cuts Barbershop",
        "neighborhood_slug": "weston-town-center",
        "categories": ["barber"],
        "address": "1855 Town Center Blvd, Suite 108, Weston, FL 33326",
        "phone": "(954) 384-1855",
        "website": "",
        "description": (
            "A well-regarded barbershop in Weston Town Center delivering "
            "precision fades, taper cuts, hot towel shaves, and beard shaping "
            "for Weston's professional male clientele. Clean, efficient, and "
            "consistent — the kind of shop where executives and their sons "
            "share the same barber."
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

    # ── Emerald Estates ─────────────────────────────────────────────────────────
    {
        "slug": "studio-isabella-weston-emerald",
        "name": "Studio Isabella",
        "neighborhood_slug": "emerald-estates",
        "categories": ["hair"],
        "address": "4476 Weston Rd, Suite 112, Weston, FL 33331",
        "phone": "(954) 349-4476",
        "website": "https://studioisabellaweston.com",
        "description": (
            "A boutique hair studio near Emerald Estates serving Weston's "
            "most discerning clientele with precision cuts, advanced color, "
            "extensions, and keratin treatments. The appointment-only studio "
            "is known for the kind of personalized service — consultations "
            "included, no rushing, no double-booking — that Weston's "
            "professionals demand."
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
        "editors_pick": True,
        "editors_note": (
            "Weston's best appointment-only salon — the color work is done "
            "with Davines and Olaplex, the cuts are architectural, and the "
            "stylist takes as long as the service needs rather than watching "
            "the clock. The extensions work is particularly strong. "
            "Worth the two-week booking window."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "nails-at-the-reserve-weston",
        "name": "Nails at The Reserve",
        "neighborhood_slug": "emerald-estates",
        "categories": ["nails"],
        "address": "4400 Weston Rd, Weston, FL 33331",
        "phone": "(954) 349-4400",
        "website": "",
        "description": (
            "A clean, upscale nail studio near the Emerald Estates area of "
            "Weston offering gel manicures, acrylic sets, Gel-X, dip powder, "
            "and spa pedicures. Known for a thorough and unhurried process "
            "that respects the natural nail and a pedicure experience that "
            "delivers on the spa promise."
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
        "slug": "weston-skin-studio-emerald",
        "name": "Weston Skin Studio",
        "neighborhood_slug": "emerald-estates",
        "categories": ["skincare", "spa"],
        "address": "4550 Weston Rd, Suite 205, Weston, FL 33331",
        "phone": "(954) 349-4550",
        "website": "https://westonskin.com",
        "description": (
            "A medical-grade esthetics studio near Emerald Estates offering "
            "HydraFacials, chemical peels, dermaplaning, microneedling, and "
            "LED light therapy. The licensed estheticians here work with a "
            "results-first protocol — every treatment is customized and the "
            "clinical approach shows in the outcomes."
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
        "slug": "color-by-claudia-weston",
        "name": "Color by Claudia",
        "neighborhood_slug": "emerald-estates",
        "categories": ["hair"],
        "address": "4300 Weston Rd, Suite 118, Weston, FL 33331",
        "phone": "(954) 349-4300",
        "website": "",
        "description": (
            "A solo colorist studio in western Weston specializing in "
            "lived-in balayage, toning, and color correction for clients "
            "who've been burned elsewhere. Claudia's book fills weeks out "
            "because clients know the results: natural-looking, low-maintenance "
            "color that grows out gracefully in the Florida sun."
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
        "slug": "emerald-lash-brow-weston",
        "name": "Emerald Lash & Brow Bar",
        "neighborhood_slug": "emerald-estates",
        "categories": ["lash-brow"],
        "address": "4680 Weston Rd, Suite 101, Weston, FL 33331",
        "phone": "(954) 349-4680",
        "website": "",
        "description": (
            "A dedicated lash and brow studio in the Emerald Estates area "
            "offering classic, hybrid, and volume lash extensions, lash lifts, "
            "brow lamination, and brow tinting. The techs here are thorough "
            "and careful — clients leave looking polished without looking overdone."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–7pm",
            "Fri": "10am–6pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },

    # ── Savanna ─────────────────────────────────────────────────────────────────
    {
        "slug": "salon-victoria-weston-savanna",
        "name": "Salon Victoria Weston",
        "neighborhood_slug": "savanna",
        "categories": ["hair"],
        "address": "2400 Weston Rd, Suite 150, Weston, FL 33326",
        "phone": "(954) 384-2400",
        "website": "https://salonvictoriaweston.com",
        "description": (
            "A beloved full-service hair salon on Weston Road serving "
            "the Savanna neighborhood with cuts, color, keratin treatments, "
            "and blowouts. The Colombian-owned salon has built a multi-generational "
            "following — mothers who started coming for highlights in the early "
            "2000s now bring their daughters for their first balayage."
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
        "slug": "savanna-nails-weston",
        "name": "Savanna Nails & Spa",
        "neighborhood_slug": "savanna",
        "categories": ["nails", "spa"],
        "address": "2600 Weston Rd, Suite 104, Weston, FL 33326",
        "phone": "(954) 384-2600",
        "website": "",
        "description": (
            "A well-run neighborhood nail and spa studio on Weston Road "
            "serving the Savanna community with gel manicures, dip powder, "
            "Gel-X, and spa pedicures at reasonable Weston prices. Known "
            "for consistent technique and a friendly team that treats "
            "regulars like family."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–6pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "massage-therapy-weston-savanna",
        "name": "Weston Massage & Wellness",
        "neighborhood_slug": "savanna",
        "categories": ["massage", "spa"],
        "address": "2800 Weston Rd, Suite 212, Weston, FL 33326",
        "phone": "(954) 384-2800",
        "website": "https://westonmassage.com",
        "description": (
            "A massage and wellness center on Weston Road offering Swedish, "
            "deep tissue, sports, and prenatal massage by licensed therapists. "
            "The appointment-focused studio runs on time, keeps the environment "
            "quiet and calm, and attracts Weston professionals who need "
            "genuine therapeutic work alongside their routine maintenance."
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
        "slug": "the-barber-collective-weston",
        "name": "The Barber Collective Weston",
        "neighborhood_slug": "savanna",
        "categories": ["barber"],
        "address": "2200 Weston Rd, Suite 108, Weston, FL 33326",
        "phone": "(954) 384-2200",
        "website": "",
        "description": (
            "A modern barbershop on Weston Road serving the Savanna area "
            "with precision fades, classic taper cuts, line-ups, and beard "
            "shaping for men of all ages. The crew here is skilled and "
            "consistent — Weston dads and their sons show up together and "
            "both leave looking sharp."
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

    # ── Indian Trace ────────────────────────────────────────────────────────────
    {
        "slug": "reflections-salon-weston-indian-trace",
        "name": "Reflections Salon & Spa",
        "neighborhood_slug": "indian-trace",
        "categories": ["hair", "spa"],
        "address": "1801 N Commerce Pkwy, Suite 120, Weston, FL 33326",
        "phone": "(954) 389-1801",
        "website": "https://reflectionssalonweston.com",
        "description": (
            "A full-service hair salon and spa in the Indian Trace area of "
            "eastern Weston offering cuts, balayage, color corrections, "
            "facials, and body treatments. One of Weston's most established "
            "salons — the team has been serving the community long enough "
            "to know exactly what Indian Trace families want."
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
        "slug": "flawless-nails-weston-indian-trace",
        "name": "Flawless Nails Weston",
        "neighborhood_slug": "indian-trace",
        "categories": ["nails"],
        "address": "2000 N Commerce Pkwy, Weston, FL 33326",
        "phone": "(954) 389-2000",
        "website": "",
        "description": (
            "A clean, busy nail studio in the Indian Trace corridor of "
            "eastern Weston offering gel manicures, acrylics, dip powder, "
            "and spa pedicures for the surrounding residential community. "
            "Fast, friendly, and consistently well-reviewed — the afternoon "
            "line moves efficiently and the quality holds up."
        ),
        "hours": {
            "Mon": "9am–7:30pm",
            "Tue": "9am–7:30pm",
            "Wed": "9am–7:30pm",
            "Thu": "9am–7:30pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–6pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "indian-trace-lash-lounge",
        "name": "Indian Trace Lash Lounge",
        "neighborhood_slug": "indian-trace",
        "categories": ["lash-brow"],
        "address": "1900 N Commerce Pkwy, Suite 205, Weston, FL 33326",
        "phone": "(954) 389-1900",
        "website": "",
        "description": (
            "A boutique lash lounge in eastern Weston offering classic, "
            "hybrid, and volume extension sets, lash lifts, brow lamination, "
            "and brow tinting. The meticulous owner-operator has cultivated "
            "a loyal book in the Indian Trace area — clients rarely leave "
            "for another set of lashes after the first appointment."
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
        "slug": "weston-wax-center-indian-trace",
        "name": "Weston Wax Center",
        "neighborhood_slug": "indian-trace",
        "categories": ["waxing"],
        "address": "2100 N Commerce Pkwy, Suite 112, Weston, FL 33326",
        "phone": "(954) 389-2100",
        "website": "",
        "description": (
            "A wax-only studio in eastern Weston offering Brazilian, bikini, "
            "full-leg, and facial waxing in private rooms with hard wax for "
            "all sensitive areas. The focused single-service approach keeps "
            "wait times short and the licensed estheticians genuinely skilled "
            "at what they do."
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
        "slug": "the-nail-lounge-weston-town-center",
        "name": "The Nail Lounge Weston",
        "neighborhood_slug": "weston-town-center",
        "categories": ["nails"],
        "address": "1737 Main St, Weston, FL 33326",
        "phone": "(954) 389-5000",
        "website": None,
        "instagram": None,
        "description": (
            "Popular nail destination in Weston Town Center offering gel manicures, "
            "pedicures, and nail art in a modern, bright setting popular with "
            "Weston's professional community."
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
        "slug": "patrick-taleb-salon-spa-weston",
        "name": "Patrick Taleb Salon & Spa",
        "neighborhood_slug": "weston-town-center",
        "categories": ["hair", "spa"],
        "address": "1585 Northpark Dr, Weston, FL 33326",
        "phone": "(954) 389-4600",
        "website": None,
        "instagram": None,
        "description": (
            "Upscale full-service salon and spa in Weston Town Center offering "
            "precision cuts, color, keratin treatments, and spa services for "
            "Weston's discerning clientele."
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
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "aura-beauty-weston-savanna",
        "name": "Aura Beauty Weston",
        "neighborhood_slug": "savanna",
        "categories": ["nails", "lash-brow"],
        "address": "2214 Weston Rd, Weston, FL 33326",
        "phone": "(754) 301-5951",
        "website": None,
        "instagram": None,
        "description": (
            "Neighborhood beauty studio on Weston Road serving the Savanna "
            "community with nail services, lash lifts, and brow shaping in "
            "a friendly, relaxed setting."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–7pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "vogue-nail-bar-indian-trace",
        "name": "Vogue Nail Bar",
        "neighborhood_slug": "indian-trace",
        "categories": ["nails"],
        "address": "1661 Bonaventure Blvd, Weston, FL 33326",
        "phone": "(954) 451-5009",
        "website": None,
        "instagram": None,
        "description": (
            "Friendly nail bar on Bonaventure Blvd in eastern Weston offering "
            "classic and gel manicures, pedicures, and acrylic extensions for "
            "the Indian Trace community."
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
        "price_range": "$",
        "status": "live",
    },
]


async def seed_weston() -> None:
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
            "The curated beauty directory for Weston, FL — salons, spas, lash studios, "
            "and nail bars discovered by locals. Covering Weston Town Center, Emerald Estates, "
            "Savanna, and Indian Trace in South Florida's most affluent planned community."
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
        f"Weston seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_weston()


if __name__ == "__main__":
    run(main())
