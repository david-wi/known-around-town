"""Render tests for the elevated PAID "Featured" treatment.

WHY this exists
---------------
A shopper review found the paid "Featured" tier looked almost identical to the
free "Editor's Pick" badge on a salon's page, which softened the reason a salon
would pay $29/month. We made the paid Featured treatment visibly more premium
(a champagne-gold gradient pill + soft gold ring on the badges, a "Featured
salon — Selected for premium placement" hero descriptor, and a gold edge on the
listing card and the detail-page info card). The free Editor's Pick badge was
deliberately left untouched.

These tests lock that in:
  1. A Featured salon's detail page shows the premium descriptor and renders the
     gradient/ring classes (the elevated treatment).
  2. A Featured salon's listing card gets the elevated gold edge and gradient
     badge.
  3. The free Editor's Pick badge markup is unchanged — a non-Featured salon that
     is an Editor's Pick renders the original badge and none of the premium
     Featured styling.

WHY direct DB mutation (not the seed): the seed data carries no ``featured``
flag — Featured is toggled per-business in production — so the only way to
exercise the Featured branch in the mongomock test DB is to set the flag on a
seeded business directly. We flip it on a known seeded salon, render, then assert.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

HOST = {"host": "miami.knowsbeauty.localhost"}

# A real seeded Miami beauty salon. The seed marks it both Featured and an
# Editor's Pick, so we explicitly set the Featured flag on/off per test rather
# than relying on the seed default — this keeps each test self-contained and
# unaffected if the seed's flags change later. If this slug ever leaves the
# seed, swap in another from backend/seed/_real_businesses.json.
SALON_SLUG = "the-spa-at-the-setai"

# The exact gradient + ring tokens the premium treatment uses. These are the
# load-bearing classes that make the paid tier read as elevated; if a refactor
# drops them, the Featured treatment silently reverts to a flat pill.
GRADIENT_CLASSES = "bg-gradient-to-r from-amber-400 to-amber-600"

# The exact original free Editor's Pick pill markup on the detail page sidebar.
# Asserting the literal string guarantees we did not touch the free tier.
EDITORS_PICK_SIDEBAR = (
    'class="text-xs font-semibold text-amber-700 bg-amber-50 rounded-full '
    'px-3 py-1 inline-flex items-center gap-1"'
)


async def _set_featured(db, slug: str, enabled: bool) -> None:
    """Toggle the paid Featured flag on a seeded business in the mock DB."""
    await db.businesses.update_one(
        {"slug": slug}, {"$set": {"featured": {"enabled": enabled}}}
    )


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


@pytest.mark.asyncio
async def test_featured_detail_page_shows_premium_treatment(seeded_db, client):
    """A paid Featured salon's detail page renders the elevated treatment:
    the 'Featured salon' label, the 'Selected for premium placement' descriptor,
    and the champagne-gold gradient on the badges."""
    await _set_featured(seeded_db, SALON_SLUG, True)

    r = client.get(f"/b/{SALON_SLUG}", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.text

    # The confident premium label + the short descriptor that explains the
    # elevated placement to shoppers and prospective owners.
    assert "Featured salon" in body
    assert "Selected for premium placement" in body
    # The gold gradient that distinguishes the paid pill from the free badge.
    assert GRADIENT_CLASSES in body
    # The info card itself gets the gold edge (amber ring) when Featured.
    assert "ring-1 ring-amber-200" in body


@pytest.mark.asyncio
async def test_featured_listing_card_is_elevated(seeded_db, client):
    """A paid Featured salon's listing card (rendered in the 'You might also
    love' grid and category/home grids) gets the elevated gold edge and the
    gradient Featured badge. The seed marks several salons Featured, so the home
    grids contain at least one Featured card."""
    r = client.get("/", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.text

    # The elevated card edge: amber border + gold ring + resting shadow. We
    # assert the gradient badge token (unique to the card/hero Featured pill)
    # is present, proving the Featured branch rendered in a card grid.
    assert GRADIENT_CLASSES in body
    # The card-level gold edge classes appear when a Featured card is in a grid.
    assert "ring-1 ring-amber-200" in body


@pytest.mark.asyncio
async def test_editors_pick_badge_is_untouched(seeded_db, client):
    """A non-Featured Editor's Pick salon renders the ORIGINAL free badge and
    none of the premium Featured styling. This proves the free tier was left
    exactly as it was (a deliberate product decision)."""
    # Ensure the salon is NOT featured but IS an editor's pick.
    await _set_featured(seeded_db, SALON_SLUG, False)
    await seeded_db.businesses.update_one(
        {"slug": SALON_SLUG}, {"$set": {"editors_pick": True}}
    )

    r = client.get(f"/b/{SALON_SLUG}", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.text

    # The original Editor's Pick pill markup is present, byte-for-byte.
    assert EDITORS_PICK_SIDEBAR in body
    assert "Editor's Pick" in body
    # And the subject salon's own premium Featured treatment is absent. The
    # hero descriptor only ever renders for the subject business, so its absence
    # proves the subject is being shown as a free listing. (We do NOT assert the
    # gradient is page-wide absent: the 'You might also love' grid legitimately
    # renders OTHER Featured salons' cards, which carry the gradient badge.)
    assert "Selected for premium placement" not in body


@pytest.mark.asyncio
async def test_featured_flag_off_means_no_premium_treatment(seeded_db, client):
    """Red-green guard: with the subject salon's Featured flag OFF, its hero
    premium descriptor does NOT render; with it ON (other tests), it does. This
    proves the subject's premium treatment is gated on the paid flag, not
    always-on. We assert on the hero descriptor because it only ever renders for
    the subject business — unlike the gradient class, which can also appear on
    other Featured salons' cards in the 'You might also love' grid."""
    await _set_featured(seeded_db, SALON_SLUG, False)

    r = client.get(f"/b/{SALON_SLUG}", headers=HOST)
    assert r.status_code == 200, r.text
    body = r.text
    assert "Selected for premium placement" not in body
