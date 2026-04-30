"""
NutriLens - Model Retraining Pipeline
======================================
Tasks:
  1. Merge meal_dataset.json + meal_dataset2.json  →  merged_meals.json
  2. Retrain NLP meal classifier from nlp_training_dataset.csv
  3. Retrain KNN SmartSwap model from merged meals
  4. Print validation report

Run from the backend folder:
    python retrain_pipeline.py
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows terminals that default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

DATASET1_PATH = BASE_DIR / "meal_dataset.json"
DATASET2_PATH = BASE_DIR / "meal_dataset2.json"
MERGED_PATH = BASE_DIR / "merged_meals.json"

NLP_CSV_CANDIDATES = [
    BASE_DIR / "nlp_training_dataset.csv",
    BASE_DIR / "ai" / "nlp_training_dataset.csv",
]

NLP_MODEL_PATH = MODELS_DIR / "nlp_meal_classifier.joblib"
KNN_MODEL_PATH = MODELS_DIR / "knn_meal_swap.joblib"

FEATURE_COLS = ["calories", "protein", "carbs", "fat"]

DIVIDER = "-" * 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _info(msg: str) -> None:
    print(f"  [..]  {msg}")


def _warn(msg: str) -> None:
    print(f"  [!!]  {msg}", file=sys.stderr)


def normalize(name: Any) -> str:
    """Lowercase + strip for duplicate-safe comparison."""
    return str(name or "").strip().lower()


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must be a JSON list, got {type(data).__name__}")
    return [item for item in data if isinstance(item, dict)]


def clean_meal(meal: dict[str, Any]) -> dict[str, Any]:
    out = dict(meal)
    out["mealName"] = str(out.get("mealName", "")).strip()
    for col in FEATURE_COLS:
        out[col] = coerce_float(out.get(col), default=0.0)
    return out


def find_nlp_csv() -> Path:
    for p in NLP_CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "nlp_training_dataset.csv not found. Checked:\n"
        + "\n".join(f"  • {p}" for p in NLP_CSV_CANDIDATES)
    )


# ---------------------------------------------------------------------------
# TASK 1 — Merge datasets
# ---------------------------------------------------------------------------

def merge_datasets(
    ds1: list[dict[str, Any]],
    ds2: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Priority: keep all meals from ds1.
    Add meals from ds2 only when not already present (case-insensitive name).
    Returns (merged_list, stats_dict).
    """
    merged: dict[str, dict[str, Any]] = {}
    ds1_dupes = 0

    for meal in ds1:
        m = clean_meal(meal)
        key = normalize(m.get("mealName"))
        if not key:
            continue
        if key in merged:
            ds1_dupes += 1
            continue
        merged[key] = m

    primary_keys = set(merged)
    ds2_skipped = 0
    ds2_added = 0

    for meal in ds2:
        m = clean_meal(meal)
        key = normalize(m.get("mealName"))
        if not key:
            continue
        if key in merged:            # in ds1  OR already added from ds2
            ds2_skipped += 1
            continue
        merged[key] = m
        ds2_added += 1

    stats = {
        "ds1_total": len(ds1),
        "ds2_total": len(ds2),
        "ds1_internal_dupes": ds1_dupes,
        "ds2_dupes_skipped": ds2_skipped,
        "ds2_new_added": ds2_added,
        "merged_total": len(merged),
    }
    return list(merged.values()), stats


def run_merge() -> list[dict[str, Any]]:
    _banner("TASK 1 — Merge Meal Datasets")

    _info(f"Loading {DATASET1_PATH.name} …")
    ds1 = load_json(DATASET1_PATH)

    _info(f"Loading {DATASET2_PATH.name} …")
    ds2 = load_json(DATASET2_PATH)

    _info("Merging (dataset1 has priority) …")
    merged, stats = merge_datasets(ds1, ds2)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with MERGED_PATH.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    _ok(f"Saved -> {MERGED_PATH.name}  ({stats['merged_total']} meals)")

    # Validation printout (TASK 4 data)
    print()
    print(f"  {'Meals in dataset1':<35} {stats['ds1_total']:>6}")
    print(f"  {'Meals in dataset2':<35} {stats['ds2_total']:>6}")
    print(f"  {'Meals after merge':<35} {stats['merged_total']:>6}")
    print(f"  {'Dataset1 internal dupes skipped':<35} {stats['ds1_internal_dupes']:>6}")
    print(f"  {'Dataset2 dupes skipped (already in ds1)':<35} {stats['ds2_dupes_skipped']:>6}")
    print(f"  {'New meals added from dataset2':<35} {stats['ds2_new_added']:>6}")

    return merged


# ---------------------------------------------------------------------------
# TASK 2 — Retrain NLP model
# ---------------------------------------------------------------------------

def run_nlp_training() -> None:
    _banner("TASK 2 — Retrain NLP Meal Classifier")

    csv_path = find_nlp_csv()
    _info(f"Loading NLP dataset from: {csv_path.relative_to(BASE_DIR)}")

    df = pd.read_csv(csv_path)

    # Validate columns
    required = {"text", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"NLP CSV is missing columns: {sorted(missing)}")

    # Clean
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.lower().str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"] != "") & (df["label"] != "")]

    if len(df) < 2:
        raise ValueError("Too few rows in NLP dataset (need ≥ 2 after cleaning).")

    _info(f"Samples: {len(df)}   |   Labels: {df['label'].nunique()}")

    # Train / test split
    label_counts = df["label"].value_counts()
    can_stratify = label_counts.min() >= 2 and df["label"].nunique() > 1
    if not can_stratify:
        _warn("Stratified split disabled — at least one label has < 2 samples.")

    x_train, x_test, y_train, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=0.2,
        random_state=42,
        stratify=df["label"] if can_stratify else None,
    )

    _info(f"Train size: {len(x_train)}   |   Test size: {len(x_test)}")

    # Build pipeline
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    stop_words="english",
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000)),
        ]
    )

    _info("Training …")
    model.fit(x_train, y_train)

    # Evaluate
    y_pred = model.predict(x_test)
    accuracy = accuracy_score(y_test, y_pred)

    _ok(f"Accuracy: {accuracy * 100:.2f}%")

    # Per-class report (condensed)
    report = classification_report(y_test, y_pred, zero_division=0)
    for line in report.splitlines():
        print(f"     {line}")

    # Save
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, NLP_MODEL_PATH)
    _ok(f"Saved -> {NLP_MODEL_PATH.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------------
# TASK 3 — Retrain KNN model
# ---------------------------------------------------------------------------

def run_knn_training(meals: list[dict[str, Any]]) -> None:
    _banner("TASK 3 — Retrain KNN Meal Swap Model")

    if len(meals) < 6:
        raise ValueError(
            f"Need at least 6 meals for n_neighbors=6 KNN; got {len(meals)}."
        )


    _info(f"Building feature matrix from {len(meals)} meals …")
    _info(f"Features: {FEATURE_COLS}")

    X = np.array(
        [[coerce_float(meal.get(col)) for col in FEATURE_COLS] for meal in meals],
        dtype=float,
    )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    knn = NearestNeighbors(n_neighbors=6, metric="euclidean")
    knn.fit(X_scaled)

    model_data = {
        "scaler": scaler,
        "knn": knn,
        "meals": meals,
        "feature_cols": FEATURE_COLS,
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_data, KNN_MODEL_PATH)

    _ok(f"Trained KNN on {len(meals)} meals")
    _ok(f"Saved -> {KNN_MODEL_PATH.relative_to(BASE_DIR)}")


# ---------------------------------------------------------------------------
# TASK 4 — Validation summary
# ---------------------------------------------------------------------------

def run_validation_summary(merged: list[dict[str, Any]]) -> None:
    _banner("TASK 4 — Validation")

    names = [normalize(m.get("mealName")) for m in merged]
    non_empty = [n for n in names if n]
    from collections import Counter
    dupes = [name for name, cnt in Counter(non_empty).items() if cnt > 1]

    _ok(f"Total meals in merged dataset : {len(merged)}")
    _ok(f"Unique meal names             : {len(set(non_empty))}")

    # Feature coverage
    fully_covered = sum(
        1 for m in merged
        if all(coerce_float(m.get(col)) > 0 for col in FEATURE_COLS)
    )
    _info(f"Meals with all nutrition fields > 0: {fully_covered}/{len(merged)}")

    if dupes:
        _warn(f"Remaining duplicates detected ({len(dupes)}): {dupes[:10]}")
    else:
        _ok("No duplicate meal names detected — dataset is clean.")

    # Model files
    print()
    for label, path in [("NLP model", NLP_MODEL_PATH), ("KNN model", KNN_MODEL_PATH)]:
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        status = f"{size_kb:,.1f} KB" if path.exists() else "MISSING"
        print(f"  {'[OK]' if path.exists() else '[!!]'} {label:<20} -> {path.relative_to(BASE_DIR)}  ({status})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=" * 60)
    print("  NutriLens - Model Retraining Pipeline")
    print("=" * 60)

    # Task 1: Merge datasets
    merged = run_merge()

    # Task 2: NLP
    run_nlp_training()

    # Task 3: KNN
    run_knn_training(merged)

    # Task 4: Validation
    run_validation_summary(merged)

    _banner("Pipeline Complete")
    _ok("All models retrained and saved successfully.")
    print()


if __name__ == "__main__":
    main()
