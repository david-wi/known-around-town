"""Seed script for Doral, FL (city #14).

Doral is South Florida's fastest-growing city and one of its most dynamic
beauty markets. The community is predominantly Latin American — Venezuelan,
Colombian, Argentine — bringing a beauty-conscious culture and high demand for
hair, lash, and nail services. City Center anchors the upscale end; Doral Blvd
is the authentic Latin beauty corridor.

Run (production):
    KAT_ALLOW_PRODUCTION_RESET=true python -m seed.seed_doral
"""

from asyncio import run
from datetime import datetime, timezone

from seed._helpers import assert_seed_target_allowed, ensure_indexes, upsert
from app.db import get_db

CITY_SLUG = "doral"
CITY_NAME = "Doral"
CITY_STATE = "FL"
CITY_DESCRIPTION = (
    "Doral is South Florida's fastest-growing city and a hub of Latin American "
    "culture, where Venezuelan and Colombian style meets suburban luxury. From "
    "the upscale boutiques of City Center to the vibrant beauty corridor on "
    "Doral Boulevard, the city's salons blend international expertise with the "
    "warm energy of a tight-knit community."
)
BEAUTY_NETWORK_ID = "eb913a29-f2d2-4f86-af0f-2deca3be3578"
BEAUTY_NETWORK_SLUG = "beauty"

DOMAIN_OVERRIDE = "doral.knowsbeauty.com"

# (slug, display_name, vibe_sentence, approx_listed_count)
NEIGHBORHOODS = [
    (
        "city-center",
        "City Center",
        "Doral's planned urban downtown — upscale mixed-use with luxury salons "
        "catering to professionals and golf-resort guests.",
        8,
    ),
    (
        "doral-boulevard",
        "Doral Boulevard",
        "The main commercial artery through the heart of Doral — packed with "
        "Latin-owned salons serving a loyal neighborhood clientele.",
        7,
    ),
    (
        "nw-87th-avenue",
        "NW 87th Avenue Corridor",
        "A strip-mall corridor running along Doral's eastern edge, mixing "
        "everyday nail bars with hidden-gem hair studios.",
        4,
    ),
    (
        "west-doral",
        "West Doral",
        "Quieter residential streets west of the Turnpike — neighborhood "
        "salons with loyal regulars and relaxed walk-in energy.",
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
    # ── City Center ────────────────────────────────────────────────────────────
    {
        "slug": "luxe-salon-doral",
        "name": "Luxe Salon Doral",
        "neighborhood_slug": "city-center",
        "categories": ["hair", "spa"],
        "address": "8405 NW 53rd St, Doral, FL 33166",
        "phone": "(305) 592-1100",
        "website": "https://luxesalondoral.com",
        "description": (
            "A full-service luxury salon inside City Center offering precision "
            "cuts, color, Brazilian blowouts, and custom hair treatments. "
            "Bilingual staff serves an international clientele."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
            "Fri": "9am–8pm",
            "Sat": "9am–6pm",
            "Sun": "Closed",
        },
        "is_editors_pick": True,
        "editors_note": (
            "City Center's standout salon — polished, professional, and "
            "bilingual. The color work here rivals Miami's top studios."
        ),
        "price_range": "$$$",
        "status": "active",
    },
    {
        "slug": "city-center-spa-doral",
        "name": "City Center Spa",
        "neighborhood_slug": "city-center",
        "categories": ["spa", "skincare", "massage"],
        "address": "8350 NW 52nd Terrace, Doral, FL 33166",
        "phone": "(305) 477-2200",
        "website": "",
        "description": (
            "A tranquil day spa in the heart of Doral's urban district offering "
            "facials, deep-tissue massage, and body wraps. Perfect post-round "
            "recovery for Trump National golfers and City Center residents."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "active",
    },
    {
        "slug": "lash-lab-doral",
        "name": "Lash Lab Doral",
        "neighborhood_slug": "city-center",
        "categories": ["lash-brow"],
        "address": "8400 NW 53rd St Ste 102, Doral, FL 33166",
        "phone": "(305) 599-5200",
        "website": "https://lashlabdoral.com",
        "description": (
            "Boutique lash studio specializing in classic, hybrid, and volume "
            "extensions. Walk-in brow threading also available. Popular with "
            "City Center office workers during lunch breaks."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "nail-republic-city-center",
        "name": "Nail Republic City Center",
        "neighborhood_slug": "city-center",
        "categories": ["nails"],
        "address": "8305 NW 53rd St, Doral, FL 33166",
        "phone": "(305) 477-9000",
        "website": "",
        "description": (
            "Modern nail lounge in City Center known for gel manicures, dip "
            "powder, and pedicure parties. Clean, contemporary design with "
            "same-day appointments most weekdays."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–8pm",
            "Fri": "9am–8pm",
            "Sat": "9am–7pm",
            "Sun": "10am–5pm",
        },
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "european-wax-center-doral",
        "name": "European Wax Center — Doral",
        "neighborhood_slug": "city-center",
        "categories": ["waxing"],
        "address": "8250 NW 52nd Terrace, Doral, FL 33166",
        "phone": "(305) 592-9292",
        "website": "https://waxcenter.com",
        "description": (
            "Franchise location delivering consistent full-body waxing in "
            "clean, private wax suites. Loyalty rewards program, online "
            "booking, and a no-wait policy keep regulars coming back."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "simply-beautiful-salon-doral",
        "name": "Simply Beautiful Salon",
        "neighborhood_slug": "city-center",
        "categories": ["hair", "makeup"],
        "address": "8100 NW 53rd St Ste 116, Doral, FL 33166",
        "phone": "(305) 463-0900",
        "website": "",
        "description": (
            "Family-run salon with a warm Latin energy offering haircuts, "
            "blowouts, bridal makeup, and quinceañera styling. Their "
            "signature flat-iron blowout is a City Center staple."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "skin-studio-doral",
        "name": "Skin Studio Doral",
        "neighborhood_slug": "city-center",
        "categories": ["skincare", "spa"],
        "address": "8401 NW 53rd St, Doral, FL 33166",
        "phone": "(305) 599-1800",
        "website": "",
        "description": (
            "Medical-adjacent esthetics studio offering chemical peels, "
            "microdermabrasion, and anti-aging facials. Popular with "
            "Doral's professional crowd for lunchtime treatments."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$$",
        "status": "active",
    },
    {
        "slug": "brow-bar-doral-city-center",
        "name": "Brow Bar Doral",
        "neighborhood_slug": "city-center",
        "categories": ["lash-brow"],
        "address": "8300 NW 53rd St, Doral, FL 33166",
        "phone": "(305) 477-3300",
        "website": "",
        "description": (
            "Walk-in threading and waxing studio inside City Center. "
            "Quick brow and lip services with no appointment needed. "
            "Flat pricing and short wait times make this a commuter favorite."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    # ── Doral Boulevard ────────────────────────────────────────────────────────
    {
        "slug": "glamour-hair-studio-doral",
        "name": "Glamour Hair Studio",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["hair"],
        "address": "3750 NW 87th Ave Ste 201, Doral, FL 33178",
        "phone": "(305) 718-5800",
        "website": "https://glamourhairstudiodoral.com",
        "description": (
            "Venezuelan-owned hair studio renowned for keratin treatments, "
            "balayage, and the ultra-smooth Coppola blowout. A go-to for the "
            "Latin community up and down Doral Blvd."
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
        "is_editors_pick": True,
        "editors_note": (
            "The best keratin and blowout specialists on Doral Blvd — "
            "Venezuelan expertise, welcoming atmosphere, and a loyal "
            "regular clientele that has followed the owner for years."
        ),
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "caracas-style-studio",
        "name": "Caracas Style Studio",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["hair", "makeup"],
        "address": "3401 NW 82nd Ave Ste 108, Doral, FL 33122",
        "phone": "(305) 470-4400",
        "website": "",
        "description": (
            "Caracas-born stylist brings Old World Venezuelan glam to Doral — "
            "meche highlights, scalp treatments, and theatrical bridal "
            "makeup. A trusted name in the Venezuelan expat community."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "vip-nails-doral",
        "name": "VIP Nails Doral",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["nails"],
        "address": "3635 NW 82nd Ave, Doral, FL 33166",
        "phone": "(305) 477-1100",
        "website": "",
        "description": (
            "Busy nail salon in a Doral Blvd strip mall delivering fast, "
            "quality gel manicures and acrylics at very competitive prices. "
            "Walk-ins always welcome; wait times usually under 15 minutes."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "massage-envy-doral",
        "name": "Massage Envy — Doral",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["massage", "skincare"],
        "address": "3601 NW 82nd Ave, Doral, FL 33122",
        "phone": "(305) 592-3689",
        "website": "https://massageenvy.com",
        "description": (
            "Membership-based massage and skincare studio offering Swedish, "
            "deep tissue, and trigger point therapy alongside chemical peels "
            "and microderm infusion facials."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "salon-one-doral",
        "name": "Salon One Doral",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["hair", "nails"],
        "address": "3400 NW 87th Ave, Doral, FL 33178",
        "phone": "(305) 468-5500",
        "website": "",
        "description": (
            "Full-service salon combining precision cuts, color, and a nail "
            "bar under one roof. Bilingual staff and flexible hours make "
            "Salon One a practical neighborhood anchor on Doral Blvd."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "dominiques-hair-studio-doral",
        "name": "Dominique's Hair Studio",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["hair"],
        "address": "3200 NW 87th Ave, Doral, FL 33178",
        "phone": "(305) 463-7700",
        "website": "",
        "description": (
            "Boutique hair studio with a devoted local following for curly "
            "hair expertise, color corrections, and silk press treatments. "
            "By appointment, with same-week openings most weeks."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "lashes-by-lucia-doral",
        "name": "Lashes by Lucía",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["lash-brow"],
        "address": "3500 NW 82nd Ave Ste 210, Doral, FL 33122",
        "phone": "(305) 599-6600",
        "website": "",
        "description": (
            "Colombiana lash artist known for mega-volume sets and precise "
            "lash lifts. Word-of-mouth clientele — book a week in advance. "
            "Brow lamination and tinting also available."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    {
        "slug": "pretty-nails-doral-blvd",
        "name": "Pretty Nails Doral",
        "neighborhood_slug": "doral-boulevard",
        "categories": ["nails", "waxing"],
        "address": "3750 NW 82nd Ave, Doral, FL 33166",
        "phone": "(305) 477-0055",
        "website": "",
        "description": (
            "Neighborhood nail salon with a loyal base of Doral regulars. "
            "Acrylic and gel services, plus quick waxing. Known for clean "
            "stations and a chatty, welcoming atmosphere."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    # ── NW 87th Avenue Corridor ────────────────────────────────────────────────
    {
        "slug": "perfect-nails-spa-doral",
        "name": "Perfect Nails Spa",
        "neighborhood_slug": "nw-87th-avenue",
        "categories": ["nails", "spa"],
        "address": "8700 NW 36th St, Doral, FL 33166",
        "phone": "(305) 594-8800",
        "website": "",
        "description": (
            "Strip-mall nail spa with a long-standing reputation for "
            "quality acrylics, pedicures, and massage chairs. "
            "Efficient, friendly service with competitive pricing."
        ),
        "hours": {
            "Mon": "9am–7pm",
            "Tue": "9am–7pm",
            "Wed": "9am–7pm",
            "Thu": "9am–7pm",
            "Fri": "9am–7:30pm",
            "Sat": "9am–6pm",
            "Sun": "10am–4pm",
        },
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "vip-hair-studio-doral",
        "name": "VIP Hair Studio",
        "neighborhood_slug": "nw-87th-avenue",
        "categories": ["hair"],
        "address": "8750 NW 36th St Ste 101, Doral, FL 33166",
        "phone": "(305) 592-6700",
        "website": "",
        "description": (
            "No-frills hair studio specializing in Dominican blowouts, "
            "relaxers, and quick color touch-ups. Among the most "
            "affordable hair services in Doral — cash and card accepted."
        ),
        "hours": {
            "Mon": "8:30am–7pm",
            "Tue": "8:30am–7pm",
            "Wed": "8:30am–7pm",
            "Thu": "8:30am–7pm",
            "Fri": "8:30am–7pm",
            "Sat": "8am–5pm",
            "Sun": "Closed",
        },
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "threading-studio-doral",
        "name": "Threading Studio Doral",
        "neighborhood_slug": "nw-87th-avenue",
        "categories": ["lash-brow"],
        "address": "8660 NW 36th St, Doral, FL 33166",
        "phone": "(305) 477-5500",
        "website": "",
        "description": (
            "Walk-in threading studio next to a major supermarket — quick "
            "eyebrow, lip, and chin threading. Among the fastest and "
            "most precise threading in the area. $10 brows."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "bliss-hair-salon-doral",
        "name": "Bliss Hair Salon",
        "neighborhood_slug": "nw-87th-avenue",
        "categories": ["hair", "makeup"],
        "address": "8900 NW 36th St Ste 109, Doral, FL 33178",
        "phone": "(305) 718-4400",
        "website": "",
        "description": (
            "Cozy two-chair salon run by a Colombian stylist specializing "
            "in highlights, cuts, and bridal hair. Intimate booking means "
            "unhurried appointments and personalized attention."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
    # ── West Doral ─────────────────────────────────────────────────────────────
    {
        "slug": "west-doral-nails-spa",
        "name": "West Doral Nails & Spa",
        "neighborhood_slug": "west-doral",
        "categories": ["nails", "spa"],
        "address": "9340 NW 41st St, Doral, FL 33178",
        "phone": "(305) 513-3000",
        "website": "",
        "description": (
            "Convenient neighborhood nail and spa destination in West Doral's "
            "residential strip. Gel manis, acrylics, and spa pedicures "
            "with a calm atmosphere and flexible weekend hours."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "sunsets-hair-studio-west-doral",
        "name": "Sunsets Hair Studio",
        "neighborhood_slug": "west-doral",
        "categories": ["hair"],
        "address": "10001 NW 41st St Ste 115, Doral, FL 33178",
        "phone": "(305) 436-5000",
        "website": "",
        "description": (
            "Friendly neighborhood salon in West Doral catering to "
            "families and long-time locals. Cuts, color, and children's "
            "haircuts all on the menu. Walk-ins welcome on weekdays."
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
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$",
        "status": "active",
    },
    {
        "slug": "glow-up-lash-studio-west-doral",
        "name": "Glow Up Lash Studio",
        "neighborhood_slug": "west-doral",
        "categories": ["lash-brow"],
        "address": "9800 NW 41st St, Doral, FL 33178",
        "phone": "(305) 436-1800",
        "website": "",
        "description": (
            "Home-based lash studio in West Doral offering classic and "
            "hybrid extensions by a certified technician. Private setting, "
            "flexible scheduling, and competitive rates."
        ),
        "hours": {
            "Mon": "Closed",
            "Tue": "10am–5pm",
            "Wed": "10am–5pm",
            "Thu": "10am–5pm",
            "Fri": "10am–5pm",
            "Sat": "9am–3pm",
            "Sun": "Closed",
        },
        "is_editors_pick": False,
        "editors_note": "",
        "price_range": "$$",
        "status": "active",
    },
]


async def seed_doral() -> None:
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
        "domain_override": DOMAIN_OVERRIDE,
        "status": "active",
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
            "neighborhood_slug": nb_slug,
            "categories": canonical_cats,
            "address": biz.get("address", ""),
            "phone": biz.get("phone", ""),
            "website": biz.get("website", ""),
            "description": biz.get("description", ""),
            "hours": biz.get("hours", {}),
            "is_editors_pick": biz.get("is_editors_pick", False),
            "editors_note": biz.get("editors_note", ""),
            "price_range": biz.get("price_range", "$$"),
            "status": biz.get("status", "active"),
            "updated_at": now,
        }

        existing = await db.businesses.find_one({"city_id": city_id, "slug": slug})
        if existing:
            if existing.get("status") == "archived":
                continue
            # Preserve claim/billing fields set by owners
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
        f"Doral seed complete:\n"
        f"  City:          {CITY_SLUG} (id={city_id})\n"
        f"  Network:       {BEAUTY_NETWORK_SLUG} (id={network_id})\n"
        f"  Neighborhoods: {len(NEIGHBORHOODS)}\n"
        f"  Categories:    {len(category_map)}\n"
        f"  Businesses:    {inserted + updated} total ({inserted} new, {updated} updated)"
    )


async def main() -> None:
    assert_seed_target_allowed()
    await ensure_indexes()
    await seed_doral()


if __name__ == "__main__":
    run(main())
