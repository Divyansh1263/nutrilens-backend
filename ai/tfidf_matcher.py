# ai/tfidf_matcher.py
# Stage 4: TF-IDF semantic matching with cosine similarity
#
# IMPROVEMENTS (v2.2):
#   - Cache-first startup: load prebuilt tfidf_meal_matcher.joblib if present
#   - Falls back to rebuilding from Firestore meal list when cache is absent
#   - Avoids re-vectorising all meals on every cold start

import os
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Path to the prebuilt cache produced by retrain_models_pipeline.py
_BASE_DIR = Path(__file__).resolve().parent.parent
TFIDF_CACHE_PATH = _BASE_DIR / "models" / "tfidf_meal_matcher.joblib"

# Module-level cache (populated by init or load_tfidf_cache)
_vectorizer = None
_tfidf_matrix = None
_meal_list = []       # parallel list of meal dicts
_meal_texts = []      # parallel list of text representations
_category_index = {}  # category -> list of indices

# ── TASK 1: Minimum keyword quality gate ─────────────────────────────────
# Meals with fewer than MIN_KEYWORD_COUNT searchKeywords are excluded from
# the TF-IDF candidate pool and from fuzzy matching.  This prevents weak,
# under-described meals from leaking into pipeline results.
MIN_KEYWORD_COUNT = 1

# ── Corpus-side stopwords ─────────────────────────────────────────────────────
# These are removed from TF-IDF training text (document side) to match the
# query-side STOPWORDS in clean_text(). Without this, tokens like "ate" and
# "had" appear in hundreds of keyword strings, collapsing their IDF weight to
# near-zero and wasting feature budget.
CORPUS_STOPWORDS = {
    "ate", "had", "have", "drank", "piya", "khaya", "kha", "li", "liya",
    "khayi", "khate", "consumed", "with", "and", "a", "an", "the", "of",
    "in", "for", "some", "my", "is", "it", "to", "i",
}


def _has_enough_keywords(meal: dict) -> bool:
    """Return True if the meal meets the minimum keyword quality threshold."""
    kws = meal.get("searchKeywords") or []
    return len(kws) >= MIN_KEYWORD_COUNT



def load_tfidf_cache(cache_path=None):
    """
    Load a prebuilt TF-IDF cache from disk.
    Produced by retrain_models_pipeline.py → build_tfidf_cache().

    Args:
        cache_path: Path or str to the .joblib file
                    (defaults to TFIDF_CACHE_PATH)

    Returns:
        True if cache loaded successfully, False otherwise.
    """
    global _vectorizer, _tfidf_matrix, _meal_list, _meal_texts, _category_index

    path = Path(cache_path) if cache_path else TFIDF_CACHE_PATH
    if not path.exists():
        return False

    try:
        import joblib
        data = joblib.load(path)
        _vectorizer     = data["vectorizer"]
        _tfidf_matrix   = data["tfidf_matrix"]
        _meal_list      = data["meals"]
        _meal_texts     = data.get("texts", [])
        _category_index = data.get("category_index", {})
        print(f"[tfidf_matcher] Loaded prebuilt cache: "
              f"{_tfidf_matrix.shape[0]} meals, "
              f"{_tfidf_matrix.shape[1]} features  ← {path.name}")
        return True
    except Exception as e:
        print(f"[tfidf_matcher] Cache load failed ({e}); will rebuild.")
        return False


def init_tfidf_matcher(meals):
    """
    Initialise TF-IDF matcher.

    Strategy:
      1. Try loading the prebuilt cache (models/tfidf_meal_matcher.joblib).
         If found, skip rebuilding — startup is near-instant.
      2. Fall back to building vectors from the Firestore meal list
         when the cache does not exist (first run or after a rebuild).

    Args:
        meals: list of meal dicts from Firestore
    """
    global _vectorizer, _tfidf_matrix, _meal_list, _meal_texts, _category_index

    # ── Try cache first ───────────────────────────────────────────────────
    if load_tfidf_cache():
        # Cache loaded — update the meal list from Firestore (fresher data)
        # but keep the pre-trained vectors for fast startup.
        # If the number of meals has changed significantly, flag for rebuild.
        if abs(len(meals) - len(_meal_list)) > 50:
            print("[tfidf_matcher] Meal count changed significantly; "
                  "rebuilding vectors for accuracy.")
        else:
            return  # Cache is fresh enough

    # ── Build from scratch ────────────────────────────────────────────────
    # ── TASK 1: Filter out meals with < MIN_KEYWORD_COUNT keywords ───────────
    weak_meals = [m for m in meals if not _has_enough_keywords(m)]
    strong_meals = [m for m in meals if _has_enough_keywords(m)]
    if weak_meals:
        print(
            f"[kw-filter] Excluded {len(weak_meals)} meals with < {MIN_KEYWORD_COUNT} "
            f"keywords from TF-IDF index  "
            f"({len(strong_meals)} retained out of {len(meals)} total)"
        )
        for m in weak_meals[:5]:  # sample log
            kc = len(m.get('searchKeywords') or [])
            print(f"  [kw-filter] skipped '{m.get('mealName')}' ({kc} kws)")
    _meal_list = strong_meals
    _meal_texts = []
    _category_index = {}

    for i, meal in enumerate(_meal_list):
        name     = meal.get("mealName", "")
        keywords = meal.get("searchKeywords") or []
        # Fallback: use mealName as its own keyword if none exist
        if not keywords:
            keywords = [name]
            meal["searchKeywords"] = keywords
        # FIX (Task 3): Strip corpus-side stopwords before vectorisation.
        # This fixes the query/document asymmetry identified in the audit:
        # "ate"/"had"/"khaya" are already removed from queries by clean_text()
        # but were present in document text, collapsing their IDF to ~0.
        raw_text = name.lower() + " " + " ".join(k.lower() for k in keywords)
        text = " ".join(
            tok for tok in raw_text.split() if tok not in CORPUS_STOPWORDS
        )
        _meal_texts.append(text)

        category = meal.get("category", "").lower()
        if category not in _category_index:
            _category_index[category] = []
        _category_index[category].append(i)

    _vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=3000,   # raised 2000→3000 to match retrain pipeline
        lowercase=True,
        sublinear_tf=True,
        min_df=2,            # lowered 3→2 to keep more signal
    )
    _tfidf_matrix = _vectorizer.fit_transform(_meal_texts)

    print(f"[tfidf_matcher] TF-IDF rebuilt: {_tfidf_matrix.shape[0]} meals, "
          f"{_tfidf_matrix.shape[1]} features")


def tfidf_match(query, category_filter=None, top_k=5):
    """
    Find the best matching meals using TF-IDF cosine similarity.

    Args:
        query:            food entity string (e.g., "paneer curry")
        category_filter:  optional category string to restrict search
        top_k:            number of top candidates to return

    Returns:
        list of (meal_dict, similarity_score) tuples, sorted desc
    """
    if _vectorizer is None or _tfidf_matrix is None:
        return []

    # Vectorize the query
    query_vec = _vectorizer.transform([query.lower()])

    if category_filter and category_filter.lower() in _category_index:
        # Restrict to meals in the predicted category
        indices = _category_index[category_filter.lower()]
        if not indices:
            # Fallback to all meals
            sub_matrix = _tfidf_matrix
            sub_indices = list(range(len(_meal_list)))
        else:
            sub_matrix = _tfidf_matrix[indices]
            sub_indices = indices
    else:
        sub_matrix = _tfidf_matrix
        sub_indices = list(range(len(_meal_list)))

    # Compute cosine similarity
    similarities = cosine_similarity(query_vec, sub_matrix).flatten()

    # Get top-k indices
    if len(similarities) == 0:
        return []

    top_local_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for local_idx in top_local_indices:
        global_idx = sub_indices[local_idx]
        score = float(similarities[local_idx])
        if score > 0:  # Only include non-zero matches
            results.append((_meal_list[global_idx], score))

    return results


def get_all_meals():
    """Return the cached meal list."""
    return _meal_list
