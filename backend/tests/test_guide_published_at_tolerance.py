"""Regression test: editorial guide pages must tolerate a string ``published_at``.

The bug this guards against: a batch of imported editorial guides stored
``published_at`` as a plain ISO string ("2026-06-12T06:00:00Z") instead of a
datetime. The guide page template emits a schema.org ``datePublished`` value
with ``guide.published_at.isoformat()`` — and a string has no ``.isoformat()``
method, so rendering raised ``AttributeError`` and returned HTTP 500. On the
live Miami site this took down 23 guide pages at once.

The fix routes that template expression through the ``iso_datetime`` Jinja
filter, which (like the existing ``humantime`` filter) returns a real datetime's
``.isoformat()`` but passes a string straight through. The full-page test fails
(500) if the filter is removed or the template reverts to ``.isoformat()``.

This mirrors test_string_address_tolerance.py exactly — an async fixture inserts
the malformed record on the live beauty tenant, and an async test renders the
page through the sync TestClient — the pattern that is known loop-safe in this
suite.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

BEAUTY_HOST = "miami.knowsbeauty.localhost"
STRING_PUBLISHED_AT = "2026-06-12T06:00:00Z"


# ---- unit: the iso_datetime filter --------------------------------------

def test_iso_datetime_filter_is_registered_on_the_app_templates():
    """The live app templates must expose an iso_datetime filter.

    WHY this doesn't call attach_templates: attach_templates sets a module-global
    `_templates` as a side effect, so calling it here with a throwaway
    Jinja2Templates would replace the app's fully-configured templates object for
    the rest of the test session and break later page-rendering tests. We assert
    against the templates object the app already built at import time instead.
    """
    from app.main import templates

    assert "iso_datetime" in templates.env.filters


def test_iso_datetime_filter_tolerates_string_and_datetime():
    """The filter must pass an ISO string through unchanged and isoformat a datetime."""
    from app.main import templates

    iso = templates.env.filters["iso_datetime"]
    # A string passes through unchanged (it is already ISO from the import).
    assert iso(STRING_PUBLISHED_AT) == STRING_PUBLISHED_AT
    # A real datetime is normalised via isoformat().
    assert iso(datetime(2026, 1, 2, tzinfo=timezone.utc)) == "2026-01-02T00:00:00+00:00"
    # Empty values collapse to "" so the template's {% if %} guard controls output.
    assert iso(None) == ""
    assert iso("") == ""


# ---- full request path: the guide page must not 500 --------------------

@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


async def _insert_guide(seeded_db, slug: str, published_at) -> str:
    """Insert one live guide on the beauty Miami city. Returns the slug.

    The seed creates three "miami" city records (beauty, wellness, health), so the
    beauty one is selected by its network slug — ensuring the guide attaches to the
    city the page renders on ``miami.knowsbeauty.localhost``.
    """
    beauty_net = await seeded_db.networks.find_one({"slug": "beauty"})
    assert beauty_net is not None, "seed must create the beauty network"
    city = await seeded_db.cities.find_one(
        {"slug": "miami", "network_id": beauty_net["_id"]}
    )
    assert city is not None, "seed must create the beauty Miami city"
    await seeded_db.editorial_guides.insert_one(
        {
            "_id": f"regression-{slug}",
            "slug": slug,
            "city_id": city["_id"],
            "network_id": beauty_net["_id"],
            "status": "live",
            "title": "Regression Guide",
            "subtitle": "Guide for the published_at regression test",
            "author": "Test Editor",
            "body_markdown": "## Heading\n\nSome guide body copy.",
            "published_at": published_at,
        }
    )
    return slug


@pytest.mark.asyncio
async def test_guide_page_renders_string_published_at_without_500(client, seeded_db):
    slug = await _insert_guide(
        seeded_db, "regression-string-published-at-guide", STRING_PUBLISHED_AT
    )
    r = client.get(f"/guides/{slug}", headers={"host": BEAUTY_HOST})
    # Without the fix this is a 500 (AttributeError: str has no .isoformat()).
    assert r.status_code == 200, r.text
    body = r.text
    assert "Regression Guide" in body
    # The schema.org datePublished carries the ISO string straight through.
    assert STRING_PUBLISHED_AT in body
    assert '"datePublished"' in body


@pytest.mark.asyncio
async def test_guide_page_still_renders_datetime_published_at(client, seeded_db):
    slug = await _insert_guide(
        seeded_db,
        "regression-datetime-published-at-guide",
        datetime(2026, 6, 12, 6, 0, 0, tzinfo=timezone.utc),
    )
    r = client.get(f"/guides/{slug}", headers={"host": BEAUTY_HOST})
    assert r.status_code == 200, r.text
    assert "2026-06-12T06:00:00" in r.text
