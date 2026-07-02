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


def test_city_home_preloads_the_hero_background_image(client):
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    body = r.text

    m = re.search(r'<link rel="preload" as="image" href="([^"]+)"', body)
    assert m, "city home is missing the hero image preload link"
    hero_url = m.group(1)

    # The preloaded URL must be the exact URL the hero CSS background uses. If it
    # doesn't match, the browser warns the preload went unused and the hero still
    # flashes dark — so matching is the whole point of the fix.
    assert f'background-image: url("{hero_url}")' in body, (
        "preload href does not match the hero background-image url"
    )
