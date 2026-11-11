"""Phase 3: synthetic data, training metrics and the served ESTIMATE."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from ml.generate_data import FEATURE_NAMES, generate_rows
from ml.train import train
from app.services import risk_model


def test_generated_data_is_deterministic() -> None:
    first = generate_rows(200, seed=7)
    second = generate_rows(200, seed=7)
    assert first == second
    assert all(set(FEATURE_NAMES) <= set(row) for row in first)


def test_labels_are_binary_with_both_classes_present() -> None:
    rows = generate_rows(500, seed=11)
    labels = {row["label"] for row in rows}
    assert labels == {0.0, 1.0}


def test_training_writes_metrics_and_model(tmp_path) -> None:
    metrics = train(rows=1200, outdir=tmp_path)

    assert (tmp_path / "metrics.json").is_file()
    assert (tmp_path / "model.json").is_file()

    model = metrics["model"]
    assert model["name"] == "StandardScaler + LogisticRegression"
    assert 0.0 <= model["accuracy"] <= 1.0
    assert 0.0 <= model["roc_auc"] <= 1.0
    assert set(model["confusion_matrix"]) == {"tn", "fp", "fn", "tp"}


def test_metrics_always_report_both_baselines_and_the_synthetic_disclosure(tmp_path) -> None:
    metrics = train(rows=1200, outdir=tmp_path)

    assert "majority_class" in metrics["baselines"]
    assert "phase_1_rule_score" in metrics["baselines"]
    assert metrics["data"]["kind"] == "SYNTHETIC"
    assert "win probability" in metrics["data"]["note"]


def test_model_beats_the_majority_baseline_on_the_documented_rule(tmp_path) -> None:
    """If it did not, the About page would be advertising something worthless."""
    metrics = train(rows=4000, outdir=tmp_path)
    assert metrics["model"]["accuracy"] > metrics["baselines"]["majority_class"]["accuracy"]


def test_served_estimate_has_top_three_factors_each_way() -> None:
    risk_model.ensure_model()
    order = SimpleNamespace(
        amount=Decimal("1899.00"),
        created_at=datetime.now(timezone.utc) - timedelta(days=41),
        tracking_number=None,
        is_first_time_buyer=True,
        buyer_country="US",
        merchant_country="IT",
        buyer_negative_history=72,
        category="electronics",
    )

    payload = risk_model.predict(order)
    assert payload is not None
    assert payload["label"] == "ESTIMATE"
    assert 0.0 <= payload["estimate"] <= 1.0
    assert len(payload["raised_by"]) <= 3
    assert len(payload["lowered_by"]) <= 3
    assert all("label" in factor for factor in payload["raised_by"])
    assert "SYNTHETIC" in payload["note"]


def test_tracked_order_estimates_lower_than_untracked() -> None:
    risk_model.ensure_model()
    base = dict(
        amount=Decimal("500.00"),
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
        is_first_time_buyer=False,
        buyer_country="US",
        merchant_country="US",
        buyer_negative_history=10,
        category="general",
    )
    untracked = risk_model.predict(SimpleNamespace(tracking_number=None, **base))
    tracked = risk_model.predict(SimpleNamespace(tracking_number="1Z999AA10123456784", **base))

    assert untracked is not None and tracked is not None
    assert tracked["estimate"] < untracked["estimate"]


def test_served_model_is_a_plain_dot_product() -> None:
    """Serving must not need scikit-learn: the coefficients are in model.json."""
    risk_model.ensure_model()
    payload = json.loads(risk_model.MODEL_FILE.read_text(encoding="utf-8"))
    assert set(payload) == {"features", "mean", "scale", "coefficients", "intercept"}
    assert len(payload["features"]) == len(payload["coefficients"]) == len(FEATURE_NAMES)
