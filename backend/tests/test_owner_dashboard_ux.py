"""Owner dashboard (/owners/me) UX-polish guards.

These render the REAL owner dashboard (owner_business is set) and assert on the
pre-launch UX fixes from the owner walk-through:

1. The "Complete your profile" checklist carries the hooks the photo-upload
   JavaScript needs to flip "Add a photo" to done the moment a photo is
   uploaded — so the checklist never contradicts what the owner just did.
2. The listing-performance panel stays hidden during the pre-traffic owner
   experience, so the dashboard does not frame a brand-new listing as empty or
   underperforming before the directory has meaningful usage.
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

    def test_photo_upload_input_uses_compiled_hidden_class(self, seeded_db):
        """The native file input must stay hidden inside the styled upload label.

        The old `sr-only` class is absent from reference.css, so the browser
        showed "Choose File / No file chosen" inside the owner-facing button.
        """
        html = _render_dashboard(seeded_db, photos=[])
        assert 'id="photo-file-input" type="file"' in html
        assert 'class="hidden" aria-label="Upload a photo"' in html
        assert "sr-only" not in html

    def test_checklist_hides_when_last_item_completes(self, seeded_db):
        """If a photo is the last unfinished item, uploading it should hide the
        whole "Complete your profile" section instead of leaving a finished
        checklist on screen. The page carries the JavaScript guard that does
        this once every item is done."""
        html = _render_dashboard(seeded_db, photos=[])
        assert "doneCount >= total" in html
        assert "section.classList.add('hidden')" in html


# ─── Fix 3: performance stats hidden until useful ────────────────────────────


class TestPerformanceEmptyState:
    def test_listing_performance_panel_is_not_rendered(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert "Listing performance" not in html
        assert 'id="stat-views"' not in html
        assert 'id="stats-error"' not in html

    def test_zero_state_performance_copy_is_not_rendered(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert "Views appear here as Miami shoppers find your listing." not in html
        assert "Messages from shoppers will show up here once they reach out." not in html

    def test_owner_stats_fetch_is_not_shipped(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert "/api/v1/owner/stats" not in html


# ─── Shopper-action tap tiles hidden with performance panel ─────────────────


class TestActionTapTiles:
    """The hidden performance panel must not leave tap-count UI fragments around."""

    def test_three_tap_tiles_do_not_render(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        for tile_id in ("stat-calls", "stat-directions", "stat-website"):
            assert f'id="{tile_id}"' not in html, f"{tile_id} tile should be hidden"
        assert "taps to call" not in html
        assert "taps for directions" not in html
        assert "website clicks" not in html

    def test_tap_tile_zero_state_notes_do_not_render(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        for note_id in (
            "stat-calls-zero-note",
            "stat-directions-zero-note",
            "stat-website-zero-note",
        ):
            assert f'id="{note_id}"' not in html, f"{note_id} should be hidden"

    def test_stats_js_does_not_reference_hidden_metrics(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[])
        assert "data.call_click_count" not in html
        assert "data.directions_click_count" not in html
        assert "data.website_click_count" not in html
        assert "stat-calls" not in html

    def test_tap_tile_color_classes_exist_in_compiled_css(self, seeded_db):
        """The tap-tile number colors must be real classes in the pre-compiled
        stylesheet — a class typed but absent renders as nothing (the site has no
        live Tailwind build)."""
        css = _reference_css()
        for cls in ("text-amber-600", "text-blue-600", "text-orange-600", "text-3xl"):
            assert _css_has_class(css, cls), f"{cls} missing from compiled reference.css"


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


# ─── Upgrade card leads with the 0% commission benefit ───────────────────────


class TestUpgradeCardSellsZeroCommission:
    """The free-tier owner's "Get Featured" upgrade card is the screen where an
    owner decides whether to pay $29/month. Our strongest selling point — 0%
    commission / keep 100% of every booking, vs booking apps that take ~30% — is
    the lead benefit on /pricing and /owners, so it must also appear here, at the
    actual pay decision. It was missing; this guards against it going missing again."""

    def test_upgrade_card_shows_zero_commission_benefit(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        assert "0% commission" in html
        assert "keep 100% of every booking" in html.lower()

    def test_zero_commission_leads_the_benefit_list(self, seeded_db):
        """It should be the FIRST benefit bullet — ahead of placement/badge/AI —
        because it's the most compelling reason to pay."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=False)
        commission_pos = html.find("0% commission")
        visibility_pos = html.find("Premium visibility")
        assert commission_pos != -1 and visibility_pos != -1
        assert commission_pos < visibility_pos

    def test_subscribed_owner_does_not_see_upgrade_card(self, seeded_db):
        """A paying owner shouldn't be pitched the upgrade they already have.

        WHY assert on the 0% commission bullet rather than the button text:
        the "Get Featured — $29/month" string also lives in the page's inline
        JavaScript (which wires the locked AI-tool overlays to checkout), so it
        is present for every owner. The 0% commission bullet appears ONLY in the
        visible upgrade card, so its absence cleanly proves the card is hidden.
        """
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        # Subscribed owners see the active-status badge, not the upgrade card.
        assert "Featured listing active" in html
        assert "0% commission — keep 100% of every booking." not in html


# ─── Featured caption generator uses real listing photos ─────────────────────


class TestCaptionGeneratorPhotoSelection:
    def test_featured_caption_tool_shows_selected_listing_photo(self, seeded_db):
        html = _render_dashboard(
            seeded_db,
            photos=[{"url": "/media/caption-photo", "alt": "Balayage result"}],
            subscribed=True,
        )
        assert 'id="caption-photo-control"' in html
        assert 'id="caption-photo-preview"' in html
        assert 'src="/media/caption-photo"' in html
        assert 'data-caption-photo-url="/media/caption-photo"' in html
        assert 'data-selected-photo-url="/media/caption-photo"' in html

    def test_featured_caption_tool_promises_seven_suggestions(self, seeded_db):
        html = _render_dashboard(
            seeded_db,
            photos=[{"url": "/media/caption-photo", "alt": "Balayage result"}],
            subscribed=True,
        )
        assert "write 7 caption suggestions" in html
        assert "Generate 7 suggestions" in html
        assert "Generate new suggestions" in html
        assert "Generate another" not in html

    def test_featured_caption_tool_has_no_photo_empty_state(self, seeded_db):
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        assert 'id="caption-photo-empty"' in html
        assert "Upload a listing photo first" in html
        assert 'href="#photos-section"' in html


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

    def test_embed_code_link_carries_mkb_badge_marker(self, seeded_db):
        """The badge link MUST carry the ?ref=mkb-badge marker. Without it, a
        shopper who clicks the badge on the salon's own site arrives with an
        external referer we can't credit — so badge-driven traffic (our #1
        acquisition lever) would silently fail to count as Miami-Knows-Beauty
        driven. The marker is what makes that click attributable, and it can't be
        backfilled, so it must ship on the embed from launch."""
        html = _render_dashboard(seeded_db, photos=[], subscribed=True)
        assert "/b/ux-test-salon?ref=mkb-badge" in html

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


class TestWebsiteBadgeEmbedCitySubdomain:
    """Ensure the absolute listing URL and website badge URL correctly reflect the business's city subdomain."""

    @pytest.mark.asyncio
    async def test_embed_urls_reflect_business_city_subdomain(self, seeded_db, monkeypatch):
        db = seeded_db
        email = "fort-lauderdale-owner@example.com"
        
        city = await db.cities.find_one({"slug": "fort-lauderdale"})
        if not city:
            network = await db.networks.find_one({"slug": "beauty"})
            city_id = str(uuid.uuid4())
            await db.cities.insert_one({
                "_id": city_id,
                "network_id": network["_id"],
                "slug": "fort-lauderdale",
                "name": "Fort Lauderdale",
                "status": "live",
            })
        else:
            city_id = city["_id"]

        biz_id = str(uuid.uuid4())
        await db.businesses.insert_one({
            "_id": biz_id,
            "name": "Lauderdale Glam",
            "slug": "lauderdale-glam",
            "city_id": city_id,
            "claimed_email": email,
            "featured": {"tier": "featured", "enabled": True},
            "stripe_subscription_id": "sub_lauderdale_123",
            "photos": [],
        })

        from app.config import get_settings
        monkeypatch.setenv("CANONICAL_BASE_URL", "https://miami.knowsbeauty.com")
        get_settings.cache_clear()

        client = _make_client()
        r = client.get(
            "/owners/me",
            headers={"host": "miami.knowsbeauty.localhost"},
            cookies={"kb_owner_session": _signed_cookie(email)},
        )
        assert r.status_code == 200
        html = r.text

        assert "https://fort-lauderdale.knowsbeauty.com/b/lauderdale-glam" in html
        assert "https://fort-lauderdale.knowsbeauty.com/badge/featured.svg" in html

        monkeypatch.delenv("CANONICAL_BASE_URL", raising=False)
        get_settings.cache_clear()

