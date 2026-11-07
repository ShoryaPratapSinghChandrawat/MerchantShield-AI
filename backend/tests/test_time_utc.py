"""Phase 0 test 4 - every API timestamp is UTC and ends with "Z" (rule R10).

Section 4 asks this to be tested rather than assumed, so the assertions here
check the actual serialized characters, not just that the string parses.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.timeutil import to_z, utcnow

# 2026-11-01T18:46:03.123Z
Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_to_z_formats_aware_utc_with_z_suffix() -> None:
    dt = datetime(2026, 11, 1, 18, 46, 3, 123000, tzinfo=timezone.utc)
    assert to_z(dt) == "2026-11-01T18:46:03.123Z"


def test_to_z_converts_a_non_utc_offset_to_utc() -> None:
    """A +05:30 (IST) timestamp must come out as the equivalent UTC instant."""
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 11, 13, 1, 30, 0, tzinfo=ist)
    assert to_z(dt) == "2026-11-12T20:00:00.000Z"


def test_to_z_treats_naive_input_as_utc() -> None:
    dt = datetime(2026, 11, 1, 18, 46, 3, 123000)
    assert to_z(dt).endswith("Z")
    assert to_z(dt) == "2026-11-01T18:46:03.123Z"


def test_utcnow_is_timezone_aware_utc() -> None:
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_health_server_time_ends_with_z(demo_client: TestClient) -> None:
    server_time = demo_client.get("/api/health").json()["server_time"]

    assert server_time.endswith("Z"), f"expected a Z suffix, got {server_time!r}"
    assert "+00:00" not in server_time
    assert Z_PATTERN.match(server_time), f"unexpected timestamp shape: {server_time!r}"


def test_order_timestamps_end_with_z(demo_client: TestClient) -> None:
    """Covers the round trip through SQLite, which cannot store an offset."""
    body = demo_client.get("/api/orders/1").json()

    for field in ("created_at", "updated_at"):
        value = body[field]
        assert value.endswith("Z"), f"{field} must end with Z, got {value!r}"
        assert "+00:00" not in value
        assert Z_PATTERN.match(value), f"{field} has unexpected shape: {value!r}"

    # The seed uses a fixed instant, so this is deterministic.
    assert body["created_at"] == "2026-11-01T09:30:00.000Z"
