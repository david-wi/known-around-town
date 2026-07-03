"""Guard against re-adding website links to domains known to be dead.

A "Visit website" button that lands on a dead domain makes a real salon look
abandoned and hurts trust in the directory. On 2026-07-02 these six salon
websites returned NXDOMAIN from two independent DNS resolvers (the domain no
longer exists), so their links were removed. This test stops any of those dead
domains from silently creeping back into the seed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Domains confirmed non-resolving (NXDOMAIN) on 2026-07-02 via system resolver
# and Cloudflare DoH. If a business relaunches on the same domain, re-verify it
# resolves before removing it from this list.
DEAD_DOMAINS = {
    "pervaizsalon.com",
    "sebastienrochesalon.com",
    "letsnailbar.com",
    "soleilblowdrybar.com",
    "drbarbaragsturm.com",
    "ugodiromas.com",
}

# Exact location URLs confirmed stale on 2026-07-03. Each old URL returned
# 404/403 while an official replacement URL for the same business returned 200.
STALE_LOCATION_URLS = {
    "https://www.thedrybar.com/locations/florida/miami-beach",
    "https://www.loewshotels.com/miami-beach/spa",
    "https://www.nuestudio.co/",
    "https://www.marriott.com/en-us/hotels/miabs-the-st-regis-bal-harbour-resort/spa/",
    "https://www.thesetaihotel.com/miami-beach/spa",
}


def test_no_beauty_listing_links_to_a_dead_domain():
    beauty = json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())["beauty"]
    offenders = {
        b["slug"]: b["website"]
        for b in beauty
        if b.get("website") and any(dead in b["website"] for dead in DEAD_DOMAINS)
    }
    assert not offenders, f"these listings link to a known-dead domain: {offenders}"


def test_no_beauty_listing_links_to_stale_location_urls():
    beauty = json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())["beauty"]
    offenders = {
        b["slug"]: b["website"]
        for b in beauty
        if b.get("website") in STALE_LOCATION_URLS
    }
    assert not offenders, f"these listings link to known-stale location URLs: {offenders}"
