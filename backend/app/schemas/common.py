"""Shared schema building blocks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

from app.core.timeutil import to_z

#: A datetime that always serializes to an ISO-8601 UTC string ending in "Z".
#: Rule R10. Tested by ``tests/test_time_utc.py``.
UtcZDatetime = Annotated[datetime, PlainSerializer(to_z, return_type=str, when_used="json")]

#: Money is serialized as a fixed 2-decimal string, never a float.
#: Floats cannot represent 189.99 exactly, and a dispute evidence packet that
#: says "189.98999999999998" is not evidence, it is a bug.
MoneyStr = Annotated[
    Decimal,
    PlainSerializer(lambda d: f"{d:.2f}", return_type=str, when_used="json"),
]
