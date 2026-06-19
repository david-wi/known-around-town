"""Owner dashboard (/owners/me) UX-polish guards.

These render the REAL owner dashboard (owner_business is set) and assert on the
pre-launch UX fixes from the owner walk-through:

1. The "Complete your profile" checklist carries the hooks the photo-upload
   JavaScript needs to flip "Add a photo" to done the moment a photo is
   uploaded — so the checklist never contradicts what the owner just did.
2. The listing-performance panel ships the encouraging empty-state lines that
   reframe a brand-new "0 page views / 0 messages" as "tracking has started"
   rather than "the directory isn't working". They carry no fabricated numbers.

The performance empty-state lines are rendered into the page hidden and revealed
by JavaScript only when the fetched count is exactly 0, so here we assert the
copy is present in the served HTML (its delivery into view is a JS concern the
esprima syntax guard covers).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _signed_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session

    return sign_session(email)


async def _insert_business(
    db,
    *,
    email: str,
    photos: list | None = None,
    subscribed: bool = False,
) -> str:
    biz_id = str(uuid.uuid4())
    doc: dict[str, Any] = {
        "_id": biz_id,
        "name": "UX Test Salon",
        "slug": "ux-test-salon",
        "claimed_email": email,
        "featured": {"tier": "free", "enabled": False},
        "photos": photos or [],
    }
    if subscribed:
        # stripe_subscription_id is the authoritative "is subscribed" signal the
        # route reads, which unlocks the Featured-only AI tool sections.
        doc["stripe_subscription_id"] = "sub_test_123"
        doc["featured"] = {"tier": "featured", "enabled": True}
    await db.businesses.insert_one(doc)
    return biz_id


def _render_dashboard(seeded_db, *, photos: list | None = None) -> str:
    email = "owner-ux@example.com"
    import asyncio

    asyncio.run(_insert_business(seeded_db, email=email, photos=photos))
    client = _make_client()
    # WHY: the test tenant resolves from the seeded local hostname, the same
    # one the smoke tests use for Miami Beauty.
    r = client.get(
        "/owners/me",
        headers={"host": "miami.knowsbeauty.localhost"},
        cookies={"kb_owner_session": _signed_cookie(email)},
    )
    assert r.status_code == 200, r.text
    return r.text


# ─── Fix 1: checklist photo item is live-updatable ───────────────────────────


class TestChecklistPhotoHooks:
    def test_checklist_present_when_profile_incomplete(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert "Complete your profile" in html

    def test_photo_row_has_both_done_and_todo_branches(self, seeded_db):
        """The photo checklist row renders both states so the JS can flip
        between them without rebuilding markup. With no photos, the not-done
        branch is visible and the done branch is hidden."""
        html = _render_dashboard(seeded_db, photos=[])
        assert 'id="checklist-item-photo"' in html
        assert "data-checklist-done" in html
        assert "data-checklist-todo" in html

    def test_checklist_carries_live_update_hooks(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert 'id="profile-checklist"' in html
        assert 'id="checklist-count"' in html
        assert 'id="checklist-progress"' in html
        assert 'data-checklist-total="5"' in html

    def test_photo_row_marked_not_done_with_zero_photos(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        # The photo item's done-state flag starts at 0 when there are no photos.
        assert 'id="checklist-item-photo" data-done="0"' in html

    def test_photo_row_marked_done_with_a_photo(self, seeded_db):
        html = _render_dashboard(
            seeded_db, photos=[{"url": "/media/abc123", "is_hero": True}]
        )
        assert 'id="checklist-item-photo" data-done="1"' in html

    def test_checklist_hides_when_last_item_completes(self, seeded_db):
        """If a photo is the last unfinished item, uploading it should hide the
        whole "Complete your profile" section instead of leaving a finished
        checklist on screen. The page carries the JavaScript guard that does
        this once every item is done."""
        html = _render_dashboard(seeded_db, photos=[])
        assert "doneCount >= total" in html
        assert "section.classList.add('hidden')" in html


# ─── Fix 3: encouraging empty-state copy on the performance panel ────────────


class TestPerformanceEmptyState:
    def test_views_zero_note_present(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert 'id="stat-views-zero-note"' in html
        assert "Views appear here as Miami shoppers find your listing." in html

    def test_messages_zero_note_present(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert 'id="stat-inquiries-zero-note"' in html
        assert "Messages from shoppers will show up here once they reach out." in html

    def test_zero_notes_start_hidden(self, seeded_db):
        """The notes are hidden on render and revealed by JS only on a real
        zero, so a busy listing never shows them."""
        html = _render_dashboard(seeded_db, photos=[])
        # Both note spans ship with the 'hidden' utility class so they don't
        # show until the stats JavaScript reveals them on a real zero.
        for note_id in ("stat-views-zero-note", "stat-inquiries-zero-note"):
            idx = html.index(f'id="{note_id}"')
            tag_end = html.index(">", idx)
            tag = html[idx:tag_end]
            assert "hidden" in tag, f"{note_id} should start hidden"
