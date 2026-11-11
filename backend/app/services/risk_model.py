"""Serve the Phase 3 ML ESTIMATE next to the Phase 1 rule score.

Everything here is labelled an ESTIMATE in the API payload and in the UI. The
model is trained on SYNTHETIC data (``ml/generate_data.py``) and beats a
majority-class baseline by a measurable amount or the About page says it does
not - see ``metrics.json``.

Prediction is a dot product over standardised features, so serving needs
neither scikit-learn nor a pickle.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.timeutil import ensure_utc, utcnow

logger = logging.getLogger(__name__)

#: backend/app/services/risk_model.py -> services -> app -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
ML_DIR = BACKEND_DIR / "ml"
MODEL_DIR = ML_DIR / "model"
MODEL_FILE = MODEL_DIR / "model.json"
METRICS_FILE = MODEL_DIR / "metrics.json"

FEATURE_LABELS = {
    "amount": "order value",
    "is_first_time_buyer": "first-time buyer",
    "country_mismatch": "buyer country differs from yours",
    "days_since_order": "days since the order",
    "has_tracking": "tracking on file",
    "buyer_negative_score": "buyer negative-history score",
    "category_risk": "product category",
}

CATEGORY_RISK = {
    "general": 0.10,
    "apparel": 0.18,
    "electronics": 0.35,
    "digital": 0.45,
    "jewellery": 0.40,
    "luxury": 0.50,
}


def ensure_model() -> bool:
    """Train on first use if the model file is missing. Returns True if trained."""
    if MODEL_FILE.is_file() and METRICS_FILE.is_file():
        return False
    logger.info("ML model missing - training on synthetic data at startup (Phase 3)")
    from ml.train import train  # imported lazily: training pulls in scikit-learn

    train(outdir=MODEL_DIR)
    return True


def load_model() -> dict[str, Any] | None:
    ensure_model()
    try:
        return json.loads(MODEL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - corrupt file
        logger.warning("ML model file unreadable; the estimate will be unavailable")
        return None


def metrics() -> dict[str, Any] | None:
    ensure_model()
    try:
        return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return None


def features_from_order(order: Any) -> dict[str, float]:
    """Map an ORM order onto the seven model features."""
    created = getattr(order, "created_at", None)
    days = 0.0
    if isinstance(created, datetime):
        days = max(0.0, (utcnow() - ensure_utc(created)).days)
    buyer_country = (getattr(order, "buyer_country", None) or "").upper()
    merchant_country = (getattr(order, "merchant_country", None) or "").upper()
    category = (getattr(order, "category", None) or "general").lower()
    return {
        "amount": float(getattr(order, "amount", 0) or 0),
        "is_first_time_buyer": 1.0 if getattr(order, "is_first_time_buyer", False) else 0.0,
        "country_mismatch": 1.0
        if buyer_country and merchant_country and buyer_country != merchant_country
        else 0.0,
        "days_since_order": float(days),
        "has_tracking": 1.0 if (getattr(order, "tracking_number", None) or "").strip() else 0.0,
        "buyer_negative_score": float(getattr(order, "buyer_negative_history", 0) or 0),
        "category_risk": CATEGORY_RISK.get(category, 0.10),
    }


def predict(order: Any) -> dict[str, Any] | None:
    """Return the ESTIMATE plus its top three up and down factors, in English."""
    model = load_model()
    if model is None:  # pragma: no cover - only if training failed
        return None

    features = features_from_order(order)
    names: list[str] = list(model["features"])
    contributions: list[tuple[str, float]] = []
    z = float(model["intercept"])

    for name in names:
        index = names.index(name)
        mean = float(model["mean"][index])
        scale = float(model["scale"][index]) or 1.0
        coefficient = float(model["coefficients"][index])
        standardised = (features.get(name, 0.0) - mean) / scale
        contribution = coefficient * standardised
        z += contribution
        contributions.append((name, contribution))

    estimate = 1.0 / (1.0 + math.exp(-z))
    increasing = sorted((c for c in contributions if c[1] > 0), key=lambda c: -c[1])[:3]
    decreasing = sorted((c for c in contributions if c[1] < 0), key=lambda c: c[1])[:3]

    def _explain(name: str, contribution: float, direction: str) -> dict[str, Any]:
        return {
            "feature": name,
            "label": FEATURE_LABELS.get(name, name),
            "direction": direction,
            "weight": round(contribution, 4),
            "value": round(features.get(name, 0.0), 3),
        }

    return {
        "estimate": round(estimate, 4),
        "label": "ESTIMATE",
        "raised_by": [_explain(n, c, "+") for n, c in increasing],
        "lowered_by": [_explain(n, c, "-") for n, c in decreasing],
        "note": (
            "Prototype trained on SYNTHETIC data. This is an estimate from your "
            "own order fields, not a probability of winning any dispute."
        ),
    }
