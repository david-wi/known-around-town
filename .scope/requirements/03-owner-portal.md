# Epic: Owner Portal — magic-code login, dashboard, profile, photos

### KAT-030 — Magic-code email login · V1 · implemented
**Persona:** Salon Owner.
Salon owners log in at `/owners/login` by entering their email. A 15-minute
OTP code is sent via Resend. After entering the code, a 30-day `kb_owner_session`
cookie (HttpOnly, Secure) is set. No password is required.
**Acceptance:** Given a claimed salon owner's email, when the owner completes the
code flow, then a `kb_owner_session` cookie is set and the owner is redirected to
`/owners/me`; given an expired code (16+ minutes), then the code is rejected.

### KAT-031 — Owner dashboard · V1 · implemented
**Persona:** Salon Owner.
The owner dashboard at `/owners/me` shows: listing preview, Featured
subscription status, owner profile tools, AI marketing tools, inquiries, and photo management. It is the
primary interface for owners after login.
**Acceptance:** Given a logged-in owner, when `/owners/me` is requested, then the
page shows their business name, photo count, subscription status, and recent inquiry count.

### KAT-032 — Profile editing · V1 · implemented
**Persona:** Salon Owner.
Owners can update their business's name, description, hours, website URL, and social
media links directly from the owner dashboard without admin involvement.
**Acceptance:** Given a logged-in owner, when they submit a profile edit, then
the updated fields appear on their public business detail page within seconds.

### KAT-033 — Photo upload and management · V1 · implemented
**Persona:** Salon Owner.
Owners can upload photos (stored in MongoDB GridFS `business_photos` bucket) and
delete existing ones from the dashboard. The first photo becomes the hero/og:image.
When the hero photo is deleted, the next photo is automatically promoted.
**Acceptance:** Given a logged-in owner, when they upload a photo, then it appears
on their public listing; when they delete the hero photo, then the next photo becomes
the hero automatically.

### KAT-034 — Claim listing · V1 · implemented
**Persona:** Salon Owner.
Any visitor can submit an ownership claim via the "Claim This Listing" button on
a business detail page. The submission creates a `business_claim` document with
name, email, phone, and message. David reviews and approves claims in the admin panel.
**Acceptance:** Given an unclaimed business, when a visitor submits a claim form,
then a `business_claim` document is created, David sees it in `/admin/claims`, and
the visitor sees a confirmation message; given an owner lands directly on the claim
form, then the Featured benefit strip explains the $29/month flat price and that
Featured takes no booking commission; given an active first-send outreach target,
then its business detail page links to a slugged owner claim entry and that owner
entry pre-fills the correct business while preserving the claim form and Featured
value copy; given an outreach link includes a bounded source/ref/UTM marker, then
the claim submission stores those markers on the `business_claim` document so David
can tell which approved send produced the claim; given a tracked outreach link lands
on the public business detail page first, then both "Claim this listing" links carry
the same bounded source/ref/UTM markers into the slugged owner claim entry.

### KAT-035 — Inquiry notifications and stats · V1 · implemented
**Persona:** Salon Owner.
Owners see a count of contact form submissions on their dashboard and receive email
notifications when new inquiries arrive.
**Acceptance:** Given an owner with 3 past inquiries, when they view `/owners/me`,
then "3 inquiries" is displayed; given a new inquiry submitted today, then the owner
receives an email notification.

### KAT-036 — /owners/claim redirect · V1 · implemented
**Persona:** Salon Owner (arriving from a marketing link).
Any request to `/owners/claim` is permanently redirected (HTTP 301) to
`/owners#claim-form`. This ensures marketing emails, social posts, or ads that
link to `/owners/claim` always land the owner on the correct page instead of
returning a 404.
**Acceptance:** Given a GET request to `/owners/claim`, when the response is
received, then the client is redirected to `/owners#claim-form` with status 301.

### KAT-037 — "As Featured on Miami Knows Beauty" website badge · V1 · implemented
**Persona:** Salon Owner (Featured tier).
Featured salon owners can add an embeddable "As Featured on Miami Knows Beauty"
badge to their own website. The badge image is served at `/badge/featured.svg`
and is exempt from the preview gate so it renders on the salon's external site
even while the directory is private. The owner dashboard (gated to Featured
owners) shows a "Add the badge to your website" section with a live preview and
a copy-paste `<a><img></a>` embed snippet whose link points to the salon's own
listing (`{origin}/b/{slug}`) — driving the salon's site visitors to its
directory page and earning a backlink. A secondary "Share your feature"
affordance offers a ready-to-post Instagram caption plus the listing link. Both
the embed code and the caption have a one-click copy button. This is the
highest-leverage shopper-acquisition artifact: one build, every Featured salon,
referral traffic + SEO backlink.
**Acceptance:** Given a request to `/badge/featured.svg`, when the response is
received (with NO preview token, while preview mode is on), then an
`image/svg+xml` badge is returned with status 200; given a logged-in Featured
owner, when `/owners/me` is requested, then the page shows the embed code
containing the salon's absolute listing URL and a copy button; given a logged-in
free-tier owner, then the badge embed section is NOT shown.

### KAT-038 — Shopper-action tracking (taps to call / directions / website) · V1 · implemented
**Persona:** Salon Owner.
Beyond page views, the directory tracks the three highest-intent shopper actions
on each listing — tap-to-call, tap-for-directions, and website click — so owners
have concrete proof their listing is driving real interest. Each action is counted
on the business document (`call_click_count`, `directions_click_count`,
`website_click_count`) the same way page views are: incremented in a background
task, with crawler/bot traffic filtered out so counts reflect real people. Tracking
is done server-side via lightweight redirect routes (`GET /b/{slug}/go/call`,
`/go/directions`, `/go/website`) that the listing's phone, directions, and website
buttons point at; each route increments the matching counter then 302-redirects to
the real `tel:` / Google Maps / website target, so tracking works even without
JavaScript and a redirect can't be missed. The three counts are returned by
`GET /api/v1/owner/stats` and shown on the owner dashboard alongside page views and
messages, with the same encouraging zero-state framing.
**Acceptance:** Given a real visitor (non-bot User-Agent) requesting
`/b/{slug}/go/call` for a salon with a phone, when the request is handled, then the
response is a 302 redirect to that salon's `tel:` number and `call_click_count` is
incremented by 1; given a bot User-Agent, then the redirect still happens but the
counter is NOT incremented; given `/go/website` for a salon with no website, then a
404 is returned; given a logged-in owner viewing `/owners/me`, then taps-to-call,
taps-for-directions, and website-clicks are displayed alongside page views and
messages.

### KAT-039 — Miami-Knows-Beauty-referred view tracking · V1 · implemented
**Persona:** Salon Owner.
A salon's free Google Business Profile already tells them how people found them,
so our "who found you" numbers are only worth keeping if they prove a distinction
Google can't: that *Miami Knows Beauty itself* sent the visitor — from one of our
editorial guides, our on-site search, a category or neighborhood page, or a sister
listing — not just that traffic happened. The directory captures this at the moment
a shopper lands on a listing (it can never be reconstructed later): when the page
they clicked through from is on our own site (a same-host `Referer`), the visit is
counted in a separate `mkb_referred_view_count` on the business document, in the same
bot-filtered background task as the total page-view counter, with no added latency. A
visit with no referrer (typed URL / bookmark) or an external referrer (Google, social,
the salon's own website) increments only the total, never the referred counter — so
the referred number can never over-claim credit. The "As Featured on Miami Knows
Beauty" badge on a salon's own site refers from the salon's domain, so its clicks land
in the total, not the referred number (a deliberate, documented under-count). The count
is returned by `GET /api/v1/owner/stats`, shown on the owner dashboard as an "N of these
came from Miami Knows Beauty" line under page views (hidden at zero so it never reads as
a failure), and carried into the dormant monthly report so the eventual email can say
"Miami Knows Beauty sent you N of your M visitors this month." The monthly email stays
dormant — no live send is enabled by this requirement.
**Acceptance:** Given a real visitor (non-bot User-Agent) requesting a listing with a
`Referer` whose host matches the site's own host, when the request is handled, then both
`page_view_count` and `mkb_referred_view_count` are incremented by 1; given the same
request with an external `Referer` (e.g. google.com) or no `Referer`, then only
`page_view_count` is incremented and `mkb_referred_view_count` is unchanged; given a bot
User-Agent, then neither counter moves; given a logged-in owner viewing `/owners/me`
whose listing has at least one referred view, then a line stating how many of their
views came from Miami Knows Beauty is shown under page views; given the monthly report is
computed for a business, then it carries this month's referred-view count without
enabling any email send.

### KAT-040 — Public owner walkthrough PDF · V1 · implemented
**Persona:** Salon Owner (reviewing the offer before claiming).
The shareable owner journey is available both as the public `/walkthrough` page
and as a public-safe PDF at `/assets/walkthrough/mkb-owner-journey.pdf`. The PDF
contains only marketing/product overview copy already safe for prospective salon
owners: claim free, sign in, dashboard, Featured upgrade, and AI caption/ad-copy
tools. Internal review PDFs and PM notes must never live under `/assets/`.
**Acceptance:** Given a request to `/assets/walkthrough/mkb-owner-journey.pdf`,
when the response is received, then it returns a PDF with status 200; given the
public static asset tree is inspected, then internal review PDFs such as
`mkb-walkthrough-david-review.pdf` are absent.
