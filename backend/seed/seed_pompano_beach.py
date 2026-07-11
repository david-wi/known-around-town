"""Seed script for Pompano Beach, FL (city #15).

Pompano Beach sits at the heart of northern Broward County — a city in
transition, blending its laid-back fishing-town roots with a fast-growing
arts district and an influx of South American and Caribbean residents who
bring a strong beauty culture. Atlantic Boulevard is the main commercial
spine; Sample Road serves the northern residential corridors; the emerging
Downtown Pompano arts scene anchors a younger, trend-forward clientele;
and North Pompano's quieter neighborhoods support loyal neighborhood salons.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_pompano_beach
"""

from datetime import datetime, timezone

from app.database import ensure_indexes, get_db
from seed._helpers import (
    assert_seed_target_allowed,
    pick_category_photo,
    preserve_existing_business_state,
    run,
    upsert,
)

CITY_SLUG = "pompano-beach"
CITY_NAME = "Pompano Beach"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Pompano Beach is northern Broward's hidden beauty hub — a city where "
    "laid-back coastal energy meets a growing arts scene and a diverse mix "
    "of South American, Caribbean, and long-time Florida residents. From "
    "bustling Atlantic Boulevard salons to intimate studios tucked into the "
    "revitalized downtown, the city offers everything from budget-friendly "
    "neighborhood nail bars to polished full-service day spas."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "pompano-beach.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "atlantic-blvd",
        "Atlantic Boulevard",
        "Pompano's main commercial corridor — a dense strip of salons, nail "
        "bars, and spas serving residents from the beach to the Turnpike.",
        8,
    ),
    (
        "sample-road",
        "Sample Road",
        "Northern Pompano's busy retail spine — diverse neighborhood salons "
        "catering to a loyal mix of Caribbean and South American clientele.",
        5,
    ),
    (
        "downtown-pompano",
        "Downtown Pompano",
        "The revitalized arts-district core — boutique studios attracting a "
        "younger, trend-forward crowd alongside longtime Pompano locals.",
        4,
    ),
    (
        "north-pompano",
        "North Pompano",
        "Quieter residential streets north of Sample Road — neighborhood "
        "salons with walk-in energy and a strong base of repeat regulars.",
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
    "makeup": "makeup",
    "skincare": "skincare",
}

BUSINESSES = [
    # ── Atlantic Boulevard ─────────────────────────────────────────────────────
    {
        "slug": "the-beauty-bar-pompano",
        "name": "The Beauty Bar Pompano",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["hair", "spa"],
        "address": "1541 E Atlantic Blvd, Pompano Beach, FL 33060",
        "phone": "(954) 941-1800",
        "website": "https://thebeautybarpompano.com",
        "description": (
            "Pompano Beach's premier full-service salon on the Atlantic "
            "corridor — precision cuts, keratin treatments, balayage color, "
            "and hydrating spa facials under one roof. Bilingual staff and a "
            "welcoming vibe keep a diverse clientele coming back."
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
            "Atlantic Boulevard's standout salon — the keratin treatments "
            "and balayage color rival anything in Fort Lauderdale. Bilingual "
            "staff and a consistently polished experience set this apart."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "coastal-nail-lounge",
        "name": "Coastal Nail Lounge",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["nails"],
        "address": "2200 E Atlantic Blvd, Pompano Beach, FL 33062",
        "phone": "(954) 785-2200",
        "website": "https://coastalnaillounge.com",
        "description": (
            "Modern nail lounge steps from the Intracoastal with a breezy "
            "coastal aesthetic. Known for gel manicures, dip powder, and "
            "impeccably clean pedicure stations. Online booking and same-day "
            "appointments available most weekdays."
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
            "The nail lounge Pompano Beach has been missing — genuinely "
            "modern design, obsessively clean stations, and gel work that "
            "holds up. The beachy vibe makes the pedicure experience feel "
            "like a proper treat."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "lash-luxe-pompano",
        "name": "Lash Luxe Pompano",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["lash-brow"],
        "address": "1850 W Atlantic Blvd Ste 108, Pompano Beach, FL 33069",
        "phone": "(954) 785-5400",
        "website": "",
        "description": (
            "Boutique lash studio on the western Atlantic corridor offering "
            "classic, hybrid, and mega-volume extensions alongside lash lifts "
            "and brow lamination. Walk-in brow threading available daily. "
            "Popular with Pompano's office professionals."
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
        "slug": "european-wax-center-pompano",
        "name": "European Wax Center — Pompano Beach",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["waxing"],
        "address": "2300 N Federal Hwy, Pompano Beach, FL 33064",
        "phone": "(954) 941-9292",
        "website": "https://waxcenter.com",
        "description": (
            "Franchise location delivering consistent full-body waxing in "
            "clean, private suites. Loyalty rewards program, online booking, "
            "and a no-wait policy keep regulars on a reliable schedule."
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
        "slug": "glamour-touch-salon-pompano",
        "name": "Glamour Touch Salon",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["hair", "makeup"],
        "address": "1100 W Atlantic Blvd, Pompano Beach, FL 33069",
        "phone": "(954) 785-1100",
        "website": "",
        "description": (
            "Family-run Colombian salon on Atlantic Blvd known for "
            "Dominican blowouts, color touch-ups, and quinceañera and bridal "
            "makeup. The signature blowout is a neighborhood institution."
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
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "tranquility-day-spa-pompano",
        "name": "Tranquility Day Spa",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["spa", "skincare", "massage"],
        "address": "1760 E Atlantic Blvd, Pompano Beach, FL 33060",
        "phone": "(954) 785-7600",
        "website": "https://tranquilitydayspapompano.com",
        "description": (
            "A full day spa on the Atlantic corridor offering Swedish and deep "
            "tissue massage, anti-aging facials, chemical peels, and body "
            "wraps. Serene environment with professional, licensed therapists."
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
            "The best full spa experience on the Atlantic corridor — the "
            "deep-tissue massage and anti-aging facials are done with real "
            "skill, and the serene environment delivers a genuine escape. "
            "Book the facial-and-massage combo for the full experience."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "quick-brow-bar-atlantic",
        "name": "Quick Brow Bar",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["lash-brow"],
        "address": "2550 W Atlantic Blvd, Pompano Beach, FL 33069",
        "phone": "(954) 785-3300",
        "website": "",
        "description": (
            "Walk-in threading and brow-waxing kiosk anchoring a busy "
            "Atlantic Blvd strip center. Fast, precise eyebrow threading "
            "at $10 a session with no appointment needed. Lip and chin "
            "services also available."
        ),
        "hours": {
            "Mon": "10am–8pm",
            "Tue": "10am–8pm",
            "Wed": "10am–8pm",
            "Thu": "10am–8pm",
            "Fri": "10am–8pm",
            "Sat": "9am–7pm",
            "Sun": "11am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "nails-by-the-beach-pompano",
        "name": "Nails by the Beach",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["nails", "waxing"],
        "address": "2700 E Atlantic Blvd, Pompano Beach, FL 33062",
        "phone": "(954) 942-1900",
        "website": "",
        "description": (
            "Neighborhood nail salon catering to beachside regulars with "
            "acrylic sets, gel manicures, and spa pedicures. Quick waxing "
            "services complement the menu. Known for clean stations and a "
            "genuinely friendly atmosphere."
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
    # ── Sample Road ────────────────────────────────────────────────────────────
    {
        "slug": "salon-bella-sample-road",
        "name": "Salon Bella",
        "neighborhood_slug": "sample-road",
        "categories": ["hair"],
        "address": "3500 W Sample Rd, Pompano Beach, FL 33073",
        "phone": "(954) 979-3500",
        "website": "https://salonbellapompano.com",
        "description": (
            "Venezuelan-owned hair salon on Sample Road renowned for "
            "keratin treatments, meche highlights, and scalp care. A "
            "warm, community-focused environment with a bilingual team "
            "and a loyal South American clientele."
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
            "The go-to keratin and highlight specialist on Sample Road — "
            "Venezuelan expertise, warm atmosphere, and a devoted clientele "
            "that schedules months in advance. Don't skip the scalp "
            "treatment add-on."
        ),
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "perfect-10-nails-sample",
        "name": "Perfect 10 Nails",
        "neighborhood_slug": "sample-road",
        "categories": ["nails"],
        "address": "4200 W Sample Rd Ste 105, Pompano Beach, FL 33073",
        "phone": "(954) 979-4200",
        "website": "",
        "description": (
            "Busy Sample Road nail salon with a strong local following for "
            "consistent acrylic sets, gel polish, and spa pedicures. "
            "Walk-ins welcome; efficient service keeps wait times short."
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
        "slug": "massage-envy-pompano-sample",
        "name": "Massage Envy — Pompano Beach",
        "neighborhood_slug": "sample-road",
        "categories": ["massage", "skincare"],
        "address": "3800 N Federal Hwy, Pompano Beach, FL 33064",
        "phone": "(954) 956-3689",
        "website": "https://massageenvy.com",
        "description": (
            "Membership-based massage and skincare studio offering Swedish, "
            "deep tissue, and trigger point therapy alongside chemical peels "
            "and microderm infusion facials. Reliable quality, flexible "
            "appointment windows."
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
        "slug": "lashes-by-mariana-pompano",
        "name": "Lashes by Mariana",
        "neighborhood_slug": "sample-road",
        "categories": ["lash-brow"],
        "address": "3100 W Sample Rd Ste 201, Pompano Beach, FL 33073",
        "phone": "(954) 979-1800",
        "website": "",
        "description": (
            "Colombian lash artist offering mega-volume and hybrid sets with "
            "an emphasis on long-lasting retention. Brow lamination and "
            "tinting available. Books up two weeks out — reserve in advance."
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
        "slug": "hair-gallery-sample-road",
        "name": "Hair Gallery",
        "neighborhood_slug": "sample-road",
        "categories": ["hair", "makeup"],
        "address": "4500 W Sample Rd, Pompano Beach, FL 33073",
        "phone": "(954) 979-5500",
        "website": "",
        "description": (
            "Full-service hair and makeup studio on Sample Road serving "
            "Pompano's Caribbean and Haitian community. Natural hair "
            "expertise, braiding, protective styles, and bridal makeup. "
            "Walk-ins welcome on weekdays."
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
    # ── Downtown Pompano ───────────────────────────────────────────────────────
    {
        "slug": "studio-glow-downtown-pompano",
        "name": "Studio Glow",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["skincare", "spa"],
        "address": "18 NE 1st St, Pompano Beach, FL 33060",
        "phone": "(954) 786-1800",
        "website": "https://studioglowpompano.com",
        "description": (
            "Boutique esthetics studio in the heart of downtown Pompano's "
            "arts district offering signature facials, chemical peels, "
            "microneedling, and LED light therapy. The studio draws a "
            "younger, results-driven crowd alongside established locals."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–6pm",
            "Wed": "10am–6pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": True,
        "editors_note": (
            "The most exciting new skincare studio in Pompano — "
            "microneedling and chemical peels done with genuine expertise "
            "in a beautifully renovated arts-district space. Results speak "
            "for themselves within a few visits."
        ),
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "the-mane-collective-pompano",
        "name": "The Mane Collective",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["hair"],
        "address": "22 SW 2nd Ave, Pompano Beach, FL 33060",
        "phone": "(954) 786-2200",
        "website": "https://themanecollectivepompano.com",
        "description": (
            "Trendy independent salon in downtown Pompano specializing in "
            "lived-in color, curtain bangs, and curly hair cuts. An "
            "Instagram-worthy space that draws clients from across "
            "Broward County for creative color work."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–8pm",
            "Fri": "10am–8pm",
            "Sat": "9am–6pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "live",
    },
    {
        "slug": "polish-and-press-downtown",
        "name": "Polish & Press",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["nails", "hair"],
        "address": "34 NE 2nd St, Pompano Beach, FL 33060",
        "phone": "(954) 786-3400",
        "website": "",
        "description": (
            "Downtown's chic nail and silk-press destination — gel nail art, "
            "chrome dip manicures, and silky blowouts in a cozy studio "
            "environment. Walk-ins accepted for nail services; hair by "
            "appointment only."
        ),
        "hours": {
            "Mon": "Closed",
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
        "slug": "brow-and-glow-pompano",
        "name": "Brow & Glow Studio",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["lash-brow", "skincare"],
        "address": "10 SW 1st Ave, Pompano Beach, FL 33060",
        "phone": "(954) 786-1000",
        "website": "",
        "description": (
            "Micro-studio in downtown Pompano pairing precise brow design "
            "with a curated skincare menu including hydrafacial-style "
            "treatments and dermaplaning. Appointment-only with a focused "
            "one-client-at-a-time approach."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–5pm",
            "Wed": "10am–5pm",
            "Thu": "10am–6pm",
            "Fri": "10am–6pm",
            "Sat": "9am–3pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "live",
    },
    # ── North Pompano ──────────────────────────────────────────────────────────
    {
        "slug": "sunshine-nails-spa-north-pompano",
        "name": "Sunshine Nails & Spa",
        "neighborhood_slug": "north-pompano",
        "categories": ["nails", "spa"],
        "address": "5200 N Federal Hwy, Pompano Beach, FL 33064",
        "phone": "(954) 956-5200",
        "website": "",
        "description": (
            "Reliable neighborhood nail and spa spot in North Pompano — "
            "acrylics, gel manis, and spa pedicures with massage chairs "
            "and a relaxed atmosphere. Consistent quality and competitive "
            "pricing keep regulars on a monthly rotation."
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
    {
        "slug": "north-pompano-hair-studio",
        "name": "North Pompano Hair Studio",
        "neighborhood_slug": "north-pompano",
        "categories": ["hair"],
        "address": "5550 N Federal Hwy Ste 4, Pompano Beach, FL 33064",
        "phone": "(954) 956-5550",
        "website": "",
        "description": (
            "Friendly neighborhood salon catering to North Pompano families "
            "and long-time locals. Haircuts, color touch-ups, kids' cuts, "
            "and Dominican blowouts. Walk-ins welcome on weekdays with "
            "minimal wait."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7pm",
            "Sat": "8:30am–4pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "serenity-lash-and-wax-north",
        "name": "Serenity Lash & Wax",
        "neighborhood_slug": "north-pompano",
        "categories": ["lash-brow", "waxing"],
        "address": "5800 N Federal Hwy, Pompano Beach, FL 33064",
        "phone": "(954) 956-5800",
        "website": "",
        "description": (
            "North Pompano's go-to for lash extensions and full-body waxing. "
            "Classic and hybrid lash sets, plus consistent Brazilian, "
            "bikini, and leg waxing. Private, comfortable treatment rooms "
            "and flexible weekday hours."
        ),
        "hours": {
            "Mon": "10am–6pm",
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
        "slug": "downtown-pompano-salon",
        "name": "Downtown Pompano Salon",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["hair"],
        "address": "11 NW 1st Ave, Pompano Beach, FL 33060",
        "phone": "(954) 942-5511",
        "website": "",
        "description": (
            "A full-service salon in downtown Pompano serving the Arts District "
            "neighborhood with cuts, color, and blow-outs. Relaxed atmosphere "
            "with a team that keeps appointments running on time."
        ),
        "hours": {
            "Mon": "9am–6pm",
            "Tue": "9am–6pm",
            "Wed": "9am–6pm",
            "Thu": "9am–6pm",
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
        "slug": "arts-district-nail-bar-pompano",
        "name": "Arts District Nail Bar",
        "neighborhood_slug": "downtown-pompano",
        "categories": ["nails"],
        "address": "20 NE 2nd St, Pompano Beach, FL 33060",
        "phone": "(954) 941-3388",
        "website": "",
        "description": (
            "A well-maintained nail bar near the Pompano Arts District with a "
            "straightforward menu of gel sets, dips, and pedicures. Clean, "
            "friendly, and easy to book for a last-minute appointment."
        ),
        "hours": {
            "Mon": "9:30am–6pm",
            "Tue": "9:30am–6pm",
            "Wed": "9:30am–6pm",
            "Thu": "9:30am–6pm",
            "Fri": "9:30am–7pm",
            "Sat": "9am–5pm",
            "Sun": "Closed",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "live",
    },
    {
        "slug": "sample-road-spa-pompano",
        "name": "Sample Road Spa",
        "neighborhood_slug": "sample-road",
        "categories": ["spa"],
        "address": "3201 W Sample Rd, Pompano Beach, FL 33073",
        "phone": "(954) 969-7700",
        "website": "",
        "description": (
            "A mid-range day spa on Sample Road offering massages, facials, and "
            "body treatments for the West Pompano community. Consistent service "
            "and fair prices have kept a strong base of repeat clients."
        ),
        "hours": {
            "Mon": "10am–7pm",
            "Tue": "10am–7pm",
            "Wed": "10am–7pm",
            "Thu": "10am–7pm",
            "Fri": "10am–7pm",
            "Sat": "9am–6pm",
            "Sun": "11am–5pm",
        },
        "editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "live",
    },
    {
        "slug": "north-pompano-lash-bar",
        "name": "North Pompano Lash Bar",
        "neighborhood_slug": "north-pompano",
        "categories": ["lash-brow"],
        "address": "4850 Coconut Creek Pkwy, Pompano Beach, FL 33063",
        "phone": "(954) 968-2200",
        "website": "",
        "description": (
            "Lash extensions and brow services in North Pompano with consistent "
            "results and a friendly, no-pressure approach. Classic and hybrid sets "
            "available with fills offered on a flexible schedule."
        ),
        "hours": {
            "Mon": "10am–6pm",
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
        "slug": "atlantic-wax-center-pompano",
        "name": "Atlantic Wax Center",
        "neighborhood_slug": "atlantic-blvd",
        "categories": ["waxing"],
        "address": "1700 E Atlantic Blvd, Pompano Beach, FL 33060",
        "phone": "(954) 785-8833",
        "website": "",
        "description": (
            "A dedicated waxing center on Atlantic Boulevard handling everything "
            "from face and brows to Brazilian and full-leg. Walk-ins welcome "
            "between appointments and same-day booking usually works."
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
]


async def seed_pompano_beach() -> None:
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
            "An index of the colorists, nail artists, lash stylists, and estheticians "
            "Pompano Beach locals actually book — from the shops along Atlantic Boulevard "
            "to beachside studios near the Pompano Beach Pier."
        ),
        "meta_description": (
            "The curated beauty directory for Pompano Beach, Florida — salons, spas, "
            "nail bars, and lash studios discovered by locals. Covering Atlantic "
            "Boulevard, Sample Road, the Pier area, and North Pompano."
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

        # Resolve category IDs
        raw_cats = biz.get("categories") or []
        canonical_cats = [_SLUG_CANON.get(c, c) for c in raw_cats]

        biz_doc = {
            "city_id": city_id,
            "network_id": network_id,
            "slug": slug,
            "name": biz["name"],
            "neighborhood_slugs": [nb_slug] if nb_slug else [],
            "category_slugs": canonical_cats,
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
            # Keep the established closed-listing behavior: archived records
            # are intentionally left untouched by source refreshes.
            if existing.get("status") == "archived":
                continue
            preserve_existing_business_state(existing, biz_doc)
            biz_doc["_id"] = existing["_id"]
            biz_doc["created_at"] = existing.get("created_at", biz_doc.get("created_at", now))
            await db.businesses.replace_one({"_id": existing["_id"]}, biz_doc)
            updated += 1
        else:
            biz_doc["created_at"] = now
            await db.businesses.insert_one(biz_doc)
            inserted += 1

    print(f"Businesses: {inserted} inserted, {updated} updated.")
    print(
        f"Pompano Beach seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_pompano_beach()


if __name__ == "__main__":
    run(main())
