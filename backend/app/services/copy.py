"""Cascading lookup for editable wording (`copy_blocks`).

Lookup order (most specific wins):
  business -> category(city) -> city -> network -> global default
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple

from app.database import get_db
from app.models import CopyScopeType


DEFAULTS: Dict[str, str] = {
    # Home page
    "home.hero.eyebrow": "{city_name}'s curated local guide",
    "home.hero.headline": "{city_name}'s best-kept addresses.",
    "home.hero.subhead": "A curated guide to the places locals book before the moment.",
    "home.categories.title": "Explore by category",
    "home.neighborhoods.title": "Explore by neighborhood",
    "home.featured.title": "Featured this month",
    "home.editorial.title": "From the editors",
    # Category page
    "category.hero.eyebrow": "{category_name} in {city_name}",
    "category.hero.subhead": "The places locals book.",
    "category.empty.title": "We're still building this list.",
    "category.empty.body": "Check back soon. If you run a {category_name} business in {city_name}, get listed.",
    # Neighborhood page
    "neighborhood.hero.eyebrow": "{neighborhood_name}",
    "neighborhood.hero.subhead": "A neighborhood guide.",
    # Business profile
    "business.cta.book": "Book",
    "business.cta.call": "Call",
    "business.cta.website": "Visit website",
    "business.cta.directions": "Get directions",
    "business.claim.title": "Own this business?",
    "business.claim.body": "Claim this profile to update details, add photos, and reach customers.",
    "business.claim.cta": "Claim this listing",
    "business.section.known_for": "Known for",
    "business.section.best_for": "Best for",
    "business.section.before_booking": "Before you book",
    "business.section.services": "Services",
    "business.section.hours": "Hours",
    "business.section.contact": "Contact",
    "business.section.nearby": "Nearby",
    # Footer
    "footer.about.title": "About this guide",
    "footer.about.body": "{network_name} {city_name} is a curated local guide. Featured listings are clearly marked.",
    "footer.business.title": "For business owners",
    "footer.business.body": "Claim your profile or upgrade to a featured listing.",
    "footer.legal": "© {year} {network_name}.",
    # Badges
    "badge.editors_pick": "Editor's Pick",
    "badge.verified": "Verified",
    "badge.claimed": "Claimed",
    "badge.featured": "Featured",
    # Index disclosure
    "page.featured_disclosure": "Featured listings are paid placements. Editorial picks are not.",
}


def _scope_keys(
    network_id: Optional[str],
    city_id: Optional[str],
    category_slug: Optional[str],
    business_id: Optional[str],
    neighborhood_slug: Optional[str],
) -> Iterable[Tuple[str, Dict[str, str]]]:
    """Yield (scope_type, scope_ref) pairs from most specific to least."""
    if business_id:
        yield CopyScopeType.business.value, {"business_id": business_id}
    if category_slug and city_id:
        yield CopyScopeType.category.value, {"city_id": city_id, "category_slug": category_slug}
    if neighborhood_slug and city_id:
        yield CopyScopeType.neighborhood.value, {"city_id": city_id, "neighborhood_slug": neighborhood_slug}
    if city_id:
        yield CopyScopeType.city.value, {"city_id": city_id}
    if network_id:
        yield CopyScopeType.network.value, {"network_id": network_id}
    yield CopyScopeType.global_.value, {}


async def get_copy(
    key: str,
    *,
    network_id: Optional[str] = None,
    city_id: Optional[str] = None,
    category_slug: Optional[str] = None,
    business_id: Optional[str] = None,
    neighborhood_slug: Optional[str] = None,
    locale: str = "en-US",
    fmt: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    db = get_db()
    now = datetime.now(timezone.utc)

    for scope_type, scope_ref in _scope_keys(
        network_id, city_id, category_slug, business_id, neighborhood_slug
    ):
        query = {
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "key": key,
            "locale": locale,
            "$or": [
                {"active_from": None},
                {"active_from": {"$lte": now}},
            ],
        }
        # `active_until` filter applied separately to keep $or simple.
        doc = await db.copy_blocks.find_one(query)
        if doc and (doc.get("active_until") is None or doc["active_until"] >= now):
            return _format(doc["value"], fmt)

    # WHY: returning None (rather than the key string) lets callers use the
    # idiomatic `await copy.get(key) or "fallback"` pattern. Returning the key
    # string previously caused literal "header.owners_cta" text to render when
    # neither a copy block nor a DEFAULTS entry existed.
    default = DEFAULTS.get(key)
    if default is None:
        return None
    return _format(default, fmt)


def _format(template: Optional[str], fmt: Optional[Dict[str, str]]) -> Optional[str]:
    if template is None:
        return None
    if not fmt:
        return template
    try:
        return template.format(**fmt)
    except (KeyError, IndexError):
        return template


class CopyResolver:
    """Per-request helper that bakes in the current tenant scope."""

    def __init__(
        self,
        *,
        network_id: Optional[str] = None,
        city_id: Optional[str] = None,
        network_name: str = "",
        city_name: str = "",
        locale: str = "en-US",
    ) -> None:
        self.network_id = network_id
        self.city_id = city_id
        self.network_name = network_name
        self.city_name = city_name
        self.locale = locale

    async def get(
        self,
        key: str,
        *,
        category_slug: Optional[str] = None,
        category_name: Optional[str] = None,
        business_id: Optional[str] = None,
        neighborhood_slug: Optional[str] = None,
        neighborhood_name: Optional[str] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        fmt = {
            "network_name": self.network_name,
            "city_name": self.city_name,
            "category_name": category_name or "",
            "neighborhood_name": neighborhood_name or "",
            "year": str(datetime.now(timezone.utc).year),
        }
        if extra:
            fmt.update(extra)
        return await get_copy(
            key,
            network_id=self.network_id,
            city_id=self.city_id,
            category_slug=category_slug,
            business_id=business_id,
            neighborhood_slug=neighborhood_slug,
            locale=self.locale,
            fmt=fmt,
        )
