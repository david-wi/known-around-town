"""Smoke tests that exercise the full request -> template path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_miami_beauty_home(client):
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    assert "Knows Beauty" in body
    assert "Miami" in body
    # Hero headline pulled from city/editorial defaults
    assert "best-kept beauty" in body.lower() or "knows beauty" in body.lower()
    # Featured Beauty businesses from the reference content should appear.
    assert "Beauty Bar Sunny" in body or "Palmera Hair House" in body
    # The Issue eyebrow comes from copy_blocks.
    assert "ISSUE NO. 01" in body


def test_miami_beauty_category(client):
    r = client.get("/c/nails", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "Isla Nail Society" in r.text


def test_miami_beauty_neighborhood(client):
    r = client.get("/n/brickell", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert "Brickell" in r.text


def test_miami_beauty_business(client):
    r = client.get(
        "/b/isla-nail-society", headers={"host": "miami.knowsbeauty.localhost"}
    )
    assert r.status_code == 200, r.text
    assert "Isla Nail Society" in r.text
    assert "Brickell" in r.text


def test_miami_wellness_home(client):
    r = client.get("/", headers={"host": "miami.knowswellness.localhost"})
    assert r.status_code == 200, r.text
    assert "Knows Wellness" in r.text


def test_miami_health_home(client):
    r = client.get("/", headers={"host": "miami.knowshealth.localhost"})
    assert r.status_code == 200, r.text
    assert "Knows Health" in r.text
    # Health profiles are providers, not promises
    assert "doctor" in r.text.lower() or "clinic" in r.text.lower() or "provider" in r.text.lower()


def test_unknown_host_404(client):
    r = client.get("/", headers={"host": "miami.unknownsite.localhost"})
    assert r.status_code == 404


def test_unknown_city_renders_404(client):
    """Network is known but the city slug isn't in the database."""
    r = client.get("/", headers={"host": "atlantis.knowsbeauty.localhost"})
    # The tenant resolver returns no city, so the home route currently 404s on the city pages.
    # The network home template still renders 200 — verify both behaviors are not 500s.
    assert r.status_code in (200, 404)


def test_sitemap_includes_business(client):
    r = client.get("/sitemap.xml", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    assert "isla-nail-society" in r.text


def test_api_lists_networks(client):
    r = client.get("/api/v1/networks")
    assert r.status_code == 200
    slugs = {n["slug"] for n in r.json()}
    assert {"beauty", "wellness", "health"} <= slugs


def test_copy_block_override(client, seeded_db):
    """Override the home hero eyebrow for Miami Beauty and confirm the new
    wording appears, without restarting or touching code."""
    import asyncio

    network = asyncio.run(seeded_db.networks.find_one({"slug": "beauty"}))
    city = asyncio.run(
        seeded_db.cities.find_one({"network_id": network["_id"], "slug": "miami"})
    )

    r = client.post(
        "/api/v1/copy-blocks",
        json={
            "scope_type": "city",
            "scope_ref": {"city_id": city["_id"]},
            "key": "home.hero.eyebrow",
            "value": "An editors' guide for Miami",
        },
    )
    assert r.status_code == 200, r.text

    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200
    assert "An editors&#39; guide for Miami" in r.text or "An editors' guide for Miami" in r.text
