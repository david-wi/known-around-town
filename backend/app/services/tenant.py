"""Resolve an incoming request's Host header into (network, city).

Domain config example: `beauty:knowsbeauty.ai.devintensive.com`
- A request to `miami.knowsbeauty.ai.devintensive.com` matches the beauty entry
  with city slug `miami`.
- A request to plain `knowsbeauty.ai.devintensive.com` matches the beauty entry
  with no city slug (the network-wide landing page).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request

from app.config import get_settings
from app.database import get_db


@dataclass
class TenantContext:
    network: dict
    city: Optional[dict]
    network_domain_suffix: str
    city_slug: Optional[str]

    @property
    def is_city_page(self) -> bool:
        return self.city is not None


def _strip_port(host: str) -> str:
    return host.split(":", 1)[0].lower().strip()


def _match_suffix(host: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (network_slug, suffix, city_slug) for the longest-suffix match."""
    pairs = sorted(
        get_settings().parse_network_domains(),
        key=lambda p: len(p[1]),
        reverse=True,
    )
    for net_slug, suffix in pairs:
        if host == suffix:
            return net_slug, suffix, None
        if host.endswith("." + suffix):
            sub = host[: -(len(suffix) + 1)]
            # Only the leftmost label is the city; if there are more dots,
            # we don't yet support nested subdomains.
            if "." in sub:
                continue
            # WHY: "stage-" / "preview-" prefixes let a parallel staging
            # deployment serve the same city content under a distinct
            # hostname (e.g. stage-miami.knowsbeauty.ai... renders Miami
            # so a reviewer can compare proposed changes side-by-side with
            # the live miami.knows... URL). The prefix is stripped before
            # the city lookup so no duplicate city records are needed.
            for prefix in ("stage-", "preview-"):
                if sub.startswith(prefix):
                    sub = sub[len(prefix):]
                    break
            return net_slug, suffix, sub
    return None, None, None


async def resolve_tenant(host: str) -> Optional[TenantContext]:
    host = _strip_port(host)
    # WHY: treat a leading "www." as an alias for the same host — a visitor
    # who types "www.miami.knowsbeauty.com" should get the Miami site, not a
    # 404. Without this, the suffix matcher strips the domain suffix, sees the
    # extra "www." label (sub = "www.miami"), rejects it as an unsupported
    # nested subdomain, and returns no tenant. Stripping the prefix here means
    # www.<city>.<network> resolves exactly like <city>.<network>.
    if host.startswith("www."):
        host = host[len("www."):]
    net_slug, suffix, city_slug = _match_suffix(host)
    if not net_slug:
        return None

    db = get_db()
    network = await db.networks.find_one({"slug": net_slug})
    if not network:
        return None

    city = None
    if city_slug:
        city = await db.cities.find_one(
            {"network_id": network["_id"], "slug": city_slug}
        )
        if not city:
            # Network domain matched but the city slug doesn't exist.
            return TenantContext(
                network=network,
                city=None,
                network_domain_suffix=suffix or "",
                city_slug=city_slug,
            )

    return TenantContext(
        network=network,
        city=city,
        network_domain_suffix=suffix or "",
        city_slug=city_slug,
    )


async def build_absolute_business_url(request: Request, business: dict) -> str:
    """Build the absolute public URL for a business, ensuring it points to the correct city subdomain,
    preserving any port, scheme, and staging/preview prefix from the request.
    
    If the business has no city or it cannot be resolved, falls back to a relative path.
    """
    city_id = business.get("city_id")
    if not city_id:
        return f"/b/{business.get('slug', '')}"

    db = get_db()
    city = await db.cities.find_one({"_id": city_id}, {"slug": 1})
    if not city or not city.get("slug"):
        return f"/b/{business.get('slug', '')}"

    city_slug = city["slug"]
    if city_slug == "wynwood":
        city_slug = "miami"

    request_host = request.headers.get("host", "")
    scheme = request.url.scheme or "https"

    port_suffix = ""
    if ":" in request_host:
        host_part, port_part = request_host.split(":", 1)
        port_suffix = f":{port_part}"
        request_host = host_part

    tenant = await resolve_tenant(request_host)
    if not tenant or not tenant.network_domain_suffix:
        return f"/b/{business.get('slug', '')}"

    suffix = tenant.network_domain_suffix

    prefix = ""
    for p in ("stage-", "preview-"):
        if request_host.startswith(p):
            prefix = p
            break

    return f"{scheme}://{prefix}{city_slug}.{suffix}{port_suffix}/b/{business.get('slug', '')}"
