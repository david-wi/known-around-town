"""Shared helpers for seed scripts."""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.database import ensure_indexes, get_db


# WHY: Multiple URLs per category so that different businesses in the same
# category get different photos on city pages. The old single-URL-per-category
# pattern caused every hair salon (for example) to display the identical Unsplash
# image — visually confusing to visitors. MD5 of the slug gives deterministic
# variety: re-seeding a business always picks the same photo, but adjacent
# businesses in the same category differ.
#
# WHY these exact IDs: every ID below was individually checked in two ways on
# 2026-07-02 before being kept/added — (a) an HTTP request to the live Unsplash
# URL returned 200 (not a 404, which renders as a broken image), and (b) the
# image was actually viewed to confirm it depicts that category's service (or
# clearly on-brand beauty). The parenthetical after each ID is a one-word note
# of what the photo shows. Dead IDs (404s) and off-topic images that used to be
# here (a brain model under "nails", a stethoscope/laptop under "spa", a flower
# shop under "lash-brow"/"makeup", a construction site under "makeup", gym/yoga
# shots, etc.) were removed in the same pass. Do NOT add an ID here without
# both liveness-checking it AND viewing it — an unverified ID is how the broken
# and wrong-content images crept in originally.
_CATEGORY_PHOTOS: Dict[str, List[str]] = {
    "hair": [
        "1595476108010-b4d1f102b1b1",  # hair wash
        "1522337360788-8b13dee7a37e",  # styled long hair
        "1560066984-138dadb4c035",     # hair salon interior
        "1562322140-8baeececf3df",     # blowout in progress
        "1521590832167-7bcbfaa6381f",  # hair salon interior
    ],
    "nails": [
        "1604654894610-df63bc536371",  # manicure
        "1632345031435-8727f6897d53",  # manicure in progress
        "1610992015762-45dca7fa3a85",  # manicured nails
        "1619607146034-5a05296c8f9a",  # nail-polish wall
    ],
    "spa": [
        "1540555700478-4be289fbecef",  # spa towel/product
        "1639162906614-0603b0ae95fd",  # back massage
        "1519824145371-296894a0daa9",  # neck/shoulder massage
        "1598556146869-aeb261893c35",  # steam facial
    ],
    "barber": [
        "1585747860715-2ba37e788b70",  # barbershop
        "1599351431202-1e0f0137899a",  # fade/razor
        "1503951914875-452162b0f3f1",  # beard trim
    ],
    "lash-brow": [
        "1583241800698-e8ab01830a07",  # makeup palette
        "1548902378-2ec44c906391",     # lash/brow eye closeup
        "1492618269284-653dce58fd6d",  # lash/brow eye closeup
        "1567629307995-b9f33097bd30",  # lash/brow eye closeup
    ],
    "med-spa": [
        "1570172619644-dfd03ed5d881",  # facial
        "1552693673-1bf958298935",     # clinical aesthetics treatment
        "1512290923902-8a9f81dc236c",  # facial treatment
        "1616394584738-fc6e612e71b9",  # clay-mask facial
    ],
    "waxing": [
        "1587179790059-5f5d937fb87d",  # smooth legs (hair removal)
        "1631125911107-0afc98f06edb",  # leg hair removal
        "1609840533741-62c180d0be79",  # waxing strip on arm
    ],
    "makeup": [
        "1583241800698-e8ab01830a07",  # makeup palette
        "1596462502278-27bfdc403348",  # makeup flat-lay
        "1516975080664-ed2fc6a32937",  # makeup brushes
        "1583784561105-a674080f391e",  # makeup flat-lay
    ],
}

_PHOTO_BASE = "https://images.unsplash.com/photo-{}?w=1600&q=80&auto=format&fit=crop"

# WHY: mirrors the keyword chain in business.html so seed scripts can populate
# schema_org_type at insert time with the same logic the template uses at render
# time. Having one canonical function here prevents the two from drifting apart.
# Keys are substrings checked against the primary category slug (lowercase).
# Dict is ordered most-specific first so earlier entries win on ambiguous slugs
# (e.g. "med-spa" must match before the generic "spa" catch further down).
_SLUG_SCHEMA_TYPE: Dict[str, str] = {
    "barber":       "BarberShop",
    "med-spa":      "MedicalSpa",
    "medspa":       "MedicalSpa",
    "medical-spa":  "MedicalSpa",
    "hair":         "HairSalon",
    "blowout":      "HairSalon",
    "blow-dry":     "HairSalon",
    "color":        "HairSalon",
    "nails":        "NailSalon",
    "nail":         "NailSalon",
    "manicure":     "NailSalon",
    "pedicure":     "NailSalon",
    "spa":          "DaySpa",
    "massage":      "DaySpa",
    "wellness":     "DaySpa",
}


def schema_org_type_for_slug(primary_category_slug: str) -> str:
    """Return the most specific schema.org type for a category slug.

    Used by seed scripts to populate schema_org_type at insert time, so the
    stored value is already accurate and the template's keyword-matching fallback
    is not needed for newly seeded businesses.

    WHY: returns "BeautySalon" (not "LocalBusiness") as the catch-all — the
    "LocalBusiness" default on the Business model is intentionally treated as
    "not yet classified". Seed helpers should always write a specific type.
    """
    slug = (primary_category_slug or "").lower()
    for keyword, schema_type in _SLUG_SCHEMA_TYPE.items():
        if keyword in slug:
            return schema_type
    # WHY: BeautySalon is the schema.org catch-all for beauty businesses without
    # a more specific subtype (lash bars, waxing studios, makeup artists, etc.).
    return "BeautySalon"


def pick_category_photo(slug: str, category: str) -> Optional[str]:
    """Return a deterministic variety photo for a business based on its slug.

    WHY: Uses MD5 of the slug so the same business always gets the same photo
    across re-seeds, but adjacent businesses in the same category get different
    photos — eliminating the identical-image repetition on city pages.
    """
    photos = _CATEGORY_PHOTOS.get(category)
    if not photos:
        return None
    idx = int(hashlib.md5(slug.encode()).hexdigest(), 16) % len(photos)
    return _PHOTO_BASE.format(photos[idx])


# WHY: the env flag a human (or the deploy script) must set on purpose to allow
# the demo-data seed/reset to touch a PRODUCTION database. The seed scripts both
# write demo content and DELETE stale records ("wipe and re-add" in
# seed_miami.py), so running them against the live database erases real data.
# Production data once vanished exactly this way — someone ran the reset pointed
# at the live cloud database by mistake. Requiring this explicit opt-in turns an
# accidental "I ran it against the wrong database" into a loud, harmless abort.
# The legitimate production seed (scripts/deploy.sh) sets this flag on purpose;
# nobody running the seed by hand from a laptop will have it set.
ALLOW_PRODUCTION_RESET_ENV = "KAT_ALLOW_PRODUCTION_RESET"

# WHY: the in-memory mongomock host the test suite uses (conftest.py sets
# MONGODB_URL=mongodb://test). It is not a real database server, so the
# destructive seed can never hurt anything when aimed at it. Classified as a
# safe target so the test harness — which runs the real seed scripts against
# mongomock — is never blocked by this guard.
_MONGOMOCK_SENTINEL_HOST = "test"


class SeedTargetForbiddenError(RuntimeError):
    """Raised when a destructive seed/reset is aimed at an unconfirmed database.

    WHY a hard error and not a warning: the whole point is to stop a wipe of the
    wrong database before it happens. A warning would scroll past; crashing
    before the first delete means the real data is untouched.
    """


def assert_seed_target_allowed() -> None:
    """Refuse to run the destructive demo-data seed unless the target is safe.

    Called at the top of every destructive seed entrypoint, BEFORE any write or
    delete. The seed is allowed only when one of two things is true:

    * The target is a local/dev database — the developer has opted in with
      ALLOW_LOCAL_MONGODB=true AND the MongoDB host is a known-local one (or it
      is the in-memory mongomock host the tests use). This is the everyday
      developer and CI path; nothing changes for them.
    * The operator has explicitly confirmed a production reset by setting
      KAT_ALLOW_PRODUCTION_RESET=true. The deploy script sets this when it
      intentionally re-seeds production; a human running the seed by hand never
      has it set.

    In every other case — including an empty/unparseable URL, a cloud (Atlas)
    host, or any target it cannot confidently classify as local — it FAILS
    CLOSED and raises SeedTargetForbiddenError. The default is "refuse", so a
    target the guard is unsure about is treated as production, never wiped.
    """
    settings = get_settings()
    host = settings.mongo_host()

    # Safe path 1: a real local/dev database the developer opted into, or the
    # in-memory mongomock host the test suite uses (not a real server at all).
    if settings.is_local_mongo_target() or host == _MONGOMOCK_SENTINEL_HOST:
        return

    # Safe path 2: an explicit, deliberate production-reset confirmation.
    if os.environ.get(ALLOW_PRODUCTION_RESET_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    # Fail closed: anything else (Atlas, an unknown remote host, an empty URL)
    # is treated as production and refused.
    target = host or "(no MONGODB_URL set)"
    raise SeedTargetForbiddenError(
        "Refusing to run the demo-data seed/reset: the target database "
        f"({target!r}) looks like production, and this seed DELETES records as "
        "part of re-seeding. To reset a LOCAL database, set "
        "ALLOW_LOCAL_MONGODB=true with a local MONGODB_URL. To intentionally "
        f"reset PRODUCTION, set {ALLOW_PRODUCTION_RESET_ENV}=true. Refused "
        "because neither was set — production data was once wiped by running "
        "this seed against the live database by mistake."
    )


async def upsert(collection_name: str, query: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    existing = await db[collection_name].find_one(query)
    if existing:
        # Preserve _id and created_at on update, refresh everything else.
        doc = {**doc, "_id": existing["_id"], "created_at": existing.get("created_at", doc.get("created_at"))}
        # WHY: a listing manually archived by an admin must stay archived even
        # when the seed re-runs and would restore it as "live". Overwriting
        # archived status caused previously-confirmed-closed businesses to
        # reappear on the live directory every time the seed ran.
        if existing.get("status") == "archived" and doc.get("status") == "live":
            doc["status"] = "archived"
        # WHY: preserve Google sync data that the seed doesn't provide. Running
        # a seed to update a business name or photo should NOT wipe out cached
        # Google star ratings, review counts, place IDs, and hours — those are
        # expensive to re-fetch (~$0.017/call) and the seed file has no way to
        # know the correct values. Copy any google_* field and hours from the
        # existing record if the new doc omits them.
        #
        _PRESERVE_KEYS = ("google_place_id", "google_rating", "google_review_count",
                          "google_rating_synced_at", "hours")
        for key in _PRESERVE_KEYS:
            if key in existing and key not in doc:
                doc[key] = existing[key]
        # WHY hero_photo_url is preserved separately (truthy check, not just
        # "key absent"): the network landing page shows a photo for each city.
        # Most per-city seeds don't set a city hero photo, so a hero photo set
        # later (in the database or admin) used to be wiped every time the seed
        # re-ran — the city card then fell back to an empty capsule on the
        # homepage. Many seeds DO pass `hero_photo_url` but as an empty string
        # (e.g. seed_hallandale_beach), which the "key not in doc" rule above
        # would treat as present and let overwrite a real saved photo with "".
        # So preserve an existing non-empty hero whenever the incoming doc would
        # leave it blank. (The live page also has its own curated fallback, so a
        # never-set city is never photoless — this just keeps the database
        # consistent with what the page renders.)
        if existing.get("hero_photo_url") and not doc.get("hero_photo_url"):
            doc["hero_photo_url"] = existing["hero_photo_url"]
        await db[collection_name].replace_one({"_id": existing["_id"]}, doc)
        return doc
    await db[collection_name].insert_one(doc)
    return doc


def category_groups(rows: List[Dict[str, Any]], order_start: int = 0) -> List[Dict[str, Any]]:
    """Normalize the raw category map definitions into Pydantic-friendly dicts."""
    out = []
    for i, r in enumerate(rows):
        out.append(
            {
                "slug": r["slug"],
                "name": r["name"],
                "description": r.get("description"),
                "examples": r.get("examples", []),
                "order": order_start + i,
                "sub_categories": [],
            }
        )
    return out


def run(coro):
    asyncio.run(coro)
