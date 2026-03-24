# ai/tfidf_matcher.py
# Stage 4: TF-IDF semantic matching with cosine similarity

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Module-level cache (populated by init)
_vectorizer = None
_tfidf_matrix = None
_meal_list = []       # parallel list of meal dicts
_meal_texts = []      # parallel list of text representations
_category_index = {}  # category -> list of indices


def init_tfidf_matcher(meals):
    """
    Build TF-IDF vectors from mealName + searchKeywords for all meals.
    Called once at server startup.

    Args:
        meals: list of meal dicts from Firestore
    """
    global _vectorizer, _tfidf_matrix, _meal_list, _meal_texts, _category_index

    _meal_list = meals
    _meal_texts = []
    _category_index = {}

    for i, meal in enumerate(meals):
        # Build text representation for each meal
        name = meal.get("mealName", "")
        keywords = meal.get("searchKeywords", [])
        text = name.lower() + " " + " ".join(k.lower() for k in keywords)
        _meal_texts.append(text)

        # Build category index
        category = meal.get("category", "").lower()
        if category not in _category_index:
            _category_index[category] = []
        _category_index[category].append(i)

    # Fit TF-IDF vectorizer
    _vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=3000,
        lowercase=True,
        sublinear_tf=True,      # Apply log normalization to TF
    )
    _tfidf_matrix = _vectorizer.fit_transform(_meal_texts)

    print(f"[tfidf_matcher] TF-IDF built: {_tfidf_matrix.shape[0]} meals, "
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
