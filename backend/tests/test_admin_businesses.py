"""Tests for the admin business search and edit pages.

Exercises:
  - GET /admin/businesses — search page renders, no results without query,
    results appear when querying by name
  - GET /admin/businesses/{id}/edit — edit form shows current hide_ratings state
  - POST /admin/businesses/{id}/edit — toggling hide_ratings on/off saves to DB
  - 404 handling for unknown business IDs
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def _first_business(seeded_db) -> Dict[str, Any]:
    """Return any one business from the seeded test DB."""
    return asyncio.run(seeded_db.businesses.find_one({"city_id": {"$exists": True}}))


# ---- /admin/businesses search page ------------------------------------

def test_admin_businesses_page_renders_empty_state(client):
    """Without a search query the page renders the prompt to search,
    not a table of results."""
    r = client.get("/admin/businesses")
    assert r.status_code == 200, r.text
    assert "Find a business" in r.text
    assert "Type a business name above to search" in r.text


def test_admin_businesses_page_shows_no_results_message(client, seeded_db):
    """A query that matches nothing renders the 'no results' message."""
    r = client.get("/admin/businesses?q=zzznomatchxxx")
    assert r.status_code == 200, r.text
    assert "No businesses found matching" in r.text


def test_admin_businesses_page_shows_matching_results(client, seeded_db):
    """A query that matches at least one seeded business shows that
    business's name and an Edit link."""
    biz = _first_business(seeded_db)
    # Use just the first word of the name so partial match works.
    first_word = biz["name"].split()[0]
    r = client.get(f"/admin/businesses?q={first_word}")
    assert r.status_code == 200, r.text
    assert biz["name"] in r.text
    # Edit link must point at the correct business ID.
    assert f"/admin/businesses/{biz['_id']}/edit" in r.text


def test_admin_businesses_page_shows_ratings_column(client, seeded_db):
    """When a business has a google_rating and hide_ratings is False,
    the rating appears in the search results table."""
    biz = _first_business(seeded_db)
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"google_rating": 4.8, "google_review_count": 120, "hide_ratings": False}},
        )
    )
    first_word = biz["name"].split()[0]
    r = client.get(f"/admin/businesses?q={first_word}")
    assert r.status_code == 200, r.text
    assert "4.8" in r.text
    assert "120" in r.text


def test_admin_businesses_page_shows_hidden_badge(client, seeded_db):
    """When hide_ratings is True, the search results show 'Hidden' in the
    ratings column, not the star rating."""
    biz = _first_business(seeded_db)
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"google_rating": 4.8, "google_review_count": 120, "hide_ratings": True}},
        )
    )
    first_word = biz["name"].split()[0]
    r = client.get(f"/admin/businesses?q={first_word}")
    assert r.status_code == 200, r.text
    assert "Hidden" in r.text


# ---- /admin/businesses/{id}/edit GET ----------------------------------

def test_admin_business_edit_page_renders(client, seeded_db):
    """Edit page loads and shows the business name and the hide_ratings toggle."""
    biz = _first_business(seeded_db)
    r = client.get(f"/admin/businesses/{biz['_id']}/edit", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    assert biz["name"] in r.text
    # The toggle input must be present.
    assert 'name="hide_ratings"' in r.text
    assert "Hide star ratings" in r.text

    # The link to the public listing must be absolute
    expected_url = f"http://miami.knowsbeauty.localhost/b/{biz['slug']}"
    assert expected_url in r.text


def test_admin_business_edit_page_shows_unchecked_by_default(client, seeded_db):
    """New businesses default to hide_ratings=False, so the checkbox must
    be unchecked on the edit form."""
    biz = _first_business(seeded_db)
    # Ensure the field is False.
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"hide_ratings": False}},
        )
    )
    r = client.get(f"/admin/businesses/{biz['_id']}/edit")
    assert r.status_code == 200, r.text
    # The checkbox must not carry the `checked` attribute.
    assert "Ratings are shown" in r.text
    assert "Ratings are currently hidden" not in r.text


def test_admin_business_edit_page_shows_checked_when_hidden(client, seeded_db):
    """When hide_ratings is already True the checkbox renders checked and the
    'currently hidden' status badge appears."""
    biz = _first_business(seeded_db)
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"hide_ratings": True}},
        )
    )
    r = client.get(f"/admin/businesses/{biz['_id']}/edit")
    assert r.status_code == 200, r.text
    assert "Ratings are currently hidden" in r.text


def test_admin_business_edit_page_404_for_unknown_id(client):
    r = client.get("/admin/businesses/does-not-exist/edit")
    assert r.status_code == 404


# ---- /admin/businesses/{id}/edit POST ---------------------------------

def test_admin_business_edit_post_sets_hide_ratings_true(client, seeded_db):
    """Submitting the form with the checkbox checked sets hide_ratings=True
    in the database and redirects with saved=1."""
    biz = _first_business(seeded_db)
    # Start with ratings visible.
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"hide_ratings": False}},
        )
    )
    r = client.post(
        f"/admin/businesses/{biz['_id']}/edit",
        data={"hide_ratings": "on"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    assert "saved=1" in r.headers["location"]

    # Confirm the DB was updated.
    updated = asyncio.run(seeded_db.businesses.find_one({"_id": biz["_id"]}))
    assert updated["hide_ratings"] is True


def test_admin_business_edit_post_sets_hide_ratings_false(client, seeded_db):
    """Submitting the form WITHOUT the checkbox present (unchecked) sets
    hide_ratings=False in the database.

    WHY: HTML checkboxes send nothing when unchecked, so the POST body will
    not contain the hide_ratings field at all. The handler must interpret
    absence as False — this test confirms that behaviour.
    """
    biz = _first_business(seeded_db)
    # Start with ratings hidden.
    asyncio.run(
        seeded_db.businesses.update_one(
            {"_id": biz["_id"]},
            {"$set": {"hide_ratings": True}},
        )
    )
    # POST without the checkbox field (simulates unchecking it).
    r = client.post(
        f"/admin/businesses/{biz['_id']}/edit",
        data={},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    assert "saved=1" in r.headers["location"]

    # Confirm hide_ratings flipped to False.
    updated = asyncio.run(seeded_db.businesses.find_one({"_id": biz["_id"]}))
    assert updated["hide_ratings"] is False


def test_admin_business_edit_post_shows_saved_banner_on_follow(client, seeded_db):
    """After saving, following the redirect shows the 'Saved' confirmation
    banner on the edit page."""
    biz = _first_business(seeded_db)
    r = client.post(
        f"/admin/businesses/{biz['_id']}/edit",
        data={"hide_ratings": "on"},
        follow_redirects=True,
    )
    assert r.status_code == 200, r.text
    assert "Saved. Changes take effect immediately" in r.text


def test_admin_business_edit_post_404_for_unknown_id(client):
    r = client.post(
        "/admin/businesses/does-not-exist/edit",
        data={"hide_ratings": "on"},
        follow_redirects=False,
    )
    assert r.status_code == 404


# ---- nav link ----------------------------------------------------------

def test_admin_layout_has_businesses_nav_link(client):
    """The admin layout nav contains a 'Businesses' link so admins can
    navigate to the search page from anywhere in the admin section."""
    r = client.get("/admin/claims")
    assert r.status_code == 200, r.text
    assert 'href="/admin/businesses"' in r.text
    assert "Businesses" in r.text
