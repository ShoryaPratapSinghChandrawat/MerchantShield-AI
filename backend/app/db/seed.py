"""Demo seeding.

Two gates, both required (section 6):

1. ``DEMO_MODE=true``  - never seed a non-demo deployment.
2. the database is empty - never duplicate or overwrite existing rows.

Phase 0 seeds exactly one order. Phase 1 replaces this with the 8 deterministic
story orders.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import SourceLabel
from app.models.order import Order

logger = logging.getLogger(__name__)

#: Fixed demo run id so seeded rows are identifiable and deletable (R10: fixed seeds).
PHASE0_DEMO_RUN_ID = "demo-seed-phase0"

#: Fixed timestamp so the seeded row is byte-for-byte reproducible across runs.
_SEED_CREATED_AT = datetime(2026, 11, 1, 9, 30, 0, tzinfo=timezone.utc)


def _phase0_order() -> Order:
    return Order(
        order_ref="MS-1001",
        buyer_name="Ava Thompson",
        buyer_email="ava.thompson@example.com",
        item_name="Aurora X2 Noise-Cancelling Headphones",
        amount=Decimal("189.99"),
        currency="USD",
        status="COMPLETED",
        # Locally generated, not a PayPal response, not a mock adapter response.
        source=SourceLabel.SIMULATED.value,
        is_demo=True,
        demo_run_id=PHASE0_DEMO_RUN_ID,
        created_at=_SEED_CREATED_AT,
        updated_at=_SEED_CREATED_AT,
    )


def database_is_empty(session: Session) -> bool:
    return session.scalar(select(Order.id).limit(1)) is None


def seed_if_needed(session: Session) -> int:
    """Seed demo data when allowed. Returns the number of orders inserted."""
    settings = get_settings()

    if not settings.demo_mode:
        logger.info("DEMO_MODE is false - skipping seeding.")
        return 0

    if not database_is_empty(session):
        logger.info("Database already has orders - skipping seeding.")
        return 0

    session.add(_phase0_order())
    session.commit()
    logger.info("Seeded 1 demo order (source=SIMULATED, is_demo=true).")
    return 1
