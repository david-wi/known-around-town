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
The owner dashboard at `/owners/me` shows: listing preview, Founding Partner
status, subscription status, inquiry statistics, and photo management. It is the
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
the visitor sees a confirmation message.

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
