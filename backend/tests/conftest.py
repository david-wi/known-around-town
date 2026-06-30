"""Test scaffolding: swap the real Motor client for `mongomock-motor` so the
suite runs without a MongoDB process. We also seed the three networks and
Miami so the public pages have data to render.
"""

from __future__ import annotations

import os
import sys

import pytest
from mongomock_motor import AsyncMongoMockClient

# Make sure backend/ is on sys.path before app imports happen.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure the host suffixes the app will recognize during tests.
os.environ["NETWORK_DOMAINS"] = (
    "beauty:knowsbeauty.localhost,"
    "wellness:knowswellness.localhost,"
    "health:knowshealth.localhost"
)
os.environ["MONGODB_URL"] = "mongodb://test"
os.environ["MONGODB_DATABASE"] = "wkl_test"
# WHY: admin gates fail closed when ADMIN_API_KEY is missing. Tests that exercise
# admin routes use this explicit key instead of relying on unset-secret dev mode.
os.environ["ADMIN_API_KEY"] = "test-admin-key"
# WHY: disable the preview gate for all tests. Pre-gate tests don't supply a
# preview_token cookie, so they'd all get 302 → /preview-login → 200 instead
# of the responses they assert. Tests that specifically exercise the gate
# (test_preview_login.py) override this within their own client fixture.
os.environ["PREVIEW_MODE_ENABLED"] = "false"
# WHY: owner-login tests intentionally use the dev log fallback to read
# one-time codes. Developer shells may have real Resend credentials set,
# but tests must never call the live email provider.
os.environ.pop("RESEND_API_KEY", None)
os.environ.pop("OWNER_EMAIL_FROM_NAME", None)
os.environ.pop("OWNER_EMAIL_FROM_ADDRESS", None)


@pytest.fixture(autouse=True)
def _clear_nav_cache():
    """Reset the in-process navigation TTL cache around every test.

    WHY: `app.services.content` caches the category/neighborhood/city lists in a
    module-level dict that lives for the whole test process. Without this reset,
    one test's cached lists could be served to a later test that seeded a fresh
    database, causing order-dependent failures. Clearing before and after keeps
    each test hermetic, matching the fresh-database isolation the suite assumes.
    """
    from app.services import content as _content

    _content.clear_nav_cache()
    yield
    _content.clear_nav_cache()


@pytest.fixture
def mock_db(monkeypatch):
    """Patch app.database.get_client to return a mongomock instance."""
    client = AsyncMongoMockClient()

    def fake_client():
        return client

    from app import database

    monkeypatch.setattr(database, "_client", client)
    monkeypatch.setattr(database, "get_client", fake_client)
    return client[os.environ["MONGODB_DATABASE"]]


@pytest.fixture
async def seeded_db(mock_db):
    """Run the real seed scripts against the mocked client."""
    from seed import seed_networks, seed_miami

    await seed_networks.main()
    await seed_miami.main()
    return mock_db
