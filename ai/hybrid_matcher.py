# ai/hybrid_matcher.py
# Stage 5: Weighted hybrid matching — TF-IDF + Fuzzy + Category + Context
#
# IMPROVEMENTS (v2.1):
#   1. Entity confidence filter — discard weak matches early
#   2. Adaptive category weighting — reduce category weight when TF-IDF is strong
#   3. Updated formula — includes context_score signal
#   4. New weights: 0.55 TF-IDF + 0.25 Fuzzy + 0.10 Category + 0.10 Context

from rapidfuzz import fuzz
from ai.tfidf_matcher import tfidf_match, get_all_meals

# -----------------------------------------------
# Default Weights for hybrid scoring
# -----------------------------------------------
W_TFIDF = 0.55
W_FUZZY = 0.25
W_CATEGORY = 0.15     # Was 0.20
W_CONTEXT = 0.10     # Was 0.05

# Minimum confidence to accept a match
CONFIDENCE_THRESHOLD = 0.20  # Minimum hybrid score to accept a match

# -----------------------------------------------
# Entity Confidence Filter thresholds
# If BOTH scores are below these, the entity is noise
# -----------------------------------------------
MIN_TFIDF_FOR_ENTITY = 0.20
MIN_FUZZY_FOR_ENTITY = 0.65


def fuzzy_match_meal(query, meals, top_k=5):
    """
    Fuzzy match a query against meal names + searchKeywords.

    Returns:
        list of (meal_dict, fuzzy_score_0_to_1) tuples
    """
    scored = []
    query_lower = query.lower()

    from rapidfuzz import process
    
    meal_names = []
    for m in meals:
        name_val = (m.get("mealName") or m.get("name") or m.get("title") or m.get("food_name") or "").strip()
        if name_val:
            meal_names.append(name_val)
            
    for meal in meals:
        name_val = (meal.get("mealName") or meal.get("name") or meal.get("title") or meal.get("food_name") or "").lower()
        keywords = " ".join(meal.get("searchKeywords") or meal.get("aliases") or []).lower()
        if not keywords:
            keywords = name_val
            
        names = [name_val] + [keywords]
        best_score = 0

        for name in names:
            score = fuzz.partial_ratio(query_lower, name)
            best_score = max(best_score, score)

        scored.append((meal, best_score / 100.0))

    # Optional explicit rapidfuzz extractOne
    if meal_names:
        match = process.extractOne(query_lower, meal_names)
        if match and match[1] > 70:
            for meal in meals:
                m_name = (meal.get("mealName") or meal.get("name") or meal.get("title") or "").lower()
                if m_name == match[0].lower():
                    scored.append((meal, match[1] / 100.0))

    # Sort desc and return top-k
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Remove duplicates
    seen = set()
    final_scored = []
    for item in scored:
        m_id = item[0].get("id") or item[0].get("mealName")
        if m_id not in seen:
            seen.add(m_id)
            final_scored.append(item)
            
    return final_scored[:top_k]


def hybrid_match(query, predicted_category=None, context_score=0.0, top_k=5):
    """
    Combine TF-IDF similarity, fuzzy matching, category agreement,
    and context score into a single weighted score.

    IMPROVEMENTS:
      - Entity confidence filter: discard if tfidf < 0.35 AND fuzzy < 0.65
      - Adaptive category weight: set to 0 if tfidf > 0.8
      - Context score: new 4th signal from context_resolver

    Args:
        query:               food entity string
        predicted_category:  predicted category from classifier (or None)
        context_score:       context rule score (0.0 or 1.0), default 0.0
        top_k:               number of results to consider from each method

    Returns:
        list of dicts: [{meal, score, tfidf_score, fuzzy_score,
                         category_match, context_score}, ...]
        sorted by final score desc
    """
    # 1. Get TF-IDF candidates (with optional category filter)
    tfidf_results = tfidf_match(query, category_filter=predicted_category, top_k=top_k * 2)

    # 2. Get fuzzy candidates from ALL meals
    all_meals = get_all_meals()
    fuzzy_results = fuzzy_match_meal(query, all_meals, top_k=top_k * 2)

    # 3. Build a unified candidate pool
    candidate_map = {}  # meal_name -> {meal, tfidf, fuzzy}

    for meal, tfidf_score in tfidf_results:
        name = (meal.get("mealName") or meal.get("name") or meal.get("title") or "")
        if name not in candidate_map:
            candidate_map[name] = {
                "meal": meal,
                "tfidf_score": tfidf_score,
                "fuzzy_score": 0.0,
            }
        else:
            candidate_map[name]["tfidf_score"] = max(
                candidate_map[name]["tfidf_score"], tfidf_score
            )

    for meal, fuzzy_score in fuzzy_results:
        name = (meal.get("mealName") or meal.get("name") or meal.get("title") or "")
        if name not in candidate_map:
            candidate_map[name] = {
                "meal": meal,
                "tfidf_score": 0.0,
                "fuzzy_score": fuzzy_score,
            }
        else:
            candidate_map[name]["fuzzy_score"] = max(
                candidate_map[name]["fuzzy_score"], fuzzy_score
            )

    # 4. Compute hybrid score for each candidate
    results = []
    for name, data in candidate_map.items():
        meal = data["meal"]
        tfidf_s = data["tfidf_score"]
        fuzzy_s = data["fuzzy_score"]

        # ---- IMPROVEMENT 1: Entity Confidence Filter ----
        # If BOTH signals are weak, this is likely a noise token — skip
        if tfidf_s < MIN_TFIDF_FOR_ENTITY and fuzzy_s < MIN_FUZZY_FOR_ENTITY:
            continue

        # ---- IMPROVEMENT 2: Adaptive Category Weighting ----
        # When TF-IDF is very confident, category match adds noise
        if tfidf_s > 0.8:
            w_cat = 0.0
            # Redistribute category weight to TF-IDF
            w_tfidf = W_TFIDF + W_CATEGORY
        else:
            w_cat = W_CATEGORY
            w_tfidf = W_TFIDF

        # Category match: 1.0 if the meal's category matches predicted
        cat_match = 0.0
        if predicted_category:
            meal_category = meal.get("category", "").lower()
            if meal_category == predicted_category.lower():
                cat_match = 1.0

        # ---- IMPROVEMENT 3: Updated 4-signal formula ----
        final_score = (
            w_tfidf * tfidf_s +
            W_FUZZY * fuzzy_s +
            w_cat * cat_match +
            W_CONTEXT * context_score
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        results.append({
            "meal": meal,
            "score": round(final_score, 4),
            "tfidf_score": round(tfidf_s, 4),
            "fuzzy_score": round(fuzzy_s, 4),
            "category_match": cat_match,
            "context_score": context_score,
        })

    # Sort by score desc
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top_k]


def resolve_best_meal(query, predicted_category=None, context_score=0.0):
    """
    Find the single best meal match for a food entity.

    Args:
        query:              food entity string
        predicted_category: predicted category (or None)
        context_score:      context boost from context_resolver (0.0 or 1.0)

    Returns:
        (meal_dict, confidence) or (None, 0.0) if below threshold
    """
    candidates = hybrid_match(
        query,
        predicted_category=predicted_category,
        context_score=context_score,
        top_k=3,
    )

    if not candidates:
        return None, 0.0

    best = candidates[0]
    confidence = best["score"]

    if confidence < CONFIDENCE_THRESHOLD:
        print(f"[hybrid] LOW CONFIDENCE for '{query}': "
              f"best='{best['meal'].get('mealName')}' score={confidence:.3f}")
        return None, confidence

    return best["meal"], confidence
