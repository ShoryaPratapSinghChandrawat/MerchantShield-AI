"""DEMO_MODE controls seeding; the demo holds exactly 15 story orders (MASTER 9)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.db.seed import STORY_ORDERS


def test_demo_mode_false_seeds_nothing(make_client: Callable[..., TestClient]) -> None:
    client = make_client(demo_mode=False, db_name="no_seed.db")

    assert client.get("/api/health").json()["demo_mode"] is False
    # Nothing was seeded, so order 1 does not exist.
    assert client.get("/api/orders/1").status_code == 404
    assert client.get("/api/orders").json()["count"] == 0


def test_demo_mode_unset_is_treated_as_false(make_client: Callable[..., TestClient]) -> None:
    """An unset DEMO_MODE must default to false, not to true."""
    client = make_client(demo_mode=None, db_name="unset.db")

    assert client.get("/api/health").json()["demo_mode"] is False
    assert client.get("/api/orders/1").status_code == 404


def test_demo_mode_true_seeds_exactly_fifteen_story_orders(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(demo_mode=True, db_name="seeded.db")

    body = client.get("/api/orders").json()
    assert body["count"] == 15
    assert body["count"] == len(STORY_ORDERS)
    assert client.get("/api/orders/16").status_code == 404


def test_story_orders_are_deterministic() -> None:
    """The spec calls for hand-written, deterministic story orders - not random ones."""
    refs = [story.ref for story in STORY_ORDERS]
    assert len(refs) == len(set(refs)) == 15
    assert refs[0] == "MS-2001"
    # The negation trap and the "no penalty for age when tracked" pair exist.
    texts = " ".join(body for story in STORY_ORDERS for _, body in story.messages)
    assert "no refund needed" in texts
    assert any(story.tracking and story.days_ago > 30 for story in STORY_ORDERS)
    assert any(not story.tracking and story.days_ago > 30 for story in STORY_ORDERS)


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

    assert count == 15, f"expected the seed to run once, found {count} orders"
