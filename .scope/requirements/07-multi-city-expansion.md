# Epic: Multi-City Expansion

### KAT-070 — Hollywood, FL city seed · V1 · implemented
**Persona:** David (operator) / Visitors in Hollywood, FL.
Add Hollywood, Florida as the seventh city on Miami Knows Beauty.
20 curated businesses across 4 neighborhoods: Downtown Hollywood (Hollywood Blvd /
Young Circle), Hollywood Broadwalk (beachside), Hollywood Hills (residential),
and Federal Highway corridor.
4 editors' picks: Studio 1847 Hair, Boulevard Nail Bar, Serenity Day Spa, Hollywood Barber Co.
Categories covered: Hair, Nails, Spa, Lash & Brow, Barber, Waxing.
**Acceptance:** Given the seed is run on production, when a visitor goes to
`hollywood.knowsbeauty.com`, then they see the Hollywood city directory with
20 businesses, 4 neighborhoods, and correct category pages.
**Code status:** seed_hollywood.py written; Traefik routing label added to
docker-compose.prod.yml; deploy.sh updated. DNS A record still needed:
`hollywood.knowsbeauty.com → 152.42.152.243`.

### KAT-071 — Coconut Grove city seed · V1 · implemented
**Persona:** David (operator) / Visitors in Coconut Grove.
Add Coconut Grove as the sixth city on Miami Knows Beauty.
18 curated businesses across 4 neighborhoods.
4 editors' picks: Grove Hair Studio, Lash & Co., Bayside Hair Co., The Grove Barber.
**Code status:** Fully live on production (PR #220 merged). 18 businesses seeded.
DNS A record still needed: `coconut-grove.knowsbeauty.com → 152.42.152.243`.

### KAT-072 — Multi-city DNS records · V1 · ready_to_build
**Persona:** David (operator).
Add DNS A records for cities that are code-complete but not yet publicly reachable.
**Acceptance:** Given A records added for all subdomain cities, when a visitor
navigates to any city subdomain, then the correct city directory loads over HTTPS.
**Blocked on:** David must add DNS A records via Dynadot:
- `coconut-grove.knowsbeauty.com → 152.42.152.243`
- `hollywood.knowsbeauty.com → 152.42.152.243`
