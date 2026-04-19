"""
Retrain NutriLens AI models after expanding the meal dataset.

Pipeline:
1. Merge meal_dataset.json and meal_dataset2.json with dataset1 priority.
2. Save merged_meals.json after validating required nutrition fields.
3. Retrain NLP meal classifier from nlp_training_dataset.csv.
4. Retrain SmartSwap KNN model from merged meals.
5. Retrain food category classifier from merged meal names/keywords.
6. Build and cache a TF-IDF meal matcher matrix for fast matching.

Run from the backend folder:
    python retrain_models_pipeline.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib


def _save_compressed(obj, path: Path, compress: int = 3) -> None:
    """
    Save a model/cache with zlib compression and print the resulting file size.
    compress=3 gives a good size/speed trade-off (scale: 0=none, 9=max).
    """
    joblib.dump(obj, path, compress=compress)
    size_mb = path.stat().st_size / (1024 * 1024)
    flag = "OK" if size_mb < 100 else "WARNING: exceeds 100 MB!"
    print(f"  Saved {path.name}: {size_mb:.2f} MB  [{flag}]")
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


BASE_DIR = Path(__file__).resolve().parent
DATASET1_PATH = BASE_DIR / "meal_dataset.json"
DATASET2_PATH = BASE_DIR / "meal_dataset2.json"
MERGED_DATASET_PATH = BASE_DIR / "merged_meals.json"
MODELS_DIR = BASE_DIR / "models"

NLP_MODEL_PATH = MODELS_DIR / "nlp_meal_classifier.joblib"
KNN_MODEL_PATH = MODELS_DIR / "knn_meal_swap.joblib"
CATEGORY_MODEL_PATH = MODELS_DIR / "food_category_classifier.joblib"
TFIDF_CACHE_PATH = MODELS_DIR / "tfidf_meal_matcher.joblib"

FEATURE_COLS = ["calories", "protein", "carbs", "fat"]
NLP_DATASET_CANDIDATES = [
    BASE_DIR / "nlp_training_dataset.csv",
    BASE_DIR / "ai" / "nlp_training_dataset.csv",
]


def normalize_meal_name(name: Any) -> str:
    """Normalize meal names for duplicate detection."""
    return str(name or "").strip().lower()


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required dataset: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON list of meals")

    meals = []
    for item in data:
        if isinstance(item, dict):
            meals.append(item)
    return meals


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        numeric_value = float(value)
        if np.isnan(numeric_value) or np.isinf(numeric_value):
            return default
        return numeric_value
    except (TypeError, ValueError):
        return default


def clean_meal(meal: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(meal)
    cleaned["mealName"] = str(cleaned.get("mealName", "")).strip()

    for field in FEATURE_COLS:
        cleaned[field] = coerce_float(cleaned.get(field), default=0.0)

    keywords = cleaned.get("searchKeywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    if not isinstance(keywords, list):
        keywords = []
    cleaned["searchKeywords"] = [
        str(keyword).strip()
        for keyword in keywords
        if str(keyword).strip()
    ]

    # Fallback: use mealName as its own keyword when none are provided
    # This ensures TF-IDF indexing still works for meals without keywords.
    if not cleaned["searchKeywords"] and cleaned["mealName"]:
        cleaned["searchKeywords"] = [cleaned["mealName"]]

    return cleaned


def merge_meal_datasets(
    dataset1: list[dict[str, Any]],
    dataset2: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    merged_by_name: dict[str, dict[str, Any]] = {}
    skipped_missing_name = 0
    dataset1_internal_duplicates = 0
    dataset2_duplicates_against_primary = 0
    dataset2_internal_duplicates = 0

    for meal in dataset1:
        cleaned = clean_meal(meal)
        key = normalize_meal_name(cleaned.get("mealName"))
        if not key:
            skipped_missing_name += 1
            continue
        if key in merged_by_name:
            dataset1_internal_duplicates += 1
            continue
        merged_by_name[key] = cleaned

    primary_keys = set(merged_by_name)

    for meal in dataset2:
        cleaned = clean_meal(meal)
        key = normalize_meal_name(cleaned.get("mealName"))
        if not key:
            skipped_missing_name += 1
            continue
        if key in primary_keys:
            dataset2_duplicates_against_primary += 1
            continue
        if key in merged_by_name:
            dataset2_internal_duplicates += 1
            continue
        merged_by_name[key] = cleaned

    merged = list(merged_by_name.values())
    stats = {
        "dataset1_internal_duplicates": dataset1_internal_duplicates,
        "dataset2_duplicates_against_primary": dataset2_duplicates_against_primary,
        "dataset2_internal_duplicates": dataset2_internal_duplicates,
        "skipped_missing_name": skipped_missing_name,
    }
    return merged, stats


def validate_no_duplicate_meal_names(meals: list[dict[str, Any]]) -> None:
    names = [normalize_meal_name(meal.get("mealName")) for meal in meals]
    duplicates = [name for name, count in Counter(names).items() if name and count > 1]
    if duplicates:
        preview = ", ".join(duplicates[:10])
        raise ValueError(f"Duplicate mealName values remain after merge: {preview}")


def save_merged_dataset(meals: list[dict[str, Any]], path: Path) -> None:
    missing_required = [
        meal.get("mealName", "<missing mealName>")
        for meal in meals
        if any(field not in meal for field in FEATURE_COLS)
    ]
    if missing_required:
        preview = ", ".join(missing_required[:10])
        raise ValueError(f"Meals missing nutrition fields after cleanup: {preview}")

    with path.open("w", encoding="utf-8") as file:
        json.dump(meals, file, indent=2, ensure_ascii=False)


def resolve_nlp_dataset_path() -> Path:
    for path in NLP_DATASET_CANDIDATES:
        if path.exists():
            return path
    candidates = ", ".join(str(path) for path in NLP_DATASET_CANDIDATES)
    raise FileNotFoundError(f"Could not find NLP training CSV. Checked: {candidates}")


def safe_train_test_split(
    x: pd.Series,
    y: pd.Series,
    test_size: float = 0.2,
    random_state: int = 42,
):
    label_counts = y.value_counts()
    can_stratify = len(label_counts) > 1 and label_counts.min() >= 2
    stratify = y if can_stratify else None

    if not can_stratify:
        print("Warning: stratified split disabled because at least one label has < 2 samples.")

    return train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )


def train_nlp_model(csv_path: Path, output_path: Path) -> Pipeline:
    df = pd.read_csv(csv_path)
    required_columns = {"text", "label"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"NLP CSV is missing columns: {sorted(missing_columns)}")

    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.lower().str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"] != "") & (df["label"] != "")]

    if len(df) < 2:
        raise ValueError("NLP training dataset must contain at least 2 valid rows")

    x_train, x_test, y_train, y_test = safe_train_test_split(df["text"], df["label"])

    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=2000,    # reduced from unlimited → cuts model size
                    min_df=3,             # ignore very rare tokens
                    stop_words="english",
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000)),
        ]
    )

    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)

    _save_compressed(model, output_path)

    print(f"NLP samples:  {len(df)}")
    print(f"NLP labels:   {df['label'].nunique()}")
    print(f"NLP accuracy: {accuracy * 100:.2f}%")
    return model


def train_knn_meal_swap_model(meals: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    if len(meals) < 6:
        raise ValueError("Need at least 6 meals to train n_neighbors=6 KNN model")

    feature_matrix = np.array(
        [[coerce_float(meal.get(field)) for field in FEATURE_COLS] for meal in meals],
        dtype=float,
    )

    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(feature_matrix)

    knn = NearestNeighbors(n_neighbors=6, metric="euclidean")
    knn.fit(scaled_features)

    model_data = {
        "scaler":       scaler,
        "knn":          knn,
        "meals":        meals,
        "feature_cols": FEATURE_COLS,
    }
    _save_compressed(model_data, output_path)

    print(f"KNN meals: {len(meals)}")
    return model_data


def meal_text_for_matching(meal: dict[str, Any]) -> str:
    name = str(meal.get("mealName", "")).lower()
    keywords = meal.get("searchKeywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    keyword_text = " ".join(str(keyword).lower() for keyword in keywords)
    return f"{name} {keyword_text}".strip()


def train_food_category_classifier(
    meals: list[dict[str, Any]],
    output_path: Path,
) -> Pipeline | None:
    training_rows = [
        (meal_text_for_matching(meal), str(meal.get("category", "")).strip())
        for meal in meals
    ]
    training_rows = [
        (text, category)
        for text, category in training_rows
        if text and category
    ]

    if len(training_rows) < 2:
        print("Skipping category classifier: not enough labeled meal/category rows.")
        return None

    x, y = zip(*training_rows)
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
    model.fit(list(x), list(y))
    _save_compressed(model, output_path)

    print(f"Category samples: {len(training_rows)}")
    print(f"Category labels:  {len(set(y))}")
    return model


def build_tfidf_cache(meals: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    """
    Build and save a TF-IDF meal matcher cache.

    The cache is loaded by ai/tfidf_matcher.py at server startup so that
    vectors are never recomputed during a cold start.

    Cache file: models/tfidf_meal_matcher.joblib
    """
    texts = [meal_text_for_matching(meal) for meal in meals]
    if not any(texts):
        raise ValueError("Cannot build TF-IDF cache because all meal texts are empty")

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=2000,    # reduced: keeps enough discriminative ngrams
        lowercase=True,
        sublinear_tf=True,
        min_df=3,             # remove very rare tokens to shrink vocabulary
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    category_index: dict[str, list[int]] = {}
    for index, meal in enumerate(meals):
        category = str(meal.get("category", "")).strip().lower()
        if category:
            category_index.setdefault(category, []).append(index)

    cache_data = {
        "vectorizer":     vectorizer,
        "tfidf_matrix":   tfidf_matrix,
        "meals":          meals,
        # 'texts' intentionally omitted — it was the largest contributor to
        # file size and is not needed at inference time.
        "category_index": category_index,
    }
    _save_compressed(cache_data, output_path)

    print(f"TF-IDF cache: {tfidf_matrix.shape[0]} meals x {tfidf_matrix.shape[1]} features")
    return cache_data


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading meal datasets...")
    dataset1 = load_json_list(DATASET1_PATH)
    dataset2 = load_json_list(DATASET2_PATH)

    merged_meals, merge_stats = merge_meal_datasets(dataset1, dataset2)
    validate_no_duplicate_meal_names(merged_meals)
    save_merged_dataset(merged_meals, MERGED_DATASET_PATH)

    print("\nMerge summary")
    print(f"  Dataset 1 meals:                 {len(dataset1)}")
    print(f"  Dataset 2 meals:                 {len(dataset2)}")
    print(f"  Merged total:                    {len(merged_meals)}")
    print(f"  Dataset1 internal duplicates:    {merge_stats['dataset1_internal_duplicates']}")
    print(f"  Dataset2 duplicates vs dataset1: {merge_stats['dataset2_duplicates_against_primary']}")
    print(f"  Dataset2 internal duplicates:    {merge_stats['dataset2_internal_duplicates']}")
    print(f"  Skipped (missing mealName):      {merge_stats['skipped_missing_name']}")
    print(f"  Saved: {MERGED_DATASET_PATH}")

    nlp_dataset_path = resolve_nlp_dataset_path()

    print("\n[1/4] Training NLP meal classifier...")
    train_nlp_model(nlp_dataset_path, NLP_MODEL_PATH)

    print("\n[2/4] Training KNN meal swap model...")
    train_knn_meal_swap_model(merged_meals, KNN_MODEL_PATH)

    print("\n[3/4] Training food category classifier...")
    train_food_category_classifier(merged_meals, CATEGORY_MODEL_PATH)

    print("\n[4/4] Building TF-IDF meal matcher cache...")
    build_tfidf_cache(merged_meals, TFIDF_CACHE_PATH)

    # ── Size report ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Final model sizes (GitHub limit = 100 MB per file):")
    for name, path in [
        ("NLP classifier",       NLP_MODEL_PATH),
        ("KNN swap model",       KNN_MODEL_PATH),
        ("Category classifier",  CATEGORY_MODEL_PATH),
        ("TF-IDF cache",         TFIDF_CACHE_PATH),
    ]:
        if path.exists():
            mb = path.stat().st_size / (1024 * 1024)
            flag = "OK  " if mb < 100 else "FAIL - EXCEEDS LIMIT"
            print(f"  [{flag}]  {name:25s}  {mb:7.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
