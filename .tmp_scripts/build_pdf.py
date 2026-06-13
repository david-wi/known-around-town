"""Build the MKB owner-journey walkthrough PDF."""
import base64, os

os.chdir('/home/david')

def img_b64(fname):
    path = f"/home/david/Code/known-around-town/.tmp_scripts/screenshots/{fname}.png"
    with open(path, 'rb') as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

# Build the HTML
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Miami Knows Beauty — Owner Journey</title>
<style>
  /* ── Typography & Reset ─────────────────────────────────── */
  @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=Inter:wght@300;400;500;600&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1c1917;
    background: white;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* ── Page layout ────────────────────────────────────────── */
  .page {{
    width: 210mm;
    min-height: 297mm;
    padding: 14mm 16mm 14mm 16mm;
    page-break-after: always;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}
  .page:last-child {{ page-break-after: avoid; }}

  /* ── Colour tokens ──────────────────────────────────────── */
  :root {{
    --rose:   #be123c;
    --rose-lt:#fef2f2;
    --gold:   #b45309;
    --stone:  #78716c;
    --ink:    #1c1917;
    --muted:  #a8a29e;
    --border: #e7e5e4;
    --bg:     #fafaf9;
  }}

  /* ── Header stripe (top of every page) ─────────────────── */
  .page-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12mm;
    padding-bottom: 4mm;
    border-bottom: 1px solid var(--border);
  }}
  .brand {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 15pt;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--ink);
  }}
  .brand em {{ font-style: italic; font-weight: 400; }}
  .step-pill {{
    background: var(--rose);
    color: white;
    font-size: 7.5pt;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2.5mm 5mm;
    border-radius: 20mm;
  }}

  /* ── Hero section ───────────────────────────────────────── */
  .hero {{
    text-align: center;
    margin-bottom: 10mm;
  }}
  .eyebrow {{
    font-size: 7pt;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--rose);
    margin-bottom: 3mm;
  }}
  h1 {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 28pt;
    font-weight: 500;
    line-height: 1.15;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin-bottom: 4mm;
  }}
  h1 em {{ font-style: italic; font-weight: 400; color: var(--rose); }}
  h2 {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 20pt;
    font-weight: 500;
    line-height: 1.2;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin-bottom: 3mm;
  }}
  h2 em {{ font-style: italic; font-weight: 400; color: var(--rose); }}
  h3 {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 13pt;
    font-weight: 500;
    color: var(--ink);
    margin-bottom: 2mm;
  }}
  .lead {{
    font-size: 10.5pt;
    color: var(--stone);
    line-height: 1.65;
    max-width: 160mm;
    margin: 0 auto;
  }}

  /* ── Screenshot containers ──────────────────────────────── */
  .screenshot {{
    border-radius: 4mm;
    overflow: hidden;
    box-shadow: 0 2mm 10mm rgba(0,0,0,0.12);
    border: 1px solid var(--border);
  }}
  .screenshot img {{ width: 100%; display: block; }}

  /* ── Body text, lists ───────────────────────────────────── */
  p {{
    font-size: 9.5pt;
    color: var(--stone);
    line-height: 1.6;
    margin-bottom: 3mm;
  }}
  ul {{
    margin-left: 4mm;
    margin-bottom: 3mm;
  }}
  li {{
    font-size: 9.5pt;
    color: var(--stone);
    line-height: 1.55;
    margin-bottom: 1.5mm;
    padding-left: 1mm;
  }}
  li::marker {{ color: var(--rose); }}
  strong {{ color: var(--ink); font-weight: 600; }}

  /* ── Two-column layout ──────────────────────────────────── */
  .cols {{
    display: flex;
    gap: 6mm;
    align-items: flex-start;
    flex: 1;
  }}
  .col {{ flex: 1; }}
  .col-wide {{ flex: 1.4; }}
  .col-narrow {{ flex: 0.7; }}

  /* ── Callout / info boxes ───────────────────────────────── */
  .callout {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--rose);
    border-radius: 2mm;
    padding: 4mm 5mm;
    margin-bottom: 4mm;
  }}
  .callout-gold {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-left: 3px solid var(--gold);
    border-radius: 2mm;
    padding: 4mm 5mm;
    margin-bottom: 4mm;
  }}
  .callout p {{ margin-bottom: 0; }}

  /* ── Stat blocks ────────────────────────────────────────── */
  .stats {{
    display: flex;
    gap: 4mm;
    margin: 5mm 0;
  }}
  .stat {{
    flex: 1;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 2mm;
    padding: 4mm;
    text-align: center;
  }}
  .stat-n {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 22pt;
    font-weight: 500;
    color: var(--rose);
    line-height: 1;
    display: block;
    margin-bottom: 1mm;
  }}
  .stat-label {{
    font-size: 7.5pt;
    color: var(--muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}

  /* ── Pricing tiers ──────────────────────────────────────── */
  .pricing-grid {{
    display: flex;
    gap: 4mm;
    margin: 4mm 0;
  }}
  .pricing-card {{
    flex: 1;
    border: 1px solid var(--border);
    border-radius: 3mm;
    padding: 5mm;
    background: white;
  }}
  .pricing-card.featured {{
    border-color: var(--rose);
    border-width: 2px;
    background: var(--rose-lt);
    position: relative;
  }}
  .pricing-card.featured::before {{
    content: 'MOST POPULAR';
    position: absolute;
    top: -3.5mm;
    left: 50%;
    transform: translateX(-50%);
    background: var(--rose);
    color: white;
    font-size: 6.5pt;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 1mm 3mm;
    border-radius: 10mm;
    white-space: nowrap;
  }}
  .price-label {{ font-size: 7pt; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1mm; }}
  .price-amount {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 20pt;
    font-weight: 500;
    color: var(--ink);
    line-height: 1;
  }}
  .price-mo {{ font-size: 9pt; color: var(--stone); }}
  .price-desc {{ font-size: 8pt; color: var(--stone); margin: 2mm 0 3mm; line-height: 1.4; }}
  .price-features {{ list-style: none; padding: 0; margin: 0; }}
  .price-features li {{
    font-size: 8pt;
    color: var(--stone);
    padding: 1mm 0;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    gap: 2mm;
  }}
  .price-features li .check {{ color: var(--rose); font-weight: 700; flex-shrink: 0; }}

  /* ── Step numbers (large decorative) ───────────────────── */
  .step-num {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 60pt;
    font-weight: 500;
    color: var(--rose);
    opacity: 0.12;
    line-height: 1;
    position: absolute;
    top: 8mm;
    right: 10mm;
    pointer-events: none;
  }}

  /* ── Footer strip ───────────────────────────────────────── */
  .page-footer {{
    margin-top: auto;
    padding-top: 4mm;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 7pt;
    color: var(--muted);
  }}
  .page-footer a {{ color: var(--rose); text-decoration: none; }}

  /* ── Tag / badge ────────────────────────────────────────── */
  .badge {{
    display: inline-block;
    background: var(--rose-lt);
    color: var(--rose);
    font-size: 7pt;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 1mm 3mm;
    border-radius: 10mm;
    border: 1px solid #fecdd3;
  }}
  .badge-gold {{
    background: #fffbeb;
    color: var(--gold);
    border-color: #fde68a;
  }}

  /* ── Feature list with icons ─────────────────────────────── */
  .feature-list {{ list-style: none; padding: 0; margin: 0; }}
  .feature-list li {{
    display: flex;
    align-items: flex-start;
    gap: 3mm;
    padding: 2.5mm 0;
    border-bottom: 1px solid var(--border);
    color: var(--stone);
    font-size: 9pt;
    line-height: 1.4;
  }}
  .feature-list li:last-child {{ border-bottom: none; }}
  .feature-list .icon {{ color: var(--rose); font-size: 10pt; flex-shrink: 0; margin-top: 0.5mm; }}

  /* ── Timeline steps ─────────────────────────────────────── */
  .timeline {{ position: relative; padding-left: 10mm; }}
  .timeline-item {{
    position: relative;
    margin-bottom: 5mm;
  }}
  .timeline-item::before {{
    content: '';
    position: absolute;
    left: -7.5mm;
    top: 1.5mm;
    width: 4mm;
    height: 4mm;
    border-radius: 50%;
    background: var(--rose);
    border: 1.5px solid white;
    box-shadow: 0 0 0 1.5px var(--rose);
  }}
  .timeline-item::after {{
    content: '';
    position: absolute;
    left: -6mm;
    top: 5.5mm;
    width: 1px;
    height: calc(100% + 1mm);
    background: var(--border);
  }}
  .timeline-item:last-child::after {{ display: none; }}
  .tl-step {{ font-size: 7pt; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--rose); margin-bottom: 1mm; }}
  .tl-title {{ font-size: 10pt; font-weight: 600; color: var(--ink); margin-bottom: 1mm; }}
  .tl-desc {{ font-size: 9pt; color: var(--stone); line-height: 1.45; }}

  /* ── Print rules ────────────────────────────────────────── */
  @media print {{
    .page {{ page-break-after: always; }}
    .page:last-child {{ page-break-after: avoid; }}
  }}
</style>
</head>
<body>

<!-- ══════════════════════════════════════════════════════════════
     PAGE 1 — The Directory
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Owner Guide</span>
  </div>

  <div class="hero" style="margin-bottom:6mm;">
    <div class="eyebrow">Miami's curated beauty directory</div>
    <h1>Miami's <em>best-kept</em><br>beauty addresses.</h1>
    <p class="lead">An index of the stylists, colorists, estheticians, and barbers locals actually book — neighborhood by neighborhood.</p>
  </div>

  <div class="screenshot" style="margin-bottom:6mm; max-height:65mm; overflow:hidden;">
    <img src="{img_b64('homepage')}" alt="Miami Knows Beauty homepage" style="object-fit:cover; object-position:top;">
  </div>

  <div class="stats">
    <div class="stat">
      <span class="stat-n">68+</span>
      <span class="stat-label">Salons listed</span>
    </div>
    <div class="stat">
      <span class="stat-n">12</span>
      <span class="stat-label">Neighborhoods</span>
    </div>
    <div class="stat">
      <span class="stat-n">6</span>
      <span class="stat-label">Beauty categories</span>
    </div>
    <div class="stat">
      <span class="stat-n">Free</span>
      <span class="stat-label">To start</span>
    </div>
  </div>

  <div class="callout" style="margin-top:4mm;">
    <p><strong>Every credible salon in Miami is already here.</strong> Miami Knows Beauty is an editorially-curated directory — not a paid-listing aggregator. Your salon was added based on its reputation. You don't need to pay to be listed. You do need to claim your listing to control it.</p>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com</span>
    <span>Page 1 of 6</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════════════════════
     PAGE 2 — Your Listing
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Step 1 of 4 — Your Listing</span>
  </div>

  <h2 style="margin-bottom:2mm;">Your listing is <em>already live.</em></h2>
  <p class="lead" style="margin:0 0 5mm; font-size:9.5pt;">Every salon in our directory has a basic listing. Claim yours to take control — and upgrade to Featured to stand out.</p>

  <div class="cols">
    <div class="col">
      <div class="eyebrow" style="margin-bottom:2mm;">Free listing</div>
      <div class="screenshot" style="margin-bottom:3mm; max-height:55mm; overflow:hidden;">
        <img src="{img_b64('salon_free')}" alt="Free listing example">
      </div>
      <ul>
        <li>Name, neighborhood, category, and price tier</li>
        <li>Phone number and address</li>
        <li>Found via search and category pages</li>
        <li>Basic AI-generated description</li>
        <li>No photos, no booking button</li>
      </ul>
    </div>
    <div class="col">
      <div class="eyebrow" style="margin-bottom:2mm; color:#b45309;">Featured listing <span class="badge-gold badge">$29/mo</span></div>
      <div class="screenshot" style="margin-bottom:3mm; max-height:55mm; overflow:hidden;">
        <img src="{img_b64('salon_featured')}" alt="Featured listing example">
      </div>
      <ul>
        <li><strong>Featured badge</strong> on every search result — permanent gold badge for Founding Partners</li>
        <li><strong>Up to 12 photos</strong> + hero image</li>
        <li><strong>Booking link</strong> and direct contact button</li>
        <li><strong>Priority placement</strong> in category results</li>
        <li><strong>AI marketing tools</strong> — Instagram captions + ad copy</li>
      </ul>
    </div>
  </div>

  <div class="callout-gold" style="margin-top:4mm;">
    <p>⭐ <strong>Founding Partner offer:</strong> The first 25 owners to upgrade to Featured earn a permanent gold "Founding Partner" badge on their listing — visible to every visitor, forever. First month free.</p>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com</span>
    <span>Page 2 of 6</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════════════════════
     PAGE 3 — How to Claim
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Step 2 of 4 — Claim Your Listing</span>
  </div>

  <h2 style="margin-bottom:2mm;">Claiming takes <em>two minutes.</em></h2>
  <p class="lead" style="margin:0 0 6mm; font-size:9.5pt;">Fill in the short form at miami.knowsbeauty.com/owners. We verify ownership and send you an email with your dashboard link within 24 hours.</p>

  <div class="cols">
    <div class="col-wide">
      <div class="screenshot" style="max-height:80mm; overflow:hidden;">
        <img src="{img_b64('owners_page')}" alt="Owner claim page">
      </div>
    </div>
    <div class="col">
      <div class="timeline">
        <div class="timeline-item">
          <div class="tl-step">Step 1</div>
          <div class="tl-title">Go to /owners</div>
          <div class="tl-desc">Visit miami.knowsbeauty.com/owners. Start typing your salon name — we match it automatically.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-step">Step 2</div>
          <div class="tl-title">Fill in the form</div>
          <div class="tl-desc">Your name, email, and phone. Takes about 90 seconds. No credit card needed to claim.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-step">Step 3</div>
          <div class="tl-title">We verify you</div>
          <div class="tl-desc">We confirm you're the owner within 24 hours — usually faster. You'll get an email with your dashboard link.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-step">Step 4</div>
          <div class="tl-title">You're in control</div>
          <div class="tl-desc">Log into your dashboard anytime to update info, add photos, respond to inquiries, and access AI tools.</div>
        </div>
      </div>
    </div>
  </div>

  <div class="callout" style="margin-top:5mm;">
    <p><strong>Already claimed?</strong> Sign in at miami.knowsbeauty.com/owners/login using your business email. We'll send you a one-time code — no password to remember.</p>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com/owners</span>
    <span>Page 3 of 6</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════════════════════
     PAGE 4 — Featured Plan
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Step 3 of 4 — Featured Plan</span>
  </div>

  <h2 style="margin-bottom:2mm;">Three ways to show up on <em>Miami Knows Beauty.</em></h2>
  <p class="lead" style="margin:0 0 5mm; font-size:9.5pt;">Start free. Upgrade when you're ready. Cancel anytime.</p>

  <div class="screenshot" style="margin-bottom:5mm; max-height:60mm; overflow:hidden;">
    <img src="{img_b64('pricing')}" alt="Pricing page">
  </div>

  <div class="pricing-grid">
    <div class="pricing-card">
      <div class="price-label">Free</div>
      <div class="price-amount">$0</div>
      <div class="price-desc">For every salon. The basics, on the house.</div>
      <ul class="price-features">
        <li><span class="check">✓</span>Listed on the directory</li>
        <li><span class="check">✓</span>Found via search and category pages</li>
        <li><span class="check">✓</span>Name, neighborhood, hours, phone</li>
      </ul>
    </div>
    <div class="pricing-card featured">
      <div class="price-label">Featured</div>
      <div class="price-amount">$29<span class="price-mo">/month</span></div>
      <div class="price-desc">Or $290/year — first month free, cancel anytime.</div>
      <ul class="price-features">
        <li><span class="check">✓</span>Featured badge on every search result</li>
        <li><span class="check">✓</span>Up to 12 photos + hero image</li>
        <li><span class="check">✓</span>AI Instagram captions &amp; ad copy</li>
        <li><span class="check">✓</span>Priority placement in results</li>
        <li><span class="check">✓</span>Booking link + direct contact</li>
        <li><span class="check">✓</span>Founding Partner badge (first 25)</li>
      </ul>
    </div>
    <div class="pricing-card" style="background:#1c1917; border-color:#1c1917;">
      <div class="price-label" style="color:#a8a29e;">Concierge</div>
      <div class="price-amount" style="color:white;">$299<span class="price-mo" style="color:#a8a29e;">/month</span></div>
      <div class="price-desc" style="color:#a8a29e;">Featured + AI phone receptionist. Never miss a booking.</div>
      <ul class="price-features">
        <li style="border-color:#292524; color:#a8a29e;"><span class="check">✓</span>Everything in Featured</li>
        <li style="border-color:#292524; color:#a8a29e;"><span class="check">✓</span>AI answers your phone</li>
        <li style="border-color:#292524; color:#a8a29e;"><span class="check">✓</span>Books straight to your calendar</li>
        <li style="border-color:#292524; color:#a8a29e;"><span class="check">✓</span>150 calls/month included</li>
      </ul>
    </div>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com/pricing</span>
    <span>Page 4 of 6</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════════════════════
     PAGE 5 — Owner Dashboard
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Step 4 of 4 — Your Dashboard</span>
  </div>

  <h2 style="margin-bottom:2mm;">Your dashboard and <em>AI tools.</em></h2>
  <p class="lead" style="margin:0 0 5mm; font-size:9.5pt;">After your claim is approved, log in at miami.knowsbeauty.com/owners/login. Everything you need to manage your listing and market your salon is in one place.</p>

  <div class="cols">
    <div class="col-wide">
      <div class="screenshot" style="max-height:75mm; overflow:hidden;">
        <img src="{img_b64('owner_login')}" alt="Owner sign in page">
      </div>
    </div>
    <div class="col">
      <div style="margin-bottom:4mm;">
        <div class="eyebrow" style="margin-bottom:2mm;">Manage your profile</div>
        <ul class="feature-list">
          <li><span class="icon">✎</span>Edit your salon name, description, hours, and contact details</li>
          <li><span class="icon">📷</span>Upload up to 12 photos + a hero image</li>
          <li><span class="icon">📬</span>View and respond to client inquiries</li>
          <li><span class="icon">📊</span>See how many people viewed your listing this month</li>
        </ul>
      </div>
      <div>
        <div class="eyebrow" style="margin-bottom:2mm;">AI marketing tools <span class="badge" style="margin-left:1mm;">Featured only</span></div>
        <ul class="feature-list">
          <li><span class="icon">✨</span><strong>Instagram captions</strong> — generate ready-to-post captions for your photos, customized to your salon's style and services</li>
          <li><span class="icon">✨</span><strong>Ad copy</strong> — get short-form ad headlines and body copy for Facebook and Google ads in seconds</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="callout" style="margin-top:5mm;">
    <p><strong>Passwordless sign-in:</strong> Enter your business email and we'll send you a one-time code. No password to create or remember — just click the link in the email and you're in.</p>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com/owners/login</span>
    <span>Page 5 of 6</span>
  </div>
</div>


<!-- ══════════════════════════════════════════════════════════════
     PAGE 6 — Getting Started
═══════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="page-header">
    <span class="brand">Miami <em>Knows</em> Beauty</span>
    <span class="step-pill">Get Started Today</span>
  </div>

  <!-- Large decorative number -->
  <div class="step-num">✦</div>

  <div style="text-align:center; margin-bottom:8mm;">
    <div class="eyebrow">You're one step away</div>
    <h1 style="font-size:24pt; margin-bottom:3mm;">Claim your listing<br>in <em>two minutes.</em></h1>
    <p class="lead">Visit the link below, fill in the short form, and we'll have your listing claimed and under your control within 24 hours.</p>
  </div>

  <!-- CTA box -->
  <div style="background:var(--rose); border-radius:4mm; padding:7mm 10mm; text-align:center; margin-bottom:7mm;">
    <div style="color:rgba(255,255,255,0.7); font-size:8pt; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:2mm;">Claim your listing at</div>
    <div style="color:white; font-family:Georgia,'Times New Roman',serif; font-size:20pt; font-weight:500; letter-spacing:-0.01em;">miami.knowsbeauty.com/owners</div>
  </div>

  <div class="cols">
    <div class="col">
      <h3 style="margin-bottom:3mm;">Quick summary</h3>
      <div class="timeline">
        <div class="timeline-item">
          <div class="tl-title">1. Your listing is already live</div>
          <div class="tl-desc">Every Miami salon starts in the directory for free.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-title">2. Claim it at /owners</div>
          <div class="tl-desc">Takes ~2 minutes. No credit card required.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-title">3. We verify ownership</div>
          <div class="tl-desc">Usually within 24 hours, often sooner.</div>
        </div>
        <div class="timeline-item">
          <div class="tl-title">4. Upgrade to Featured (optional)</div>
          <div class="tl-desc">$29/month. First month free. Cancel anytime.</div>
        </div>
      </div>
    </div>
    <div class="col">
      <h3 style="margin-bottom:3mm;">Questions?</h3>
      <div class="callout" style="margin-bottom:3mm;">
        <p>Email us at <strong>hello@knowsbeauty.com</strong> and we'll get back to you within one business day.</p>
      </div>
      <div class="callout-gold">
        <p>⭐ <strong>Founding Partner spots are limited.</strong> The first 25 owners to upgrade get a permanent gold badge on their listing — for as long as they're a subscriber. Early claimers get priority.</p>
      </div>
      <div style="margin-top:3mm;">
        <div class="eyebrow" style="margin-bottom:2mm;">Helpful links</div>
        <ul>
          <li><strong>Claim form:</strong> miami.knowsbeauty.com/owners</li>
          <li><strong>Owner sign-in:</strong> miami.knowsbeauty.com/owners/login</li>
          <li><strong>Pricing:</strong> miami.knowsbeauty.com/pricing</li>
          <li><strong>The directory:</strong> miami.knowsbeauty.com</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="page-footer">
    <span>miami.knowsbeauty.com</span>
    <span style="text-align:center; flex:1;">Miami Knows Beauty — Owner Journey Guide</span>
    <span>Page 6 of 6</span>
  </div>
</div>

</body>
</html>"""

# Write the HTML
html_path = "/home/david/Code/known-around-town/.tmp_scripts/mkb-owner-journey.html"
with open(html_path, 'w') as f:
    f.write(html)
print(f"HTML written: {len(html):,} chars -> {html_path}")
