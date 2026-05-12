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
            return net_slug, suffix, sub
    return None, None, None


async def resolve_tenant(host: str) -> Optional[TenantContext]:
    host = _strip_port(host)
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
