"""Seed script for Hialeah, FL (city #15).

Hialeah is Miami-Dade's second-largest city and one of the most distinctly
Cuban-American communities in the United States. Over 90% of residents identify
as Hispanic or Latino, and the culture here is proud, tight-knit, and intensely
beauty-conscious — Cuban women are known for never skipping salon day. Westland
Mall anchors the retail end; Calle Ocho-adjacent corridors carry the soul.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_hialeah
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import assert_seed_target_allowed, run, upsert, pick_category_photo

CITY_SLUG = "hialeah"
CITY_NAME = "Hialeah"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Hialeah is Miami-Dade's proudly Cuban-American heartland — a city where "
    "salon appointments are a weekly ritual and beauty is a community language. "
    "From the Cuban-owned blowout bars along Palm Avenue to the full-service "
    "day spas near Westland Mall, Hialeah's beauty scene is vibrant, bilingual, "
    "and deeply loyal. This is where Miami's beauty culture has roots."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "hialeah.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "palm-avenue",
        "Palm Avenue Corridor",
        "Hialeah's main commercial spine — a dense strip of Cuban-owned salons, "
        "nail bars, and beauty supply stores serving a loyal local clientele.",
        8,
    ),
    (
        "westland",
        "Westland Mall Area",
        "The retail hub of western Hialeah, anchored by Westland Mall and "
        "surrounded by franchise and independent beauty shops.",
        6,
    ),
    (
        "hialeah-gardens",
        "Hialeah Gardens",
        "The quieter residential fringe on the city's western edge — neighborhood "
        "salons where everyone knows your name.",
        4,
    ),
    (
        "east-hialeah",
        "East Hialeah",
        "The older, denser side of the city closest to Miami — traditional "
        "Cuban blowout bars and community nail salons that have been here for decades.",
        4,
    ),
]

# WHY: normalize variant slugs to canonical category keys used by the network
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
    "makeup": "makeup",
    "skincare": "skincare",
}

BUSINESSES = [
    # ── Palm Avenue Corridor ───────────────────────────────────────────────────
    {
        "slug": "salon-bello-hialeah",
        "name": "Salon Bello",
        "neighborhood_slug": "palm-avenue",
        "categories": ["hair", "makeup"],
        "address": "930 E 25th St, Hialeah, FL 33013",
        "phone": "(305) 558-1200",
        "website": "",
        "description": (
            "One of Palm Avenue's best-known Cuban-owned salons, serving "
            "Hialeah women for over 20 years. Known for silky Dominican "
            "blowouts, keratin treatments, and bridal hair styling. Bilingual "
            "staff, walk-ins welcome on weekdays."
        ),
        "hours": {
            "Mon": "8am–7pm",
            "Tue": "8am–7pm",
            "Wed": "8am–7pm",
            "Thu": "8am–7pm",
            "Fri": "8am–7pm",
            "Sat": "8am–6pm",
            "Sun": "9am–4pm",
        },
        "editors_pick": True,
        "editors_note": (
            "A Hialeah institution — Cuban blowout culture at its finest. "
            "20+ years of loyal clients and the best Dominican blowout on "
            "the Palm Avenue strip."
        ),
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "unas-perfectas-hialeah",
        "name": "Uñas Perfectas",
        "neighborhood_slug": "palm-avenue",
        "categories": ["nails"],
        "address": "955 E 25th St, Hialeah, FL 33013",
        "phone": "(305) 558-4400",
        "website": "",
        "description": (
            "High-volume nail salon on Palm Avenue known for fast acrylics, "
            "gel polish, and competitive prices. Spanish-speaking staff, "
            "walk-ins always welcome, with waits rarely over 20 minutes."
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
        "slug": "glamour-cuban-beauty-salon",
        "name": "Glamour Cuban Beauty Salon",
        "neighborhood_slug": "palm-avenue",
        "categories": ["hair", "makeup"],
        "address": "1020 Palm Ave, Hialeah, FL 33010",
        "phone": "(305) 883-1100",
        "website": "",
        "description": (
            "Traditional Cuban beauty salon offering blowouts, roller sets, "
            "and hair coloring at prices unchanged since 1995. A beloved "
            "neighborhood spot where regulars are treated like family."
        ),
        "hours": {
            "Mon": "8am–6pm",
            "Tue": "8am–6pm",
            "Wed": "8am–6pm",
            "Thu": "8am–6pm",
            "Fri": "8am–7pm",
            "Sat": "7:30am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "Old-school Cuban beauty at its most authentic — roller sets, "
            "blowouts, and a price list that hasn't changed in years. "
            "Regulars have been coming here since the 90s."
        ),
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "centro-de-belleza-hialeah",
        "name": "Centro de Belleza Hialeah",
        "neighborhood_slug": "palm-avenue",
        "categories": ["hair", "waxing", "makeup"],
        "address": "845 Palm Ave, Hialeah, FL 33010",
        "phone": "(305) 883-2200",
        "website": "",
        "description": (
            "Full-service beauty center on Palm Avenue offering hair, waxing, "
            "and makeup. Specializes in quinceañera and bridal packages. "
            "Known for threading brows and applying long-lasting makeup looks."
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
        "slug": "lashes-by-maria-hialeah",
        "name": "Lashes by María",
        "neighborhood_slug": "palm-avenue",
        "categories": ["lash-brow"],
        "address": "960 E 24th St Ste 3, Hialeah, FL 33013",
        "phone": "(305) 883-5500",
        "website": "",
        "description": (
            "Hialeah's go-to lash artist for classic and mega-volume sets. "
            "María trained in Havana and brought Cuban attention to detail "
            "to her Hialeah studio. Book at least a week out — she fills fast."
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
            "Trained in Havana, operating in Hialeah — María's lash sets "
            "have a precision you don't often find at this price point. "
            "A hidden gem worth the week-out wait."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "nail-art-studio-hialeah",
        "name": "Nail Art Studio",
        "neighborhood_slug": "palm-avenue",
        "categories": ["nails"],
        "address": "1100 E 25th St, Hialeah, FL 33013",
        "phone": "(305) 558-6600",
        "website": "",
        "description": (
            "Modern nail studio on Palm Avenue specializing in nail art, "
            "chrome powder, and 3D extensions. Trendy techniques at "
            "neighborhood prices, with an Instagram-friendly aesthetic."
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
        "slug": "belleza-latina-hialeah",
        "name": "Belleza Latina Salon",
        "neighborhood_slug": "palm-avenue",
        "categories": ["hair", "skincare"],
        "address": "720 Palm Ave, Hialeah, FL 33010",
        "phone": "(305) 884-1300",
        "website": "",
        "description": (
            "Multi-service salon combining hair with facial treatments and "
            "skin consultations. Popular for hydrafacials and vitamin C "
            "treatments alongside classic blowouts and color."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "waxing-the-city-hialeah-palm",
        "name": "Waxing the City — Palm Ave",
        "neighborhood_slug": "palm-avenue",
        "categories": ["waxing"],
        "address": "1050 Palm Ave, Hialeah, FL 33010",
        "phone": "(305) 557-9000",
        "website": "https://waxingthecity.com",
        "description": (
            "Franchise waxing studio with private suites, consistent results, "
            "and a membership program. Clean, efficient, and reliable — a "
            "modern option among Palm Avenue's traditional salons."
        ),
        "hours": {
            "Mon": "9am–8pm",
            "Tue": "9am–8pm",
            "Wed": "9am–8pm",
            "Thu": "9am–8pm",
            "Fri": "9am–8pm",
            "Sat": "8am–7pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    # ── Westland Mall Area ────────────────────────────────────────────────────
    {
        "slug": "spa-luxe-westland",
        "name": "Spa Luxe Westland",
        "neighborhood_slug": "westland",
        "categories": ["spa", "skincare", "massage"],
        "address": "1675 W 49th St Ste 202, Hialeah, FL 33012",
        "phone": "(305) 558-7700",
        "website": "",
        "description": (
            "Full-service day spa near Westland Mall offering facials, "
            "deep-tissue massage, hot stone therapy, and body wraps. "
            "One of the few true day spas in Hialeah — appointments recommended."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–6pm",
            "Sun": "10am–5pm",
        },
        "editors_pick": True,
        "editors_note": (
            "One of the very few full day spas in Hialeah — relaxing, "
            "professional, and surprisingly affordable. The hot stone "
            "massage is worth the appointment."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "great-clips-westland",
        "name": "Great Clips — Westland",
        "neighborhood_slug": "westland",
        "categories": ["hair"],
        "address": "1675 W 49th St, Hialeah, FL 33012",
        "phone": "(305) 556-1200",
        "website": "https://greatclips.com",
        "description": (
            "Reliable walk-in haircut chain in the Westland shopping corridor. "
            "Consistent results, online check-in, and affordable pricing — "
            "ideal for the whole family."
        ),
        "hours": {
            "Mon": "9am–9pm",
            "Tue": "9am–9pm",
            "Wed": "9am–9pm",
            "Thu": "9am–9pm",
            "Fri": "9am–9pm",
            "Sat": "8am–7pm",
            "Sun": "9am–6pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "european-wax-center-hialeah",
        "name": "European Wax Center — Hialeah",
        "neighborhood_slug": "westland",
        "categories": ["waxing"],
        "address": "1621 W 49th St, Hialeah, FL 33012",
        "phone": "(305) 818-8300",
        "website": "https://waxcenter.com",
        "description": (
            "Clean, professional waxing studio with private suites and a "
            "Comfort Wax formula. Membership pricing for regulars. "
            "Consistent results for face, body, and brow waxing."
        ),
        "hours": {
            "Mon": "9am–9pm",
            "Tue": "9am–9pm",
            "Wed": "9am–9pm",
            "Thu": "9am–9pm",
            "Fri": "9am–9pm",
            "Sat": "8am–8pm",
            "Sun": "10am–6pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "nails-plus-westland",
        "name": "Nails Plus",
        "neighborhood_slug": "westland",
        "categories": ["nails"],
        "address": "1700 W 49th St, Hialeah, FL 33012",
        "phone": "(305) 556-3300",
        "website": "",
        "description": (
            "Busy nail salon in the Westland corridor known for quality gel "
            "manicures, acrylic sets, and thorough pedicures. Online booking "
            "available; walk-ins accommodated most weekdays."
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
        "slug": "glam-studio-westland",
        "name": "Glam Studio",
        "neighborhood_slug": "westland",
        "categories": ["hair", "lash-brow"],
        "address": "1580 W 49th St Ste 110, Hialeah, FL 33012",
        "phone": "(305) 556-8800",
        "website": "",
        "description": (
            "Modern salon and lash studio combining precision cuts, color, "
            "and lash extensions under one roof. Bilingual staff and a "
            "contemporary vibe that sets it apart from Palm Avenue traditionalists."
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
        "slug": "beauty-bar-westland",
        "name": "Beauty Bar Westland",
        "neighborhood_slug": "westland",
        "categories": ["makeup", "lash-brow"],
        "address": "1640 W 49th St, Hialeah, FL 33012",
        "phone": "(305) 558-5500",
        "website": "",
        "description": (
            "Makeup and brow bar offering airbrush foundation, lash services, "
            "and brow shaping. Popular for quinceañera and wedding party prep. "
            "Walk-ins welcome for brow threading on weekdays."
        ),
        "hours": {
            "Mon": "10am–7pm",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–6pm",
            "Sun": "11am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    # ── Hialeah Gardens ───────────────────────────────────────────────────────
    {
        "slug": "oasis-salon-hialeah-gardens",
        "name": "Oasis Salon & Spa",
        "neighborhood_slug": "hialeah-gardens",
        "categories": ["hair", "spa", "skincare"],
        "address": "9300 NW 103rd St, Hialeah Gardens, FL 33016",
        "phone": "(305) 819-5000",
        "website": "",
        "description": (
            "Neighborhood salon and mini-spa in Hialeah Gardens combining "
            "hair services with facials and waxing. A calm, unhurried alternative "
            "to the busier Palm Avenue corridor."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "venus-nails-hialeah-gardens",
        "name": "Venus Nails",
        "neighborhood_slug": "hialeah-gardens",
        "categories": ["nails", "waxing"],
        "address": "9500 NW 103rd St, Hialeah Gardens, FL 33016",
        "phone": "(305) 822-6600",
        "website": "",
        "description": (
            "Friendly walk-in nail salon in a Hialeah Gardens strip mall. "
            "Known for detailed pedicures, reliable gel manis, and a quick, "
            "no-fuss experience. Waxing services also available."
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
        "slug": "cuban-style-studio-hialeah-gardens",
        "name": "Cuban Style Studio",
        "neighborhood_slug": "hialeah-gardens",
        "categories": ["hair"],
        "address": "9100 NW 103rd St Ste 5, Hialeah Gardens, FL 33016",
        "phone": "(305) 822-3300",
        "website": "",
        "description": (
            "Small, intimate hair studio in Hialeah Gardens run by a "
            "Cuban-trained stylist. Specializes in blowouts, hair treatments, "
            "and keratin smoothing. Appointment-only boutique feel."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8am–4pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "glow-nails-spa-hialeah-gardens",
        "name": "Glow Nails & Spa",
        "neighborhood_slug": "hialeah-gardens",
        "categories": ["nails", "spa"],
        "address": "9700 NW 103rd St, Hialeah Gardens, FL 33016",
        "phone": "(305) 822-9900",
        "website": "",
        "description": (
            "Spa-style nail salon in Hialeah Gardens offering hot-stone "
            "pedicures, gel manicures, and relaxing spa packages. "
            "Quieter and more spa-focused than typical neighborhood nail bars."
        ),
        "hours": {
            "Mon": "9:30am–7pm",
            "Tue": "9:30am–7pm",
            "Wed": "9:30am–7pm",
            "Thu": "9:30am–7pm",
            "Fri": "9:30am–7pm",
            "Sat": "9am–6pm",
            "Sun": "10am–4pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    # ── East Hialeah ──────────────────────────────────────────────────────────
    {
        "slug": "salon-margarita-east-hialeah",
        "name": "Salon Margarita",
        "neighborhood_slug": "east-hialeah",
        "categories": ["hair", "makeup"],
        "address": "615 E 8th Ave, Hialeah, FL 33010",
        "phone": "(305) 888-1500",
        "website": "",
        "description": (
            "One of East Hialeah's oldest Cuban-owned salons, in operation "
            "since 1988. Known for traditional roller sets, precision cuts, "
            "and event makeup. A neighborhood fixture with three generations "
            "of loyal clients."
        ),
        "hours": {
            "Mon": "8am–6pm",
            "Tue": "8am–6pm",
            "Wed": "8am–6pm",
            "Thu": "8am–6pm",
            "Fri": "8am–7pm",
            "Sat": "7:30am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "Open since 1988, Salon Margarita is a living piece of Hialeah's "
            "Cuban heritage. Three generations of clients, a price list that "
            "defies inflation, and roller sets done exactly right."
        ),
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "nails-by-rosa-east-hialeah",
        "name": "Nails by Rosa",
        "neighborhood_slug": "east-hialeah",
        "categories": ["nails"],
        "address": "700 E 4th Ave, Hialeah, FL 33010",
        "phone": "(305) 888-4400",
        "website": "",
        "description": (
            "Old-school East Hialeah nail salon with over 15 years in the "
            "same location. Rosa and her team deliver consistent acrylics, "
            "gel polish, and pedicures at prices that keep the neighborhood "
            "coming back week after week."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "9am–5:30pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "blowout-bar-hialeah",
        "name": "Blowout Bar Hialeah",
        "neighborhood_slug": "east-hialeah",
        "categories": ["hair"],
        "address": "650 E 9th Ave, Hialeah, FL 33010",
        "phone": "(305) 888-7700",
        "website": "",
        "description": (
            "Dedicated blowout bar in East Hialeah offering fast, "
            "professional blowouts starting at $25. No cuts, no color — "
            "just flawless blowouts, every time, walk-in friendly."
        ),
        "hours": {
            "Mon": "8am–7pm",
            "Tue": "8am–7pm",
            "Wed": "8am–7pm",
            "Thu": "8am–7pm",
            "Fri": "8am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "elite-lash-studio-hialeah",
        "name": "Elite Lash Studio",
        "neighborhood_slug": "east-hialeah",
        "categories": ["lash-brow"],
        "address": "720 E 10th Ave Ste 102, Hialeah, FL 33010",
        "phone": "(305) 888-9900",
        "website": "",
        "description": (
            "Lash and brow studio in East Hialeah offering classic, hybrid, "
            "and volume lash extensions along with brow lamination and tinting. "
            "Spanish-speaking technicians, appointment preferred."
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
        "slug": "moonlight-beauty-salon-palm-ave",
        "name": "Moonlight Beauty Salon",
        "neighborhood_slug": "palm-avenue",
        "categories": ["hair", "nails"],
        "address": "1368 Palm Ave, Hialeah, FL 33010",
        "phone": "(305) 888-1710",
        "website": None,
        "instagram": None,
        "description": (
            "Neighborhood beauty salon on historic Palm Avenue serving Hialeah's "
            "tight-knit community with hair and nail services at accessible prices."
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
    {
        "slug": "crystal-nails-spa-hialeah",
        "name": "Crystal Nails & Spa",
        "neighborhood_slug": "westland",
        "categories": ["nails", "lash-brow", "waxing"],
        "address": "1557 W 49th St, Hialeah, FL 33012",
        "phone": "(305) 826-4147",
        "website": None,
        "instagram": None,
        "description": (
            "Well-established spa-style nail salon in the Westland area offering "
            "a full menu of nail, lash, and waxing services in a clean, modern environment."
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
        "slug": "fingers-toes-nail-salon-hialeah",
        "name": "Fingers & Toes Nail Salon",
        "neighborhood_slug": "westland",
        "categories": ["nails"],
        "address": "3798 W 12th Ave Ste B, Hialeah, FL 33012",
        "phone": "(786) 362-6004",
        "website": None,
        "instagram": None,
        "description": (
            "Friendly neighborhood nail salon in western Hialeah offering manicures, "
            "pedicures, and gel services at community-friendly prices."
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
]


async def seed_hialeah() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    # Resolve network
    network = await db.networks.find_one({"_id": BEAUTY_NETWORK_ID})
    if not network:
        network = await db.networks.find_one({"slug": BEAUTY_NETWORK_SLUG})
    if not network:
        raise RuntimeError(
            f"Network not found: id={BEAUTY_NETWORK_ID} slug={BEAUTY_NETWORK_SLUG}"
        )
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
            "An index of the colorists, nail artists, lash stylists, and estheticians "
            "Hialeah locals actually book — from the classic barberías of Palm Avenue "
            "to the modern beauty studios of Hialeah Gardens."
        ),
        "meta_description": (
            "The curated beauty directory for Hialeah, Florida — salons, nail bars, "
            "lash studios, and spas discovered by locals. Covering Palm Avenue, "
            "Hialeah Drive, Westland Mall area, and Hialeah Gardens."
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

    # Upsert categories from the network's category_map
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
        f"Hialeah seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_hialeah()


if __name__ == "__main__":
    run(main())
