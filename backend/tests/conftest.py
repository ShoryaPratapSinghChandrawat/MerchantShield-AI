"""Shared test fixtures.

Two guarantees enforced here for every test in the suite (section 9):

1. **Temporary database.** Each client gets its own SQLite file under pytest's
   ``tmp_path``. No test ever touches a developer's real ``merchantshield.db``.
2. **No network.** ``_block_network`` replaces the socket connect primitives so
   any accidental outbound call fails loudly instead of silently hitting
   PayPal. Loopback is still allowed so a local stub server stays possible.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


class NetworkAccessBlocked(RuntimeError):
    """Raised when a test tries to open a non-loopback socket."""


@pytest.fixture(autouse=True)
def _isolate_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the dotenv loader at a file that does not exist.

    Without this, a developer who has a real ``.env`` at the project root
    would get different test results from CI - the classic "passes on my
    machine" failure. Tests must depend only on what they set themselves.
    """
    monkeypatch.setenv("MS_ENV_FILE", str(tmp_path / "absent.env"))


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that attempts a real outbound connection."""
    real_connect = socket.socket.connect
    real_create_connection = socket.create_connection

    def guard(address: object) -> None:
        host = address[0] if isinstance(address, tuple) and address else address
        if str(host) not in _ALLOWED_HOSTS:
            raise NetworkAccessBlocked(
                f"Tests must not touch the network (attempted connection to {host!r})."
            )

    def patched_connect(self: socket.socket, address: object) -> None:
        guard(address)
        return real_connect(self, address)  # type: ignore[arg-type]

    def patched_create_connection(address: object, *args: object, **kwargs: object) -> object:
        guard(address)
        return real_create_connection(address, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", patched_connect)
    monkeypatch.setattr(socket, "create_connection", patched_create_connection)


@pytest.fixture
def make_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., TestClient]]:
    """Factory building a TestClient against a fresh temporary database.

    The factory sets environment variables *before* the app is constructed,
    because settings are cached and the engine is process-global.
    """
    created: list[TestClient] = []

    def _factory(
        *,
        demo_mode: bool | None = True,
        db_name: str = "test.db",
        **extra_env: str,
    ) -> TestClient:
        from app.core.config import reset_settings_cache
        from app.db.base import reset_engine_for_tests

        monkeypatch.delenv("DEMO_MODE", raising=False)
        if demo_mode is not None:
            monkeypatch.setenv("DEMO_MODE", "true" if demo_mode else "false")

        db_path = tmp_path / db_name
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        # Never let a developer's real credentials leak into a test run.
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("PAYPAL_MODE", "mock")
        for key, value in extra_env.items():
            monkeypatch.setenv(key.upper(), value)

        reset_settings_cache()
        reset_engine_for_tests()

        from app.main import create_app

        client = TestClient(create_app())
        client.__enter__()  # run lifespan: init_db + conditional seeding
        created.append(client)
        return client

    yield _factory

    for client in created:
        client.__exit__(None, None, None)

    from app.core.config import reset_settings_cache
    from app.db.base import reset_engine_for_tests

    reset_engine_for_tests()
    reset_settings_cache()


@pytest.fixture
def demo_client(make_client: Callable[..., TestClient]) -> TestClient:
    """A client with DEMO_MODE=true, so exactly one order is seeded."""
    return make_client(demo_mode=True)
