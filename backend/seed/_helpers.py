"""Shared helpers for seed scripts."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

from app.config import get_settings
from app.database import ensure_indexes, get_db


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
