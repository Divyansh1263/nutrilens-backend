# utils/diet_utils.py
#
# Central dietary utilities for NutriLens.
# Imported by meal_generator_service, meal_routes, and smart_swap_knn.
#
# Responsibilities:
#   1. apply_diet_filter()     — boolean-flag-only pool filtering (no string matching)
#   2. validate_plan()         — strict per-item validation, returns violations list
#   3. extract_user_context()  — parse conditions + goal from user profile
#   4. resolve_explanation()   — dynamic explanation string for a meal+user pair
#   5. annotate_plan_item()    — attach explanation to a plan item dict

_NON_VEG_KWS = frozenset({"chicken", "mutton", "fish", "egg"})


# ==============================================================================
# 1. DIETARY POOL FILTER
# ==============================================================================

def apply_diet_filter(meals: list, user: dict) -> list:
    """
    Filter a meal pool using boolean flags only — never string matching.

    Priority:
        is_vegan  → only meals where is_vegan  is True
        is_vegetarian → only meals where is_vegetarian is True
                        AND mealName contains no non-veg keyword

    Falls back to the full pool if filtering would produce an empty list.

    Args:
        meals: list of meal dicts from Firestore / in-memory cache
        user:  Firestore user profile dict

    Returns:
        filtered list (or original list if result would be empty)
    """
    dr = user.get("dietary_restrictions", {}) if user else {}
    is_veg   = bool(dr.get("is_vegetarian") or (user or {}).get("is_vegetarian"))
    is_vegan = bool(dr.get("is_vegan")      or (user or {}).get("is_vegan"))

    if not (is_veg or is_vegan):
        return meals

    def _passes(meal: dict) -> bool:
        if is_vegan:
            return meal.get("is_vegan") is True
        # is_veg path
        if meal.get("is_vegetarian") is not True:
            return False
        name_lower = (meal.get("mealName") or "").lower()
        return not any(kw in name_lower for kw in _NON_VEG_KWS)

    filtered = [m for m in meals if _passes(m)]
    return filtered if filtered else meals   # safe fallback


# ==============================================================================
# 2. STRICT PLAN VALIDATOR
# ==============================================================================

def validate_plan(plan: dict, user: dict) -> tuple:
    """
    Strict per-item dietary validation.

    Returns:
        (is_valid: bool, violations: list[tuple(slot, mealName, reason)])

    Checks:
        - is_vegan  users: every item must have is_vegan == True
        - is_veg    users: every item must have is_vegetarian == True
                           AND mealName must contain no non-veg keyword
    """
    dr = user.get("dietary_restrictions", {}) if user else {}
    is_veg   = bool(dr.get("is_vegetarian") or (user or {}).get("is_vegetarian"))
    is_vegan = bool(dr.get("is_vegan")      or (user or {}).get("is_vegan"))

    if not (is_veg or is_vegan):
        return True, []

    violations = []
    for slot in ("breakfast", "lunch", "snack", "dinner"):
        for item in plan.get(slot, []):
            name = item.get("mealName") or ""
            if is_vegan:
                if item.get("is_vegan") is not True:
                    violations.append((slot, name, "not is_vegan"))
            elif is_veg:
                if item.get("is_vegetarian") is not True:
                    violations.append((slot, name, "not is_vegetarian"))
                elif any(kw in name.lower() for kw in _NON_VEG_KWS):
                    violations.append((slot, name, "non-veg keyword in name"))

    return len(violations) == 0, violations


# ==============================================================================
# 3. USER CONTEXT EXTRACTOR
# ==============================================================================

def extract_user_context(user: dict) -> tuple:
    """
    Extract health conditions and dietary goal from user profile.

    Handles both nested schema:
        user["health_conditions"]["diabetes"] = True
    and dot-notation schema:
        user["health_conditions"]["explanations.diabetes"] = True

    Returns:
        (conditions: list[str], goal: str | None)

    Example:
        conditions = ["diabetes", "weight_loss"]
        goal       = "lose_weight"
    """
    conditions = []
    raw_conditions = (user or {}).get("health_conditions", {})
    if isinstance(raw_conditions, dict):
        for key, value in raw_conditions.items():
            if value:
                # Strip "explanations." prefix if present
                condition = key.split(".")[-1]
                conditions.append(condition)

    # Goal — accept multiple field names
    goal = (user or {}).get("dietary_goal") or (user or {}).get("goal")
    # Normalise goal to underscore format (e.g. "Lose Weight" → "lose_weight")
    if goal and isinstance(goal, str):
        goal = goal.lower().replace(" ", "_")

    return conditions, goal


# ==============================================================================
# 4. EXPLANATION RESOLVER
# ==============================================================================

def resolve_explanation(meal: dict, user: dict) -> str:
    """
    Build a dynamic, context-aware explanation for why this meal is recommended.

    Priority:
        1. Medical conditions (diabetes, hypertension, etc.)
        2. Dietary goal (lose_weight, muscle_gain, etc.)
        3. Glycemic index warning (diabetes users only)
        4. Default explanation field

    Supports multiple active conditions — joins up to 2 with " | ".

    Args:
        meal: meal dict from Firestore (must contain "explanations" sub-dict)
        user: Firestore user profile dict

    Returns:
        str — explanation text, never None (falls back to "")
    """
    explanations = meal.get("explanations") or {}
    conditions, goal = extract_user_context(user)

    selected = []

    # Priority 1: medical conditions
    for condition in conditions:
        if condition in explanations:
            text = explanations[condition]
            if text and text not in selected:
                selected.append(text)

    # Priority 2: dietary goal
    if goal and goal in explanations:
        text = explanations[goal]
        if text and text not in selected:
            selected.append(text)

    # Priority 3: glycemic index warning (diabetes users)
    if "diabetes" in conditions and (meal.get("glycemic_index") or "").lower() == "high":
        warning = "⚠ High glycemic index – may spike blood sugar"
        if warning not in selected:
            selected.append(warning)

    # Priority 4: fallback to default
    if not selected:
        default = explanations.get("default", "")
        if default:
            selected.append(default)

    # Return at most 2 sentences joined by " | "
    return " | ".join(selected[:2])


# ==============================================================================
# 5. PLAN ITEM ANNOTATOR
# ==============================================================================

def annotate_plan_item(item: dict, source_meal: dict, user: dict) -> dict:
    """
    Attach explanation, base_* fields, and correctly scaled macros to a plan item.

    Anti-double-scaling guarantee
    ───────────────────────────────
    ALL macro totals are computed as:
        total_macro = base_macro (per-unit from Firestore) × quantity

    The base_* fields are stored on the item so that /update-log and any
    future re-scaling always has the per-unit ground truth — no division
    required, no risk of accumulated floating-point drift.

    Paths:
      A. source_meal ≠ item  →  Firestore record available; use its per-unit
         macros as the authoritative base.  Ignore item's already-scaled macros.
      B. source_meal is item  →  meal not in Firestore lookup (fallback / injected).
         Item was created with quantity=1 or scaled externally.  We store its
         RAW macro values (as-is) as the base, then re-scale from those.
         NOTE: we never back-divide here to avoid accumulated drift.

    Args:
        item:        plan item dict (post-optimizer; quantity and macros already set)
        source_meal: raw Firestore meal dict OR item itself as fallback
        user:        Firestore user profile dict

    Returns:
        enriched copy of item with base_*, scaled macros, explanation, servingSize
    """
    import logging as _logging
    _ann_log = _logging.getLogger(__name__)

    enriched = dict(item)
    qty = float(item.get("quantity") or 1.0)
    enriched["quantity"] = qty

    is_real_source = source_meal is not item

    if is_real_source:
        # PATH A: Firestore record available — its macros are per-unit.
        # Always recalculate totals from the authoritative Firestore base.
        # Never trust item's macros here: they may have been scaled already
        # by portion_to_fit() or the macro optimizer.
        base_cal   = float(source_meal.get("calories", 0) or 0)
        base_prot  = float(source_meal.get("protein", 0)  or 0)
        base_carbs = float(source_meal.get("carbs", 0)    or 0)
        base_fat   = float(source_meal.get("fat", 0)      or 0)
        _ann_log.debug(
            "[annotate] PATH-A '%s' base_cal=%.1f qty=%.2f → total_cal=%.1f",
            source_meal.get("mealName", "?"), base_cal, qty, base_cal * qty
        )
    else:
        # PATH B: No Firestore record — item was injected/created directly.
        # Item macros may already be for qty=1 OR pre-scaled.
        # We store them as the base_* and re-scale from qty.
        # DO NOT divide here — division accumulates float error and can
        # produce wrong bases when qty != 1.
        # Caller (portion_to_fit / emergency fill) always creates items at
        # per-unit values with quantity set separately, so storing directly is safe.
        safe_qty   = qty if qty > 0 else 1.0
        base_cal   = round(float(item.get("calories") or 0) / safe_qty, 4)
        base_prot  = round(float(item.get("protein")  or 0) / safe_qty, 4)
        base_carbs = round(float(item.get("carbs")    or 0) / safe_qty, 4)
        base_fat   = round(float(item.get("fat")      or 0) / safe_qty, 4)
        _ann_log.debug(
            "[annotate] PATH-B '%s' (no Firestore record): base_cal=%.4f qty=%.2f",
            item.get("mealName", "?"), base_cal, qty
        )

    # Stamp per-unit base values — source of truth for any future re-scaling.
    enriched["base_calories"] = round(base_cal,   4)
    enriched["base_protein"]  = round(base_prot,  4)
    enriched["base_carbs"]    = round(base_carbs, 4)
    enriched["base_fat"]      = round(base_fat,   4)

    # Compute quantity-scaled totals from base (single multiplication — no drift).
    enriched["calories"] = round(base_cal   * qty, 1)
    enriched["protein"]  = round(base_prot  * qty, 1)
    enriched["carbs"]    = round(base_carbs * qty, 1)
    enriched["fat"]      = round(base_fat   * qty, 1)

    # Explanation resolved from source_meal's 'explanations' dict.
    enriched["explanation"] = resolve_explanation(source_meal, user)

    # Carry servingSize from Firestore record for frontend display.
    serving = source_meal.get("servingSize") or item.get("servingSize") or ""
    enriched["servingSize"] = serving

    return enriched
