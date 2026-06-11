"""Tests for the MongoDB-URL safety guard in app.config.Settings.

WHY this exists: a throwaway local MongoDB was once left exposed to the
internet and wiped by a ransomware bot. The app must never silently fall back
to a local Mongo in production — it must use the managed Atlas database or
crash loudly. These tests pin that behavior so a future change can't quietly
reintroduce the silent local fall-back.
"""

from __future__ import annotations

import os
import sys

import pytest

# Make sure backend/ is on sys.path before app imports happen (mirrors conftest).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import LocalMongoForbiddenError, Settings


def _settings(url: str, *, allow_local: bool = False) -> Settings:
    """Build a Settings instance with explicit values.

    WHY explicit kwargs instead of env vars: get_settings() is lru_cache'd and
    Settings also reads a local .env file, so constructing directly keeps each
    test isolated and free of cache/.env interference.
    """
    return Settings(
        mongodb_url=url,
        allow_local_mongodb=allow_local,
        network_domains="",
    )


# --- empty / missing URL is always a hard error -----------------------------


def test_empty_url_raises():
    with pytest.raises(LocalMongoForbiddenError):
        _settings("").validate_mongodb_url()


def test_whitespace_url_raises():
    with pytest.raises(LocalMongoForbiddenError):
        _settings("   ").validate_mongodb_url()


def test_empty_url_raises_even_with_opt_in():
    # The opt-in only allows *local* hosts; it does not permit a missing URL.
    with pytest.raises(LocalMongoForbiddenError):
        _settings("", allow_local=True).validate_mongodb_url()


# --- local hosts are rejected without the opt-in ----------------------------


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://localhost:27017",
        "mongodb://localhost",
        "mongodb://127.0.0.1:27017",
        "mongodb://mongo:27017",  # the docker-compose service name
        "mongodb://mongodb:27017",
        "mongodb://0.0.0.0:27017",
        "mongodb://admin:secret@localhost:27017/db",  # creds must not hide the host
    ],
)
def test_local_host_rejected_without_opt_in(url):
    with pytest.raises(LocalMongoForbiddenError):
        _settings(url).validate_mongodb_url()


# --- local hosts are allowed WITH the explicit dev opt-in -------------------


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://localhost:27017",
        "mongodb://mongo:27017",
        "mongodb://127.0.0.1:27017",
    ],
)
def test_local_host_allowed_with_opt_in(url):
    # Should not raise.
    _settings(url, allow_local=True).validate_mongodb_url()


# --- remote / Atlas URLs always pass ----------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "mongodb+srv://expertly.xuf7uv.mongodb.net",
        "mongodb+srv://appuser:pw@expertly.xuf7uv.mongodb.net/who_knows_local",
        "mongodb://db.internal.example.com:27017",
        "mongodb://test",  # the value the test conftest uses
    ],
)
def test_remote_url_passes(url):
    # Should not raise, with or without the opt-in.
    _settings(url).validate_mongodb_url()
    _settings(url, allow_local=True).validate_mongodb_url()


# --- the prod default must NOT silently be a local host ----------------------


def test_default_url_is_empty_not_localhost():
    """A bare Settings() (no MONGODB_URL provided) must have an empty URL.

    WHY: the old default was 'mongodb://localhost:27017', which let a
    production deploy with a missing env var silently use a local Mongo. The
    default is now empty so validate_mongodb_url() turns that mistake into a
    loud crash instead.
    """
    s = Settings(network_domains="")
    # Either truly unset (empty) — never a localhost fall-back.
    assert "localhost" not in (s.mongodb_url or "")
    assert "127.0.0.1" not in (s.mongodb_url or "")
