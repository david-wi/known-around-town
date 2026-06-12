"""Site-wide settings stored in MongoDB, editable from the admin UI.

All settings live in a single document at ``site_settings._id == "global"``.
The DB value takes precedence over the corresponding env var so the admin web
interface can override defaults without a redeploy or server command.
"""

from __future__ import annotations

from typing import Any, Dict

from app.database import get_db

# WHY: "global" is the one document that holds all site-level settings.
# There is intentionally only one document per site — not one per tenant.
# If multi-tenant settings are ever needed, the schema will need a
# network_id key; for now a single document is simpler and fast.
_SETTINGS_ID = "global"


async def get_all_site_settings() -> Dict[str, Any]:
    """Return the current site settings document, or an empty dict if not yet set."""
    doc = await get_db().site_settings.find_one({"_id": _SETTINGS_ID})
    if doc is None:
        return {}
    doc.pop("_id", None)
    return doc


async def get_site_setting(key: str, default: Any = None) -> Any:
    """Return a single setting value, or *default* when not set."""
    doc = await get_db().site_settings.find_one(
        {"_id": _SETTINGS_ID},
        {key: 1},
    )
    if doc is None or key not in doc:
        return default
    return doc[key]


async def update_site_settings(updates: Dict[str, Any]) -> None:
    """Persist one or more settings values. Creates the document if it doesn't exist."""
    await get_db().site_settings.update_one(
        {"_id": _SETTINGS_ID},
        {"$set": updates},
        upsert=True,
    )


async def get_marketing_ai_enabled() -> bool:
    """Return whether Marketing AI is enabled.

    DB value takes precedence. Falls back to the MARKETING_AI_ENABLED env var
    so the system keeps working even before the admin settings page has been used.
    """
    from app.services.ai_caption import feature_enabled as env_feature_enabled

    db_val = await get_site_setting("marketing_ai_enabled", default=None)
    if db_val is not None:
        return bool(db_val)
    # WHY: fall back to env-var check so behaviour is unchanged on first deploy
    # before anyone has touched the admin settings page.
    return env_feature_enabled()
