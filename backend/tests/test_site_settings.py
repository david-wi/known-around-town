"""Tests for site_settings.update_site_settings $set/$unset behaviour.

The key invariant: saving None for a text field removes it from the DB so
the env-var default applies.  Saving "" instead would silently override the
default with an empty string — the bug this tests.
"""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.services.site_settings import update_site_settings


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.site_settings.update_one = AsyncMock(return_value=None)
    return db


@pytest.mark.asyncio
async def test_update_settings_uses_set_for_non_none(mock_db):
    """Non-None values are sent via $set."""
    with patch("app.services.site_settings.get_db", return_value=mock_db):
        await update_site_settings({"marketing_ai_enabled": True})

    mock_db.site_settings.update_one.assert_called_once()
    _, kwargs = mock_db.site_settings.update_one.call_args
    args = mock_db.site_settings.update_one.call_args[0]
    update_doc = args[1]
    assert "$set" in update_doc
    assert update_doc["$set"]["marketing_ai_enabled"] is True
    assert "$unset" not in update_doc


@pytest.mark.asyncio
async def test_update_settings_uses_unset_for_none(mock_db):
    """None values are sent via $unset so the env-var default applies."""
    with patch("app.services.site_settings.get_db", return_value=mock_db):
        await update_site_settings({"support_email": None, "marketing_ai_enabled": True})

    args = mock_db.site_settings.update_one.call_args[0]
    update_doc = args[1]
    assert "$set" in update_doc
    assert "$unset" in update_doc
    assert "marketing_ai_enabled" in update_doc["$set"]
    assert "support_email" in update_doc["$unset"]
    # Confirm the empty string is NOT saved to $set
    assert "support_email" not in update_doc.get("$set", {})


@pytest.mark.asyncio
async def test_update_settings_no_ops_for_empty_dict(mock_db):
    """Empty updates dict issues no DB call."""
    with patch("app.services.site_settings.get_db", return_value=mock_db):
        await update_site_settings({})

    mock_db.site_settings.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_update_settings_all_none_uses_only_unset(mock_db):
    """All-None update only sends $unset, no $set."""
    with patch("app.services.site_settings.get_db", return_value=mock_db):
        await update_site_settings({"support_email": None, "google_site_verification": None})

    args = mock_db.site_settings.update_one.call_args[0]
    update_doc = args[1]
    assert "$unset" in update_doc
    assert "$set" not in update_doc
