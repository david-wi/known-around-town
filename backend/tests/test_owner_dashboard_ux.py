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


def _render_dashboard(
    seeded_db, *, photos: list | None = None, subscribed: bool = False
) -> str:
    email = "owner-ux@example.com"
    import asyncio

    asyncio.run(
        _insert_business(seeded_db, email=email, photos=photos, subscribed=subscribed)
    )
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


# ─── Locked AI-tool upsell overlay must be opaque (free-tier owners) ─────────


def _reference_css() -> str:
    """Read the compiled stylesheet the dashboard actually links to.

    WHY: the site ships a single pre-compiled `reference.css` rather than a
    live Tailwind build, so a utility class is only honoured if it was baked
    into that file. A class typed in the template but missing from the CSS
    renders as NOTHING — which is exactly the bug this test guards against.
    """
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(
        here, "..", "app", "static", "css", "reference.css"
    )
    with open(css_path, "r", encoding="utf-8") as fh:
        return fh.read()


def _css_has_class(css: str, class_name: str) -> bool:
    """True if `class_name` has a real rule in the compiled stylesheet.

    Tailwind escapes the `/` in opacity classes (`bg-white/95` -> `bg-white\\/95`)
    and the `[` `]` in arbitrary values, so we check for the escaped selector.
    """
    escaped = class_name.replace("/", r"\/").replace("[", r"\[").replace("]", r"\]")
    return f".{escaped}" in css


class TestLockedAiUpsellOverlay:
    """The free-tier dashboard shows the caption + ad-copy tools behind a
    'Featured listing required' overlay. The overlay MUST fully cover the
    disabled preview textarea behind it, or the upsell message collides with
    the textarea placeholder and reads as broken — at the worst possible moment,
    when we're asking the owner to pay $29/month.

    The original overlay used `bg-white/70` and `backdrop-blur-[1px]`, neither
    of which exists in the compiled reference.css, so it rendered transparent.
    """

    def test_free_tier_shows_locked_overlays(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        # Both AI tools render their locked upgrade prompt, not the live tool.
        assert 'id="caption-upgrade-btn"' in html
        assert 'id="adcopy-upgrade-btn"' in html
        # The live generate controls must NOT be present for a free owner.
        assert 'id="caption-generate"' not in html
        assert 'id="adcopy-generate"' not in html

    def test_overlay_background_classes_are_css_backed(self, seeded_db):
        """Every utility class on the locked overlay must exist in the compiled
        stylesheet — otherwise the overlay is invisible and the bug returns."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        css = _reference_css()
        # The opaque-background + blur recipe the fix uses.
        for cls in ("bg-white/95", "backdrop-blur-sm"):
            assert cls in html, f"locked overlay should use {cls}"
            assert _css_has_class(css, cls), (
                f"{cls} is used on the locked overlay but has no rule in "
                f"reference.css — it would render as nothing"
            )

    def test_overlay_does_not_use_uncompiled_classes(self, seeded_db):
        """Guard against re-introducing the transparent-overlay classes.

        `bg-white/70` and `backdrop-blur-[1px]` are not in reference.css, so
        using them makes the overlay see-through. Fail if they come back."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        css = _reference_css()
        for cls in ("bg-white/70", "backdrop-blur-[1px]"):
            assert not _css_has_class(css, cls), (
                f"{cls} unexpectedly appeared in reference.css — update this "
                f"test if it was deliberately added"
            )
            assert cls not in html, (
                f"{cls} is back on the locked overlay; it has no compiled CSS "
                f"rule so the overlay would render transparent again"
            )


# ─── Website badge embed section (KAT-037) ───────────────────────────────────


class TestWebsiteBadgeEmbed:
    """The Featured-tier 'Add the badge to your website' section. Featured owners
    get a copy-paste embed snippet whose link points to THEIR listing; free-tier
    owners don't see it at all."""

    def test_featured_owner_sees_badge_section(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        assert "Add the badge to your website" in html
        # The copy control and its source <pre> both render so the JS can wire up.
        assert 'id="badge-embed-code"' in html
        assert 'id="badge-copy"' in html

    def test_embed_code_links_to_this_salons_listing(self, seeded_db):
        """The embed snippet's link must point at the owner's own listing slug —
        that's what drives the salon's visitors to its directory page (and earns
        the backlink). The fixture salon slug is 'ux-test-salon'."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        # Jinja autoescapes the snippet inside the <pre>, so the angle brackets
        # arrive as &lt;a … but the listing path and badge image src survive as
        # plain substrings.
        assert "/b/ux-test-salon" in html
        assert "/badge/featured.svg" in html

    def test_share_caption_present_for_featured_owner(self, seeded_db):
        """The secondary 'share your feature' affordance ships a ready-to-post
        caption and its own copy button."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        assert "Share your feature on Instagram" in html
        assert 'id="share-caption"' in html
        assert 'id="share-copy"' in html
        # The caption names the publication and links to the listing.
        assert "Miami Knows Beauty" in html

    def test_free_owner_does_not_see_badge_section(self, seeded_db):
        """The badge is a Featured perk — a free-tier owner must NOT see the
        embed section or the share caption."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        assert "Add the badge to your website" not in html
        assert 'id="badge-embed-code"' not in html
        assert 'id="share-caption"' not in html

    def test_badge_section_classes_are_css_backed(self, seeded_db):
        """Every utility class on the badge section must exist in the compiled
        stylesheet, or the section renders unstyled/broken (the reference.css is
        static — a class typed but not compiled does nothing)."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        css = _reference_css()
        # A representative set of the classes the new section relies on.
        for cls in (
            "rounded-2xl", "border-stone-200", "overflow-x-auto",
            "whitespace-pre-wrap", "font-mono", "text-emerald-700",
        ):
            assert _css_has_class(css, cls), (
                f"{cls} is used in the badge section but has no rule in "
                f"reference.css — it would render as nothing"
            )
