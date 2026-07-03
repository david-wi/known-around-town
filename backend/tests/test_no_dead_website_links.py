"""Guard against re-adding seeded listing data known to be stale.

A "Visit website" button that lands on a dead domain makes a real listing look
abandoned and hurts trust in the directory. On 2026-07-02 these six business
websites returned NXDOMAIN from two independent DNS resolvers (the domain no
longer exists), so their links were removed. This test stops any of those dead
domains from silently creeping back into the seed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

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


def _normalized_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            parts.query,
            "",
        )
    )


NORMALIZED_STALE_LOCATION_URLS = {_normalized_url(url) for url in STALE_LOCATION_URLS}

# Source slugs found stale against production search on 2026-07-03. If either old
# slug returns, a future reseed can insert a duplicate instead of updating the
# existing live record because the city seed scripts upsert by city_id + slug.
CANONICAL_SOURCE_SLUGS = {
    "seed_plantation.py": {
        "old": "bella-donna-hair-salon-sunrise-blvd",
        "new": "bella-donna-hair-salon",
    },
    "seed_weston.py": {
        "old": "patrick-taleb-salon-spa-weston",
        "new": "patrick-taleb-salon-spa",
    },
}


def _seed_businesses():
    data = json.loads((_BACKEND / "seed" / "_real_businesses.json").read_text())
    for network_slug, businesses in data.items():
        for business in businesses:
            yield network_slug, business


def _businesses_from_seed_file(path: Path):
    tree = ast.parse(path.read_text())
    for node in tree.body:
        value_node = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "BUSINESSES"
            for target in node.targets
        ):
            value_node = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "BUSINESSES"
        ):
            value_node = node.value
        if value_node is not None:
            return ast.literal_eval(value_node)
    return []


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
        if b.get("website") and _normalized_url(b["website"]) in NORMALIZED_STALE_LOCATION_URLS
    }
    assert not offenders, f"these listings link to known-stale location URLs: {offenders}"


def test_no_seed_files_contain_stale_location_urls():
    seed_dir = _BACKEND / "seed"
    offenders = {}
    for path in seed_dir.glob("seed_*.py"):
        text = path.read_text()
        for stale_url in STALE_LOCATION_URLS:
            if stale_url in text or _normalized_url(stale_url) in text:
                key = f"{path.relative_to(seed_dir)}::{stale_url}"
                offenders[key] = stale_url
    assert not offenders, f"these seed files contain known-stale location URLs: {offenders}"


def test_seed_source_slugs_match_checked_live_canonical_pages():
    # @define-test KAT-013
    seed_dir = _BACKEND / "seed"
    offenders = {}
    for filename, expected in CANONICAL_SOURCE_SLUGS.items():
        slugs = {b.get("slug") for b in _businesses_from_seed_file(seed_dir / filename)}
        if expected["old"] in slugs or expected["new"] not in slugs:
            offenders[filename] = {
                "old_slug_present": expected["old"] in slugs,
                "canonical_slug_present": expected["new"] in slugs,
            }
    assert not offenders, f"seed files contain source/live slug drift: {offenders}"
