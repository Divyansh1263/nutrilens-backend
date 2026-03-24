# ai/nlp_pipeline.py
# Main NLP pipeline orchestrator — chains all stages together
# 12-step hybrid NLP pipeline for meal logging
#
# IMPROVEMENTS (v2.1):
#   - Alias normalization stage (new step between clean + spell)
#   - Context scoring (feeds into hybrid matcher as 4th signal)
#   - Debug logging to Firestore nlp_debug_logs collection
#   - PIPELINE_CACHE global for cold-start performance

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

    for entity in resolved_entities:
        quantity = resolved_quantities.get(entity, 1)
        ctx_score = context_scores.get(entity, 0.0)

        # Step 7: Predict category
        first_word = entity.split()[0]
        category = predict_category(first_word)
        print(f"[Step 7] predict_category('{entity}'): {category}")

        # Steps 8-11: Hybrid matching (TF-IDF + fuzzy + category + context)
        meal, confidence = resolve_best_meal(
            entity,
            predicted_category=category,
            context_score=ctx_score,
        )

        match_debug = {
            "entity": entity,
            "category": category,
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
              f"(confidence={confidence:.3f})")

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

    Strategy:
        - Query the last 30 meal_logs for this user
        - Count how many times this meal appears
        - Add a small boost: min(0.05 * count, 0.15)
    """
    if not db or not user_id:
        return base_confidence

    try:
        logs_ref = db.collection("meal_logs") \
            .where("userId", "==", user_id) \
            .order_by("timestamp", direction="DESCENDING") \
            .limit(30)

        count = 0
        for doc in logs_ref.stream():
            log = doc.to_dict()
            if log.get("mealName") == meal.get("mealName"):
                count += 1

        if count > 0:
            boost = min(0.05 * count, 0.15)
            print(f"[Step 12] User preference boost for "
                  f"'{meal['mealName']}': +{boost:.2f} (logged {count}x)")
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
