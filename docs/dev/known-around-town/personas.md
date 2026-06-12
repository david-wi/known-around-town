# Miami Knows Beauty — Personas

## 1. David (Operator / Admin)

**Who**: David Bodnick, the product owner who runs Miami Knows Beauty.

**Goals**:
- Fill the 25 Founding Partner slots and collect subscription revenue
- Get Miami salon owners to claim and subscribe to their listings
- Build a directory that ranks well on Google for Miami beauty search terms
- Expand the platform to other cities and verticals ("Knows Wellness", "Knows Health", etc.)

**How David uses the product**:
- Seeds the database with salon data via `seed/seed_miami.py`
- Sends outreach emails to salon owners
- Reviews ownership claims via `/admin/claims`
- Monitors subscription conversions and inquiry volume via `/admin/analytics`
- Configures the site via environment variables (no code deploy needed for most changes)
- Uses Stripe dashboard to manage the subscription product and billing

**David's access**: Full access — `ADMIN_API_KEY` grants write access to all management API endpoints.

---

## 2. Salon Owner (Claimant / Subscriber)

**Who**: The owner or manager of a Miami beauty salon listed in the directory.

**Goals**:
- Get found by new clients searching for salons
- Show off their salon (photos, description, hours, services)
- Earn the "Founding Partner" badge for credibility
- Stay informed about inquiries from potential clients

**Owner journey**:
1. Receives outreach email from David → clicks claim link
2. Visits their business page → clicks "Claim This Listing"
3. Fills out claim form (name, email, phone, message) → David reviews in admin
4. Receives approval email → logs into owner portal (magic code to email)
5. Uploads photos, edits profile, adds hours/description
6. Subscribes to Founding Partner plan ($29/month) via Stripe Checkout
7. Permanent badge appears on their listing immediately after payment

**Owner touchpoints**:
- `/owners/login` — magic-code email login (no password)
- `/owners/me` — dashboard with listing preview, photo management, subscription status, inquiry notifications
- Session cookie: `kb_owner_session` (30-day, HttpOnly, Secure)

---

## 3. Salon Seeker (Public Visitor)

**Who**: A Miami resident looking for a salon for hair, nails, spa, etc.

**Goals**:
- Find a salon near their neighborhood
- Compare options by category (hair, nails, waxing, etc.)
- Read editorial picks from the Knows Beauty editors
- Contact a salon or get directions

**Visitor journey**:
1. Arrives via Google search or direct link
2. Browses neighborhood or category landing pages
3. Clicks into a business detail page
4. Uses the contact/inquiry form or clicks the salon's external links
5. Reads editorial guides for curated recommendations

**Currently**: Visitors cannot access the site during preview mode. Access requires an approved email.

---

## 4. Posey (AI Product Manager)

**Who**: An AI agent assistant managing Miami Knows Beauty's product development.

**Goals**:
- Keep the site healthy and shipping
- Monitor for David's instructions and execute them autonomously
- Track pending items (Stripe webhook setup, domain purchases, etc.)
- Proactively surface product issues and opportunities

**Posey's channels**:
- Slack: `#agent-posey-knows-beauty` (expertlyhq workspace, channel ID `C0B4Y1KELQJ`)
- Uses Dorian's Slack bot token (`DORIAN_EXPERTLYHQ_SLACK_TOKEN`)
- All Slack messages prefixed `[agent:posey]`
