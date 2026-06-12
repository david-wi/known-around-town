# Epic: Roadmap — upcoming features in planning or blocked states

### KAT-060 — Public launch toggle · V1 · ready_to_build
**Persona:** David (operator).
Disable the preview gate when the site is ready for the general public. Requires
setting `PREVIEW_MODE_ENABLED=false` in production `.env` and restarting the
container. No code deploy needed — the toggle is already implemented.
**Acceptance:** Given the env var change and container restart, then any visitor
can access the public directory without email authentication.
**Blocked on:** Stripe webhook operational + David's launch go/no-go decision.

### KAT-061 — "Knows" vertical domain portfolio · V2 · ready_to_build
**Persona:** David (operator).
Purchase 9 planned "Knows" vertical domains (e.g., knowshealth.com, knowsfitness.com)
via Dynadot API for 2 years with auto-renewal, then point each to the production
server as new networks are activated.
**Acceptance:** Given Dynadot account funded, when the purchase script runs, then
all 9 domains are registered for 2 years with auto-renewal and Dynadot DNS configured.
**Blocked on:** David must add payment method to Dynadot account (current balance: $0).

### KAT-062 — Google Search Console verification · V1 · ready_to_build
**Persona:** David (operator).
Verify `miami.knowsbeauty.com` in Google Search Console using the meta tag already
present in all page `<head>` elements (`GOOGLE_SITE_VERIFICATION` env var).
**Acceptance:** Given the verification meta tag in production HTML, when David
completes verification at search.google.com, then GSC shows the property as verified.
**Blocked on:** David must complete the verification step in GSC.

### KAT-063 — Resend domain verification (knowsbeauty.com) · V1 · ready_to_build
**Persona:** David (operator).
Add SPF, DKIM, and MX DNS records for `knowsbeauty.com` via Dynadot API so email
can be sent from `david@knowsbeauty.com` using Resend.
**Acceptance:** Given the DNS records added, when Resend verifies the domain, then
emails sent from `david@knowsbeauty.com` pass SPF/DKIM and are not marked as spam.
**Blocked on:** Dynadot DNS access (dependent on KAT-061 account funding).

### KAT-064 — Voice profile builder · V2 · draft
**Persona:** Salon Owner.
The highest-value on-ramp for owners: record a 3-minute voice conversation answering
profile prompts, get AI-written magazine-style copy they approve. Uses Deepgram for
transcription and Expertly's centralized LLM for rewriting. Depends on claim-and-pay
being established (KAT-040 through KAT-044).
**Acceptance:** Given a logged-in owner, when they record a 3-minute voice answer
to profile prompts, then they receive publishable profile copy within 5 minutes that
they can review, edit, and publish with one click.

### KAT-065 — Owner outreach email campaign · V1 · ready_to_build
**Persona:** David (operator).
Send personalised outreach emails to unclaimed Miami salon owners with a direct link
to claim their listing. Drafts are prepared at
`/home/david/Spaces/posey/work/owner-outreach-email-draft.md`.
**Acceptance:** Given the outreach campaign launched, when an owner clicks the link
in the email, then they are taken directly to their business claim page with their
name pre-filled.
**Code status:** The server-side pre-fill is fully implemented. The `/owners?slug=<biz-slug>`
route resolves the business record and passes `claim_prefill = {id, name, slug}` to the
template, which shows a "Claiming: [Name]" banner and locks the name input as read-only.
The email draft (updated 2026-06-11) now uses `miami.knowsbeauty.com/owners?slug=[slug]`
as the primary CTA — a direct one-click path to the pre-filled form.
**Blocked on:** (1) DNS cutover for `miami.knowsbeauty.com`; (2) David sends the outreach
emails (external communication rule applies).
