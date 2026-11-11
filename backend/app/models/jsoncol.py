"""A JSON column that behaves the same on SQLite as it does in Python.

SQLAlchemy ships ``JSON``, but on SQLite it round-trips through ``json.dumps``
with default settings, which is fine for values but makes ordering and diffs
unstable. This decorator pins the serialisation (sorted keys, compact) so an
audit row's ``detail`` is byte-stable and two runs of the same story produce
the same evidence.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class JsonText(TypeDecorator[Any]):
    """Store a Python value as deterministic JSON text."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def process_result_value(self, value: str | None, dialect: Any) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):  # pragma: no cover - corrupt row
            return {"_unparsable": str(value)}
