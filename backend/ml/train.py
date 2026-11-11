"""Train the honest ML estimate (Phase 3).

StandardScaler + LogisticRegression, 80/20 split, fixed seed. It writes:

``model/metrics.json``  accuracy, ROC-AUC and a confusion matrix for the model
                        AND for two baselines (majority class, Phase 1 rule
                        score), plus the synthetic-data disclosure
``model/model.json``    standardiser mean/scale and the coefficients, so
                        prediction needs no pickle and no scikit-learn at
                        request time

The baselines are the interesting part: if a logistic regression on synthetic
data cannot beat "always predict the majority class" then it is not adding
anything, and the About page should say so.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.preprocessing import StandardScaler

# Allow `python ml/train.py` as well as `python -m ml.train`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.generate_data import FEATURE_NAMES, SEED, generate_rows  # noqa: E402

TEST_FRACTION = 0.2
MODEL_DIR = Path(__file__).with_name("model")


def phase1_rule_scores(rows: list[dict[str, float]]) -> list[float]:
    """The Phase 1 rule score, as the first baseline.

    Reimplemented in five lines rather than importing the app, so training has
    no web dependencies. It mirrors the dominant rules: value, tracking, age,
    first-time buyer, country mismatch, buyer history and category.
    """
    scores: list[float] = []
    for row in rows:
        points = 0
        points += 18 if row["amount"] >= 500 else (8 if row["amount"] >= 200 else 0)
        points += 0 if row["has_tracking"] else 20
        points += 0 if row["has_tracking"] else (10 if row["days_since_order"] > 30 else 0)
        points += 9 if row["is_first_time_buyer"] else 0
        points += 11 if row["country_mismatch"] else 0
        points += 15 if row["buyer_negative_score"] >= 60 else 0
        points += 6 if row["category_risk"] >= 0.35 else 0
        scores.append(min(100, points) / 100.0)
    return scores


def _matrix(rows: list[dict[str, float]]) -> np.ndarray:
    return np.array([[float(row[name]) for name in FEATURE_NAMES] for row in rows], dtype=float)


def train(*, rows: int = 6000, seed: int = SEED, outdir: Path = MODEL_DIR) -> dict[str, object]:
    data = generate_rows(rows, seed)
    labels = np.array([float(row["label"]) for row in data], dtype=float)

    indices = list(range(len(data)))
    random.Random(seed).shuffle(indices)
    split = int(len(indices) * (1 - TEST_FRACTION))
    train_idx, test_idx = indices[:split], indices[split:]

    train_rows = [data[i] for i in train_idx]
    test_rows = [data[i] for i in test_idx]

    x_train, x_test = _matrix(train_rows), _matrix(test_rows)
    y_train, y_test = labels[train_idx], labels[test_idx]

    scaler = StandardScaler().fit(x_train)
    model = LogisticRegression(max_iter=1000, random_state=seed)
    model.fit(scaler.transform(x_train), y_train)

    probabilities = model.predict_proba(scaler.transform(x_test))[:, 1]
    predictions = (probabilities >= 0.5).astype(float)

    accuracy = float((predictions == y_test).mean())
    try:
        auc = float(roc_auc_score(y_test, probabilities))
    except ValueError:  # pragma: no cover - only if one class is absent
        auc = float("nan")

    majority = float((y_test == float(np.bincount(y_test.astype(int)).argmax())).mean())
    rule_scores = np.array(phase1_rule_scores(test_rows))
    rule_accuracy = float(((rule_scores >= 0.5).astype(float) == y_test).mean())
    try:
        rule_auc = float(roc_auc_score(y_test, rule_scores))
    except ValueError:  # pragma: no cover
        rule_auc = float("nan")

    def _matrix_dict(matrix: np.ndarray) -> dict[str, int]:
        tn, fp, fn, tp = matrix.ravel()
        return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

    metrics: dict[str, object] = {
        "trained_at": "generated",
        "rows_total": len(data),
        "rows_train": len(train_idx),
        "rows_test": len(test_idx),
        "positives": int(labels.sum()),
        "features": list(FEATURE_NAMES),
        "model": {
            "name": "StandardScaler + LogisticRegression",
            "accuracy": round(accuracy, 4),
            "roc_auc": round(auc, 4),
            "confusion_matrix": _matrix_dict(confusion_matrix(y_test.astype(int), predictions.astype(int))),
        },
        "baselines": {
            "majority_class": {"accuracy": round(majority, 4)},
            "phase_1_rule_score": {
                "accuracy": round(rule_accuracy, 4),
                "roc_auc": round(rule_auc, 4),
            },
        },
        "data": {
            "kind": "SYNTHETIC",
            "note": (
                "Generated locally from a documented rule plus 8% label noise. "
                "This is a prototype, not a model trained on PayPal data, and "
                "its output is an ESTIMATE - never a win probability."
            ),
            "seed": seed,
        },
    }

    payload = {
        "features": list(FEATURE_NAMES),
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) for v in scaler.scale_],
        "coefficients": [float(v) for v in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
    }

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (outdir / "model.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Phase 3 ML estimate")
    parser.add_argument("--rows", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--outdir", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    metrics = train(rows=args.rows, seed=args.seed, outdir=args.outdir)
    print(json.dumps(metrics["model"], indent=2))
    print(json.dumps(metrics["baselines"], indent=2))
    print(f"written to {args.outdir}")


if __name__ == "__main__":
    main()
