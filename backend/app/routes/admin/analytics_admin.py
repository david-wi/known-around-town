"""Admin analytics dashboard — site-wide traffic and conversion funnel.

Why this page exists: page view counts are collected on every business
listing visit but David had no way to see them without running a database
query by hand. This page gives him a self-serve view of which salons are
getting traffic, how far along the claim funnel submissions are, and
how many owner accounts have been created — so he can prioritise
outreach and measure progress toward the first subscriber.

Auth model: same admin cookie as the claims page.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_db
from app.routes.api.v1._auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

_templates: Optional[Jinja2Templates] = None




def attach_templates(t: Jinja2Templates) -> None:
    """Wire in the shared Jinja2 instance. Called from main.py after FastAPI
    is constructed, the same pattern used by claims_admin."""
    global _templates
    _templates = t


@router.get(
    "/analytics",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
async def analytics_page(request: Request) -> HTMLResponse:
    """Show site-wide stats: top listings by page views, claim funnel,
    owner account count, and Pro subscriber count."""
    if _templates is None:
        raise HTTPException(500, "Templates not attached")

    db = get_db()

    # WHY: Filter by network_id so every stat counts ALL beauty-network salons
    # across all 26 cities — not just Miami. The old filter used city_id for
    # the Miami city record, which showed only ~122 of the ~800+ beauty businesses.
    # We have 3 networks (beauty, health, wellness) in one database; without
    # this filter the numbers would mix all three.
    beauty_network = await db.networks.find_one({"slug": "beauty"})
    city_filter: Dict[str, Any] = (
        {"network_id": beauty_network["_id"]} if beauty_network else {}
    )

    # ── Page view stats ──────────────────────────────────────────────────────
    # Total views across beauty listings only
    pipeline_total = [
        {"$match": city_filter},
        {"$group": {"_id": None, "total": {"$sum": "$page_view_count"}}},
    ]
    total_views_result = await db.businesses.aggregate(pipeline_total).to_list(1)
    total_views: int = total_views_result[0]["total"] if total_views_result else 0

    # Top 20 most-visited listings
    top_listings: List[Dict[str, Any]] = await db.businesses.find(
        {**city_filter, "page_view_count": {"$gt": 0}},
        {"name": 1, "slug": 1, "neighborhood": 1, "page_view_count": 1, "featured": 1, "city_id": 1},
    ).sort("page_view_count", -1).limit(20).to_list(20)

    from app.services.tenant import build_absolute_business_url
    for biz in top_listings:
        biz["public_url"] = await build_absolute_business_url(request, biz)


    # Businesses with zero or no page_view_count field (not yet visited)
    total_biz: int = await db.businesses.count_documents(city_filter)

    # WHY: $or handles documents where the field is explicitly 0 AND documents
    # where the field has never been set (created before the counter was added).
    unvisited: int = await db.businesses.count_documents(
        {**city_filter, "$or": [{"page_view_count": {"$lte": 0}}, {"page_view_count": {"$exists": False}}]}
    )
    visited: int = total_biz - unvisited

    # ── Claim funnel ─────────────────────────────────────────────────────────
    # WHY: uses business_claims collection (same as claims_admin.py uses).
    total_claims: int = await db.business_claims.count_documents({})
    pending_claims: int = await db.business_claims.count_documents({"status": "pending"})
    # WHY: the claim verification endpoint stores the successful review state
    # as "verified"; the admin dashboard labels that business-facing outcome as
    # "approved" so David sees plain-language funnel counts.
    approved_claims: int = await db.business_claims.count_documents({"status": "verified"})
    rejected_claims: int = await db.business_claims.count_documents({"status": "rejected"})

    # ── Owner accounts ───────────────────────────────────────────────────────
    total_owners: int = await db.owner_accounts.count_documents({})

    # ── Subscriptions ────────────────────────────────────────────────────────
    pro_count: int = await db.businesses.count_documents({**city_filter, "featured.enabled": True})

    # ── Recent claims (last 10) ──────────────────────────────────────────────
    recent_claims: List[Dict[str, Any]] = await (
        # @define KAT-051 "Analytics dashboard"
        # WHY: include attribution fields so the admin dashboard can answer the
        # launch question: which approved outreach send produced this claim?
        db.business_claims.find(
            {},
            {
                "business_id": 1,
                "submitter_email": 1,
                "status": 1,
                "submitted_at": 1,
                "claim_source": 1,
                "claim_ref": 1,
                "utm_source": 1,
                "utm_medium": 1,
                "utm_campaign": 1,
            },
        )
        .sort("submitted_at", -1)
        .to_list(10)
    )
    # Enrich with business names
    recent_biz_ids = [c["business_id"] for c in recent_claims if c.get("business_id")]
    recent_businesses: Dict[str, Dict[str, Any]] = {}
    if recent_biz_ids:
        async for b in db.businesses.find({"_id": {"$in": recent_biz_ids}}, {"name": 1, "slug": 1}):
            recent_businesses[b["_id"]] = b

    return _templates.TemplateResponse(
        request,
        "admin/analytics.html",
        {
            "request": request,
            "total_views": total_views,
            "total_biz": total_biz,
            "visited": visited,
            "unvisited": unvisited,
            "top_listings": top_listings,
            "total_claims": total_claims,
            "pending_claims": pending_claims,
            "approved_claims": approved_claims,
            "rejected_claims": rejected_claims,
            "total_owners": total_owners,
            "pro_count": pro_count,
            "recent_claims": recent_claims,
            "recent_businesses": recent_businesses,
        },
    )
