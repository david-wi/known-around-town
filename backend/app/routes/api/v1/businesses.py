from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database import get_db
from app.models import Business, PublishStatus
from app.mongo_ids import business_id_value
from app.responses import MongoSafeJSONResponse
from app.routes.api.v1._auth import require_admin
from app.routes.api.v1._crud import now_utc, to_doc
from app.services.content import invalidate_nav_after_business_write

router = APIRouter(prefix="/businesses", tags=["businesses"])

_PUBLIC_BUSINESS_FIELDS = frozenset(
    {
        "_id",
        "network_id",
        "city_id",
        "slug",
        "name",
        "legal_name",
        "category_slugs",
        "neighborhood_slugs",
        "address",
        "service_area_text",
        "phone",
        "website",
        "email",
        "booking_url",
        "socials",
        "hours",
        "services",
        "photos",
        "category_blurbs",
        "description",
        "short_description",
        "editorial_blurb",
        "editor_blurb",
        "known_for",
        "best_for",
        "before_booking_notes",
        "price_cues",
        "review_themes_summary",
        "google_rating",
        "google_review_count",
        "hide_ratings",
        "nearby_business_ids",
        "voice_phone_number",
        "claim_status",
        "featured",
        "editors_pick",
        "schema_org_type",
        "meta_title_override",
        "meta_description_override",
        "status",
        "created_at",
        "updated_at",
    }
)


class BusinessPatch(BaseModel):
    """Validate navigation fields while preserving established admin extras."""

    city_id: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[PublishStatus] = None
    neighborhood_slugs: Optional[List[str]] = None

    # WHY: legacy admin clients update stored fields that predate the Business
    # model. Keep those fields compatible while validating navigation inputs.
    model_config = {"extra": "allow"}

    @field_validator("city_id")
    @classmethod
    def validate_city_id(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("city_id must be a non-empty canonical identifier")
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _is_canonical_slug(value):
            raise ValueError("slug must be canonical lowercase text")
        return value

    @field_validator("neighborhood_slugs")
    @classmethod
    def validate_neighborhood_slugs(
        cls, value: Optional[List[str]]
    ) -> Optional[List[str]]:
        if value is None:
            return None
        normalized: List[str] = []
        for slug in value:
            if not _is_canonical_slug(slug):
                raise ValueError(
                    "neighborhood_slugs must contain canonical lowercase slugs"
                )
            if slug not in normalized:
                normalized.append(slug)
        return normalized


def _is_canonical_slug(value: str) -> bool:
    return (
        bool(value)
        and value == value.strip().lower()
        and all(segment and segment.isalnum() for segment in value.split("-"))
    )


async def _validate_neighborhood_assignment(
    db, city_id: Optional[str], neighborhood_slugs: List[str]
) -> None:
    city = await db.cities.find_one({"_id": city_id}) if city_id else None
    if not city or city.get("status") == "archived":
        raise HTTPException(404, "City not found")
    if not neighborhood_slugs:
        return
    neighborhood_docs = await db.neighborhoods.find(
        {
            "city_id": city_id,
            "slug": {"$in": neighborhood_slugs},
            "status": {"$ne": "archived"},
        },
        {"slug": 1},
    ).to_list(length=len(neighborhood_slugs))
    found_slugs = {doc["slug"] for doc in neighborhood_docs}
    if found_slugs != set(neighborhood_slugs):
        raise HTTPException(422, "Every neighborhood must belong to the selected city")


def _public_business(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return only shopper-safe fields from a business document.

    # @define KAT-075 "Revenue-path security hardening"
    """
    public = {key: doc[key] for key in _PUBLIC_BUSINESS_FIELDS if key in doc}
    if public.get("hide_ratings"):
        public.pop("google_rating", None)
        public.pop("google_review_count", None)
    return public


async def _city_is_public(city_id: str) -> bool:
    city = await get_db().cities.find_one({"_id": city_id}, {"status": 1})
    return bool(city and city.get("status") != "archived")


@router.get("")
async def list_businesses(
    city_id: str = Query(...),
    category_slug: Optional[str] = Query(default=None),
    neighborhood_slug: Optional[str] = Query(default=None),
    featured_only: bool = Query(default=False),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=60, le=200),
    offset: int = Query(default=0, ge=0),
) -> List[Dict[str, Any]]:
    if not await _city_is_public(city_id):
        return MongoSafeJSONResponse([])
    if status and status != "live":
        return MongoSafeJSONResponse([])
    q: Dict[str, Any] = {"city_id": city_id, "status": "live"}
    if category_slug:
        q["category_slugs"] = category_slug
    if neighborhood_slug:
        q["neighborhood_slugs"] = neighborhood_slug
    if featured_only:
        q["featured.enabled"] = True
    cur = (
        get_db()
        .businesses.find(q)
        .sort(
            [
                ("featured.enabled", -1),
                ("editors_pick", -1),
                ("quality_score", -1),
                ("name", 1),
            ]
        )
        .skip(offset)
        .limit(limit)
    )
    docs = await cur.to_list(length=limit)
    return MongoSafeJSONResponse([_public_business(doc) for doc in docs])


@router.get("/by-slug/{city_id}/{slug}")
async def get_business_by_slug(city_id: str, slug: str) -> Dict[str, Any]:
    if not await _city_is_public(city_id):
        raise HTTPException(404, "Business not found")
    doc = await get_db().businesses.find_one(
        {"city_id": city_id, "slug": slug, "status": "live"}
    )
    if not doc:
        raise HTTPException(404, "Business not found")
    return MongoSafeJSONResponse(_public_business(doc))


@router.get("/{business_id}")
async def get_business(business_id: str) -> Dict[str, Any]:
    db = get_db()
    doc = await db.businesses.find_one(
        {"_id": business_id_value(business_id), "status": "live"}
    )
    if doc and not await _city_is_public(doc.get("city_id", "")):
        doc = None
    if not doc:
        raise HTTPException(404, "Business not found")
    return MongoSafeJSONResponse(_public_business(doc))


@router.post("", dependencies=[Depends(require_admin)])
async def create_business(body: Business) -> Dict[str, Any]:
    doc = to_doc(body)
    db = get_db()
    if not _is_canonical_slug(doc["slug"]):
        raise HTTPException(422, "Business slug must be canonical lowercase text")
    validated_assignment = BusinessPatch(
        city_id=doc["city_id"],
        neighborhood_slugs=doc.get("neighborhood_slugs", []),
    )
    doc["neighborhood_slugs"] = validated_assignment.neighborhood_slugs or []
    await _validate_neighborhood_assignment(
        db, doc["city_id"], doc["neighborhood_slugs"]
    )
    if await db.businesses.find_one({"city_id": doc["city_id"], "slug": doc["slug"]}):
        raise HTTPException(409, "Business slug already exists in this city")
    try:
        await db.businesses.insert_one(doc)
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, "A business already uses one of these unique values"
        ) from exc
    # @define KAT-010 "Neighborhood browsing follows current live businesses"
    # WHY: a newly live business can make one or more neighborhood links
    # eligible immediately; clear this worker's short-lived public-nav cache.
    invalidate_nav_after_business_write()
    return MongoSafeJSONResponse(doc)


@router.patch("/{business_id}", dependencies=[Depends(require_admin)])
async def update_business(business_id: str, patch: BusinessPatch) -> Dict[str, Any]:
    db = get_db()
    if {"_id", "id"}.intersection(patch.model_extra or {}):
        raise HTTPException(422, "A business identifier cannot be changed")
    submitted_fields = patch.model_fields_set
    navigation_fields = {"city_id", "slug", "status", "neighborhood_slugs"}
    if any(
        field in submitted_fields and getattr(patch, field) is None
        for field in navigation_fields
    ):
        raise HTTPException(422, "Navigation fields cannot be null")
    updates = to_doc(patch)
    updates["updated_at"] = now_utc()
    update_filter: Dict[str, Any] = {"_id": business_id_value(business_id)}
    identity_fields = {"city_id", "neighborhood_slugs", "slug"}
    publishing_live = (
        "status" in submitted_fields and updates.get("status") == PublishStatus.live
    )
    if identity_fields.intersection(submitted_fields) or publishing_live:
        existing = await db.businesses.find_one(
            update_filter, {"city_id": 1, "neighborhood_slugs": 1, "slug": 1}
        )
        if not existing:
            raise HTTPException(404, "Business not found")
        target_city_id = updates.get("city_id", existing.get("city_id"))
        target_slugs = updates.get(
            "neighborhood_slugs", existing.get("neighborhood_slugs", [])
        )
        if (
            {"city_id", "neighborhood_slugs"}.intersection(submitted_fields)
            or publishing_live
        ):
            await _validate_neighborhood_assignment(db, target_city_id, target_slugs)
        target_business_slug = updates.get("slug", existing.get("slug"))
        if not _is_canonical_slug(target_business_slug):
            raise HTTPException(422, "Business slug must be canonical lowercase text")
        if (
            {"city_id", "slug"}.intersection(submitted_fields) or publishing_live
        ) and await db.businesses.find_one(
            {
                "_id": {"$ne": update_filter["_id"]},
                "city_id": target_city_id,
                "slug": target_business_slug,
            },
            {"_id": 1},
        ):
            raise HTTPException(409, "Business slug already exists in this city")
        # WHY: if the city changes while assignment validation is in flight,
        # fail instead of applying slugs or a business slug validated against
        # the former city.
        update_filter["city_id"] = existing.get("city_id")
        if "neighborhood_slugs" not in submitted_fields:
            # WHY: a city-only move validates the business's current neighborhoods
            # against the destination city. Guard that snapshot so a concurrent
            # neighborhood edit cannot cross into the new city unvalidated.
            update_filter["neighborhood_slugs"] = existing.get(
                "neighborhood_slugs", {"$exists": False}
            )
        if (
            "city_id" in submitted_fields or publishing_live
        ) and "slug" not in submitted_fields:
            # WHY: a city move checks the current slug in the destination.
            # Reject a concurrent slug edit rather than moving an unchecked slug.
            update_filter["slug"] = existing.get("slug")
    # WHY: changing only submitted fields atomically prevents an unrelated edit
    # from restoring stale status/city/neighborhood values written concurrently.
    try:
        updated = await db.businesses.find_one_and_update(
            update_filter,
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, "A business already uses one of these unique values"
        ) from exc
    if not updated:
        if "city_id" in update_filter and await db.businesses.find_one(
            {"_id": update_filter["_id"]}, {"_id": 1}
        ):
            raise HTTPException(409, "Business assignment changed; retry the update")
        raise HTTPException(404, "Business not found")
    # @define KAT-010 "Neighborhood browsing follows current live businesses"
    # WHY: status, city, and neighborhood assignment changes alter public
    # neighborhood eligibility; unrelated profile edits do not.
    invalidate_nav_after_business_write(submitted_fields)
    return MongoSafeJSONResponse(updated)


@router.delete("/{business_id}", dependencies=[Depends(require_admin)])
async def archive_business(business_id: str) -> Dict[str, str]:
    db = get_db()
    res = await db.businesses.update_one(
        {"_id": business_id_value(business_id)},
        {"$set": {"status": "archived", "updated_at": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Business not found")
    # @define KAT-010 "Neighborhood browsing follows current live businesses"
    # WHY: archiving the final live business in a neighborhood removes that
    # public link, so invalidate the local navigation cache immediately.
    invalidate_nav_after_business_write()
    return {"status": "archived"}
