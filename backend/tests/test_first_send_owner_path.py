from __future__ import annotations

import asyncio
from html import escape
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app.main import app


# WHY: these are the current v3 first-send targets in Posey's outreach handoff.
# If one drifts, David's approved send packet can point owners at the wrong page.
FIRST_SEND_TARGETS = (
    (
        "Trini Salon & Spa",
        "brickell.knowsbeauty.localhost",
        "/b/trini-salon-and-spa-brickell-ave",
        "trini-salon-and-spa-brickell-ave",
    ),
    (
        "Sana Skin Studio",
        "coconut-grove.knowsbeauty.localhost",
        "/b/sana-skin-studio-coconut-grove",
        "sana-skin-studio-coconut-grove",
    ),
    (
        "Lux MedSpa Brickell",
        "brickell.knowsbeauty.localhost",
        "/b/lux-medspa-brickell",
        "lux-medspa-brickell",
    ),
    (
        "McAllister Spa",
        "south-beach.knowsbeauty.localhost",
        "/b/mcallister-spa-south-beach",
        "mcallister-spa-south-beach",
    ),
)


class _HrefCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def _hrefs_from(html: str) -> list[str]:
    parser = _HrefCollector()
    parser.feed(html)
    return parser.hrefs


@pytest.fixture
def client(seeded_db):
    from seed import seed_brickell, seed_coconut_grove, seed_south_beach

    # WHY: the production outreach packet uses city subdomain URLs, and the
    # default test seed only creates the Miami city. Seed exactly the three city
    # editions the packet depends on so the test exercises the real hosts.
    asyncio.run(seed_brickell.main())
    asyncio.run(seed_coconut_grove.main())
    asyncio.run(seed_south_beach.main())
    return TestClient(app)


def test_first_send_listing_and_owner_entry_paths_stay_claim_ready(
    client: TestClient,
):
    """First-send links must not drift away from the prefilled claim form.

    @define-test KAT-034
    """
    for name, host, listing_path, slug in FIRST_SEND_TARGETS:
        listing = client.get(listing_path, headers={"host": host})
        assert listing.status_code == 200, f"{name} listing returned {listing.status_code}"

        listing_body = listing.text
        assert escape(name) in listing_body, f"{name} missing from listing page"
        assert "Claim this listing" in listing_body, f"{name} listing missing claim CTA"
        assert f'/owners?slug={slug}#claim-form' in listing_body, (
            f"{name} listing must link to its slugged owner entry"
        )

        owner_entry = client.get(
            f"/owners?slug={slug}#claim-form", headers={"host": host}
        )
        assert owner_entry.status_code == 200, (
            f"{name} owner entry returned {owner_entry.status_code}"
        )

        owner_body = owner_entry.text
        escaped_name = escape(name)
        assert escaped_name in owner_body, f"{name} owner entry did not prefill name"
        assert f'value="{escaped_name}"' in owner_body, (
            f"{name} owner entry did not lock the business name input"
        )
        assert slug in owner_body, (
            f"{name} owner entry directory is missing its slug"
        )
        assert 'id="claim-form__form"' in owner_body, f"{name} missing claim form"
        assert 'id="claim-form__business-id"' in owner_body, (
            f"{name} missing hidden business id field"
        )
        assert "Claim your listing" in owner_body, f"{name} missing claim headline"
        assert "$29/month flat &middot; no booking commission" in owner_body, (
            f"{name} owner entry missing Featured value copy"
        )


def test_first_send_listing_claim_links_preserve_tracking(
    client: TestClient,
):
    """Tracked listing URLs must not lose attribution before the owner claim form.

    @define-test KAT-034
    """
    name, host, listing_path, slug = FIRST_SEND_TARGETS[0]
    long_source = "x" * 140
    listing = client.get(
        f"{listing_path}?claim_source={long_source}"
        "&ref=trini-direct"
        "&utm_source=david-email"
        "&utm_medium=email"
        "&utm_campaign=first-send-v3"
        "&next=https://bad.example/ignore-me",
        headers={"host": host},
    )
    assert listing.status_code == 200, f"{name} listing returned {listing.status_code}"

    claim_hrefs = [
        href
        for href in _hrefs_from(listing.text)
        if href.startswith(f"/owners?slug={slug}")
    ]
    expected_href = (
        f"/owners?slug={slug}"
        f"&claim_source={'x' * 120}"
        "&ref=trini-direct"
        "&utm_source=david-email"
        "&utm_medium=email"
        "&utm_campaign=first-send-v3"
        "#claim-form"
    )
    assert claim_hrefs == [expected_href, expected_href]
    assert long_source not in "".join(claim_hrefs)
    assert "next=" not in "".join(claim_hrefs)
