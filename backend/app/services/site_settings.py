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
    """Persist one or more settings values. Creates the document if it doesn't exist.

    Values that are None are removed from the document (``$unset``) so the
    callers that read them fall back to the corresponding env-var default.
    This prevents saving an empty string that silently overrides the default.
    """
    set_ops = {k: v for k, v in updates.items() if v is not None}
    unset_ops = {k: "" for k, v in updates.items() if v is None}
    update_doc: Dict[str, Any] = {}
    if set_ops:
        update_doc["$set"] = set_ops
    if unset_ops:
        update_doc["$unset"] = unset_ops
    if not update_doc:
        return
    await get_db().site_settings.update_one(
        {"_id": _SETTINGS_ID},
        update_doc,
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


async def get_preview_mode_enabled() -> bool:
    """Return whether the preview gate is active (site is private).

    DB value takes precedence. Falls back to the PREVIEW_MODE_ENABLED env var
    (default True) so the site stays private on a fresh deploy before David
    has touched the admin settings page.
    """
    from app.config import get_settings

    db_val = await get_site_setting("preview_mode_enabled", default=None)
    if db_val is not None:
        return bool(db_val)
    # WHY: env var fallback preserves existing production behaviour unchanged
    return get_settings().preview_mode_enabled


async def get_google_site_verification() -> str:
    """Return the Google Search Console verification code.

    DB value takes precedence. Falls back to the GOOGLE_SITE_VERIFICATION env
    var so the old setup-by-SSH path keeps working alongside the admin UI.
    """
    from app.config import get_settings

    db_val = await get_site_setting("google_site_verification", default=None)
    if db_val is not None:
        return str(db_val).strip()
    return get_settings().google_site_verification


async def get_ratings_min_review_count() -> int:
    """Return the minimum number of Google reviews required before a rating is shown.

    DB value takes precedence. Falls back to 20 — enough reviews to make a
    rating statistically meaningful (a 5-star average from 3 friends is noise;
    4.7 from 20+ strangers is signal). Configurable so David can raise or lower
    the bar without a code deploy.
    """
    db_val = await get_site_setting("ratings_min_review_count", default=None)
    if db_val is not None:
        return int(db_val)
    # WHY: 20 reviews is the threshold used by several major directory sites
    # (Yelp, Tripadvisor) to distinguish "signal" from "noise" ratings. Below
    # this count, a single bad review can tank a 5-star business or vice versa.
    return 20


async def get_support_email() -> str:
    """Return the public-facing support email address.

    DB value takes precedence. Falls back to the SUPPORT_EMAIL env var (default
    hello@knowsbeauty.com) so the site keeps working before the admin UI has
    been used to set a real address.
    """
    from app.config import get_settings

    db_val = await get_site_setting("support_email", default=None)
    if db_val is not None:
        return str(db_val).strip()
    return get_settings().support_email
