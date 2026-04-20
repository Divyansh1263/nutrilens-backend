# ai/meal_plan_generator.py
# Meal Plan Generator v3 — Macro-balanced, protein-prioritised
#
# IMPROVEMENTS over v2:
#   1. Macro Balancing Solver
#   2. Protein Prioritisation
#   3. Calorie Tolerance ±3%
#   4. Fixed _apply_portions()
#   5. Meal logging correctness
#   6. Combined candidate score inside solve_meal()
#   TASK 6: is_vegetarian strict filter applied BEFORE scoring (per meal type)
#   TASK 5/6: Calorie-aware penalty added to candidate scoring + debug logging

import random
import copy
from ai.meal_patterns import (
    MEAL_PATTERNS, get_portion, infer_derived_tag,
    HEAVY_DISH_KEYWORDS, CARB_BASE_KEYWORDS,
)
from ai.compatibility_scorer import score_combination

# ==============================================================================
# 1. CONSTANTS
# ==============================================================================
MEAL_SPLIT = {
    "Breakfast": 0.25,
    "Lunch": 0.35,
    "Dinner": 0.30,
    "Snack": 0.10,
}

# Number of candidate meals to generate before scoring
NUM_CANDIDATES = 10

# Penalty applied per recent occurrence of the same meal (variety control)
# Relaxed -8 → -3 (TASK 3) to prevent over-pruning of valid candidates
VARIETY_PENALTY = -3


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================

def get_tags(meal):
    """Safely extract semantic tags with defaults."""
    return {
        "cuisine": meal.get("cuisine", "indian").lower(),
        "group": meal.get("food_group", "grain").lower(),
        "role": meal.get("meal_role", "main").lower(),
        "name": meal.get("mealName", ""),
    }


def filter_candidates(candidates, filters):
    """
    Filter candidate meals based on criteria.
    filters: dict of {key: value or list_of_values}
    """
    matches = []
    for meal in candidates:
        tags = get_tags(meal)
        match = True

        for key, criteria in filters.items():
            if key == "exclude_names":
                if tags["name"] in criteria:
                    match = False
                    break
                continue
            if key == "exclude_ids":
                if meal.get("id", tags["name"]) in criteria:
                    match = False
                    break
                continue

            meal_val = tags.get(key)

            if isinstance(criteria, list):
                if criteria == ["all"]:
                    continue
                if meal_val not in criteria:
                    match = False
                    break
            else:
                if meal_val != criteria:
                    match = False
                    break

        if match:
            matches.append(meal)

    return matches


def pick_valid_pattern(meal_type, candidates):
    """
    Select a meal pattern that can be fulfilled by available candidates.

    Returns:
        pattern dict or None
    """
    available_patterns = MEAL_PATTERNS.get(meal_type, [])
    valid_patterns = []

    for pattern in available_patterns:
        # Check cuisine availability
        cuisine_pool = filter_candidates(candidates, {"cuisine": pattern["cuisine"]})
        if not cuisine_pool:
            continue

        # Check required slots can be filled
        possible = True
        for slot in pattern["slots"]:
            if not slot["required"]:
                continue

            criteria = {}
            if slot["role"]:
                criteria["role"] = slot["role"]
            if slot["group"]:
                criteria["group"] = slot["group"]

            slot_options = filter_candidates(cuisine_pool, criteria)
            if not slot_options:
                possible = False
                break

        if possible:
            valid_patterns.append(pattern)

    if not valid_patterns:
        # Fallback: return first pattern and try best-effort
        return available_patterns[0] if available_patterns else None

    return random.choice(valid_patterns)


# ==============================================================================
# 3. SCORING HELPER FUNCTIONS
# ==============================================================================

def _compute_macro_score(items, target_macros):
    """
    FIX #1: Macro Balancing Solver with Remaining-Aware Scoring.

    Penalises candidates whose combined macros deviate from the SLOT-proportional
    macro targets (not the full-day targets).  Protein deviation is double-weighted
    because it carries the most nutritional importance.
    
    Strategic Scoring:
      • If remaining protein is high: reward high-protein candidates
      • If remaining fat is low: avoid high-fat candidates
      • If remaining calories are small: prefer lower-calorie combinations

    Formula:
        score = -(protein_deviation * 2 + carbs_deviation + fat_deviation)

    Args:
        items:        list of meal dicts in this candidate
        target_macros: dict {protein, carbs, fat} — SLOT-proportional or remaining targets

    Returns:
        float score (negative = bad, closer to 0 = good)
    """
    if not target_macros:
        return 0

    total_protein = sum(item.get("protein", 0) or 0 for item in items)
    total_carbs   = sum(item.get("carbs",   0) or 0 for item in items)
    total_fat     = sum(item.get("fat",     0) or 0 for item in items)

    protein_target = target_macros.get("protein", 0)
    carbs_target = target_macros.get("carbs", 0)
    fat_target = target_macros.get("fat", 0)

    # Calculate deviations
    protein_dev = abs(total_protein - protein_target)
    carbs_dev   = abs(total_carbs   - carbs_target)
    fat_dev     = abs(total_fat     - fat_target)

    # Strategic weighting based on remaining targets
    # If remaining target is high, overages are less penalized
    # If remaining target is low, we need exact matches
    protein_weight = 2.0  # Always prioritize protein
    
    if protein_target > 0:
        # If target is small, penalize deviations more harshly
        protein_weight = 2.0 if protein_target > 30 else 3.0
    
    if fat_target > 0 and fat_target < 20:
        # Fat is low in remaining — strictly penalize high-fat candidates
        fat_dev *= 1.5

    score = -(protein_dev * protein_weight + carbs_dev + fat_dev)
    return score


def _compute_protein_density_score(items):
    """
    FIX #2: Protein Prioritisation.

    Rewards candidates with a high protein-to-calorie ratio.
    Meals with eggs, paneer, dal, yogurt naturally score higher than
    pure carb-heavy meals (rice-only, fruit-only).

    Guard: returns 0 if total calories are 0.

    Returns:
        float — protein_density * 100 (higher = better)
    """
    total_protein  = sum(item.get("protein",  0) or 0 for item in items)
    total_calories = sum(item.get("calories", 0) or 0 for item in items)

    # FIX guard: avoid zero-division if database entry has 0 calories
    if total_calories == 0:
        return 0

    protein_density = total_protein / total_calories
    return protein_density * 100


def _compute_calorie_tolerance_score(portioned_calories, target_calories):
    """
    FIX #3: Calorie Tolerance ±3%.

    NOTE: This function must be called AFTER _apply_portions() so that
    portioned_calories reflects the actual scaled quantities, not raw values.

    Scoring:
        Within ±3% of target  →  +5 (strong positive)
        Within ±10% of target →  +1 (small positive)
        Outside ±10%          →  -3 (negative)

    Returns:
        int score
    """
    if not target_calories or target_calories == 0:
        return 0

    ratio = portioned_calories / target_calories

    if 0.97 <= ratio <= 1.03:   # ±3 %
        return 5
    elif 0.90 <= ratio <= 1.10:  # ±10 %
        return 1
    else:
        return -3


# ==============================================================================
# 4. CORE GENERATION — Refactored solve_meal()
# ==============================================================================

def _generate_one_candidate(pattern, pool, target_calories):
    """
    Generate a single candidate meal by filling pattern slots.

    Returns:
        list of meal dicts (the items in this candidate)
    """
    selected = []
    used_names = set()

    # Randomly pick cuisine from pattern's allowed list
    allowed_cuisines = pattern["cuisine"]
    if allowed_cuisines == ["all"]:
        all_c = list(set(get_tags(m)["cuisine"] for m in pool))
        cuisine = random.choice(all_c) if all_c else "indian"
    else:
        cuisine = random.choice(allowed_cuisines)

    cuisine_pool = filter_candidates(pool, {"cuisine": [cuisine]})

    # Fill slots in order (required first, then optional)
    all_slots = pattern["slots"]
    constraints = pattern.get("constraints", {})
    max_carb = constraints.get("max_carb_base", 1)
    max_heavy = constraints.get("max_heavy_curry", 1)

    carb_count = 0
    heavy_count = 0

    for slot in all_slots:
        if len(selected) >= pattern["max_items"]:
            break

        # Build filter criteria
        criteria = {"exclude_names": used_names}
        if slot["role"]:
            criteria["role"] = slot["role"]
        if slot["group"]:
            criteria["group"] = slot["group"]

        options = filter_candidates(cuisine_pool, criteria)

        # FIX 4: Three-tier fallback for required slots so they are ALWAYS filled.
        # Tier 1: cuisine + role + group (already done above)
        # Tier 2: cuisine + role only (drop group restriction)
        # Tier 3: full pool, role only (drop both cuisine and group restrictions)
        # This ensures meals like Roti Thali always have ≥ 2 items.
        if not options and slot["required"]:
            relaxed = {"exclude_names": used_names}
            if slot["role"]:
                relaxed["role"] = slot["role"]
            # Try within cuisine pool first (relax group)
            options = filter_candidates(cuisine_pool, relaxed)

        if not options and slot["required"]:
            # Last resort: search the ENTIRE pool (ignore cuisine), role only
            relaxed_full = {"exclude_names": used_names}
            if slot["role"]:
                relaxed_full["role"] = slot["role"]
            options = filter_candidates(pool, relaxed_full)

        if not options and slot["required"]:
            # Absolute fallback: any unused item in the full pool
            options = [m for m in pool if m.get("mealName", "") not in used_names]

        if not options:
            continue  # only skip truly optional empty slots

        # Filter by collision constraints
        filtered_options = []
        for opt in options:
            dtag = infer_derived_tag(opt)
            if dtag == "carb_base" and carb_count >= max_carb:
                continue
            if dtag == "heavy_dish" and heavy_count >= max_heavy:
                continue
            filtered_options.append(opt)

        if not filtered_options:
            if slot["required"]:
                filtered_options = options[:3]  # Fallback: use unfiltered
            else:
                continue

        # Random selection
        choice = random.choice(filtered_options)
        selected.append(choice)
        used_names.add(choice.get("mealName", ""))

        # Update constraint counts
        dtag = infer_derived_tag(choice)
        if dtag == "carb_base":
            carb_count += 1
        if dtag == "heavy_dish":
            heavy_count += 1

    return selected, cuisine



def _apply_portions(items, pattern):
    """
    FIX #4: Portion Scaling Fix.

    Apply PORTION_RULES strictly. Quantities are set to portion["default"]
    and are NEVER increased to plug a calorie deficit.

    Original scaling block removed:
        Previously, if total_calories < target * 0.8, the generator increased
        the main item's quantity — causing "Mint Rice x3" style entries.
        This block is now deleted.

    Returns:
        (list of item dicts with 'quantity' set, total_calories: int)
    """
    final_items = []
    current_calories = 0

    for i, item in enumerate(items):
        item_copy = copy.deepcopy(item)

        # Determine slot label for portion lookup
        slot_label = "carb_base"  # default
        if i < len(pattern["slots"]):
            slot_label = pattern["slots"][i].get("label", "carb_base")

        portion = get_portion(item, slot_label)

        # FIX: Strictly use PORTION_RULES default — do NOT scale to fill calorie gap
        qty = portion["default"]
        item_copy["quantity"] = qty
        current_calories += item.get("calories", 0) * qty

        final_items.append(item_copy)

    return final_items, round(current_calories)


def _compute_variety_penalty(items, recent_meals):
    """
    Penalize items that appeared in recent meal plans (last 3 days).

    Args:
        items:        list of meal dicts in this candidate
        recent_meals: set of meal names from recent plans

    Returns:
        penalty score (negative integer)
    """
    if not recent_meals:
        return 0

    penalty = 0
    for item in items:
        name = item.get("mealName", "")
        if name in recent_meals:
            penalty += VARIETY_PENALTY

    return penalty


# TASK 4: Meal completeness check
# Keywords defining carb sources and protein sources for balance check.
_CARB_KEYWORDS   = {
    "rice", "roti", "chapati", "chapatti", "naan", "paratha",
    "bread", "poha", "upma", "idli", "dosa", "oats", "millet",
}
_PROTEIN_KEYWORDS = {
    "dal", "lentil", "paneer", "egg", "chicken", "mutton", "fish",
    "prawn", "tofu", "chana", "rajma", "chole", "moong", "soya",
    "curd", "yogurt", "dahi",
}


# Minimum protein grams for an item to count as a protein source (TASK 4)
# Relaxed 5.0 → 3.0 (TASK 4 relax) to avoid rejecting low-but-valid protein items
MIN_PROTEIN_G = 3.0


def _check_meal_completeness(items):
    """
    TASK 4 + TASK 5: Ensure candidate has at least one carb + one protein source.

    TASK 5 addition: An item only counts as a protein source when its protein
    field is ≥ MIN_PROTEIN_G (5g). Items labelled as protein by name/food_group
    but with negligible protein content are excluded.

    Returns:
        (is_complete: bool, penalty: float, details: str)
    """
    has_carb    = False
    has_protein = False
    protein_log = []   # TASK 6: per-item protein detection log

    for item in items:
        name_lower = item.get("mealName", "").lower()
        food_group = item.get("food_group", "").lower()
        item_protein = item.get("protein", 0) or 0

        if not has_carb:
            has_carb = (
                any(kw in name_lower for kw in _CARB_KEYWORDS)
                or food_group in {"grain", "bread", "cereal"}
            )

        if not has_protein:
            # Check name/food_group match first
            name_or_group_match = (
                any(kw in name_lower for kw in _PROTEIN_KEYWORDS)
                or food_group in {"legume", "protein", "dairy", "meat", "poultry"}
            )
            # TASK 5: also require protein quantity ≥ MIN_PROTEIN_G
            if name_or_group_match:
                if item_protein >= MIN_PROTEIN_G:
                    has_protein = True
                    protein_log.append(
                        f"{item.get('mealName','?')}(protein={item_protein:.1f}g ✓)"
                    )
                else:
                    # Name matched but protein too low — skip
                    protein_log.append(
                        f"{item.get('mealName','?')}(protein={item_protein:.1f}g<{MIN_PROTEIN_G}g ✗)"
                    )
            else:
                protein_log.append(
                    f"{item.get('mealName','?')}(no_protein_match)"
                )

        if has_carb and has_protein:
            break

    is_complete = has_carb and has_protein
    missing = []
    if not has_carb:
        missing.append("carb")
    if not has_protein:
        missing.append("protein")

    COMPLETENESS_PENALTY = -5.0
    penalty  = COMPLETENESS_PENALTY if not is_complete else 0.0
    details  = "OK" if is_complete else f"missing={missing}"

    # TASK 6: always print protein detection result
    print(f"[completeness] {details}  protein_detection={protein_log}")

    return is_complete, penalty, details


def solve_meal(pattern, candidates, target_calories, target_macros=None, recent_meals=None):
    """
    REFACTORED solve_meal() v3 — macro-balanced, protein-prioritised.

    FIX #6: Candidate Scoring Integration.

    Algorithm:
      1. Generate NUM_CANDIDATES candidate meal combinations
      2. Score each with:
            compatibility_score  (pair-wise culinary rules)
            macro_score          (deviation from slot-proportional macro targets)
            protein_density_score (rewards high-protein candidates)
            variety_penalty      (penalises recently-used meals)
      3. Select the highest-scoring candidate (macro/protein/compat combined)
      4. Apply PORTION_RULES strictly to the best candidate
      5. Compute calorie_tolerance_score AFTER portioning (accurate calories)
         — used for logging/reporting, not re-selection (pool size is fixed)

    Args:
        pattern:         pattern dict from MEAL_PATTERNS
        candidates:      list of candidate meal dicts
        target_calories: calorie target for this meal SLOT
        target_macros:   dict {protein, carbs, fat} — SLOT-proportional targets
                         (computed in generate_full_meal_plan as daily * split ratio)
        recent_meals:    set of meal names from last 3 days (for variety)

    Returns:
        dict: {items, mealCalories, cuisineTheme, template, calorie_ok}
    """
    if recent_meals is None:
        recent_meals = set()

    if target_macros is None:
        target_macros = {}

    best_candidate = None
    best_score = -9999
    best_cuisine = "indian"

    for attempt in range(NUM_CANDIDATES):
        # Step 1: Generate one candidate
        items, cuisine = _generate_one_candidate(
            pattern, candidates, target_calories
        )

        if not items:
            continue

        # Step 2: Score it — macro/protein scores use RAW item values
        # (before portioning), which is sufficient for candidate selection.
        # Calorie tolerance score runs after portioning (see Step 5 below).

        # FIX #6: Combined candidate score
        compat_score          = score_combination(items, target_calories=target_calories)["score"]
        macro_score           = _compute_macro_score(items, target_macros)
        protein_density_score = _compute_protein_density_score(items)
        variety_penalty       = _compute_variety_penalty(items, recent_meals)

        # TASK 2 (relaxed): Calorie-aware penalty.
        # Old formula: (ratio^1.5) * 0.4  — too harsh, caused empty results.
        # New formula: (ratio^1.2) * 0.25 — gentler convex penalty.
        raw_cals = sum(item.get("calories", 0) or 0 for item in items)
        if target_calories and target_calories > 0:
            cal_ratio = abs(raw_cals - target_calories) / target_calories
            calorie_penalty = (cal_ratio ** 1.2) * 0.25
        else:
            calorie_penalty = 0.0

        # TASK 4: Meal completeness check
        is_complete, completeness_penalty, completeness_details = _check_meal_completeness(items)

        total_score = (
            compat_score
            + macro_score
            + protein_density_score
            + variety_penalty
            - calorie_penalty            # TASK 3
            + completeness_penalty       # TASK 4 (0 or -5)
        )

        # TASK 5 / TASK 6: Debug log per candidate
        item_names = [i.get("mealName", "?") for i in items]
        print(
            f"[solve_meal] attempt={attempt+1}  items={item_names}  "
            f"raw_cal={raw_cals:.0f}  target_cal={target_calories:.0f}  "
            f"cal_penalty={calorie_penalty:.3f}  "
            f"completeness={completeness_details}  comp_penalty={completeness_penalty:.1f}  "
            f"compat={compat_score:.2f}  macro={macro_score:.2f}  "
            f"protein_density={protein_density_score:.2f}  variety={variety_penalty:.1f}  "
            f"total_score={total_score:.3f}"
        )

        # Step 3: Track best candidate
        if total_score > best_score:
            best_score = total_score
            best_candidate = items
            best_cuisine = cuisine

    if best_candidate is None:
        # TASK 1: Fallback — calorie-proximity only, ignore all penalties
        print("[meal-plan] fallback triggered — no candidate passed scoring; using calorie-proximity fallback")
        if candidates:
            # Pick top-N meals closest to target calories, ignoring completeness/variety/protein
            sorted_by_cal = sorted(
                candidates,
                key=lambda m: abs((m.get("calories") or 0) - target_calories)
            )
            fallback_items = sorted_by_cal[:2]  # take the 2 closest
            fallback_copies = []
            for fb in fallback_items:
                fb_copy = copy.deepcopy(fb)
                fb_copy["quantity"] = 1
                fallback_copies.append(fb_copy)
            fallback_cals = sum(f.get("calories", 0) for f in fallback_copies)
            return {
                "items": fallback_copies,
                "mealCalories": round(fallback_cals),
                "cuisineTheme": get_tags(fallback_copies[0])["cuisine"] if fallback_copies else "indian",
                "template": pattern["name"],
                "calorie_ok": False,
            }
        return {
            "items": [], "mealCalories": 0, "cuisineTheme": "indian",
            "template": pattern["name"], "calorie_ok": False,
        }

    # Step 4: Apply PORTION_RULES strictly (no calorie-deficit inflation)
    portioned_items, total_cals = _apply_portions(best_candidate, pattern)

    # Step 5: Calorie tolerance — computed AFTER portioning for accuracy
    # FIX #3: Uses real portioned calories, not raw item sum
    calorie_tolerance_score = _compute_calorie_tolerance_score(total_cals, target_calories)
    calorie_ok = calorie_tolerance_score >= 1  # True if within ±10 %

    return {
        "items": portioned_items,
        "mealCalories": total_cals,
        "cuisineTheme": best_cuisine,
        "template": pattern["name"],
        "calorie_ok": calorie_ok,
    }


# ==============================================================================
# 5. ORCHESTRATOR
# ==============================================================================

def generate_full_meal_plan(target, meals_by_type, recent_meals=None, is_vegetarian=False):
    """
    ISSUE 1 FIX: Sequential Macro-Aware Generation.

    Generate a complete daily meal plan with sequential macro tracking.
    After each meal, remaining macros are updated so subsequent meals compensate.

    TASK 6: Vegetarian Pre-filter.
    When is_vegetarian=True, each meal type pool is filtered to only meals
    where is_vegetarian==True BEFORE any scoring takes place.
    Falls back to the full pool for a meal type if no vegetarian meals exist.

    Args:
        target:        dict with {calories, protein, carbs, fat}
        meals_by_type: dict with {Breakfast: [...], Lunch: [...], ...}
        recent_meals:  optional set of meal names from last 3 days
        is_vegetarian: if True, filter each pool to vegetarian meals only

    Returns:
        plan dict with total_calories and validation status
    """
    if recent_meals is None:
        recent_meals = set()

    # ── TASK 6 / strict TASK 4: Vegetarian pre-filter (applied BEFORE scoring) ─
    if is_vegetarian:
        # Non-veg keywords that must NOT appear in mealName (case-insensitive)
        NON_VEG_KEYWORDS = {"chicken", "mutton", "fish", "egg"}

        def _is_strict_veg(meal):
            """Meal passes if flagged vegetarian AND name contains no non-veg word."""
            if meal.get("is_vegetarian") is not True:
                return False
            name_lower = meal.get("mealName", "").lower()
            return not any(kw in name_lower for kw in NON_VEG_KEYWORDS)

        filtered_by_type = {}
        for meal_type, meals in meals_by_type.items():
            veg_meals = [m for m in meals if _is_strict_veg(m)]
            if veg_meals:
                filtered_by_type[meal_type] = veg_meals
                print(
                    f"[Meal Plan] Strict-veg filter: {meal_type} pool "
                    f"{len(meals)} → {len(veg_meals)} (veg-only, non-veg keywords excluded)"
                )
            else:
                # Fallback: relax keyword check, keep flag-only filter
                flag_only = [m for m in meals if m.get("is_vegetarian") is True]
                if flag_only:
                    filtered_by_type[meal_type] = flag_only
                    print(
                        f"[Meal Plan] Strict-veg filter: {meal_type} — "
                        f"no strict-veg meals; relaxed to is_vegetarian flag only "
                        f"({len(flag_only)} meals)"
                    )
                else:
                    filtered_by_type[meal_type] = meals
                    print(
                        f"[Meal Plan] Strict-veg filter: {meal_type} — "
                        f"no veg meals at all, using full pool ({len(meals)} meals)"
                    )
        meals_by_type = filtered_by_type

    # STEP 1: Initialize remaining targets
    remaining = {
        "calories": float(target["calories"]),
        "protein": float(target["protein"]),
        "carbs": float(target["carbs"]),
        "fat": float(target["fat"]),
    }

    plan = {
        "target_calories": target["calories"],
        "target_macros": {
            "protein": target["protein"],
            "carbs": target["carbs"],
            "fat": target["fat"],
        },
    }

    total_generated_calories = 0
    total_generated_protein = 0
    total_generated_carbs = 0
    total_generated_fat = 0
    today_meals = set()  # Track meals chosen today for cross-meal variety

    order = ["Breakfast", "Lunch", "Snack", "Dinner"]

    for meal_index, meal_type in enumerate(order):
        candidates = meals_by_type.get(meal_type, [])
        if not candidates:
            plan[meal_type.lower()] = {"items": [], "mealCalories": 0}
            continue

        # 1. Pick a valid pattern
        pattern = pick_valid_pattern(meal_type, candidates)
        if not pattern:
            plan[meal_type.lower()] = {
                "items": [], "mealCalories": 0, "error": "No valid pattern"
            }
            continue

        # STEP 2: Compute target using remaining macros (sequential awareness)
        # For the last meal, use all remaining - otherwise use proportional split
        if meal_index == (len(order) - 1):  # Last meal (Dinner)
            # Use ALL remaining for final meal
            meal_target_cals = max(100, remaining["calories"])  # min 100 cal
            meal_macro_target = {
                "protein": max(5, remaining["protein"]),  # clamp to prevent negatives
                "carbs": max(10, remaining["carbs"]),
                "fat": max(5, remaining["fat"]),
            }
        else:
            # For earlier meals, use a portion of remaining
            # Split remaining proportionally based on default meal split
            split_ratio = MEAL_SPLIT.get(meal_type, 0.25)
            meal_target_cals = remaining["calories"] * split_ratio
            
            meal_macro_target = {
                "protein": remaining["protein"] * split_ratio,
                "carbs": remaining["carbs"] * split_ratio,
                "fat": remaining["fat"] * split_ratio,
            }

        # 3. Combine recent meals + today's meals for variety
        combined_recent = recent_meals | today_meals

        # 4. Solve with remaining-aware targets
        solved_meal = solve_meal(
            pattern,
            candidates,
            meal_target_cals,
            target_macros=meal_macro_target,
            recent_meals=combined_recent,
        )

        # STEP 3: Subtract actual macros from remaining (sequential awareness)
        for item in solved_meal.get("items", []):
            qty = item.get("quantity", 1)
            item_calories = item.get("calories", 0) * qty
            item_protein = item.get("protein", 0) * qty
            item_carbs = item.get("carbs", 0) * qty
            item_fat = item.get("fat", 0) * qty

            remaining["calories"] -= item_calories
            remaining["protein"] -= item_protein
            remaining["carbs"] -= item_carbs
            remaining["fat"] -= item_fat

            # Track totals for validation
            total_generated_calories += item_calories
            total_generated_protein += item_protein
            total_generated_carbs += item_carbs
            total_generated_fat += item_fat

        # Clamp remaining to prevent negatives for next iteration
        remaining["calories"] = max(0, remaining["calories"])
        remaining["protein"] = max(0, remaining["protein"])
        remaining["carbs"] = max(0, remaining["carbs"])
        remaining["fat"] = max(0, remaining["fat"])

        # 5. Track today's selected meals for cross-meal variety
        for item in solved_meal.get("items", []):
            today_meals.add(item.get("mealName", ""))

        plan[meal_type.lower()] = solved_meal

    # STEP 4: Final Validation — Check if totals within tolerance
    plan["total_calories"] = round(total_generated_calories)
    plan["total_generated_macros"] = {
        "protein": round(total_generated_protein, 1),
        "carbs": round(total_generated_carbs, 1),
        "fat": round(total_generated_fat, 1),
    }

    # Validation: Within ±5% = acceptable
    def validate_macro(generated, target, tolerance_pct):
        if target == 0:
            return True
        deviation_pct = abs(generated - target) / target * 100
        return deviation_pct <= tolerance_pct

    cal_ok = validate_macro(total_generated_calories, target["calories"], 3)
    protein_ok = validate_macro(total_generated_protein, target["protein"], 5)
    fat_ok = validate_macro(total_generated_fat, target["fat"], 10)
    carbs_ok = validate_macro(total_generated_carbs, target["carbs"], 10)

    plan["validation"] = {
        "calories_ok": cal_ok,
        "protein_ok": protein_ok,
        "fat_ok": fat_ok,
        "carbs_ok": carbs_ok,
        "all_targets_met": cal_ok and protein_ok and fat_ok and carbs_ok,
    }

    # IMPROVEMENT 5: Correction Pass — Replace highest deviation meal
    # Only performs swap if plan fails validation AND cache is available
    if not plan["validation"]["all_targets_met"]:
        print(f"[Meal Plan] Validation failed, attempting correction pass...")
        
        try:
            from repositories.meal_repository import meal_repo
            
            # Find which macros are most off
            def find_highest_deviation():
                """Find which macro has highest deviation"""
                deviations = {
                    "calories": (total_generated_calories, target["calories"], 3),
                    "protein": (total_generated_protein, target["protein"], 5),
                    "carbs": (total_generated_carbs, target["carbs"], 10),
                    "fat": (total_generated_fat, target["fat"], 10),
                }
                
                max_dev = 0
                worst_macro = "calories"
                
                for macro_name, (generated, target_val, tolerance) in deviations.items():
                    if target_val == 0:
                        continue
                    dev = abs(generated - target_val) / target_val * 100
                    if dev > tolerance and dev > max_dev:
                        max_dev = dev
                        worst_macro = macro_name
                
                return worst_macro, max_dev
            
            worst_macro, deviation = find_highest_deviation()
            print(f"[Meal Plan] Correction: {worst_macro} deviates by {deviation:.1f}%")
            
            # IMPROVEMENT 5: Only swap within same meal_type (safe meal interchange)
            # Try to fix by replacing an item in the meal with highest contribution to deviation
            for meal_type in order:
                meal_key = meal_type.lower()
                if meal_key not in plan or not plan[meal_key].get("items"):
                    continue
                
                current_meal = plan[meal_key]
                
                # Get candidate meals of same type using meal_type index
                candidates = meal_repo.get_meals_by_type(meal_type)
                if not candidates:
                    continue
                
                # Find which item in current meal contributes most to worst_macro
                worst_item_idx = 0
                worst_contribution = 0
                
                for idx, item in enumerate(current_meal.get("items", [])):
                    qty = item.get("quantity", 1)
                    contribution = item.get(worst_macro, 0) * qty if worst_macro in item else 0
                    if contribution > worst_contribution:
                        worst_contribution = contribution
                        worst_item_idx = idx
                
                # Try replacing this item with something from the same meal_type
                current_item_name = current_meal["items"][worst_item_idx].get("mealName")
                replacement_candidates = [
                    c for c in candidates 
                    if c.get("mealName") != current_item_name
                ]
                
                if replacement_candidates:
                    # Pick replacement that better matches the target
                    best_replacement = min(
                        replacement_candidates,
                        key=lambda m: abs(m.get(worst_macro, 0) - current_meal["items"][worst_item_idx].get(worst_macro, 0))
                    )
                    
                    old_item = current_meal["items"][worst_item_idx]
                    new_qty = old_item.get("quantity", 1)
                    
                    # Create replacement item with same quantity
                    replacement_item = dict(best_replacement)
                    replacement_item["quantity"] = new_qty
                    
                    current_meal["items"][worst_item_idx] = replacement_item
                    
                    # Recalculate meal calories with new item
                    new_meal_calories = sum(
                        item.get("calories", 0) * item.get("quantity", 1)
                        for item in current_meal["items"]
                    )
                    current_meal["mealCalories"] = round(new_meal_calories)
                    
                    print(f"[Meal Plan] Correction: Swapped '{current_item_name}' with "
                          f"'{best_replacement.get('mealName')}' in {meal_type} (safe, same meal_type)")
                    plan[meal_key] = current_meal
                    break  # Only fix one meal per correction pass
        
        except Exception as e:
            print(f"[Meal Plan] Correction pass failed: {e}")
    
    # DEBUG: Log deviations for monitoring
    print(f"[Meal Plan] Generated: {total_generated_calories}cal, "
          f"{total_generated_protein:.1f}g protein, "
          f"{total_generated_carbs:.1f}g carbs, "
          f"{total_generated_fat:.1f}g fat")
    print(f"[Meal Plan] Target: {target['calories']}cal, "
          f"{target['protein']:.1f}g protein, "
          f"{target['carbs']:.1f}g carbs, "
          f"{target['fat']:.1f}g fat")
    print(f"[Meal Plan] Validation: {plan['validation']}")

    # TASK 5 (improved): Safety fallback — type-safe, diet-compliant, calorie-aware
    # TASK 1: use per-slot pool (meals_by_type[slot]), not the full flat list
    # TASK 2: respect is_vegetarian filter
    # TASK 3: prefer calorie proximity; random only as last resort
    for slot in order:
        slot_key = slot.lower()
        slot_data = plan.get(slot_key, {})
        if slot_data.get("items"):
            continue  # slot already filled — nothing to do

        # TASK 1: type-correct pool for this slot
        slot_pool = list(meals_by_type.get(slot, []))

        # TASK 2: apply veg filter when required
        if is_vegetarian and slot_pool:
            veg_pool = [
                m for m in slot_pool
                if m.get("is_vegetarian") is True
                and not any(
                    kw in (m.get("mealName") or "").lower()
                    for kw in {"chicken", "mutton", "fish", "egg"}
                )
            ]
            if veg_pool:
                slot_pool = veg_pool
            # else: no veg meals for this type — keep unfiltered pool

        if not slot_pool:
            # Absolute last resort: anything from any type
            slot_pool = [m for ms in meals_by_type.values() for m in ms]

        if not slot_pool:
            print(f"[meal-plan] fallback triggered — {slot}: no meals available at all, skipping")
            continue

        # TASK 3: pick by calorie proximity to the slot's proportional target
        slot_target_cals = target["calories"] * MEAL_SPLIT.get(slot, 0.25)
        slot_pool_sorted = sorted(
            slot_pool,
            key=lambda m: abs((m.get("calories") or 0) - slot_target_cals)
        )
        fallback_meal = slot_pool_sorted[0]

        # TASK 4: structured log message
        print(
            f"[meal-plan] fallback triggered — type-safe selection: "
            f"{slot} → '{fallback_meal.get('mealName')}' "
            f"(cal={fallback_meal.get('calories', 0)}, target≈{slot_target_cals:.0f}, "
            f"pool={len(slot_pool)}, veg={is_vegetarian})"
        )

        fb_copy = copy.deepcopy(fallback_meal)
        fb_copy["quantity"] = 1
        plan[slot_key] = {
            "items": [fb_copy],
            "mealCalories": fallback_meal.get("calories", 0),
            "cuisineTheme": get_tags(fallback_meal)["cuisine"],
            "template": "safety_fallback",
            "calorie_ok": False,
        }

    return plan
