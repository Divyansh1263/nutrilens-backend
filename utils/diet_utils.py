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
    Attach a dynamic 'explanation' field to a plan item dict.

    Macro handling (FIX 3+4):
      - If source_meal is the raw Firestore record (different object from item),
        compute macros as source_meal_base * item_quantity. This is the normal
        path for meals that exist in the Firestore lookup.
      - If source_meal IS the item itself (fallback: meal not in lookup, or
        optimizer-injected item), the macros on item are ALREADY quantity-scaled
        by the optimizer. Use them directly — do NOT multiply again.

    Explanation is always resolved from source_meal (carries 'explanations' dict).

    Args:
        item:        plan item dict (post-optimizer quantity + macros)
        source_meal: raw Firestore meal dict OR item itself as fallback
        user:        Firestore user profile dict

    Returns:
        enriched copy of item (macros correct, explanation attached)
    """
    enriched = dict(item)
    qty = float(item.get("quantity") or 1.0)
    enriched["quantity"] = qty

    # Detect whether source_meal is a genuine Firestore record or the item itself.
    # We consider it a "real" source when it has a different identity (is not item)
    # AND its calories represent a per-unit (single-serving) value.
    # Heuristic: if source_meal is not the same dict object as item, treat it as
    # per-unit; otherwise macros on item are already fully scaled.
    is_real_source = source_meal is not item

    if is_real_source:
        # Normal path: source_meal holds per-unit Firestore values.
        # Apply the item's optimizer-adjusted quantity to get final macros.
        base_cal   = float(source_meal.get("calories") or item.get("calories") or 0)
        base_prot  = float(source_meal.get("protein")  or item.get("protein")  or 0)
        base_carbs = float(source_meal.get("carbs")    or item.get("carbs")    or 0)
        base_fat   = float(source_meal.get("fat")      or item.get("fat")      or 0)
        enriched["calories"] = round(base_cal   * qty, 1)
        enriched["protein"]  = round(base_prot  * qty, 1)
        enriched["carbs"]    = round(base_carbs * qty, 1)
        enriched["fat"]      = round(base_fat   * qty, 1)
    else:
        # Fallback / injected-item path: macros on item are already qty-scaled
        # by the optimizer. Preserve them as-is (cast to float for type safety).
        enriched["calories"] = round(float(item.get("calories") or 0), 1)
        enriched["protein"]  = round(float(item.get("protein")  or 0), 1)
        enriched["carbs"]    = round(float(item.get("carbs")    or 0), 1)
        enriched["fat"]      = round(float(item.get("fat")      or 0), 1)

    # Explanation resolved from source_meal's 'explanations' dict.
    # source_meal may be item itself — resolve_explanation handles missing keys.
    enriched["explanation"] = resolve_explanation(source_meal, user)

    # TASK 2 FIX: carry servingSize from the Firestore record so the frontend
    # can display e.g. "1 bowl" without a separate lookup.
    # Prefer source_meal value; fall back to whatever is already on item.
    serving = source_meal.get("servingSize") or item.get("servingSize") or ""
    enriched["servingSize"] = serving

    return enriched
