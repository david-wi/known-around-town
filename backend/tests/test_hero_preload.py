"""Regression test: the city home preloads its above-the-fold hero image.

The city home hero is rendered as a CSS background-image. Browsers discover a
CSS background image late (only after the stylesheet is parsed and the element
matched), so without a preload the hero photo downloads late and the hero flashes
dark for a beat before it paints — a cheap-looking first impression on a premium
directory. A <link rel="preload" as="image"> in the head starts the fetch during
HTML parse. The preload href must match the CSS url() exactly, or the browser
both warns "preloaded but not used" AND still flashes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def _assert_hero_preloaded_and_matches(body: str, where: str) -> None:
    """The page must emit a hero image preload whose href is the EXACT url the
    hero CSS background uses. Exact match matters: a mismatch means the browser
    warns "preloaded but unused" AND the hero still flashes dark."""
    m = re.search(r'<link rel="preload" as="image" href="([^"]+)"', body)
    assert m, f"{where}: missing the hero image preload link"
    hero_url = m.group(1)
    assert f'background-image: url("{hero_url}")' in body, (
        f"{where}: preload href does not match any hero background-image url"
    )


def test_city_home_preloads_the_hero_background_image(client):
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    _assert_hero_preloaded_and_matches(r.text, "city home")


def test_listing_page_preloads_the_hero_background_image(client):
    # The listing hero photo is the page a salon owner looks at — it must not
    # flash dark on first paint.
    r = client.get(
        "/b/blow-dry-bar-brickell", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200
    _assert_hero_preloaded_and_matches(r.text, "listing page")


def test_neighborhood_page_preloads_the_hero_background_image(client):
    r = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    _assert_hero_preloaded_and_matches(r.text, "neighborhood page")
