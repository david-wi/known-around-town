"""Tests for the destructive-seed production guardrail.

WHY this exists: the demo-data seed scripts (seed_networks.py, seed_miami.py)
DELETE stale records as part of "wipe and re-add" re-seeding. Production data
was once erased by running the seed pointed at the live cloud database by
mistake. `seed._helpers.assert_seed_target_allowed` now refuses to run unless
the target is a confirmed-safe one. These tests pin that behavior — including
the critical "aborts against an Atlas target" case — so a future change can't
quietly reopen the path that wiped production.

The guard's contract:
  * ALLOW when the target is local/dev (ALLOW_LOCAL_MONGODB=true AND a local
    host) or the in-memory mongomock host the tests use ("test").
  * ALLOW when KAT_ALLOW_PRODUCTION_RESET is explicitly set (the deploy path).
  * Otherwise FAIL CLOSED: abort, including for Atlas, unknown remote hosts,
    and an empty/missing URL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import importlib

import pytest

# Make sure backend/ is on sys.path before app imports happen (mirrors conftest).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config as config_module
from app.config import Settings
from seed import _helpers
from seed._helpers import (
    ALLOW_PRODUCTION_RESET_ENV,
    SeedTargetForbiddenError,
    assert_seed_target_allowed,
)

# A representative production MongoDB Atlas connection string. The guard must
# treat this as production and refuse unless production is explicitly confirmed.
ATLAS_URL = "mongodb+srv://appuser:pw@expertly.xuf7uv.mongodb.net/known_around_town"

# Keep the guard inventory tied to the actual destructive city writers. This
# prevents a newly deploy-invoked replace loop from escaping the fail-closed
# entrypoint test merely because it was not added to a hand-maintained list.
CITY_WRITER_MODULES = tuple(
    sorted(
        path.stem
        for path in (Path(__file__).parents[1] / "seed").glob("seed_*.py")
        if "businesses.replace_one" in path.read_text()
    )
)


@pytest.fixture
def guard_env(monkeypatch):
    """Drive the guard with explicit Settings + env, isolated from the real env.

    WHY a fixture: the guard reads BOTH get_settings() (lru_cached, .env-backed)
    and os.environ. This fixture patches get_settings to return a Settings built
    from explicit kwargs and clears the production-reset env var, so each test is
    deterministic and free of cache/.env/shell interference.
    """

    def configure(url: str, *, allow_local: bool = False, prod_reset=None):
        settings = Settings(
            mongodb_url=url,
            allow_local_mongodb=allow_local,
            network_domains="",
        )
        monkeypatch.setattr(config_module, "get_settings", lambda: settings)
        monkeypatch.setattr(_helpers, "get_settings", lambda: settings)
        monkeypatch.delenv(ALLOW_PRODUCTION_RESET_ENV, raising=False)
        if prod_reset is not None:
            monkeypatch.setenv(ALLOW_PRODUCTION_RESET_ENV, prod_reset)
        return settings

    return configure


# --- the core incident: a production/Atlas target must ABORT --------------------


def test_atlas_without_any_flag_aborts(guard_env):
    """The exact failure mode that wiped production: seed aimed at Atlas, no
    confirmation. Must refuse loudly."""
    guard_env(ATLAS_URL)
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


def test_atlas_error_message_is_actionable(guard_env):
    """The abort message must tell the operator how to proceed safely."""
    guard_env(ATLAS_URL)
    with pytest.raises(SeedTargetForbiddenError) as exc:
        assert_seed_target_allowed()
    msg = str(exc.value)
    assert ALLOW_PRODUCTION_RESET_ENV in msg
    assert "ALLOW_LOCAL_MONGODB" in msg


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://db.internal.example.com:27017",  # unknown remote host
        "mongodb+srv://cluster0.abcd.mongodb.net/app",  # generic Atlas
        "mongodb://prod-replica-1:27017,prod-replica-2:27017/app",  # replica set
    ],
)
def test_unknown_remote_hosts_abort(guard_env, url):
    """Any host the guard can't confirm is local is treated as production."""
    guard_env(url)
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


def test_empty_url_aborts(guard_env):
    """An empty/missing URL can't be confirmed local — fail closed."""
    guard_env("")
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


# --- the deploy path: explicit production-reset confirmation ALLOWS -------------


@pytest.mark.parametrize("flag", ["true", "TRUE", "1", "yes", "on", " true "])
def test_atlas_with_explicit_production_reset_proceeds(guard_env, flag):
    """The deploy script sets KAT_ALLOW_PRODUCTION_RESET on purpose; the seed
    must then be allowed to run against Atlas."""
    guard_env(ATLAS_URL, prod_reset=flag)
    assert_seed_target_allowed()  # should not raise


@pytest.mark.parametrize("flag", ["false", "0", "no", "off", "", "  "])
def test_atlas_with_falsey_production_flag_aborts(guard_env, flag):
    """A falsey/blank confirmation value is NOT a confirmation — fail closed."""
    guard_env(ATLAS_URL, prod_reset=flag)
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


# --- the dev path: local host + opt-in ALLOWS; either alone ABORTS --------------


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://localhost:27017",
        "mongodb://127.0.0.1:27017",
        "mongodb://mongo:27017",  # the docker-compose service name
        "mongodb://mongodb:27017",
    ],
)
def test_local_host_with_opt_in_proceeds(guard_env, url):
    guard_env(url, allow_local=True)
    assert_seed_target_allowed()  # should not raise


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://localhost:27017",
        "mongodb://mongo:27017",
    ],
)
def test_local_host_without_opt_in_aborts(guard_env, url):
    """A local host without the dev opt-in is still refused — fail closed."""
    guard_env(url, allow_local=False)
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


def test_opt_in_with_atlas_host_still_aborts(guard_env):
    """The critical fail-closed case: a developer left ALLOW_LOCAL_MONGODB=true
    in their shell but MONGODB_URL points at Atlas. The opt-in flag alone must
    NOT make Atlas count as local — the seed must still refuse."""
    guard_env(ATLAS_URL, allow_local=True)
    with pytest.raises(SeedTargetForbiddenError):
        assert_seed_target_allowed()


# --- the test harness: mongomock sentinel host ALLOWS --------------------------


def test_mongomock_sentinel_host_proceeds(guard_env):
    """conftest seeds with MONGODB_URL=mongodb://test (mongomock). It is not a
    real server, so the destructive seed is harmless against it and must run."""
    guard_env("mongodb://test")
    assert_seed_target_allowed()  # should not raise


# --- config helper: is_local_mongo_target requires BOTH flag AND local host ----


def _settings(url: str, *, allow_local: bool) -> Settings:
    return Settings(mongodb_url=url, allow_local_mongodb=allow_local, network_domains="")


def test_is_local_mongo_target_requires_both():
    assert _settings("mongodb://mongo:27017", allow_local=True).is_local_mongo_target()
    # flag set but Atlas host -> not local
    assert not _settings(ATLAS_URL, allow_local=True).is_local_mongo_target()
    # local host but no flag -> not local
    assert not _settings("mongodb://mongo:27017", allow_local=False).is_local_mongo_target()
    # neither -> not local
    assert not _settings(ATLAS_URL, allow_local=False).is_local_mongo_target()


# --- wiring: the real seed entrypoints abort against Atlas BEFORE touching DB --
#
# WHY these matter beyond the unit tests above: they prove the guard is actually
# WIRED INTO the destructive entrypoints (seed_miami.main / seed_networks.main),
# not merely importable. If a future refactor removed the assert_seed_target_
# allowed() call from main(), the unit tests would still pass but these would
# fail — catching exactly the regression that would re-expose production.


@pytest.fixture
def atlas_target(monkeypatch):
    """Point the seed entrypoints at an Atlas target with no confirmation, and
    make any DB access explode — so a passing test PROVES the guard fired before
    the seed could read or write the database."""
    # Import entrypoints before replacing app.database.ensure_indexes. The seed
    # modules import that function by name, so patch each module's bound alias
    # after import to prove its own main() guard runs first.
    modules = {
        name: importlib.import_module(f"seed.{name}")
        for name in (*CITY_WRITER_MODULES, "seed_networks")
    }

    settings = Settings(mongodb_url=ATLAS_URL, allow_local_mongodb=False, network_domains="")
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(_helpers, "get_settings", lambda: settings)
    monkeypatch.delenv(ALLOW_PRODUCTION_RESET_ENV, raising=False)

    def _boom(*_args, **_kwargs):
        raise AssertionError(
            "Database was accessed despite an unconfirmed production target — "
            "the seed guard did not fire first."
        )

    # If the guard is wired correctly, none of these bound aliases is reached.
    for module in modules.values():
        monkeypatch.setattr(module, "get_db", _boom, raising=False)
        monkeypatch.setattr(module, "ensure_indexes", _boom, raising=False)
    return settings


@pytest.mark.asyncio
async def test_seed_miami_main_aborts_before_db_access(atlas_target):
    from seed import seed_miami

    with pytest.raises(SeedTargetForbiddenError):
        await seed_miami.main()


@pytest.mark.asyncio
async def test_seed_networks_main_aborts_before_db_access(atlas_target):
    from seed import seed_networks

    with pytest.raises(SeedTargetForbiddenError):
        await seed_networks.main()


@pytest.mark.parametrize("module_name", CITY_WRITER_MODULES)
@pytest.mark.asyncio
async def test_satellite_seed_main_aborts_before_db_access(atlas_target, module_name):
    """Every city destructive entrypoint must fail closed before DB access."""
    module = importlib.import_module(f"seed.{module_name}")
    with pytest.raises(SeedTargetForbiddenError):
        await module.main()
