"""The test harness's own guarantees, asserted rather than assumed.

Section 9 requires that tests use a temporary database and never touch the
network, and BUG-0004 added an autouse fixture isolating them from a
developer's real ``.env``. Those three promises live in ``conftest.py``, so
nothing was checking that they actually hold. If someone deletes an autouse
fixture, every other test keeps passing and the guarantee silently evaporates.

These tests make that failure loud.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import ENV_FILE_OVERRIDE_VAR, get_settings, resolve_env_file
from tests.conftest import NetworkAccessBlocked


# --------------------------------------------------------------------------
# 1. Isolation from a developer's real .env
# --------------------------------------------------------------------------


def test_env_file_override_is_set_for_every_test() -> None:
    assert ENV_FILE_OVERRIDE_VAR in os.environ, (
        "the autouse _isolate_env_file fixture is not running"
    )


def test_resolve_env_file_is_none_even_if_a_real_dotenv_exists() -> None:
    """A `.env` at the project root must not influence a test run."""
    assert resolve_env_file() is None

    pointed_at = Path(os.environ[ENV_FILE_OVERRIDE_VAR])
    assert not pointed_at.exists(), "the override must point at a non-existent file"


# --------------------------------------------------------------------------
# 2. No network
# --------------------------------------------------------------------------


def test_create_connection_to_a_public_host_is_blocked() -> None:
    with pytest.raises(NetworkAccessBlocked):
        socket.create_connection(("api-m.sandbox.paypal.com", 443), timeout=1)


def test_socket_connect_to_a_public_address_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessBlocked):
            sock.connect(("93.184.216.34", 80))
    finally:
        sock.close()


def test_loopback_is_still_permitted() -> None:
    """The guard must not break a local stub server (needed from Phase 5)."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        client.close()
    finally:
        server.close()


# --------------------------------------------------------------------------
# 3. Temporary database
# --------------------------------------------------------------------------


def test_client_database_lives_under_pytest_tmp_path(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    make_client(demo_mode=True, db_name="guard.db")

    database_url = get_settings().database_url
    assert database_url.startswith("sqlite:///")
    assert tmp_path.as_posix() in database_url, (
        f"test database must live in pytest's tmp_path, got {database_url!r}"
    )


def test_no_database_file_is_written_into_the_repository(
    make_client: Callable[..., TestClient]
) -> None:
    """The default ./merchantshield.db must never appear during a test run."""
    from app.core.config import REPO_ROOT

    make_client(demo_mode=True, db_name="norepo.db")

    stray = REPO_ROOT / "merchantshield.db"
    assert not stray.exists(), f"a test wrote a database into the repository: {stray}"
