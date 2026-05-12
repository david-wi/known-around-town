"""All MongoDB document schemas as Pydantic models.

Conventions:
- `_id` is a string UUID (string for portability, generated client-side).
- Timestamps are timezone-aware UTC datetimes.
- Status fields are explicit string enums; we never write raw strings outside this file.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- enums --------------------------------------------------------------

class PublishStatus(str, Enum):
    draft = "draft"
    live = "live"
    archived = "archived"


class ClaimStatus(str, Enum):
    unclaimed = "unclaimed"
    pending = "pending"
    claimed = "claimed"
    verified = "verified"


class FeaturedTier(str, Enum):
    free = "free"
    enhanced = "enhanced"
    premium = "premium"


class IndexStatus(str, Enum):
    indexed = "indexed"
    noindex = "noindex"
    thin = "thin"


class IndexOverride(str, Enum):
    auto = "auto"
    force_index = "force_index"
    force_noindex = "force_noindex"


class CopyScopeType(str, Enum):
    global_ = "global"
    network = "network"
    city = "city"
    neighborhood = "neighborhood"
    category = "category"
    business = "business"


# ---- sub-documents ------------------------------------------------------

class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "US"
    lat: Optional[float] = None
    lng: Optional[float] = None


class Socials(BaseModel):
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    facebook: Optional[str] = None
    x: Optional[str] = None
    youtube: Optional[str] = None
    linkedin: Optional[str] = None


class HoursEntry(BaseModel):
    day: str  # mon|tue|wed|thu|fri|sat|sun
    opens_at: Optional[str] = None  # "09:00"
    closes_at: Optional[str] = None  # "18:00"
    closed: bool = False


class ServiceItem(BaseModel):
    name: str
    description: Optional[str] = None
    price_from: Optional[float] = None
    price_to: Optional[float] = None
    currency: str = "USD"
    duration_min: Optional[int] = None


class Photo(BaseModel):
    url: str
    alt: Optional[str] = None
    caption: Optional[str] = None
    credit: Optional[str] = None
    order: int = 0
    is_hero: bool = False


class Featured(BaseModel):
    enabled: bool = False
    tier: FeaturedTier = FeaturedTier.free
    until: Optional[datetime] = None


class Theme(BaseModel):
    primary_color: str = "#1a1a1a"
    accent_color: str = "#c89f5b"
    body_font: str = "Inter, system-ui, sans-serif"
    display_font: str = "Playfair Display, Georgia, serif"
    hero_treatment: str = "dark"  # dark | light | gradient


class NetworkCategoryGroup(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    examples: List[str] = Field(default_factory=list)
    order: int = 0
    sub_categories: List["NetworkCategoryGroup"] = Field(default_factory=list)


NetworkCategoryGroup.model_rebuild()


class EditorialHeadline(BaseModel):
    headline: str
    active_from: Optional[datetime] = None
    active_until: Optional[datetime] = None
    is_default: bool = False


# ---- documents ----------------------------------------------------------

class Network(BaseModel):
    """A vertical brand: Beauty, Wellness, Health, Fitness, Pets, etc.

    `domains` lists every hostname suffix that resolves to this network. The
    server matches a request's Host header against these suffixes; whatever
    comes before the suffix is treated as the city slug.
    """
    id: str = Field(default_factory=_id, alias="_id")
    slug: str
    name: str
    tagline: Optional[str] = None
    description: Optional[str] = None
    domains: List[str] = Field(default_factory=list)
    theme: Theme = Field(default_factory=Theme)
    category_map: List[NetworkCategoryGroup] = Field(default_factory=list)
    badge_policy: Dict[str, Any] = Field(default_factory=dict)
    sensitive_content_review: bool = False
    status: PublishStatus = PublishStatus.draft
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class City(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    network_id: str
    slug: str
    name: str
    state: Optional[str] = None
    country: str = "US"
    timezone: str = "America/New_York"
    tagline: Optional[str] = None
    hero_description: Optional[str] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    editorial_headlines: List[EditorialHeadline] = Field(default_factory=list)
    domain_override: Optional[str] = None
    status: PublishStatus = PublishStatus.draft
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class Neighborhood(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    city_id: str
    slug: str
    name: str
    description: Optional[str] = None
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    hero_description: Optional[str] = None
    order: int = 0
    status: PublishStatus = PublishStatus.live
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class Category(BaseModel):
    """A city-scoped instance of one of the network's master categories.

    Stored per-city so wording, examples, and even SEO copy can be customized
    locally without affecting other cities.
    """
    id: str = Field(default_factory=_id, alias="_id")
    network_id: str
    city_id: str
    slug: str
    parent_slug: Optional[str] = None
    name: str
    description: Optional[str] = None
    editorial_blurb: Optional[str] = None
    examples: List[str] = Field(default_factory=list)
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    order: int = 0
    status: PublishStatus = PublishStatus.live
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class Business(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    network_id: str
    city_id: str
    slug: str
    name: str
    legal_name: Optional[str] = None
    category_slugs: List[str] = Field(default_factory=list)
    neighborhood_slugs: List[str] = Field(default_factory=list)
    address: Address = Field(default_factory=Address)
    service_area_text: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    booking_url: Optional[str] = None
    socials: Socials = Field(default_factory=Socials)
    hours: List[HoursEntry] = Field(default_factory=list)
    services: List[ServiceItem] = Field(default_factory=list)
    photos: List[Photo] = Field(default_factory=list)
    short_description: Optional[str] = None
    known_for: Optional[str] = None
    best_for: Optional[str] = None
    before_booking_notes: Optional[str] = None
    price_cues: Optional[str] = None  # "$", "$$", "$$$", "$$$$"
    review_themes_summary: Optional[str] = None
    nearby_business_ids: List[str] = Field(default_factory=list)
    claim_status: ClaimStatus = ClaimStatus.unclaimed
    claimed_by_user_id: Optional[str] = None
    claimed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    featured: Featured = Field(default_factory=Featured)
    editors_pick: bool = False
    index_status: IndexStatus = IndexStatus.thin
    index_override: IndexOverride = IndexOverride.auto
    meta_title_override: Optional[str] = None
    meta_description_override: Optional[str] = None
    schema_org_type: str = "LocalBusiness"
    data_source: str = "imported"  # imported | owner_submitted | editorial
    import_source: Optional[str] = None
    import_data: Optional[Dict[str, Any]] = None
    quality_score: int = 0
    status: PublishStatus = PublishStatus.draft
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class CopyBlock(BaseModel):
    """A single editable piece of wording.

    `scope_type` + `scope_ref` together say where this block applies. `key`
    identifies the surface (for example `home.hero.eyebrow`). At render time
    the server tries the most specific scope first and falls back outward
    until it finds a match or returns the bundled default.
    """
    id: str = Field(default_factory=_id, alias="_id")
    scope_type: CopyScopeType
    scope_ref: Dict[str, str] = Field(default_factory=dict)
    key: str
    value: str
    locale: str = "en-US"
    active_from: Optional[datetime] = None
    active_until: Optional[datetime] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class EditorialGuide(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    network_id: str
    city_id: str
    slug: str
    title: str
    subtitle: Optional[str] = None
    hero_image_url: Optional[str] = None
    body_markdown: str = ""
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    featured_business_ids: List[str] = Field(default_factory=list)
    seo_title: Optional[str] = None
    meta_description: Optional[str] = None
    published_at: Optional[datetime] = None
    status: PublishStatus = PublishStatus.draft
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}


class BusinessClaim(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    business_id: str
    submitter_name: str
    submitter_email: str
    submitter_phone: Optional[str] = None
    relationship: Optional[str] = None
    verification_method: Optional[str] = None
    verification_token: Optional[str] = None
    status: str = "pending"  # pending | verified | rejected
    submitted_at: datetime = Field(default_factory=_now)
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class BusinessInquiry(BaseModel):
    id: str = Field(default_factory=_id, alias="_id")
    business_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: str
    referrer_url: Optional[str] = None
    submitted_at: datetime = Field(default_factory=_now)

    model_config = {"populate_by_name": True}
