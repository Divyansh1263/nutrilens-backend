# utils/meal_validation.py
#
# Production-safe meal deduplication and validation layer.
# Applied AFTER apply_diet_filter() in the meal loading pipeline.
#
# Functions:
#   normalize_name()      — canonical key for dedup comparison
#   deduplicate_meals()   — keep lowest-calorie entry per normalized name
#   hard_validate_meal()  — reject physiologically impossible entries

from utils.logger import app_logger


# ──────────────────────────────────────────────────────────────────────────────
# 1. NAME NORMALIZER
# ──────────────────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    Produce a canonical lowercase key for dedup comparisons.
    Strips leading/trailing whitespace and removes filler prefixes
    like "plain " so that "Roti" and "Plain Roti" resolve to the
    same key ("roti").
    """
    return (
        name.lower()
            .strip()
            .replace("plain ", "")
            .replace("  ", " ")
    )


# ──────────────────────────────────────────────────────────────────────────────
# 2. DEDUPLICATION
# ──────────────────────────────────────────────────────────────────────────────

def deduplicate_meals(meals: list) -> list:
    """
    Deduplicate a meal list by normalized name, keeping the entry
    with the *lowest calories* per key (most realistic / conservative).

    Args:
        meals: raw list of meal dicts from Firestore / local cache

    Returns:
        deduplicated list — deterministic, no random picks
    """
    seen: dict = {}

    for meal in meals:
        raw_name = meal.get("mealName") or ""
        if not raw_name:
            continue

        key = normalize_name(raw_name)
        calories = float(meal.get("calories") or 0)

        if key not in seen:
            seen[key] = meal
        else:
            existing_cal = float(seen[key].get("calories") or 0)
            if calories < existing_cal:
                app_logger.debug(
                    "[dedup] replacing '%s' (%.0f kcal) with '%s' (%.0f kcal) — lower cal kept",
                    seen[key].get("mealName"), existing_cal,
                    meal.get("mealName"), calories,
                )
                seen[key] = meal
            else:
                app_logger.debug(
                    "[dedup] discarding duplicate '%s' (%.0f kcal) — kept '%s' (%.0f kcal)",
                    meal.get("mealName"), calories,
                    seen[key].get("mealName"), existing_cal,
                )

    result = list(seen.values())
    app_logger.info("[dedup] %d meals → %d after deduplication", len(meals), len(result))
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 3. HARD VALIDATION FILTER
# ──────────────────────────────────────────────────────────────────────────────

# Per-serving physiological upper bounds
_MAX_CALORIES = 500   # kcal  — single-serving cap
_MAX_PROTEIN  = 50    # g     — protein cap per serving
_MAX_CARBS    = 150   # g     — carbs cap per serving


def hard_validate_meal(meal: dict) -> bool:
    """
    Return True if the meal passes all hard numeric limits.
    Rejects clearly wrong Firestore entries before they corrupt plans.

    Limits:
        calories  <= 500 kcal
        protein   <= 50 g
        carbs     <= 150 g
    """
    name     = meal.get("mealName") or "unknown"
    calories = float(meal.get("calories") or 0)
    protein  = float(meal.get("protein")  or 0)
    carbs    = float(meal.get("carbs")    or 0)

    if calories > _MAX_CALORIES:
        app_logger.warning(
            "[validate] SKIPPED '%s': calories=%.0f > %d (too high)",
            name, calories, _MAX_CALORIES,
        )
        return False

    if protein > _MAX_PROTEIN:
        app_logger.warning(
            "[validate] SKIPPED '%s': protein=%.0f > %dg (too high)",
            name, protein, _MAX_PROTEIN,
        )
        return False

    if carbs > _MAX_CARBS:
        app_logger.warning(
            "[validate] SKIPPED '%s': carbs=%.0f > %dg (too high)",
            name, carbs, _MAX_CARBS,
        )
        return False

    return True


# ──────────────────────────────────────────────────────────────────────────────
# 4. COMBINED PIPELINE HELPER
# ──────────────────────────────────────────────────────────────────────────────

def clean_meal_pool(meals: list) -> list:
    """
    Full cleaning pipeline:
      1. Hard-validate each entry  (remove impossible values)
      2. Deduplicate by normalized name  (keep lowest-cal per key)

    Call this AFTER apply_diet_filter() in meal_generator_service.
    """
    validated = [m for m in meals if hard_validate_meal(m)]
    skipped   = len(meals) - len(validated)
    if skipped:
        app_logger.info("[validate] Removed %d invalid meals from pool", skipped)

    deduped = deduplicate_meals(validated)
    return deduped
