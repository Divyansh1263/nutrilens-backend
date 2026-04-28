# routes/meal_routes.py
import os
from flask import Blueprint, request
from datetime import datetime
from utils.response_utils import success, error
from utils.logger import app_logger
from utils.auth_middleware import firebase_auth_optional, get_user_id_from_request
from validators.meal_validator import (
    validate_generate_plan, validate_log_meal,
    validate_update_log, validate_delete_log
)
from services.meal_generator_service import meal_generator_service
from services.meal_logging_service import meal_logging_service
from services.search_service import search_service

meal_bp = Blueprint('meal', __name__)

# ─────────────────────────────────────────────────────────────────────────────
# DEMO MODE — controlled via DEMO_MODE env variable.
# Set DEMO_MODE=true in Cloud Run to activate; defaults to false (real AI).
# Never hardcode True here — use the env var instead.
# ─────────────────────────────────────────────────────────────────────────────
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


def get_demo_meal_plan() -> dict:
    """Returns a realistic hardcoded meal plan used during DEMO_MODE.
    Meal names match the live dataset so the swap endpoint still works."""
    return {
        "breakfast": [
            {"mealName": "Masala Oats",  "calories": 150, "protein": 5,  "carbs": 25, "fat": 3,  "quantity": 1},
            {"mealName": "Boiled Egg",   "calories": 75,  "protein": 6,  "carbs": 1,  "fat": 5,  "quantity": 2},
        ],
        "lunch": [
            {"mealName": "Dal Tadka",    "calories": 300, "protein": 12, "carbs": 30, "fat": 10, "quantity": 1},
            {"mealName": "Plain Rice",   "calories": 200, "protein": 4,  "carbs": 45, "fat": 1,  "quantity": 1},
        ],
        "snack": [
            {"mealName": "Banana",       "calories": 100, "protein": 1,  "carbs": 27, "fat": 0,  "quantity": 1},
        ],
        "dinner": [
            {"mealName": "Roti",                    "calories": 120, "protein": 3, "carbs": 20, "fat": 3,  "quantity": 2},
            {"mealName": "Mixed Vegetable Sabzi",   "calories": 180, "protein": 5, "carbs": 15, "fat": 10, "quantity": 1},
        ],
        "target_calories": 1500,
        "target_macros":   {"protein": 90, "carbs": 150, "fat": 50},
        "total_calories":  1400,
    }


# =============================================================================
# GENERATION
# =============================================================================
@meal_bp.route("/generate-meal-plan", methods=["POST"])
@firebase_auth_optional
def generate_meal_plan():
    # TASK 3: DEMO MODE — short-circuit everything, return hardcoded plan
    if DEMO_MODE:
        from flask import jsonify
        print("[meal-plan] DEMO MODE ACTIVE — returning hardcoded plan")
        plan = get_demo_meal_plan()
        return jsonify({
            "success": True,
            "message": "Demo meal plan generated",

            # Nested "data" block — APK reads res['data']['breakfast']
            "data": {
                "breakfast":       plan["breakfast"],
                "lunch":           plan["lunch"],
                "snack":           plan["snack"],
                "dinner":          plan["dinner"],
                "target_calories": plan["target_calories"],
                "target_macros":   plan["target_macros"],
                "total_calories":  plan["total_calories"],
            },

            # Flat keys — kept for any client reading top-level
            "breakfast":       plan["breakfast"],
            "lunch":           plan["lunch"],
            "snack":           plan["snack"],
            "dinner":          plan["dinner"],
            "target_calories": plan["target_calories"],
            "target_macros":   plan["target_macros"],
            "total_calories":  plan["total_calories"],
        }), 200


    app_logger.info("[meal-plan] REAL MODE ACTIVE — using AI generation")
    data = request.get_json(force=True)
    is_valid, msg = validate_generate_plan(data)
    if not is_valid:
        return error(msg)

    user_id = get_user_id_from_request(data)
    date_str = data.get("date")
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # TASK 3: bypass stale cached plans — force AI regeneration every request.
    # Original cache lookup kept below for future re-enable.
    from repositories.tracker_repository import tracker_repo
    existing = None  # Cache bypass: was tracker_repo.get_plan_by_date(user_id, date_str)

    # --- ORIGINAL CACHE LOGIC (re-enable when cache invalidation is implemented) ---
    # existing = tracker_repo.get_plan_by_date(user_id, date_str)
    # if existing:
    #     existing = _normalize_plan_structure(existing)
    #     if not _is_plan_empty(existing):
    #         app_logger.info("[meal-plan] valid cached plan used for user=%s", user_id)
    #         return _meal_plan_response(existing, "Meal plan retrieved")
    #     app_logger.warning(
    #         "[meal-plan] cached plan empty → regenerating for user=%s date=%s",
    #         user_id, date_str
    #     )
    # --- END ORIGINAL CACHE LOGIC ---

    if existing:  # always False with bypass, kept for structural parity
        pass

    # Generate (or regenerate) — save_plan() inside overwrites Firestore
    try:
        plan, err = meal_generator_service.generate_daily_plan(user_id, date_str)
    except Exception as exc:
        app_logger.exception("generate_daily_plan crashed: %s", exc)
        return error(f"Internal error: {exc}", 500)

    if err:
        return error(err, 500 if "Error" in err else 400)

    # TASK 1: normalize fresh plan too (defensive)
    plan = _normalize_plan_structure(plan)

    # TASK 4: final safety — force-fill any still-empty slot
    slots = ("breakfast", "lunch", "snack", "dinner")
    if _is_plan_empty(plan):
        import random
        app_logger.warning("[meal-plan] WARNING: generated plan is empty → forcing fallback")
        from meals_cache import MEALS_CACHE
        pool = list(MEALS_CACHE) if MEALS_CACHE else []
        for slot in slots:
            if not plan.get(slot) and pool:
                m = random.choice(pool)
                plan[slot] = [{
                    "mealName": m.get("mealName", "fallback"),
                    "quantity":  1.0,
                    "calories": round(float(m.get("calories") or 0), 1),
                    "protein":  round(float(m.get("protein")  or 0), 1),
                    "carbs":    round(float(m.get("carbs")    or 0), 1),
                    "fat":      round(float(m.get("fat")      or 0), 1),
                }]

    # TASK 2: DEBUG PLAN — log full item keys before response serialization
    print("[DEBUG PLAN]", {
        slot: [
            {k: v for k, v in item.items()}
            for item in plan.get(slot, [])
        ]
        for slot in slots
    })

    return _meal_plan_response(plan, "Meal plan generated")



def _normalize_plan_structure(plan: dict) -> dict:
    """
    TASK 1: Normalize Firestore slot values so they are always Python lists.
    Firestore sometimes stores arrays as dicts {"0": {...}, "1": {...}}.
    Also coerces None slots to empty lists.
    """
    for key in ("breakfast", "lunch", "snack", "dinner"):
        val = plan.get(key)
        if isinstance(val, dict):
            plan[key] = list(val.values())   # {"0":{...}, "1":{...}} → [{...}, {...}]
        elif val is None:
            plan[key] = []
    return plan


def _is_plan_empty(plan: dict) -> bool:
    """
    TASK 2: Returns True when ALL meal slots are absent or empty.
    Uses normalization so Firestore dict-as-array is handled correctly.
    """
    if not plan:
        return True
    for key in ("breakfast", "lunch", "snack", "dinner"):
        val = plan.get(key)
        if isinstance(val, dict):
            val = list(val.values())
        if val and len(val) > 0:
            return False
    return True




def _meal_plan_response(plan, message):
    """
    TASK 5: Flat-only response — exactly what the existing APK expects.
    No nested 'data' key. Both cached and fresh paths use this helper.

    Fields preserved per item (TASKS 3+4):
      mealName, quantity, calories, protein, carbs, fat, explanation, servingSize
    Top-level analytics: optimization_score, score_label, macro_deviation
    """
    from utils.response_utils import sanitize_firestore_data
    from flask import jsonify

    # Normalize one final time (handles any Firestore dict-as-array edge cases)
    plan = _normalize_plan_structure(plan)
    clean = sanitize_firestore_data(plan)

    slots = ("breakfast", "lunch", "snack", "dinner")

    # TASK 6 / TASK 3: FINAL PLAN debug log — verify all fields present
    slot_counts = {s: len(clean.get(s) or []) for s in slots}
    print(f"[meal-plan] FINAL PLAN: {slot_counts}")
    for slot in slots:
        for item in (clean.get(slot) or []):
            has_explanation  = bool(item.get("explanation"))
            has_serving_size = bool(item.get("servingSize"))
            has_quantity     = item.get("quantity") is not None
            if not (has_explanation and has_serving_size and has_quantity):
                print(
                    f"[meal-plan] MISSING FIELDS in {slot}/{item.get('mealName')}: "
                    f"explanation={has_explanation} servingSize={has_serving_size} "
                    f"quantity={has_quantity}"
                )

    response = {
        "success":             True,
        "message":             message,
        # TASK 5: flat keys only — no 'data' envelope
        "breakfast":           clean.get("breakfast", []),
        "lunch":               clean.get("lunch",     []),
        "snack":               clean.get("snack",     []),
        "dinner":              clean.get("dinner",    []),
        "target_calories":     clean.get("target_calories"),
        "target_macros":       clean.get("target_macros"),
        "total_calories":      clean.get("total_calories"),
        # TASK 4: optimization analytics — frontend quality badge
        "optimization_score":  clean.get("optimization_score"),
        "score_label":         clean.get("score_label"),
        "macro_deviation":     clean.get("macro_deviation"),
    }

    assert "data" not in response, "[meal-plan] BUG: 'data' key must not be present"

    return jsonify(response), 200




# ==========================================
# MANUAL LOGGING & SEARCH
# ==========================================
@meal_bp.route("/search-food", methods=["GET"])
def search_food():
    # Accept both 'q' (frontend) and 'query' (legacy)
    query = request.args.get("q") or request.args.get("query", "")
    results = search_service.search_food(query)
    return success(results)

@meal_bp.route("/food-details", methods=["GET"])
def food_details():
    # Accept both 'name' (frontend) and 'food_name' (legacy)
    name = request.args.get("name") or request.args.get("food_name")
    if not name:
        return error("name required")
    details = search_service.get_food_details(name)
    if not details:
        return error("Food not found", 404)
    return success(details)

@meal_bp.route("/log-meal", methods=["POST"])
@firebase_auth_optional
def log_meal():
    data = request.get_json(force=True)
    is_valid, msg = validate_log_meal(data)
    if not is_valid:
        return error(msg)

    log_id, err = meal_logging_service.log_meal(
        user_id=get_user_id_from_request(data),  # B2 FIX: token-first
        meal_name=data.get("mealName"),
        quantity=data.get("quantity", 1),
        meal_type=data.get("mealType"),
        source=data.get("source", "manual"),
        date_str=data.get("date"),
        provided_macros={
            "calories": data.get("calories"),
            "protein": data.get("protein"),
            "carbs": data.get("carbs"),
            "fat": data.get("fat"),
        } if any(k in data for k in ["calories", "protein", "carbs", "fat"]) else None
    )
    if err:
        return error(err, 404)
    return success({"log_id": log_id}, "Meal logged successfully")

# ==========================================
# NLP ANALYSIS (Analyze only — no logging)
# ==========================================
@meal_bp.route("/analyze-meal-nlp", methods=["POST"])
def analyze_meal_nlp():
    """Identify meals from text without logging them.
    
    Request:  { "text": "2 roti and dal", "userId": "optional" }
    Response: { "success": true, "data": [{"mealName":..,"calories":..,"protein":..,"carbs":..,"fat":..,"quantity":..}] }
    """
    data = request.get_json(force=True)
    text = data.get("text")
    
    if not text:
        return error("text is required")
    
    from ai.nlp_pipeline import process_meal_text
    from repositories.tracker_repository import tracker_repo
    
    # Use sentinel userId/date — NLP pipeline should NOT persist with this userId
    result = process_meal_text(text, "__analyze_only__", "1970-01-01", db=None)
    
    if "error" in result:
        return error(result["error"], 400)
    
    # Normalize items: NLP pipeline uses "meal" key, frontend expects "mealName"
    raw_items = result.get("items", [])
    items = []
    for item in raw_items:
        items.append({
            "mealName": item.get("meal") or item.get("mealName") or "Unknown",
            "quantity": item.get("quantity", 1),
            "calories": item.get("calories", 0),
            "protein": item.get("protein", 0),
            "carbs": item.get("carbs", 0),
            "fat": item.get("fat", 0),
            "confidence": item.get("confidence", 0),
        })
    
    return success(items, f"Identified {len(items)} meal(s)")

# ==========================================
# NLP LOGGING (Analyze + Log — legacy)
# ==========================================

@meal_bp.route("/log-meal-nlp-ml", methods=["POST"])
@firebase_auth_optional
def log_meal_nlp_ml():
    data = request.get_json(force=True)
    user_id  = get_user_id_from_request(data)
    date_str = data.get("date")
    text     = data.get("text")
    
    if not user_id or not date_str or not text:
        return error("userId, date, and text are required")
        
    from ai.nlp_pipeline import process_meal_text
    from repositories.tracker_repository import tracker_repo
    
    result = process_meal_text(text, user_id, date_str, db=tracker_repo.db)
    
    if "error" in result:
        return error(result["error"], 400)
    
    # We must also trigger the tracker summary since logging happened natively in process_meal_text
    if len(result.get("items", [])) > 0:
        from services.tracker_service import tracker_service
        tracker_service.recalculate_daily_tracker(user_id, date_str)
        
    return success({"items": result.get("items", [])}, result.get("message", "NLP meals logged"))

@meal_bp.route("/update-log", methods=["PUT"])
@firebase_auth_optional
def update_log():
    data = request.get_json(force=True)
    is_valid, msg = validate_update_log(data)
    if not is_valid:
        return error(msg)

    log_id   = data.get("logId") or data.get("log_id")
    quantity = data.get("quantity")

    # update_log_quantity now returns a 3-tuple: (success, err_msg, updated_macros)
    result = meal_logging_service.update_log_quantity(log_id, quantity)
    success_status, err, updated_macros = result

    if not success_status:
        return error(err, 404)

    # TASK 1 FIX: include quantity in response so the UI never resets to the
    # old value.  updated_macros may or may not contain "quantity" already;
    # we always stamp it explicitly from the validated request value.
    return success({
        "quantity": quantity,
        "calories": updated_macros.get("calories"),
        "protein":  updated_macros.get("protein"),
        "carbs":    updated_macros.get("carbs"),
        "fat":      updated_macros.get("fat"),
    }, "Log quantity updated")

@meal_bp.route("/delete-log", methods=["DELETE"])
def delete_log():
    data = request.get_json(force=True)
    is_valid, msg = validate_delete_log(data)
    if not is_valid:
         return error(msg)
         
    success_status, err = meal_logging_service.delete_log(data.get("logId") or data.get("log_id"))
    if not success_status:
         return error(err, 404)
    return success({}, "Log deleted")

@meal_bp.route("/replace-meal", methods=["POST"])
def replace_meal():
    """
    Smart meal swap endpoint.

    Tiers:
      1. Case-insensitive meal lookup in DB
      2. KNN dietary-filtered replacements (find_replacements_for_user)
      3. Random pool top-up from in-memory cache (dietary-filtered)

    Always returns HTTP 200 with up to 5 suggestions.
    Dietary filter uses boolean flags only — never string matching.
    """
    data = request.get_json(force=True)
    meal_name = data.get("mealName")
    if not meal_name:
        return error("mealName required")

    print(f"[replace-meal] request: {meal_name}")

    from app import knn_model
    from repositories.meal_repository import meal_repo
    from utils.diet_utils import apply_diet_filter

    # ── Resolve user profile (for dietary filter + explanations) ───────────────
    _profile = {}
    try:
        user_id = get_user_id_from_request(data)
        if user_id:
            from repositories.user_repository import user_repo as _ur
            _profile = _ur.get_user_profile(user_id) or {}
    except Exception as _e:
        print(f"[replace-meal] profile fetch failed: {_e}")

    # TIER 1: Case-insensitive meal lookup
    meal = meal_repo.get_meal_by_name(meal_name)
    if not meal:
        try:
            from dev_store import MEALS_CACHE
            query = meal_name.lower().strip()
            candidates = [
                m for m in MEALS_CACHE
                if (m.get("mealName") or "").lower() == query
            ]
            if candidates:
                meal = candidates[0]
                print(f"[replace-meal] case-insensitive match: {meal['mealName']}")
        except Exception:
            pass

    suggestions = []

    # TIER 2: KNN — use find_replacements_for_user (TASK 1.2)
    if knn_model and knn_model.knn and meal:
        try:
            knn_suggestions = knn_model.find_replacements_for_user(
                meal=meal, user=_profile, k=5
            ) or []
            suggestions.extend(knn_suggestions)
            print(f"[replace-meal] KNN returned {len(knn_suggestions)} filtered suggestions")
        except Exception as e:
            print(f"[replace-meal] KNN failed: {e}")
    
    # TIER 3: Top up to 5 using random meals from global cache (0 Firestore reads)
    if len(suggestions) < 5:
        try:
            import random
            from meals_cache import MEALS_CACHE as _all_meals

            needed = 5 - len(suggestions)
            existing_names = {s.get("mealName", "") for s in suggestions} | {meal_name}

            available_meals = [
                m for m in _all_meals
                if m.get("mealName", "").lower() not in {n.lower() for n in existing_names}
                and _diet_ok(m)  # dietary filter applied here
            ]
            random.shuffle(available_meals)
    # TIER 3: Top up to 5 from in-memory cache (dietary-filtered)
    if len(suggestions) < 5:
        try:
            import random
            from repositories.meal_repository import meal_repo as _mr

            _all_meals  = _mr.get_all_meals()
            _diet_ok_pool = apply_diet_filter(_all_meals, _profile)

            needed        = 5 - len(suggestions)
            existing_names = {s.get("mealName", "").lower() for s in suggestions} | {meal_name.lower()}

            available = [
                m for m in _diet_ok_pool
                if m.get("mealName", "").lower() not in existing_names
            ]
            random.shuffle(available)
            suggestions.extend(available[:needed])
            print(f"[replace-meal] TIER 3 top-up: total={len(suggestions)}")
        except Exception as e:
            print(f"[replace-meal] TIER 3 failed: {e}")

    # ── Build response (include explanation per TASK 2.3) ───────────────────
    from utils.diet_utils import resolve_explanation

    result_suggestions = []
    for s in suggestions[:5]:
        mapped = {
            "mealName":    s.get("mealName", "Unknown"),
            "calories":    float(s.get("calories") or 100),
            "protein":     float(s.get("protein")  or 5),
            "carbs":       float(s.get("carbs")    or 20),
            "fat":         float(s.get("fat")      or 3),
            "explanation": resolve_explanation(s, _profile),
        }
        print(f"[replace-meal] suggestion: {mapped['mealName']} kcal={mapped['calories']}")
        result_suggestions.append(mapped)

    print(f"[replace-meal] returning {len(result_suggestions)} suggestions")
    return success({"aiSuggestions": result_suggestions}, "Replacements found")



@meal_bp.route("/swap-meal", methods=["POST"])
def swap_meal():
    data = request.get_json(force=True)
    log_id = data.get("mealLogId")
    new_meal_name = data.get("newMeal")
    if not log_id or not new_meal_name:
        return error("mealLogId and newMeal required")

    from repositories.tracker_repository import tracker_repo
    from repositories.meal_repository import meal_repo
    from services.tracker_service import tracker_service
    from firebase_admin import firestore as fs

    log = tracker_repo.get_log(log_id)
    if not log:
        return error("Log not found", 404)

    # ──────────────────────────────────────────────────────────
    # TIER 1: Exact Firestore match on mealName
    # ──────────────────────────────────────────────────────────
    new_meal = meal_repo.get_meal_by_name(new_meal_name)
    matched_by = "exact"

    # ──────────────────────────────────────────────────────────
    # TIER 2: Case-insensitive partial name match (in-memory)
    # ──────────────────────────────────────────────────────────
    if not new_meal:
        try:
            from app import MEALS
            query = new_meal_name.lower().strip()
            candidates = [
                m for m in MEALS
                if query in (m.get("mealName") or "").lower()
            ]
            if not candidates:
                # Try word-level: any word in query matches any word in name
                query_words = set(query.split())
                candidates = [
                    m for m in MEALS
                    if query_words & set((m.get("mealName") or "").lower().split())
                ]
            if candidates:
                new_meal = candidates[0]
                matched_by = "partial"
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # TIER 3: Closest-calorie fallback (same category preferred)
    # ──────────────────────────────────────────────────────────
    if not new_meal:
        try:
            from app import MEALS
            target_cal = float(log.get("calories") or 300) / float(log.get("quantity") or 1)
            target_cat = log.get("mealType", "")

            # Prefer same category
            pool = [m for m in MEALS if m.get("category", "").lower() == target_cat.lower()]
            if not pool:
                pool = MEALS  # fallback to all meals

            new_meal = min(
                pool,
                key=lambda m: abs((m.get("calories") or 0) - target_cal)
            )
            matched_by = "calorie_similar"
        except Exception:
            pass  # FIX 2: fall through to custom-meal creation instead of erroring

    # ──────────────────────────────────────────────────────────
    # FIX 2: TIER 4 — Custom meal (not in DB) — store with 0 macros
    # If the user typed a food not in the dataset, create it on-the-fly
    # so the swap always succeeds.
    # ──────────────────────────────────────────────────────────
    if not new_meal:
        new_meal = {
            "mealName": new_meal_name,
            "calories": 0,
            "protein":  0,
            "carbs":    0,
            "fat":      0,
        }
        matched_by = "custom"


    qty = float(log.get("quantity") or 1)
    new_calories = round((new_meal.get("calories") or 0) * qty, 1)
    new_protein  = round((new_meal.get("protein")  or 0) * qty, 1)
    new_carbs    = round((new_meal.get("carbs")    or 0) * qty, 1)
    new_fat      = round((new_meal.get("fat")      or 0) * qty, 1)

    # Write to Firestore with SERVER_TIMESTAMP
    db_updates = {
        "mealName":   new_meal.get("mealName", new_meal_name),
        "calories":   new_calories,
        "protein":    new_protein,
        "carbs":      new_carbs,
        "fat":        new_fat,
        "updated_at": fs.SERVER_TIMESTAMP
    }
    tracker_repo.update_log_quantity(log_id, db_updates)
    tracker_service.recalculate_daily_tracker(log["userId"], log["date"])

    # Return response without SERVER_TIMESTAMP
    response_data = {
        "mealName":   new_meal.get("mealName", new_meal_name),
        "calories":   new_calories,
        "protein":    new_protein,
        "carbs":      new_carbs,
        "fat":        new_fat,
        "matched_by": matched_by,  # tells client which tier resolved the meal
    }
    return success(response_data, f"Meal swapped successfully (matched by: {matched_by})")

# ==========================================
# DEBUG/ADMIN ENDPOINTS
# ==========================================
@meal_bp.route("/get-meal-combos", methods=["GET"])
def get_combos():
    from repositories.meal_repository import meal_repo
    combos = meal_repo.get_meal_combos()
    return success(combos)

@meal_bp.route("/get-meal-patterns", methods=["GET"])
def get_patterns():
    from ai.meal_patterns import MEAL_PATTERNS
    return success(MEAL_PATTERNS)
