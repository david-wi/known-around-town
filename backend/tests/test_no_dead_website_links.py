"""Guard against re-adding website links to domains known to be dead.

A "Visit website" button that lands on a dead domain makes a real listing look
abandoned and hurts trust in the directory. On 2026-07-02 these six business
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
    "https://www.marriott.com/en-us/hotels/miabh-the-st-regis-bal-harbour-resort/spa/",
    "https://www.marriott.com/en-us/hotels/miabs-the-st-regis-bal-harbour-resort/spa/",
    "https://www.marriott.com/hotels/hotel-information/spa/miabr-the-st-regis-bal-harbour-resort/",
    "https://thesetaihotel.com/spa-and-wellness/spa",
    "https://www.thesetaihotel.com/miami-beach/spa",
}


def _seed_businesses():
    data = json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())
    for network_slug, businesses in data.items():
        for business in businesses:
            yield network_slug, business


def test_no_seeded_listing_links_to_a_dead_domain():
    offenders = {
        f"{network_slug}/{b['slug']}": b["website"]
        for network_slug, b in _seed_businesses()
        if b.get("website") and any(dead in b["website"] for dead in DEAD_DOMAINS)
    }
    assert not offenders, f"these listings link to a known-dead domain: {offenders}"


def test_no_seeded_listing_links_to_stale_location_urls():
    offenders = {
        f"{network_slug}/{b['slug']}": b["website"]
        for network_slug, b in _seed_businesses()
        if b.get("website") in STALE_LOCATION_URLS
    }
    assert not offenders, f"these listings link to known-stale location URLs: {offenders}"


def test_no_seed_files_contain_stale_location_urls():
    seed_dir = _BACKEND / "seed"
    offenders = {}
    for path in seed_dir.glob("seed_*.py"):
        text = path.read_text()
        for stale_url in STALE_LOCATION_URLS:
            if stale_url in text:
                key = f"{path.relative_to(seed_dir)}::{stale_url}"
                offenders[key] = stale_url
    assert not offenders, f"these seed files contain known-stale location URLs: {offenders}"
