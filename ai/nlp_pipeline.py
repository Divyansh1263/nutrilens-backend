# ai/nlp_pipeline.py
# Main NLP pipeline orchestrator — chains all stages together
# 12-step hybrid NLP pipeline for meal logging
#
# IMPROVEMENTS (v2.5):
#   - Alias normalization stage (new step between clean + spell)
#   - Context scoring (feeds into hybrid matcher as 4th signal)
#   - Debug logging to Firestore nlp_debug_logs collection
#   - PIPELINE_CACHE global for cold-start performance
#   - TASK 4: category_confidence extracted + passed to resolve_best_meal
#   - TASK 7: category confidence logged per entity
#   - TASK 1/5: COMBO_SPLIT_MAP — combo entities expanded before hybrid matching

from ai.text_preprocessor import (
    init_preprocessor, clean_text, correct_spelling, normalize_aliases
)
from ai.phrase_detector import init_phrase_detector, detect_phrases
from ai.quantity_extractor import extract_quantities
from ai.tfidf_matcher import init_tfidf_matcher
from ai.context_resolver import resolve_context
from ai.hybrid_matcher import resolve_best_meal
from ai.food_category_model import predict_category
from utils.logger import app_logger

# -----------------------------------------------
# IMPROVEMENT 7: Global Pipeline Cache
# All expensive objects loaded once during cold start
# -----------------------------------------------
PIPELINE_CACHE = {
    "initialized": False,
    "meals": [],
    "db": None,
    # These are populated inside each module's init function:
    # "vectorizer": set by tfidf_matcher.init_tfidf_matcher()
    # "matrix":     set by tfidf_matcher.init_tfidf_matcher()
    # "phrases":    set by phrase_detector.init_phrase_detector()
    # "vocab":      set by text_preprocessor.init_preprocessor()
    # "classifier": loaded by food_category_model at import time
}

# -----------------------------------------------
# TASK 1: Combo Split Map
# Context resolver may produce combo names (e.g. "Dal Roti").
# These are NOT real meal entries — split them into constituent
# entities so EACH component is matched individually by the
# hybrid matcher, producing correct separate nutritional entries.
# -----------------------------------------------
COMBO_SPLIT_MAP = {
    # legume + bread
    "Dal Roti":    ["dal",  "roti"],
    # legume + rice
    "Dal Chawal":  ["dal",  "rice"],
    "Rice Dal":    ["dal",  "rice"],
    "Chawal Dal":  ["dal",  "rice"],
    # dairy + rice
    "Curd Rice":   ["curd", "rice"],
    # bread + vegetable ("sabzi" → "mixed vegetable sabzi" by Step 2)
    "Roti Sabzi":  ["roti", "mixed vegetable sabzi"],
}


def init_pipeline(meals, db=None):
    """
    Initialize all NLP pipeline components.
    Called ONCE at server startup after MEALS are loaded from Firestore.

    All expensive data structures (TF-IDF vectors, phrase sets, vocabulary)
    are computed here and cached in module-level globals — never recomputed.

    Args:
        meals: list of meal dicts (with mealName, searchKeywords, category, etc.)
        db:    Firestore client (optional, for user preference + debug logging)
    """
    PIPELINE_CACHE["meals"] = meals
    PIPELINE_CACHE["db"] = db

    print("[nlp_pipeline] Initializing pipeline (v2.1)...")

    # If the meal list is empty (e.g., Firestore quota limits / cache corruption),
    # fall back to the seeded meal list so the pipeline can still function.
    if not meals:
        app_logger.warning(
            "NLP pipeline initialized with empty meal list; falling back to seeded meals."
        )
        try:
            from dev_store import ensure_meals_available, MEALS_CACHE

            ensure_meals_available()
            meals = MEALS_CACHE
            PIPELINE_CACHE["meals"] = meals
            app_logger.info(f"Using {len(meals)} meals for NLP pipeline after fallback.")
        except Exception as e:
            app_logger.error(f"Could not load seeded meals for NLP pipeline: {e}")

    # 1. Build spelling correction vocabulary + alias map
    init_preprocessor(meals)

    # 2. Build phrase detection set (now supports 4-word phrases)
    init_phrase_detector(meals)

    # 3. Build TF-IDF vectors (cached in tfidf_matcher module)
    try:
        init_tfidf_matcher(meals)
    except Exception as e:
        if "empty vocabulary" in str(e).lower():
            app_logger.warning(
                "TF-IDF init failed due to empty vocabulary; retrying with seeded meals."
            )
            try:
                from dev_store import ensure_meals_available, MEALS_CACHE

                ensure_meals_available()
                meals = MEALS_CACHE
                PIPELINE_CACHE["meals"] = meals
                init_preprocessor(meals)
                init_phrase_detector(meals)
                init_tfidf_matcher(meals)
            except Exception as e2:
                app_logger.error(f"TF-IDF retry also failed: {e2}")
                raise
        else:
            raise

    PIPELINE_CACHE["initialized"] = True
    # Avoid unicode symbols here (Windows console encoding can crash startup).
    print("[nlp_pipeline] Pipeline v2.1 initialized successfully")


def process_meal_text(text, user_id, date, db=None):
    """
    Full 12-step hybrid NLP pipeline (v2.1).

    Pipeline stages:
      1. clean_text()
      2. normalize_aliases()          ← NEW
      3. correct_spelling()
      4. detect_phrases()             ← UPGRADED (4-word)
      5. extract_quantities()
      6. resolve_context()            ← UPGRADED (scoring, not override)
      7. predict_category()
      8. candidate_filter()           (inside hybrid_match)
      9. tfidf_match()               (inside hybrid_match)
     10. fuzzy_match()               (inside hybrid_match)
     11. hybrid_score()              ← UPGRADED (4-signal formula)
     12. user_preference_boost()
     13. log_firestore()

    Args:
        text:     raw user input
        user_id:  Firestore user ID
        date:     date string (YYYY-MM-DD)
        db:       Firestore client

    Returns:
        dict with "message" and "items" list
    """
    if not PIPELINE_CACHE["initialized"]:
        return {"error": "Pipeline not initialized", "items": []}

    firestore_db = db or PIPELINE_CACHE["db"]

    # Debug log accumulator
    debug_log = {
        "raw_text": text,
        "user_id": user_id,
        "date": date,
    }

    print(f"\n{'='*60}")
    print(f"[NLP PIPELINE v2.1] Input: \"{text}\"")
    print(f"{'='*60}")

    # -----------------------------------------------
    # STEP 1: Clean text
    # -----------------------------------------------
    cleaned = clean_text(text)
    debug_log["cleaned_text"] = cleaned
    print(f"[Step 1] clean_text: \"{cleaned}\"")

    # -----------------------------------------------
    # STEP 2: Alias normalization (NEW)
    # -----------------------------------------------
    tokens = cleaned.split()
    tokens = normalize_aliases(tokens)
    alias_text = " ".join(tokens)
    debug_log["after_aliases"] = alias_text
    print(f"[Step 2] normalize_aliases: \"{alias_text}\"")

    # -----------------------------------------------
    # STEP 3: Spelling correction
    # -----------------------------------------------
    corrected_tokens = correct_spelling(tokens)
    corrected_text = " ".join(corrected_tokens)
    debug_log["after_spelling"] = corrected_text
    print(f"[Step 3] correct_spelling: \"{corrected_text}\"")

    # -----------------------------------------------
    # STEP 4: Phrase detection (UPGRADED — 4-word)
    # -----------------------------------------------
    phrases = detect_phrases(corrected_tokens)
    debug_log["phrases"] = phrases
    print(f"[Step 4] detect_phrases: {phrases}")

    # -----------------------------------------------
    # STEP 5: Quantity extraction
    # -----------------------------------------------
    food_entities = _filter_food_entities(phrases)
    quantities = extract_quantities(food_entities, corrected_text)
    debug_log["entities"] = food_entities
    debug_log["quantities"] = quantities
    print(f"[Step 5] extract_quantities: {quantities}")

    # -----------------------------------------------
    # STEP 6: Context-aware resolution (UPGRADED — scoring)
    # -----------------------------------------------
    resolved_entities, resolved_quantities, context_scores = resolve_context(
        food_entities, quantities
    )
    debug_log["resolved_entities"] = resolved_entities
    debug_log["context_scores"] = context_scores
    print(f"[Step 6] resolve_context: entities={resolved_entities}, "
          f"context_scores={context_scores}")

    # -----------------------------------------------
    # STEPS 7-11: Match each entity
    # -----------------------------------------------
    logged_items = []
    debug_log["matches"] = []

    # TASK 1: Expand combo entities before hybrid matching
    # Build the final working list with smart quantity assignment:
    #   - Bread-type parts (roti, chapati) inherit the combo quantity
    #     (user likely said "3 roti" before it was context-resolved)
    #   - All other parts (dal, rice, curd, sabzi) default to qty 1
    # ----------------------------------------------------------------
    # TASK 2: Primary food priority
    # Primary foods are staple carb bases — their query signal is stronger
    PRIMARY_FOODS = {"rice", "roti", "chapati", "chapatti", "naan", "paratha"}

    BREAD_PARTS = {"roti", "chapati", "chapatis", "chapatti", "naan", "paratha"}

    expanded_entities       = []
    expanded_quantities     = dict(resolved_quantities)
    expanded_context_scores = dict(context_scores)
    expanded_priorities     = {}   # TASK 2: entity → priority_score
    expanded_force_generic  = {}   # TASK 3: True for entities from combo splits

    for entity in resolved_entities:
        if entity in COMBO_SPLIT_MAP:
            parts     = COMBO_SPLIT_MAP[entity]
            combo_qty = resolved_quantities.get(entity, 1)

            # TASK 1: Smart quantity per part
            part_qty_map = {}
            for part in parts:
                if part.lower() in BREAD_PARTS:
                    part_qty_map[part] = combo_qty   # bread inherits count
                else:
                    part_qty_map[part] = 1           # liquids/grains default 1

            # TASK 5: Log with per-part quantities
            print(
                f"[combo_split] '{entity}' \u2192 {part_qty_map}"
            )
            debug_log.setdefault("combo_splits", []).append(
                {"combo": entity, "parts": part_qty_map}
            )

            for part in parts:
                expanded_entities.append(part)
                expanded_quantities[part]     = part_qty_map[part]
                expanded_context_scores[part] = 0.0  # pair already resolved
                # TASK 2: assign priority by part type
                expanded_priorities[part] = 1.0 if part.lower() in PRIMARY_FOODS else 0.8
                expanded_force_generic[part] = True   # TASK 3: force generic
        else:
            expanded_entities.append(entity)
            # TASK 2: priority for non-combo entities
            expanded_priorities[entity] = 1.0 if entity.lower() in PRIMARY_FOODS else 0.8
            expanded_force_generic[entity] = False  # TASK 3: native entity — normal matching

    print(f"[Step 6b] after combo_split: {expanded_entities}")
    print(f"[Step 6b] priorities: {expanded_priorities}")

    for entity in expanded_entities:
        quantity      = expanded_quantities.get(entity, 1)
        ctx_score     = expanded_context_scores.get(entity, 0.0)
        priority_score = expanded_priorities.get(entity, 0.8)  # TASK 2
        force_generic  = expanded_force_generic.get(entity, False)  # TASK 3

        # Step 7: Predict category + TASK 4/7: extract confidence
        first_word = entity.split()[0]
        category = predict_category(first_word)

        # TASK 4 + TASK 7: Attempt to retrieve classifier confidence
        # Uses predict_proba if available; defaults to None (no confidence gate)
        category_confidence = None
        try:
            from ai.food_category_model import model as _cat_model
            proba = _cat_model.predict_proba([first_word])[0]
            category_confidence = float(max(proba))
        except Exception:
            pass  # Model doesn't support predict_proba — gate stays off

        # TASK 7: Log category + confidence
        conf_str = f"{category_confidence:.2f}" if category_confidence is not None else "N/A"
        print(
            f"[Step 7] predict_category('{entity}'): '{category}' "
            f"(confidence={conf_str}, priority={priority_score:.1f})"
        )

        # Steps 8-11: Hybrid matching (TF-IDF + fuzzy + category + context)
        meal, confidence = resolve_best_meal(
            entity,
            predicted_category=category,
            context_score=ctx_score,
            category_confidence=category_confidence,
            entity_priority=priority_score,   # TASK 1: pass priority
            force_generic=force_generic,       # TASK 3: base-only for combo parts
        )

        match_debug = {
            "entity": entity,
            "category": category,
            "category_confidence": round(category_confidence, 3) if category_confidence is not None else None,
            "context_score": ctx_score,
        }

        if meal is None:
            print(f"[Step 11] ❌ No match for '{entity}' "
                  f"(confidence={confidence:.3f})")
            match_debug["match"] = None
            match_debug["confidence"] = round(confidence, 3)
            debug_log["matches"].append(match_debug)
            continue

        print(f"[Step 11] ✅ '{entity}' → '{meal['mealName']}' "
              f"(confidence={confidence:.3f}, priority={priority_score:.1f})")

        # Step 12: User preference boost
        confidence = _apply_user_preference(
            meal, user_id, confidence, firestore_db
        )

        match_debug["match"] = meal["mealName"]
        match_debug["confidence"] = round(confidence, 3)
        debug_log["matches"].append(match_debug)

        # Build result item
        item = {
            "meal": meal["mealName"],
            "category": category,
            "quantity": quantity,
            "confidence": round(confidence, 2),
            "calories": meal.get("calories", 0) * quantity,
            "protein": meal.get("protein", 0) * quantity,
            "carbs": meal.get("carbs", 0) * quantity,
            "fat": meal.get("fat", 0) * quantity,
        }
        logged_items.append(item)

        # Step 13: Log to Firestore
        if firestore_db:
            _log_to_firestore(
                firestore_db, user_id, date, text, meal,
                quantity, confidence, category
            )

    print(f"\n[RESULT] Logged {len(logged_items)} items")
    print(f"{'='*60}\n")

    # -----------------------------------------------
    # IMPROVEMENT 6: Debug logging to Firestore
    # -----------------------------------------------
    debug_log["items_logged"] = len(logged_items)
    debug_log["final_items"] = [
        {"meal": item["meal"], "confidence": item["confidence"]}
        for item in logged_items
    ]
    _write_debug_log(firestore_db, debug_log)

    return {
        "message": "Meal logged using hybrid NLP pipeline",
        "items": logged_items,
    }


# -----------------------------------------------
# Helper Functions
# -----------------------------------------------

def _filter_food_entities(phrases):
    """
    Remove non-food tokens (pure numbers, quantity words, etc.)
    from the phrase list.
    """
    from ai.quantity_extractor import NUMBER_WORDS, FRACTIONS, PORTION_WORDS

    skip_tokens = set(NUMBER_WORDS.keys()) | set(FRACTIONS.keys()) | PORTION_WORDS

    filtered = []
    for phrase in phrases:
        if phrase.isdigit():
            continue
        if phrase.lower() in skip_tokens:
            continue
        filtered.append(phrase)

    return filtered


def _apply_user_preference(meal, user_id, base_confidence, db):
    """
    Boost confidence for meals the user has frequently logged before.

    Index fix: removed DESCENDING order_by on timestamp (required a
    composite index on userId+timestamp DESC).  Instead, query by userId
    only (single-field index — always available) and count matches in
    Python. The result is more accurate (all history, not just last 30).
    """
    if not db or not user_id:
        return base_confidence

    try:
        from utils.logger import app_logger
        logs_ref = db.collection("meal_logs") \
            .where("userId", "==", user_id) \
            .limit(100) \
            .stream()

        target_name = meal.get("mealName", "")
        # Convert to list to iterate + count correctly while knowing the length for logging
        docs_list = list(logs_ref)
        app_logger.info(f"[db] fetched {len(docs_list)} docs for meal_logs preference check")
        count = sum(
            1 for doc in docs_list
            if doc.to_dict().get("mealName") == target_name
        )

        if count > 0:
            boost = min(0.05 * count, 0.15)
            print(f"[Step 12] User preference boost for "
                  f"'{target_name}': +{boost:.2f} (logged {count}x)")
            return min(1.0, base_confidence + boost)

    except Exception as e:
        print(f"[Step 12] User preference lookup failed: {e}")

    return base_confidence


def _log_to_firestore(db, user_id, date, raw_text, meal,
                       quantity, confidence, category):
    """
    Write a meal log entry to Firestore.
    """
    try:
        from firebase_admin import firestore as fs

        doc_ref = db.collection("meal_logs").document()
        log_data = {
            "userId": user_id,
            "date": date,
            "mealName": meal["mealName"],
            "mealType": meal.get("category", category),
            "calories": meal.get("calories", 0) * quantity,
            "protein": meal.get("protein", 0) * quantity,
            "carbs": meal.get("carbs", 0) * quantity,
            "fat": meal.get("fat", 0) * quantity,
            "quantity": quantity,
            "source": "hybrid_nlp_v2.1",
            "rawText": raw_text,
            "confidence": round(confidence, 2),
            "timestamp": fs.SERVER_TIMESTAMP,
            "logId": doc_ref.id
        }
        doc_ref.set(log_data)
    except Exception as e:
        print(f"[Step 13] Firestore logging failed: {e}")


def _write_debug_log(db, debug_data):
    """
    IMPROVEMENT 6: Write pipeline debug data to nlp_debug_logs collection.
    Helps analyze failures and tune thresholds.
    """
    if not db:
        return

    try:
        from firebase_admin import firestore as fs

        debug_data["timestamp"] = fs.SERVER_TIMESTAMP
        db.collection("nlp_debug_logs").add(debug_data)
    except Exception as e:
        # Debug logging should never crash the pipeline
        print(f"[debug_log] Failed to write debug log: {e}")
