# Epic: Public Directory — browsing, business pages, SEO

### KAT-010 — Neighborhood browsing · V1 · implemented
**Persona:** Salon Seeker.
The home page shows a grid of Miami neighborhoods. Each tile links to a
neighborhood landing page listing businesses in that area.
**Acceptance:** Given a visitor at `/`, when the page loads, then neighborhood
tiles are shown; clicking one leads to `/<neighborhood-slug>/` with filtered listings.

### KAT-011 — Category browsing · V1 · implemented
**Persona:** Salon Seeker.
Each service category (Hair, Nails, Waxing, etc.) has its own landing page at
`/<category-slug>/` listing matching businesses.
**Acceptance:** Given a visitor at `/hair-salons/`, when the page loads, then only
businesses in the "Hair Salons" category are shown.

### KAT-012 — Neighborhood × category filtering · V1 · implemented
**Persona:** Salon Seeker.
Visitors can filter by both neighborhood AND category simultaneously at
`/<neighborhood>/<category>/`.
**Acceptance:** Given a visitor at `/brickell/nail-salons/`, when the page loads,
then only businesses in Brickell AND in the Nail Salons category are shown.

### KAT-013 — Business detail pages · V1 · implemented
**Persona:** Salon Seeker.
Each business has a detail page at `/<slug>/` with name, description, photo gallery,
hours, neighborhood, categories, contact links, and inquiry form.
**Acceptance:** Given a visitor at `/<slug>/`, when the page loads, then all
business fields are displayed and the inquiry form is functional.

### KAT-014 — JSON-LD structured data · V1 · implemented
**Persona:** Google (search indexer).
Each business detail page includes JSON-LD structured data with `LocalBusiness`
and `BreadcrumbList` schemas for rich search results.
**Acceptance:** Given a business detail page, when the HTML source is inspected,
then a `<script type="application/ld+json">` block is present with valid
`@type: LocalBusiness` and breadcrumb data.

### KAT-015 — Photo gallery (GridFS) · V1 · implemented
**Persona:** Salon Seeker, Salon Owner.
Business pages show owner-uploaded photos stored in MongoDB GridFS
(`business_photos` bucket). The first photo is used as the hero/og:image.
**Acceptance:** Given a business with uploaded photos, when the detail page loads,
then the photos appear in the gallery and the first photo is the hero image.

### KAT-016 — Inquiry form · V1 · implemented
**Persona:** Salon Seeker.
Visitors can contact a salon via an inquiry form on the business detail page.
The submission is stored as a `business_inquiry` document and an email notification
is sent to the owner and admin.
**Acceptance:** Given a visitor who submits the inquiry form, when the form is
submitted, then a confirmation message is shown, the inquiry appears in the admin
view, and the owner receives an email notification.

### KAT-017 — Editorial guides · V1 · implemented
**Persona:** Salon Seeker.
Curated "Best of Miami" guide pages at `/guides/<slug>/` feature a selection of
salons with editorial commentary. Business detail pages show backlinks when featured.
**Acceptance:** Given an editorial guide with featured businesses, when a visitor
views the guide, then featured businesses are listed with descriptions; when a
visitor views a featured business page, then a "Featured in: [guide name]" link appears.

### KAT-018 — XML sitemap · V1 · implemented
**Persona:** Google (search indexer).
A machine-readable sitemap at `/sitemap.xml` lists all published business pages,
neighborhood pages, and category pages with their canonical URLs.
**Acceptance:** Given a request to `/sitemap.xml`, when the response is received,
then it returns valid XML with `<loc>` entries for all live businesses and landing pages.

### KAT-019 — Canonical URLs and GA4 analytics · V1 · implemented
**Persona:** David (operator).
All pages use canonical `<link rel="canonical">` tags pointing to
`https://miami.knowsbeauty.com/...`. Google Analytics 4 is injected via
`GA_MEASUREMENT_ID` env var.
**Acceptance:** Given a business detail page, when the HTML source is inspected,
then a canonical URL tag is present and the GA4 snippet is included when
`GA_MEASUREMENT_ID` is set.
