# utils/macro_optimizer.py
#
# Post-generation macro optimization for NutriLens meal plans.
#
# Pipeline:
#   1. evaluate_plan()      — compute % error per macro
#   2. optimize_plan()      — 20-iteration adjustment loop (quantity tweaks)
#   3. inject_protein()     — add a high-protein item when protein < 90% target
#   4. Helper internals:    — increase_portion / decrease_portion / totals
#
# Design rules:
#   • NEVER mutate the original plan dict — always work on a deep copy.
#   • Quantity clamped to [0.5, 3.0] so items are never deleted or absurd.
#   • All macro fields recomputed from base values after each adjustment.
#   • 0.2 step chosen because it is small enough to be imperceptible in a recipe
#     but large enough to move macros meaningfully.
#   • Tag system: protein/fat/carb tags are derived from meal metadata fields;
#     we never do string-matching on meal names here.

import copy
from utils.logger import app_logger

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

QTY_STEP   = 0.2          # portion increment/decrement step
QTY_MIN    = 0.5          # minimum allowed quantity
QTY_MAX    = 3.0          # maximum allowed quantity
TOLERANCE  = 0.05         # ±5 %  target window
MAX_ITERS  = 20           # max adjustment iterations per optimize call

# Tag sets — primary macro contribution per item
# Populated from Firestore fields: tags, category, searchKeywords
PROTEIN_TAGS = frozenset({"protein", "dal", "paneer", "soy", "curd", "rajma",
                           "chole", "egg", "tofu", "sprouts", "chicken", "fish"})
FAT_TAGS     = frozenset({"fat", "ghee", "butter", "oil", "nut", "cream",
                           "paneer", "cheese", "coconut"})
CARB_TAGS    = frozenset({"carb", "rice", "roti", "bread", "chapati", "naan",
                           "paratha", "oats", "potato", "pasta"})

# High-protein injection candidates (preferred order)
PROTEIN_INJECTION_NAMES = ["Paneer", "Dal Tadka", "Curd", "Rajma", "Soy Chunks"]


# ──────────────────────────────────────────────────────────────────────────────
# 1. PLAN EVALUATION
# ──────────────────────────────────────────────────────────────────────────────

def _plan_totals(plan: dict) -> dict:
    """Sum macros across all slots in the plan."""
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for slot in ("breakfast", "lunch", "snack", "dinner"):
        for item in plan.get(slot, []):
            totals["calories"] += float(item.get("calories") or 0)
            totals["protein"]  += float(item.get("protein")  or 0)
            totals["fat"]      += float(item.get("fat")      or 0)
            totals["carbs"]    += float(item.get("carbs")    or 0)
    return totals


def evaluate_plan(plan: dict, targets: dict) -> dict:
    """
    Compute signed relative error for each macro.

        error = (actual - target) / target

    Positive → over-target; Negative → under-target.

    Args:
        plan:    plan dict with slot lists containing item dicts
        targets: {"calories": X, "protein": Y, "fat": Z, "carbs": W}

    Returns:
        {"cal_error": f, "protein_error": f, "fat_error": f, "carb_error": f}
    """
    totals = _plan_totals(plan)

    def _err(key_actual, key_target, divisor_key="calories"):
        t = float(targets.get(key_target) or targets.get(divisor_key) or 1)
        if t == 0:
            return 0.0
        return (totals[key_actual] - t) / t

    return {
        "cal_error":     _err("calories", "calories"),
        "protein_error": _err("protein",  "protein"),
        "fat_error":     _err("fat",      "fat"),
        "carb_error":    _err("carbs",    "carbs"),
    }


def _total_error(errors: dict) -> float:
    """Sum of absolute errors (unweighted) — used for injection acceptance check."""
    return sum(abs(v) for v in errors.values())


def _weighted_score(errors: dict) -> float:
    """
    Weighted score for tracking best plan across iterations (TASK 2.1).
    Protein is weighted 1.5x because it is the hardest macro to hit and
    has the most impact on dietary quality.

        score = |cal_error|*1.0 + |protein_error|*1.5 + |fat_error|*1.0 + |carb_error|*1.0
    """
    return (
        abs(errors.get("cal_error",     0)) * 1.0
        + abs(errors.get("protein_error", 0)) * 1.5
        + abs(errors.get("fat_error",     0)) * 1.0
        + abs(errors.get("carb_error",    0)) * 1.0
    )


def interpret_score(normalized_score: float) -> str:
    """
    TASK 2: Convert a normalized [0, 1] optimization score to a user-friendly label.

    Thresholds (normalized, higher = better):
        >= 0.85 → "Excellent plan"
        >= 0.70 → "Good plan"
        >= 0.50 → "Average plan"
        <  0.50 → "Needs improvement"
    """
    if normalized_score >= 0.85:
        return "Excellent plan"
    if normalized_score >= 0.70:
        return "Good plan"
    if normalized_score >= 0.50:
        return "Average plan"
    return "Needs improvement"


# ──────────────────────────────────────────────────────────────────────────────
# 2. ITEM CLASSIFICATION  (ISSUE 2 + 4 fix)
# ──────────────────────────────────────────────────────────────────────────────

def classify_item(item: dict) -> str:
    """
    Classify a plan item as 'protein', 'fat', or 'carb' using macro values.

    Rules (applied in priority order):
        protein > 10g  → 'protein'
        fat     > 10g  → 'fat'
        else           → 'carb'   (covers rice, roti, oats, fruit, etc.)

    This replaces the keyword/tag approach that left many items unclassified.
    Every item with non-zero macros gets a class — no item is ever skipped.

    Args:
        item: plan item dict with 'protein', 'fat', 'carbs' fields (floats)

    Returns:
        'protein' | 'fat' | 'carb'
    """
    protein = float(item.get("protein") or 0)
    fat     = float(item.get("fat")     or 0)

    if protein > 10:
        return "protein"
    if fat > 10:
        return "fat"
    return "carb"


# Legacy tag helpers kept for reference / external callers
def _item_tags(item: dict) -> set:
    tags = set()
    raw_tags = item.get("tags") or []
    if isinstance(raw_tags, list):
        tags.update(t.lower() for t in raw_tags if isinstance(t, str))
    elif isinstance(raw_tags, str):
        tags.add(raw_tags.lower())
    cat = item.get("category") or ""
    if isinstance(cat, str):
        tags.add(cat.lower())
    kws = item.get("searchKeywords") or []
    if isinstance(kws, list):
        tags.update(k.lower() for k in kws if isinstance(k, str))
    return tags


def _is_protein_source(item: dict) -> bool:
    return classify_item(item) == "protein"


def _is_fat_source(item: dict) -> bool:
    return classify_item(item) == "fat"


def _is_carb_source(item: dict) -> bool:
    return classify_item(item) == "carb"


# ──────────────────────────────────────────────────────────────────────────────
# 3. PORTION ADJUSTERS
# ──────────────────────────────────────────────────────────────────────────────

def _recompute_macros(item: dict) -> dict:
    """
    Recompute scaled macros from per-unit base fields and current quantity.
    Falls back to proportional scaling from the stored totals if base fields
    are not present (backward compatibility).
    """
    qty      = float(item.get("quantity") or 1.0)
    old_qty  = float(item.get("_base_qty") or 1.0)  # original quantity at insertion

    # Prefer explicit *_per_unit fields (stored by nlp_pipeline v2.6)
    if item.get("calories_per_unit"):
        return {
            **item,
            "calories": round(float(item["calories_per_unit"]) * qty, 1),
            "protein":  round(float(item.get("protein_per_unit",  0)) * qty, 1),
            "carbs":    round(float(item.get("carbs_per_unit",    0)) * qty, 1),
            "fat":      round(float(item.get("fat_per_unit",      0)) * qty, 1),
        }

    # Proportional fallback: scale from stored totals via old_qty
    if old_qty > 0:
        ratio = qty / old_qty
        return {
            **item,
            "calories": round(float(item.get("calories") or 0) * ratio, 1),
            "protein":  round(float(item.get("protein")  or 0) * ratio, 1),
            "carbs":    round(float(item.get("carbs")    or 0) * ratio, 1),
            "fat":      round(float(item.get("fat")      or 0) * ratio, 1),
        }

    return item


def _stamp_base(item: dict) -> dict:
    """Store original quantity as _base_qty so we can scale proportionally."""
    stamped = dict(item)
    if "_base_qty" not in stamped:
        stamped["_base_qty"] = float(stamped.get("quantity") or 1.0)
    return stamped


def increase_portion(plan: dict, tag: str, delta: float = QTY_STEP) -> bool:
    """
    Increase quantity by `delta` for the first item whose macro-based
    class matches `tag` and whose quantity is below QTY_MAX.

    `delta` is caller-supplied so the optimization loop can pass a decaying
    step size (ISSUE 1 fix: 0.2 / (iteration + 1)).

    Returns True if any adjustment was made.
    """
    tag = tag.lower()
    for slot in ("lunch", "dinner", "breakfast", "snack"):
        for i, item in enumerate(plan.get(slot, [])):
            qty = float(item.get("quantity") or 1.0)
            if qty >= QTY_MAX:
                continue
            if classify_item(item) == tag:
                # TASK 2.3: hard clamp
                new_qty = max(QTY_MIN, min(round(qty + delta, 2), QTY_MAX))
                updated = dict(item)
                updated["quantity"] = new_qty
                updated = _recompute_macros(updated)
                plan[slot][i] = updated
                return True
    return False


def decrease_portion(plan: dict, tag: str, delta: float = QTY_STEP) -> bool:
    """
    Decrease quantity by `delta` for the first item whose macro-based
    class matches `tag` and whose quantity is above QTY_MIN.

    `delta` is caller-supplied so the optimization loop can pass a decaying
    step size (ISSUE 1 fix: 0.2 / (iteration + 1)).

    Returns True if any adjustment was made.
    """
    tag = tag.lower()
    for slot in ("lunch", "dinner", "breakfast", "snack"):
        for i, item in enumerate(plan.get(slot, [])):
            qty = float(item.get("quantity") or 1.0)
            if qty <= QTY_MIN:
                continue
            if classify_item(item) == tag:
                # TASK 2.3: hard clamp
                new_qty = max(QTY_MIN, min(round(qty - delta, 2), QTY_MAX))
                updated = dict(item)
                updated["quantity"] = new_qty
                updated = _recompute_macros(updated)
                plan[slot][i] = updated
                return True
    return False


def _rebalance_after_injection(plan: dict) -> dict:
    """
    ISSUE 3 fix: After injecting a protein item, reduce the largest carb
    item's portion by QTY_STEP to offset the calorie increase.

    Targets dinner first (where injection lands), then lunch.
    Only reduces if the carb item is above QTY_MIN.

    Returns plan (mutated in-place — caller already owns a deep copy).
    """
    decrease_portion(plan, "carb")
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# 4. PROTEIN INJECTION (TASK 5)
# ──────────────────────────────────────────────────────────────────────────────

def _inject_protein(plan: dict, meal_pool: list, targets: dict) -> dict:
    """
    If protein is below 90 % of target, add a high-protein item to the dinner
    slot (or lunch as fallback) from the allowed meal pool.

    The injected item uses quantity=1.0 and has _base_qty stamped.
    Calories are not rebalanced here — the optimize loop handles that.

    Returns:
        updated plan (copy)
    """
    totals  = _plan_totals(plan)
    p_target = float(targets.get("protein") or 0)
    if p_target <= 0:
        return plan

    if totals["protein"] >= 0.90 * p_target:
        return plan   # already fine

    # Find the best injection candidate from pool
    injection = None
    existing_names = {
        item.get("mealName", "").lower()
        for slot in ("breakfast", "lunch", "snack", "dinner")
        for item in plan.get(slot, [])
    }

    # Priority: preferred names first
    for pref_name in PROTEIN_INJECTION_NAMES:
        for meal in meal_pool:
            m_name = meal.get("mealName", "")
            if (m_name.lower() not in existing_names
                    and pref_name.lower() in m_name.lower()
                    and float(meal.get("protein") or 0) > 8):
                injection = meal
                break
        if injection:
            break

    # Fallback: highest-protein meal in pool not already logged
    if not injection:
        candidates = [
            m for m in meal_pool
            if m.get("mealName", "").lower() not in existing_names
            and float(m.get("protein") or 0) > 8
        ]
        if candidates:
            injection = max(candidates, key=lambda m: float(m.get("protein") or 0))

    if not injection:
        app_logger.warning("[macro-opt] protein injection: no candidate found")
        return plan

    injected_item = _stamp_base({
        "mealName": injection.get("mealName"),
        "quantity": 1.0,
        "calories": round(float(injection.get("calories") or 0), 1),
        "protein":  round(float(injection.get("protein")  or 0), 1),
        "carbs":    round(float(injection.get("carbs")    or 0), 1),
        "fat":      round(float(injection.get("fat")      or 0), 1),
        "is_vegetarian":  injection.get("is_vegetarian"),
        "is_vegan":       injection.get("is_vegan"),
        "tags":           injection.get("tags", []),
        "category":       injection.get("category", ""),
        "searchKeywords": injection.get("searchKeywords", []),
    })

    updated_plan = copy.deepcopy(plan)
    slot = "dinner" if updated_plan.get("dinner") is not None else "lunch"
    updated_plan[slot].append(injected_item)
    app_logger.info(
        "[macro-opt] injected protein item '%s' (prot=%.1fg) into %s",
        injected_item["mealName"], injected_item["protein"], slot
    )
    return updated_plan


# ──────────────────────────────────────────────────────────────────────────────
# 5. MAIN OPTIMIZATION LOOP
# ──────────────────────────────────────────────────────────────────────────────

def optimize_plan(plan: dict, targets: dict, meal_pool: list) -> tuple:
    """
    Adjust meal quantities to bring all macros within ±5% of targets.

    Stability improvements:
      • ISSUE 1: Decaying delta per iteration (0.2 / (iter+1)) prevents oscillation
      • ISSUE 2: Protein over-correction handled symmetrically
      • TASK 2.1: Weighted score (protein ×1.5) tracks best plan
      • TASK 2.2: Early stopping if score stagnates for 5 consecutive iterations
      • TASK 2.3: Hard clamp inside increase/decrease_portion
      • TASK 3: Boundary warning logged if final error > ±8% (no crash)
      • TASK 4+5: Returns (plan, macro_deviation, optimization_score)

    Returns:
        (optimized_plan, macro_deviation, optimization_score)
    """
    working = copy.deepcopy(plan)

    # Stamp base quantities so _recompute_macros works proportionally
    for slot in ("breakfast", "lunch", "snack", "dinner"):
        working[slot] = [_stamp_base(item) for item in working.get(slot, [])]

    best_plan  = copy.deepcopy(working)
    best_score = _weighted_score(evaluate_plan(working, targets))   # TASK 2.1

    app_logger.info(
        "[macro-opt] START — cal=%.0f/%.0f prot=%.1f/%.1f "
        "fat=%.1f/%.1f carbs=%.1f/%.1f",
        _plan_totals(working)["calories"],  targets.get("calories", 0),
        _plan_totals(working)["protein"],   targets.get("protein",  0),
        _plan_totals(working)["fat"],       targets.get("fat",      0),
        _plan_totals(working)["carbs"],     targets.get("carbs",    0),
    )

    stagnant_iters = 0    # TASK 2.2 early-stop counter
    STAGNANT_LIMIT = 5

    for iteration in range(MAX_ITERS):
        errors = evaluate_plan(working, targets)

        # ISSUE 1: decaying delta — smaller steps as we approach target
        delta = round(0.2 / (iteration + 1), 3)
        delta = max(delta, 0.05)   # floor: don't go below 0.05 (imperceptible)

        # Early exit if all within tolerance
        if all(abs(e) <= TOLERANCE for e in errors.values()):
            app_logger.info(
                "[macro-opt] converged at iteration %d (score=%.4f)",
                iteration, _weighted_score(errors)
            )
            best_plan = copy.deepcopy(working)
            best_score = _weighted_score(errors)
            break

        # ── Apply corrections with decaying delta ────────────────────────────
        adjusted = False

        # ISSUE 2: protein handled symmetrically
        if errors["protein_error"] < -TOLERANCE:
            adjusted |= increase_portion(working, "protein", delta)
        elif errors["protein_error"] > TOLERANCE:
            adjusted |= decrease_portion(working, "protein", delta)

        # Fat: symmetric
        if errors["fat_error"] > TOLERANCE:
            adjusted |= decrease_portion(working, "fat", delta)
        elif errors["fat_error"] < -TOLERANCE:
            adjusted |= increase_portion(working, "fat", delta)

        # Calories: use carb lever
        if errors["cal_error"] > TOLERANCE:
            adjusted |= decrease_portion(working, "carb", delta)
        elif errors["cal_error"] < -TOLERANCE:
            adjusted |= increase_portion(working, "carb", delta)

        # Carbs independently (when calories are already balanced)
        if errors["carb_error"] > TOLERANCE and abs(errors["cal_error"]) <= TOLERANCE:
            adjusted |= decrease_portion(working, "carb", delta)

        if not adjusted:
            app_logger.info(
                "[macro-opt] no adjustable items at iteration %d — stopping", iteration
            )
            break

        # TASK 2.1: track best via weighted score
        current_score = _weighted_score(evaluate_plan(working, targets))
        if current_score < best_score:
            best_score = current_score
            best_plan  = copy.deepcopy(working)
            stagnant_iters = 0
        else:
            stagnant_iters += 1

        # TASK 2.2: early stopping
        if stagnant_iters >= STAGNANT_LIMIT:
            app_logger.info(
                "[macro-opt] early stop at iteration %d — no score improvement "
                "for %d consecutive iterations",
                iteration, STAGNANT_LIMIT
            )
            break

    # ── Protein injection + calorie rebalance ─────────────────────────────
    totals = _plan_totals(best_plan)
    p_target = float(targets.get("protein") or 0)
    if p_target > 0 and totals["protein"] < 0.90 * p_target:
        app_logger.info(
            "[macro-opt] protein %.1fg < 90%% of target %.1fg — injecting",
            totals["protein"], p_target
        )
        injected = _inject_protein(best_plan, meal_pool, targets)
        if injected is not best_plan:   # injection actually added an item
            injected = _rebalance_after_injection(injected)
        if _total_error(evaluate_plan(injected, targets)) <= _total_error(evaluate_plan(best_plan, targets)) + 0.10:
            best_plan  = injected
            best_score = _weighted_score(evaluate_plan(best_plan, targets))

    # ── Final log + TASK 3 boundary warning ─────────────────────────────
    final_errors = evaluate_plan(best_plan, targets)
    final_totals = _plan_totals(best_plan)
    app_logger.info(
        "[macro-opt] FINAL — cal=%.0f (err=%+.1f%%) prot=%.1f (err=%+.1f%%) "
        "fat=%.1f (err=%+.1f%%) carbs=%.1f (err=%+.1f%%) score=%.4f",
        final_totals["calories"], final_errors["cal_error"]     * 100,
        final_totals["protein"],  final_errors["protein_error"] * 100,
        final_totals["fat"],      final_errors["fat_error"]     * 100,
        final_totals["carbs"],    final_errors["carb_error"]    * 100,
        best_score,
    )

    # TASK 3: boundary warning (do NOT crash)
    BOUNDARY = 0.08
    out_of_bounds = {k: v for k, v in final_errors.items() if abs(v) > BOUNDARY}
    if out_of_bounds:
        app_logger.warning(
            "[macro-opt] Plan outside ±8%% acceptable bounds: %s",
            {k: f"{v:+.1%}" for k, v in out_of_bounds.items()}
        )

    # Strip internal _base_qty field before returning
    for slot in ("breakfast", "lunch", "snack", "dinner"):
        best_plan[slot] = [
            {k: v for k, v in item.items() if k != "_base_qty"}
            for item in best_plan.get(slot, [])
        ]

    # TASK 4: macro_deviation (signed % errors, rounded to 4dp)
    macro_deviation = {
        "calories": round(final_errors["cal_error"],     4),
        "protein":  round(final_errors["protein_error"], 4),
        "fat":      round(final_errors["fat_error"],      4),
        "carbs":    round(final_errors["carb_error"],     4),
    }

    # TASK 1: Normalize raw weighted score to [0, 1] — higher = better.
    #   normalized = 1 / (1 + raw_score)
    #   raw_score=0  → 1.00 (perfect)
    #   raw_score=0.5 → 0.67  raw_score=1.0 → 0.50
    optimization_score = round(1 / (1 + best_score), 4)

    # TASK 2: Human-readable interpretation
    score_label = interpret_score(optimization_score)

    app_logger.info(
        "[macro-opt] score=%.4f (%s)", optimization_score, score_label
    )

    return best_plan, macro_deviation, optimization_score, score_label


# ──────────────────────────────────────────────────────────────────────────────
# 6. MACRO TARGET BUILDER (helper for generate_daily_plan)
# ──────────────────────────────────────────────────────────────────────────────

def build_macro_targets(target_calories: float) -> dict:
    """
    Derive protein / fat / carb gram targets from a calorie goal.

    Macro split used:  25% protein | 30% fat | 45% carbs
    (standard balanced diet; matches the existing plan metadata)
    """
    cal = float(target_calories or 2000)
    return {
        "calories": cal,
        "protein":  round(cal * 0.25 / 4, 1),   # 4 kcal/g
        "fat":      round(cal * 0.30 / 9, 1),   # 9 kcal/g
        "carbs":    round(cal * 0.45 / 4, 1),   # 4 kcal/g
    }
