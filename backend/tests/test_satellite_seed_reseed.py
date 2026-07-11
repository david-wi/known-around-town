"""Disposable canary for the satellite city replacement writers.

The Miami writer already has a live-state regression test. This canary covers
three representative rows in each of the four satellite writers so the shared
replacement boundary cannot drift back to a short, incomplete field list.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import re

import pytest

from seed import seed_aventura, seed_coral_gables, seed_south_beach, seed_sunny_isles


# WHY: twelve satellite rows plus the Miami control row in the helper regression
# cover the 13-row disposable manifest without making production-sized city
# seeds the assertion surface. Each satellite writer still runs its complete
# local fixture seed.
SATELLITE_CANARY = (
    ("aventura", seed_aventura, (0, 1, 2)),
    ("coral-gables", seed_coral_gables, (0, 1, 2)),
    ("south-beach", seed_south_beach, (0, 1, 2)),
    ("sunny-isles-beach", seed_sunny_isles, (0, 1, 2)),
)


def test_every_deploy_invoked_business_replacer_uses_shared_preservation_helper():
    """Every city replacement writer must use the one reviewed live-state policy."""
    backend_root = Path(__file__).parents[1]
    seed_root = backend_root / "seed"
    deploy_script = backend_root.parent / "scripts" / "deploy.sh"
    deployed_modules = {
        match.group(1)
        for match in re.finditer(r"python -m seed\.(seed_[a-z_]+)", deploy_script.read_text())
    }
    writer_modules = {
        path.stem
        for path in seed_root.glob("seed_*.py")
        if "businesses.replace_one" in path.read_text()
    }

    deployed_writer_modules = writer_modules & deployed_modules
    assert deployed_writer_modules, "deploy.sh must invoke at least one city replacement writer"
    # Sunny Isles is intentionally covered by the helper and canary but is not
    # currently in the production deploy list. Any other mismatch means a new
    # writer was added without an explicit deploy decision and must fail review.
    assert writer_modules - deployed_modules == {"seed_sunny_isles"}, (
        "unexpected deploy-list coverage drift: "
        f"{sorted(writer_modules - deployed_modules)}"
    )
    # Validate all writers, including a city module kept out of the current
    # deploy list, so a later deploy-list expansion cannot bypass this policy.
    for module_name in sorted(writer_modules):
        source = (seed_root / f"{module_name}.py").read_text()
        tree = ast.parse(source, filename=module_name)
        helper_imported = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "seed._helpers"
            and any(alias.name == "preserve_existing_business_state" for alias in node.names)
            for node in ast.walk(tree)
        )
        helper_called = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "preserve_existing_business_state"
            for node in ast.walk(tree)
        )
        assert helper_imported, f"{module_name} does not import the shared helper"
        assert helper_called, f"{module_name} does not call the shared helper"


def _source_row(module, index: int) -> dict:
    return module.BUSINESSES[index]


async def _business_for_source(db, city_slug: str, module, index: int) -> dict:
    city = await db.cities.find_one({"slug": city_slug})
    assert city is not None
    source = _source_row(module, index)
    business = await db.businesses.find_one(
        {"city_id": city["_id"], "slug": source["slug"]}
    )
    assert business is not None, f"missing seeded canary row {city_slug}/{source['slug']}"
    return business


def _source_photo(module, source: dict) -> str:
    return module.pick_category_photo(source["slug"], source["category_slugs"][0])


@pytest.mark.asyncio
async def test_satellite_reseed_canary_preserves_state_and_refreshes_source(seeded_db):
    """All four replacement loops preserve live state and remain idempotent."""
    # @define-test KAT-052 "Satellite reseeding preserves live operational state"
    for _city_slug, module, _indexes in SATELLITE_CANARY:
        await module.main()

    # Save three rows per city before mutating the live records. The first row
    # exercises archived/owner state, the second paid/voice state, and the third
    # proves ordinary source fields and the representative photo still refresh.
    cases = []
    for city_slug, module, indexes in SATELLITE_CANARY:
        for row_number, index in enumerate(indexes):
            source = _source_row(module, index)
            existing = await _business_for_source(seeded_db, city_slug, module, index)
            stable_created_at = existing["created_at"]
            old_source_photo = {"url": f"https://old-source.example/{source['slug']}.jpg"}
            update = {
                "name": f"Old {source['name']}",
                "address": {"street": "Old source address", "city": "Miami", "state": "FL"},
                "category_slugs": ["old-category"],
                "neighborhood_slugs": ["old-neighborhood"],
                "short_description": "Old source description",
                "photos": [old_source_photo],
            }
            expected_live = {}
            if row_number == 0:
                expected_live = {
                    "status": "archived",
                    "claim_status": "verified",
                    "claimed_email": f"owner+{city_slug}@example.com",
                    "claimed_by_user_id": f"owner-{city_slug}",
                    # mongomock stores timezone-aware datetimes as naive values;
                    # the production invariant is the timestamp itself.
                    "claimed_at": datetime(2026, 7, 1),
                    "verified_at": datetime(2026, 7, 2),
                    "stripe_customer_id": f"cus-{city_slug}",
                    "stripe_subscription_id": f"sub-{city_slug}",
                    "is_founding_partner": True,
                    "phone": "(305) 555-0100",
                    "website": "https://owner.example/claimed",
                    "instagram": "@owner_claimed",
                    "socials": {
                        "instagram": "@owner_claimed",
                        "facebook": "https://facebook.example/claimed",
                    },
                    "email": f"contact+{city_slug}@example.com",
                    "facebook": "https://facebook.example/claimed",
                    "booking_url": "https://booking.example/claimed",
                    "hours": [{"day": "Mon", "open": "10:00", "close": "18:00"}],
                    "services": [{"name": "Owner service", "price_from": 80}],
                    "page_view_count": 41,
                    "mkb_referred_view_count": 17,
                    "call_click_count": 5,
                    "directions_click_count": 6,
                    "website_click_count": 7,
                    "google_place_id": f"place-{city_slug}",
                    "google_rating": 4.9,
                    "google_review_count": 321,
                    "google_rating_synced_at": datetime(2026, 7, 3),
                    "featured": {"enabled": True, "tier": "premium"},
                    "voice_phone_number": "(669) 232-8894",
                    "vapi_phone_number_id": f"phone-{city_slug}",
                    "vapi_assistant_id": f"assistant-{city_slug}",
                }
                # Include a prior seed photo beside the owner upload: the
                # source photo must refresh while the GridFS photo remains.
                update["photos"] = [
                    old_source_photo,
                    {"url": f"/media/owner-{city_slug}", "is_hero": True},
                ]
            elif row_number == 1:
                expected_live = {
                    "claim_status": "claimed",
                    "stripe_customer_id": f"cus-featured-{city_slug}",
                    "stripe_subscription_id": f"sub-featured-{city_slug}",
                    "featured": {"enabled": True, "tier": "concierge"},
                    "voice_phone_number": "(669) 232-8895",
                    "vapi_phone_number_id": f"phone-featured-{city_slug}",
                    "vapi_assistant_id": f"assistant-featured-{city_slug}",
                    "page_view_count": 99,
                    "mkb_referred_view_count": 40,
                    "call_click_count": 8,
                    "directions_click_count": 9,
                    "website_click_count": 10,
                    "is_founding_partner": True,
                    "google_place_id": f"place-featured-{city_slug}",
                    "google_rating": 4.8,
                    "google_review_count": 222,
                }
            else:
                expected_live = {"claim_status": "unclaimed"}

            update.update(expected_live)
            await seeded_db.businesses.update_one({"_id": existing["_id"]}, {"$set": update})
            cases.append(
                {
                    "city_slug": city_slug,
                    "module": module,
                    "source": source,
                    "existing_id": existing["_id"],
                    "created_at": stable_created_at,
                        "expected_live": expected_live,
                        "old_source_photo": old_source_photo,
                        "owner_photo": row_number == 0,
                }
            )

    # First replacement run: every writer must use the shared preservation policy.
    for _city_slug, module, _indexes in SATELLITE_CANARY:
        await module.main()

    first_results = []
    for case in cases:
        result = await _business_for_source(
            seeded_db, case["city_slug"], case["module"],
            case["module"].BUSINESSES.index(case["source"]),
        )
        source = case["source"]
        assert result["_id"] == case["existing_id"]
        assert result["created_at"] == case["created_at"]
        assert result["name"] == source["name"]
        assert result["address"] == source["address"]
        assert result["category_slugs"] == source["category_slugs"]
        assert result["neighborhood_slugs"] == source.get("neighborhood_slugs", [])
        assert result["short_description"] == source["short_description"]
        for field, expected in case["expected_live"].items():
            assert result[field] == expected, f"{case['city_slug']}/{source['slug']} lost {field}"

        source_photo = _source_photo(case["module"], source)
        photo_urls = [photo.get("url") for photo in result.get("photos", [])]
        assert source_photo in photo_urls
        assert case["old_source_photo"] not in result.get("photos", [])
        if case["owner_photo"]:
            assert f"/media/owner-{case['city_slug']}" in photo_urls

        city = await seeded_db.cities.find_one({"slug": case["city_slug"]})
        assert await seeded_db.businesses.count_documents(
            {"city_id": city["_id"], "slug": source["slug"]}
        ) == 1
        first_results.append(result)

    # Second replacement run: stable identity and every preserved/source field
    # must remain unchanged, and the writer must not create duplicate listings.
    for _city_slug, module, _indexes in SATELLITE_CANARY:
        await module.main()
    for case, first in zip(cases, first_results):
        second = await _business_for_source(
            seeded_db, case["city_slug"], case["module"],
            case["module"].BUSINESSES.index(case["source"]),
        )
        for field in (
            "_id", "created_at", "name", "address", "category_slugs",
            "neighborhood_slugs", "short_description", "status", "claim_status",
            "claimed_email", "stripe_customer_id", "stripe_subscription_id",
            "featured", "voice_phone_number", "vapi_phone_number_id",
            "vapi_assistant_id", "page_view_count", "mkb_referred_view_count",
            "call_click_count", "directions_click_count", "website_click_count",
            "services", "hours", "photos",
        ):
            assert second.get(field) == first.get(field), (
                f"{case['city_slug']}/{case['source']['slug']} is not idempotent for {field}"
            )
        city = await seeded_db.cities.find_one({"slug": case["city_slug"]})
        assert await seeded_db.businesses.count_documents(
            {"city_id": city["_id"], "slug": case["source"]["slug"]}
        ) == 1
