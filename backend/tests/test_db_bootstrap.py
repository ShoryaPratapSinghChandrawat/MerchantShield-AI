"""Regression tests for database bootstrapping.

Covers BUG-0001: SQLite reports "unable to open database file" when the parent
directory of the database file does not exist. This is the exact situation in
a freshly extracted ZIP, where ``artifacts/`` has not been created yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.db.base import _ensure_sqlite_parent_dir, reset_engine_for_tests
from app.main import create_app


def test_startup_creates_a_missing_sqlite_parent_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-0001 regression: nested, non-existent directories must be created."""
    nested = tmp_path / "artifacts" / "phase-0" / "local-windows"
    assert not nested.exists(), "precondition: the directory must not exist yet"

    db_file = nested / "e2e.sqlite3"
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("PAYPAL_MODE", "mock")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    reset_settings_cache()
    reset_engine_for_tests()

    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/orders/1").status_code == 200

    assert db_file.is_file(), "the database file should have been created"

    reset_engine_for_tests()
    reset_settings_cache()


def test_in_memory_sqlite_url_is_left_alone() -> None:
    """An in-memory URL has no directory, and must not raise."""
    _ensure_sqlite_parent_dir("sqlite://")
    _ensure_sqlite_parent_dir("sqlite:///:memory:")


def test_non_sqlite_url_is_left_alone() -> None:
    _ensure_sqlite_parent_dir("postgresql+psycopg://user:pw@localhost/db")
