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
business fields are displayed, website/contact links render when provided, known
dead or stale seeded website destinations covered by regression guards are absent,
seed source slugs for checked live listings continue to resolve to canonical
business detail pages, and the inquiry form is functional.

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
view, and the owner receives an email notification. The form requires at least one
contact method (email or phone) — submitting with neither is blocked with a clear
error so the salon always has a way to reply. Either field alone is sufficient.

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
All pages use canonical `<link rel="canonical">` tags pointing to the current
request host for the resolved city/network. Google Analytics 4 is injected via
`GA_MEASUREMENT_ID` env var.
**Acceptance:** Given a business detail page, when the HTML source is inspected,
then a canonical URL tag is present and the GA4 snippet is included when
`GA_MEASUREMENT_ID` is set.

### KAT-073 — Single og:image tag on home page · V1 · implemented
**Persona:** Google, social media platforms (Facebook, Slack, iMessage link previews).
The home page emits exactly one `og:image` meta tag — the city hero image — so that
social sharing previews display a single, correct image instead of a blank or doubled
card. All other page types already handled this through the base template; the home
route was the lone exception that added a second manual tag.
**Acceptance:** Given a GET request to the home page, when the HTML source is
inspected, then exactly one `<meta property="og:image">` tag is present and its
`content` attribute contains the city hero photo URL.

### KAT-074 — Sitemap guide lastmod uses actual publish date · V1 · implemented
**Persona:** Google (search indexer).
Each editorial guide entry in `/sitemap.xml` reports its actual `published_at` (or
`updated_at`) date as `<lastmod>`, not today's date. Reporting today's date on every
crawl told Google that every guide was modified daily, wasting crawl budget and weakening
the trustworthiness of our lastmod signals for guides that haven't changed.
**Acceptance:** Given a published editorial guide, when `/sitemap.xml` is fetched, then
the guide's `<lastmod>` value matches the guide's publish date, not the current date.

### KAT-076 — Public page landmark and heading structure · V1 · implemented
**Persona:** Salon Seeker, Salon Owner using assistive technology.
Public directory pages expose a clean semantic structure so screen readers and
automated accessibility tools do not encounter skipped footer headings or nested
complementary landmarks in the main content.
**Acceptance:** Given the city home page or a business detail page, when the
rendered HTML is inspected, then footer column labels do not create skipped heading
levels and page sidebars/banners inside `<main>` do not expose nested
`complementary` landmarks.

### KAT-077 — Category-context listing cards · V1 · implemented
**Persona:** Salon Seeker.
Businesses can belong to every service category they truly offer, and listing
cards on category-aware surfaces lead with the visitor's active category instead
of always falling back to the business's default category.
**Acceptance:** Given a business tagged with both Nails and Hair, when a visitor
views `/c/hair`, `/n/<neighborhood>/c/hair`, or searches for the exact Hair
category, then that business's card shows Hair as the category label and uses the
Hair-specific first sentence and category-tagged photo when those values exist.
Given the same business on `/all` or a non-category page, then the card falls
back to the business's default category, default short description, and hero/first
photo. Given seeded source data includes `category_slugs`, then the Miami seed
preserves the complete category list instead of reducing it to one category.
Direct production database edits and public photo-provenance notes are out of
scope for this requirement.

### KAT-078 — Business-name search with independent service and neighborhood filters · V1 · ready_to_build
**Risk:** medium
**Verified:** not yet
**Incidents:**
- 2026-07-13 — Whole-phrase AI selection can make a direct business-name query depend on the model understanding unrelated service or neighborhood words.
**Refs:**
**Persona:** Salon Seeker.
Business-name lookup is a primary search job: an exact or partial business name
must surface the matching live listing even when the query is not a complete
sentence. Service and neighborhood are separate constraints, so a shopper can
search for a service in a neighborhood without relying on one fragile parser.
Mixed natural-language phrases may remain a convenience path, but they must not
weaken a clear name match or allow a service/neighborhood constraint to be
ignored.

**Acceptance:**

- Given a live business in the current city and a query equal to its normalized
  name, `/search` returns that listing.
- Given a live business in the current city and a query containing a contiguous
  meaningful substring of its normalized name, `/search` returns that listing;
  generic business-type words alone are not sufficient to claim a name match.
- Given a service term and neighborhood term, results contain only live
  businesses that match both the service/category or service-menu evidence and
  the neighborhood; a service-only or neighborhood-only query remains broad.
- Given the existing search page, separate Service and Neighborhood controls
  submit independent URL parameters, preserve their selected values on the
  results page, and work with an empty business-name field.
- Given a business name plus service and/or neighborhood constraints, the name
  match is still considered first but the explicit constraints are applied to
  the final result set.
- Given a mixed phrase such as `lash near Aventura`, the system may use the
  semantic fallback, but it must preserve the current-city and live-status
  boundaries and must fail closed when the AI selector is unavailable.
- Draft, archived, and other-city businesses never appear in public search,
  including when their names exactly match the query.
- Empty and no-match queries render the existing browse or empty states without
  an exception.

**Out of scope:** Additional filter types, a new service taxonomy, service-data
backfills, location deduplication, production database writes, and changes to
featured/editor's-pick ordering beyond ranking within the matching result set.

## Verification

- `@define-test KAT-078-name-exact` — exact business-name query returns the
  live current-city listing without requiring an AI response.
- `@define-test KAT-078-name-partial` — meaningful partial name matching works
  while generic-only terms do not become name matches.
- `@define-test KAT-078-filter-composition` — service and neighborhood filters
  are independently applied, including name-plus-filter queries.
- `@define-test KAT-078-filter-controls` — the existing search form submits and
  preserves independent Service and Neighborhood selections.
- `@define-test KAT-078-visibility-boundary` — draft, archived, and other-city
  rows remain excluded.
- `@define-test KAT-078-ai-fallback` — semantic fallback uses the centralized
  gateway and returns the existing safe empty result on gateway failure.
- Manual QA: use `/search` on desktop and mobile with an exact name, a partial
  name, `nails Brickell`, and `lash near Aventura`; capture the rendered results
  and empty state after deployment.
