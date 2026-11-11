"""Methodology endpoint: what the numbers are, where they came from, what they are not."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.models.action import Action
from app.models.enums import ActionStatus, SourceLabel
from app.models.order import Order
from app.services import risk_model
from app.services.paypal_service import get_paypal_service

router = APIRouter(prefix="/about", tags=["about"])


@router.get("/methodology", summary="How the scores work, and what they are not")
def methodology(db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    metrics = risk_model.metrics()
    counts = {
        label.value: db.scalar(
            select(func.count()).select_from(Order).where(Order.source == label.value)
        )
        for label in SourceLabel
    }
    executed = db.scalar(
        select(func.count()).select_from(Action).where(Action.status == ActionStatus.EXECUTED.value)
    )
    return {
        "rule_score": {
            "what": "Integer points from hand-written rules over your order fields.",
            "range": "0-1, banded LOW < 0.33 <= MEDIUM < 0.66 <= HIGH",
            "is_not": "Not a probability, not a prediction of any outcome.",
        },
        "ml_estimate": {
            "what": "StandardScaler + LogisticRegression, served next to the rule score.",
            "trained_on": "6,000 SYNTHETIC rows generated locally with a fixed seed.",
            "metrics": metrics,
            "is_not": "Not trained on PayPal data and not a win probability.",
        },
        "evidence_strength": {
            "what": "A weighted checklist of documents you hold (0-100).",
            "is_not": "Not machine learning and not a prediction.",
        },
        "source_labels": {
            "PAYPAL_SANDBOX": "A real PayPal Sandbox response.",
            "SIMULATED": "Generated locally by MerchantShield.",
            "MOCK": "A mock adapter stood in for PayPal.",
        },
        "counts_by_source": counts,
        "actions_executed": executed,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "fallback": "Deterministic templates of the same shape; drafts are labelled.",
        },
        "paypal": get_paypal_service().describe(),
        "honesty_rules": [
            "Every record shows the source it actually came from.",
            "An external action is only EXECUTED after a confirmed success.",
            "Uncertain external outcomes stay UNKNOWN until reconciled.",
            "No win probability, no money-protected figure, no measured-claim theatre.",
        ],
    }
