# Epic: Preview Gate — private beta access control

### KAT-020 — Preview gate middleware · V1 · implemented
**Persona:** David (operator).
When `PREVIEW_MODE_ENABLED=true`, a FastAPI middleware intercepts every request.
Unauthenticated visitors are redirected to `/preview-login`. Authenticated visitors
(valid `preview_token` cookie) pass through. Routes bypassed: `/health`,
`/api/v1/billing/webhook`, `/preview-login`, `/assets/`, `/media/`.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=true` and no session cookie, when any
page is requested, then the response is a redirect to `/preview-login`; given a
valid cookie, then the requested page is served normally.

### KAT-021 — Email + 6-digit code authentication · V1 · implemented
**Persona:** Allowed preview user.
Visitors enter their email on `/preview-login`. If the email is on the allowed list,
a 6-digit code is sent via Resend. The visitor enters the code; if correct, a
30-day `preview_token` cookie is set. Disallowed emails receive the same
"check your email" response (no information leak about the allowed list).
**Acceptance:** Given an allowed email, when the visitor completes the code flow,
then they receive a `preview_token` cookie and are redirected to the requested page;
given a non-allowed email, when the visitor submits it, then they see "check your
email" but no code is sent and no cookie is set.

### KAT-022 — Preview session storage (MongoDB) · V1 · implemented
**Persona:** David (operator).
OTP codes are stored in `preview_codes` (TTL 15 minutes). Validated sessions are
stored in `preview_sessions` (TTL 30 days). Both collections are cleaned up automatically
via MongoDB TTL indexes.
**Acceptance:** Given a 6-digit code issued 16 minutes ago, when the visitor tries
to use it, then it is rejected; given a session cookie from 31 days ago, then the
visitor is redirected to `/preview-login`.

### KAT-023 — Public launch toggle · V1 · implemented
**Persona:** David (operator).
Setting `PREVIEW_MODE_ENABLED=false` in `/opt/known-around-town/.env` and
restarting the container disables the gate entirely. No code deploy is needed.
**Acceptance:** Given `PREVIEW_MODE_ENABLED=false` in production `.env`, when the
container is restarted, then unauthenticated visitors can access all public pages
without any redirect.
