"""Regression tests for the host-level deploy lock in scripts/deploy.sh."""

from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "deploy.sh"


def test_deploy_script_defaults_to_kat_lock_file():
    script = SCRIPT_PATH.read_text()

    assert (
        'DEPLOY_LOCK_FILE="${DEPLOY_LOCK_FILE:-/opt/deploy-locks/known-around-town.lock}"'
        in script
    )
    assert 'DEPLOY_LOCK_WAIT_SECONDS="${DEPLOY_LOCK_WAIT_SECONDS:-900}"' in script


def test_deploy_script_acquires_lock_before_git_or_docker_work():
    script = SCRIPT_PATH.read_text()

    mkdir_index = script.index('mkdir -p "$(dirname "$DEPLOY_LOCK_FILE")"')
    open_fd_index = script.index('exec 9>"$DEPLOY_LOCK_FILE"')
    lock_index = script.index('flock -w "$DEPLOY_LOCK_WAIT_SECONDS" 9')
    git_index = script.index("git fetch --quiet")
    build_index = script.index("docker build")
    compose_index = script.index("docker compose")

    assert mkdir_index < open_fd_index
    assert open_fd_index < lock_index
    assert lock_index < git_index
    assert lock_index < build_index
    assert lock_index < compose_index
