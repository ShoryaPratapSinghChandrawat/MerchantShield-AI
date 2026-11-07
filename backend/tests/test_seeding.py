"""Phase 0 test 5 - DEMO_MODE controls seeding.

Section 6: "Seeding runs only when DEMO_MODE=true and the database is empty."
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_demo_mode_false_seeds_nothing(make_client: Callable[..., TestClient]) -> None:
    client = make_client(demo_mode=False, db_name="no_seed.db")

    assert client.get("/api/health").json()["demo_mode"] is False
    # Nothing was seeded, so order 1 does not exist.
    assert client.get("/api/orders/1").status_code == 404


def test_demo_mode_unset_is_treated_as_false(make_client: Callable[..., TestClient]) -> None:
    """An unset DEMO_MODE must default to false, not to true."""
    client = make_client(demo_mode=None, db_name="unset.db")

    assert client.get("/api/health").json()["demo_mode"] is False
    assert client.get("/api/orders/1").status_code == 404


def test_demo_mode_true_seeds_exactly_one_order(make_client: Callable[..., TestClient]) -> None:
    client = make_client(demo_mode=True, db_name="seeded.db")

    assert client.get("/api/orders/1").status_code == 200
    # Phase 0 seeds exactly one order - there is no second one.
    assert client.get("/api/orders/2").status_code == 404


def test_seeding_is_idempotent_on_a_non_empty_database(tmp_path, monkeypatch) -> None:
    """Starting the app twice against the same database must not duplicate rows."""
    from sqlalchemy import func, select

    from app.core.config import reset_settings_cache
    from app.db.base import get_session_factory, reset_engine_for_tests
    from app.main import create_app
    from app.models.order import Order

    db_path = tmp_path / "idempotent.db"
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("PAYPAL_MODE", "mock")

    for _ in range(2):
        reset_settings_cache()
        reset_engine_for_tests()
        with TestClient(create_app()):
            pass

    reset_settings_cache()
    reset_engine_for_tests()
    session = get_session_factory()()
    try:
        count = session.scalar(select(func.count()).select_from(Order))
    finally:
        session.close()

    assert count == 1, f"expected the seed to run once, found {count} orders"
