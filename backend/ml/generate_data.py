"""Synthetic data generator for the ML estimate (Phase 3).

**The data is synthetic.** 6,000 rows are generated from a documented label
rule plus noise, with a fixed seed, so the numbers are reproducible and honest
about what they are: a prototype trained on invented data, not on PayPal's.

The label rule (``_label_probability``) is written out in full so anyone can
audit how the training target was made. It is deliberately simple and
monotonic - more value, no tracking, a first-time buyer, a country mismatch, a
negative buyer history and time passing all raise the probability of the
synthetic "dispute" label.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

SEED = 20261107
ROWS = 6000

CATEGORIES = ("general", "electronics", "digital", "jewellery", "luxury", "apparel")
CATEGORY_RISK = {
    "general": 0.10,
    "apparel": 0.18,
    "electronics": 0.35,
    "digital": 0.45,
    "jewellery": 0.40,
    "luxury": 0.50,
}

FEATURE_NAMES = (
    "amount",
    "is_first_time_buyer",
    "country_mismatch",
    "days_since_order",
    "has_tracking",
    "buyer_negative_score",
    "category_risk",
)


def _label_probability(row: dict[str, float]) -> float:
    """The documented label rule. Linear score squashed to a probability."""
    score = (
        0.0016 * row["amount"]
        + 0.85 * row["is_first_time_buyer"]
        + 0.95 * row["country_mismatch"]
        + 0.018 * row["days_since_order"]
        - 1.25 * row["has_tracking"]
        + 0.022 * row["buyer_negative_score"]
        + 1.60 * row["category_risk"]
        - 2.35
    )
    # logistic squashing keeps it in (0, 1)
    import math

    return 1.0 / (1.0 + math.exp(-score))


def generate_rows(count: int = ROWS, seed: int = SEED) -> list[dict[str, float]]:
    rng = random.Random(seed)
    rows: list[dict[str, float]] = []
    for _ in range(count):
        category = rng.choice(CATEGORIES)
        row = {
            "amount": round(rng.choice([rng.uniform(5, 80), rng.uniform(80, 700), rng.uniform(700, 4000)]), 2),
            "is_first_time_buyer": float(rng.random() < 0.32),
            "country_mismatch": float(rng.random() < 0.22),
            "days_since_order": float(rng.randint(0, 75)),
            "has_tracking": float(rng.random() < 0.72),
            "buyer_negative_score": float(rng.randint(0, 100)),
            "category_risk": CATEGORY_RISK[category],
            "category": category,  # kept for the CSV, not a model feature
        }
        # noise: flip 8% of labels so the model cannot be perfect
        p = _label_probability(row)
        label = 1.0 if rng.random() < p else 0.0
        if rng.random() < 0.08:
            label = 1.0 - label
        row["label"] = label
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, float]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(*FEATURE_NAMES, "category", "label"))
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic training set")
    parser.add_argument("--rows", type=int, default=ROWS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("synthetic_orders.csv"))
    args = parser.parse_args()
    rows = generate_rows(args.rows, args.seed)
    written = write_csv(args.out, rows)
    positives = sum(1 for row in rows if row["label"] == 1.0)
    print(f"wrote {len(rows)} rows to {written} ({positives} positive, {len(rows) - positives} negative)")


if __name__ == "__main__":
    main()
