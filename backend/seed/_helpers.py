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
_CATEGORY_PHOTOS: Dict[str, List[str]] = {
    "hair": [
        "1522337360788-8b13dee7a37e", "1560066984-138dadb4c035", "1562322140-8baeececf3df",
        "1595476108010-b4d1f102b1b1", "1605497788044-5a32c7078486", "1521590832167-7bcbfaa6381f",
    ],
    "nails": [
        "1604654894610-df63bc536371", "1604654894517-85b5bb6ef18d", "1604654894468-a4c600c60c6b",
        "1559757148-5c350d0d3c56", "1571019613454-1cb2f99b2d8b",
    ],
    "spa": [
        "1540555700478-4be289fbecef", "1544161515-4c0d0de6e43a", "1545205597-3d9d02c29597",
        "1576091160550-2173dba999ef", "1606811971618-4486d14f3f99",
    ],
    "barber": [
        "1599351431202-1e0f0137899a", "1585747860715-2ba37e788b70",
        "1503951914875-452162b0f3f1", "1521119989659-3bd22a06cba8",
    ],
    "lash-brow": [
        "1583241800698-e8ab01830a07", "1577527843344-8e51c4da1cce",
        "1487070183336-b863922373d4", "1533236898036-2d4b83a3c8a9",
    ],
    "med-spa": [
        "1570172619644-dfd03ed5d881", "1576091160400-aa43de2d1fce",
        "1527613788048-8a20a56e7a07", "1588776814546-1ffedbe47ada",
    ],
    "waxing": [
        "1556228852-80b6e5eeff06", "1560750588-73207b1ef5b8",
        "1509042239860-f550ce710b93", "1571019614242-c5c5dee9f50b",
    ],
    "makeup": [
        "1487070183336-b863922373d4", "1512207736890-6ffed8a84e8d",
        "1522338242992-e1d3aedef060", "1583241475307-44a34c96a4e5",
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
        _PRESERVE_KEYS = ("google_place_id", "google_rating", "google_review_count",
                          "google_rating_synced_at", "hours")
        for key in _PRESERVE_KEYS:
            if key in existing and key not in doc:
                doc[key] = existing[key]
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
