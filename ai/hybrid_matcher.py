# ai/hybrid_matcher.py
# Stage 5: Weighted hybrid matching — TF-IDF + Fuzzy + Category + Keyword + Context
#
# IMPROVEMENTS (v2.4):
#   1. Tighter acceptance: tfidf>0.35 OR (fuzzy>0.65 AND keyword>0)
#   2. Hard-reject floor: tfidf<0.25 AND fuzzy<0.60 → discard
#   3. Keyword_score capped at 0.5 (prevents over-boosting)
#   4. Debug logging — prints all signals + final score after penalty
#   5. test_hybrid_matcher() helper for quick smoke tests
#   6. TASK 2: Specificity penalty (0.05 * word_count) — prefer simple meals
#   7. TASK 4: category_confidence gate — disables category filter if low
#   8. TASK 7: Logs final_score after penalty + category_confidence

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

# Specificity penalty weight per word in meal name
# Raised 0.05 → 0.07 (TASK 3) for stronger preference of simple names
SPECIFICITY_PENALTY_PER_WORD = 0.07

# TASK 4: Minimum category confidence below which category filter is disabled
# Raised 0.50 → 0.60 (TASK 3) for stricter gating
CATEGORY_CONFIDENCE_THRESHOLD = 0.60

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


def hybrid_match(query, predicted_category=None, context_score=0.0, top_k=5,
                 category_confidence=None, entity_priority=0.8):
    """
    Combine TF-IDF similarity, fuzzy matching, category agreement,
    and context score into a single weighted score.

    IMPROVEMENTS (v2.5):
      - Entity confidence filter, adaptive category weight, context score
      - Specificity penalty, exact match boost
      - TASK 1: entity_priority — primary foods score higher
      - TASK 2: sabzi-aware keyword boost for vegetable queries
      - TASK 5: logs priority_contribution + sabzi_boost

    Args:
        query:               food entity string
        predicted_category:  predicted category from classifier (or None)
        context_score:       context rule score (0.0 or 1.0), default 0.0
        top_k:               number of results to consider from each method
        category_confidence: classifier confidence; below threshold disables filter
        entity_priority:     0.8 (default) or 1.0 for primary foods

    Returns:
        list of dicts sorted by final score desc
    """
    # TASK 4: Disable category filter when confidence is low
    effective_category = predicted_category
    if (
        category_confidence is not None
        and category_confidence < CATEGORY_CONFIDENCE_THRESHOLD
    ):
        effective_category = None
        print(
            f"[hybrid] Low category confidence ({category_confidence:.2f}) "
            f"< {CATEGORY_CONFIDENCE_THRESHOLD} → category filter DISABLED, using full dataset"
        )

    # TASK 7: Log category confidence
    if category_confidence is not None:
        print(f"[hybrid] category='{predicted_category}' confidence={category_confidence:.2f}")

    # 1. Get TF-IDF candidates (with optional category filter)
    tfidf_results = tfidf_match(query, category_filter=effective_category, top_k=top_k * 2)

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

        # ── TASK 1: Priority contribution ──────────────────────────────────
        # Primary foods (rice/roti) get entity_priority=1.0 from pipeline
        # Secondary items get 0.8. Difference = +0.02 in final score.
        PRIORITY_WEIGHT = 0.1
        priority_contribution = entity_priority * PRIORITY_WEIGHT
        final_score += priority_contribution

        # ── TASK 2: Sabzi-aware vegetable boost (TASK 1 here: reduced 0.15→0.08) ──
        VEG_QUERY_TRIGGERS  = {"vegetable", "sabzi", "mixed", "veg"}
        SABZI_MEAL_KEYWORDS = {"mixed", "veg", "vegetable"}
        SABZI_BOOST = 0.08   # TASK 1: reduced 0.15 → 0.08 to prevent over-boosting
        sabzi_boost = 0.0
        query_words = set(query_lower.split())
        if query_words & VEG_QUERY_TRIGGERS:
            name_lower_check = name.lower()
            if any(kw in name_lower_check for kw in SABZI_MEAL_KEYWORDS):
                sabzi_boost = SABZI_BOOST
                final_score += sabzi_boost

        # ── Exact match boost ─────────────────────────────────────────
        EXACT_MATCH_BOOST = 0.10
        if name.lower() == query_lower:
            final_score += EXACT_MATCH_BOOST
            print(f"[hybrid] '{name}' EXACT MATCH → +{EXACT_MATCH_BOOST}")

        # ── TASK 3: Specificity penalty (raised 0.05→0.07) ─────────────────
        # Subtract 0.07 per word in the meal name.
        word_count = len(name.split())
        specificity_penalty = SPECIFICITY_PENALTY_PER_WORD * word_count
        final_score -= specificity_penalty

        # ── TASK 2: Clamp AFTER all boosts ──────────────────────────────
        # All boosts + penalties applied above; clamp is the FINAL step.
        pre_clamp = final_score
        final_score = max(0.0, min(1.0, final_score))
        was_clamped = pre_clamp != final_score

        # ── TASK 6: Debug logging ─────────────────────────────────────
        clamp_note = f" [CLAMPED from {pre_clamp:.3f}]" if was_clamped else ""
        print(
            f"[hybrid] '{name}' "
            f"tfidf={tfidf_s:.3f}  fuzzy={fuzzy_s:.3f}  "
            f"kw={keyword_s:.2f}  cat={cat_match:.1f}  ctx={context_score:.1f}  "
            f"priority={entity_priority:.1f}(+{priority_contribution:.3f})  "
            f"sabzi_boost={sabzi_boost:.2f}  "
            f"words={word_count}  spec_penalty={specificity_penalty:.3f}  "
            f"→ final_score={final_score:.3f}"
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


def resolve_best_meal(query, predicted_category=None, context_score=0.0,
                      category_confidence=None, entity_priority=0.8):
    """
    Find the single best meal match for a food entity.

    Args:
        query:               food entity string
        predicted_category:  predicted category (or None)
        context_score:       context boost from context_resolver (0.0 or 1.0)
        category_confidence: classifier confidence; low values disable category filter
        entity_priority:     1.0 for primary foods, 0.8 for others (TASK 1)

    Returns:
        (meal_dict, confidence) or (None, 0.0) if below threshold
    """
    print(f"\n[hybrid] Matching query: '{query}' (priority={entity_priority:.1f})")

    candidates = hybrid_match(
        query,
        predicted_category=predicted_category,
        context_score=context_score,
        top_k=3,
        category_confidence=category_confidence,
        entity_priority=entity_priority,
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
