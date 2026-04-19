# ai/hybrid_matcher.py
# Stage 5: Weighted hybrid matching — TF-IDF + Fuzzy + Category + Keyword + Context
#
# IMPROVEMENTS (v2.3):
#   1. Tighter acceptance: tfidf>0.35 OR (fuzzy>0.65 AND keyword>0)
#   2. Hard-reject floor: tfidf<0.25 AND fuzzy<0.60 → discard
#   3. Keyword_score capped at 0.5 (prevents over-boosting)
#   4. Debug logging — prints all 5 signals + final score per candidate
#   5. test_hybrid_matcher() helper for quick smoke tests

from rapidfuzz import fuzz
from ai.tfidf_matcher import tfidf_match, get_all_meals

# -----------------------------------------------
# Scoring weights  (must sum to 1.0)
# -----------------------------------------------
W_TFIDF    = 0.55
W_FUZZY    = 0.25
W_CATEGORY = 0.10
W_KEYWORD  = 0.05   # explicit searchKeywords overlap
W_CONTEXT  = 0.05   # context resolver signal

# Minimum hybrid score to accept a match
CONFIDENCE_THRESHOLD = 0.30

# -----------------------------------------------
# Entity Confidence Filter — OR logic
# Discard entity only when BOTH signals are weak
# -----------------------------------------------
MIN_TFIDF_FOR_ENTITY = 0.35
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
    query_lower = query.lower()

    for name, data in candidate_map.items():
        meal = data["meal"]
        tfidf_s = data["tfidf_score"]
        fuzzy_s = data["fuzzy_score"]

        # ── Keyword boost (capped at 0.5) ─────────────────────────────────────
        # 0.5 if any searchKeyword appears in / contains the query, else 0.0
        # Capped at 0.5 to prevent keywords from overpowering TF-IDF signal.
        keyword_s = 0.0
        keywords = meal.get("searchKeywords") or meal.get("aliases") or []
        for kw in keywords:
            if kw.lower() in query_lower or query_lower in kw.lower():
                keyword_s = 0.5
                break

        # ── Hard-reject floor ─────────────────────────────────────────────────
        # Discard candidates where BOTH primary signals are very weak.
        # This prevents noisy / off-topic meals from leaking into scoring.
        if tfidf_s < 0.25 and fuzzy_s < 0.60:
            continue

        # ── Acceptance gate (OR logic per spec) ───────────────────────────────
        # Require a meaningful signal from at least one primary method.
        passes_filter = (
            tfidf_s > MIN_TFIDF_FOR_ENTITY                      # strong TF-IDF
            or (fuzzy_s > MIN_FUZZY_FOR_ENTITY and keyword_s > 0)  # fuzzy + keyword
            or fuzzy_s > 0.80                                    # dominant fuzzy
        )
        if not passes_filter:
            continue

        # ── Adaptive Category Weighting ───────────────────────────────────────
        # When TF-IDF is highly confident, category signal adds noise
        if tfidf_s > 0.8:
            w_cat   = 0.0
            w_tfidf = W_TFIDF + W_CATEGORY   # redistribute
        else:
            w_cat   = W_CATEGORY
            w_tfidf = W_TFIDF

        # Category match: 1.0 if meal's category equals predicted
        cat_match = 0.0
        if predicted_category:
            meal_category = meal.get("category", "").lower()
            if meal_category == predicted_category.lower():
                cat_match = 1.0

        # ── 5-signal weighted formula ─────────────────────────────────────────
        final_score = (
            w_tfidf    * tfidf_s   +
            W_FUZZY    * fuzzy_s   +
            w_cat      * cat_match +
            W_KEYWORD  * keyword_s +
            W_CONTEXT  * context_score
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        # ── Debug logging ─────────────────────────────────────────────────────
        print(
            f"[hybrid] '{name}' "
            f"tfidf={tfidf_s:.3f}  fuzzy={fuzzy_s:.3f}  "
            f"kw={keyword_s:.2f}  cat={cat_match:.1f}  "
            f"ctx={context_score:.1f}  → score={final_score:.3f}"
        )

        results.append({
            "meal":           meal,
            "score":          round(final_score, 4),
            "tfidf_score":    round(tfidf_s, 4),
            "fuzzy_score":    round(fuzzy_s, 4),
            "keyword_score":  round(keyword_s, 4),
            "category_match": cat_match,
            "context_score":  context_score,
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
    print(f"\n[hybrid] Matching query: '{query}'")

    candidates = hybrid_match(
        query,
        predicted_category=predicted_category,
        context_score=context_score,
        top_k=3,
    )

    if not candidates:
        print(f"[hybrid] No candidates passed filter for '{query}' → unknown")
        return None, 0.0

    best = candidates[0]
    confidence = best["score"]

    # Safety filter: final score below floor → reject
    if confidence < CONFIDENCE_THRESHOLD:
        print(
            f"[hybrid] REJECTED '{query}' — score={confidence:.3f} < "
            f"threshold={CONFIDENCE_THRESHOLD} → unknown"
        )
        return None, confidence

    print(
        f"[hybrid] ACCEPTED '{query}' → '{best['meal'].get('mealName')}' "
        f"(score={confidence:.3f})"
    )
    return best["meal"], confidence


# ---------------------------------------------------------------------------
# Quick smoke-test  —  run directly:  python -m ai.hybrid_matcher
# ---------------------------------------------------------------------------
def test_hybrid_matcher():
    """
    Smoke-test the hybrid matcher against a set of known inputs.
    Requires the pipeline to already be initialised (call init_pipeline first).
    """
    test_cases = [
        "2 roti aur dal",
        "paner butter masla",
        "chai biscuit",
        "rice",
        "kurkure",
    ]

    print("\n" + "=" * 60)
    print("HYBRID MATCHER SMOKE TEST")
    print("=" * 60)

    for text in test_cases:
        meal, confidence = resolve_best_meal(text)
        if meal:
            print(
                f"  INPUT : '{text}'\n"
                f"  MATCH : '{meal.get('mealName')}' "
                f"(confidence={confidence:.3f})\n"
            )
        else:
            print(
                f"  INPUT : '{text}'\n"
                f"  MATCH : unknown (confidence={confidence:.3f})\n"
            )

    print("=" * 60)
