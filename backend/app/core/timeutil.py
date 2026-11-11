"""UTC time helpers.

Rule R10: every timestamp this app stores or returns is UTC, and every timestamp
that leaves the API as JSON ends with a literal ``Z`` suffix.

Why this matters for MerchantShield: dispute evidence is judged on *when* things
happened (shipped date, delivery date, buyer message date). An ambiguous or
local-time timestamp in an evidence packet is worse than no timestamp, because
it looks authoritative while being wrong.
"""

from __future__ import annotations

from datetime import datetime, timezone

__all__ = ["utcnow", "ensure_utc", "to_z"]


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    Naive datetimes (for example values read back out of SQLite, which has no
    native timezone storage) are *assumed* to already be UTC, because that is
    the only thing this application ever writes.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_z(dt: datetime) -> str:
    """Serialize a datetime as an ISO-8601 UTC string ending in ``Z``.

    Example: ``2026-11-01T18:46:03.123Z``
    """
    aware = ensure_utc(dt)
    return aware.isoformat(timespec="milliseconds").replace("+00:00", "Z")
