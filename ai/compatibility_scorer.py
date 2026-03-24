# ai/compatibility_scorer.py
# Scores meal combinations for culinary realism
#
# Uses pair-wise compatibility rules and collision constraints
# to rank candidate meals. Higher score = more realistic combo.

from ai.meal_patterns import infer_derived_tag

# ==============================================================================
# 1. PAIR COMPATIBILITY RULES
# ==============================================================================
# (tag_A, tag_B) → score bonus or penalty
# Positive = good pair, Negative = bad pair

PAIR_SCORES = {
    # GOOD COMBINATIONS (+)
    ("roti", "dal"): +3,
    ("roti", "sabzi"): +3,
    ("roti", "paneer"): +2,
    ("roti", "curd"): +1,
    ("roti", "curry"): +2,
    ("rice", "dal"): +3,
    ("rice", "sambar"): +3,
    ("rice", "curd"): +2,
    ("rice", "rasam"): +2,
    ("rice", "curry"): +1,
    ("idli", "sambar"): +3,
    ("idli", "chutney"): +3,
    ("dosa", "sambar"): +3,
    ("dosa", "chutney"): +3,
    ("upma", "chutney"): +2,
    ("paratha", "curd"): +2,
    ("paratha", "pickle"): +2,
    ("naan", "paneer"): +2,
    ("naan", "curry"): +2,
    ("biryani", "raita"): +3,
    ("pulao", "raita"): +2,
    ("dal", "salad"): +1,

    # BAD COMBINATIONS (-)
    ("dosa", "roti"): -4,
    ("dosa", "naan"): -4,
    ("idli", "roti"): -4,
    ("idli", "naan"): -4,
    ("rice", "roti"): -3,
    ("rice", "naan"): -3,
    ("biryani", "roti"): -4,
    ("biryani", "rice"): -4,
    ("biryani", "naan"): -3,
    ("biryani", "dal"): -2,
    ("pulao", "roti"): -3,
    ("pulao", "rice"): -4,
    ("naan", "roti"): -4,
    ("pasta", "roti"): -4,
    ("pasta", "rice"): -4,
    ("noodles", "roti"): -4,
    ("noodles", "rice"): -4,
}

# Keywords to extract pair tags from meal names
_PAIR_KEYWORDS = [
    "biryani", "pulao", "roti", "chapati", "naan", "rice", "dal",
    "dosa", "idli", "upma", "paratha", "sambar", "chutney", "curry",
    "sabzi", "paneer", "curd", "raita", "rasam", "salad", "pickle",
    "pasta", "noodles",
]


def _extract_pair_tags(meal):
    """Extract all compatibility-relevant keywords from a meal name."""
    name = meal.get("mealName", "").lower()
    keywords = [k.lower() for k in meal.get("searchKeywords", [])]
    full_text = name + " " + " ".join(keywords)

    tags = []
    for kw in _PAIR_KEYWORDS:
        if kw in full_text:
            tags.append(kw)

    # Normalize: chapati → roti
    if "chapati" in tags:
        tags.append("roti")

    return list(set(tags))


# ==============================================================================
# 2. COLLISION RULES
# ==============================================================================

def check_collisions(items):
    """
    Check for heavy dish and carb-base collisions.

    Returns:
        penalty: negative score for violations
        violations: list of description strings
    """
    penalty = 0
    violations = []

    # Count derived tags
    carb_base_count = 0
    heavy_dish_count = 0

    for item in items:
        dtag = infer_derived_tag(item)
        if dtag == "carb_base":
            carb_base_count += 1
        if dtag == "heavy_dish":
            heavy_dish_count += 1

    # Rule: Only 1 main carb base per meal (no rice + roti)
    if carb_base_count > 1:
        over = carb_base_count - 1
        penalty -= over * 5
        violations.append(f"Multiple carb bases ({carb_base_count})")

    # Rule: Only 1 heavy dish per meal (no biryani + butter chicken)
    if heavy_dish_count > 1:
        over = heavy_dish_count - 1
        penalty -= over * 5
        violations.append(f"Multiple heavy dishes ({heavy_dish_count})")

    return penalty, violations


# ==============================================================================
# 3. COMPATIBILITY SCORER
# ==============================================================================

def score_combination(items, target_calories=None):
    """
    Score a list of meal items for culinary compatibility.

    Higher score = better combination.

    Components:
        1. Pair-wise compatibility scores
        2. Collision penalties
        3. Calorie fit bonus (if target provided)

    Args:
        items:           list of meal dicts
        target_calories: optional calorie target for this meal

    Returns:
        dict: {score, pair_score, collision_penalty, calorie_bonus, violations}
    """
    pair_score = 0
    all_tags = []

    # 1. Extract tags for all items
    for item in items:
        tags = _extract_pair_tags(item)
        all_tags.append(tags)

    # 2. Compute pair-wise scores
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            for tag_a in all_tags[i]:
                for tag_b in all_tags[j]:
                    key = (tag_a, tag_b)
                    rev_key = (tag_b, tag_a)
                    if key in PAIR_SCORES:
                        pair_score += PAIR_SCORES[key]
                    elif rev_key in PAIR_SCORES:
                        pair_score += PAIR_SCORES[rev_key]

    # 3. Check collisions
    collision_penalty, violations = check_collisions(items)

    # 4. Calorie fit bonus (optional)
    calorie_bonus = 0
    if target_calories and target_calories > 0:
        total_cals = sum(item.get("calories", 0) for item in items)
        ratio = total_cals / target_calories
        if 0.8 <= ratio <= 1.2:
            calorie_bonus = 2  # Within 20% of target
        elif 0.6 <= ratio <= 1.4:
            calorie_bonus = 0  # Tolerable
        else:
            calorie_bonus = -2  # Too far off

    total_score = pair_score + collision_penalty + calorie_bonus

    return {
        "score": total_score,
        "pair_score": pair_score,
        "collision_penalty": collision_penalty,
        "calorie_bonus": calorie_bonus,
        "violations": violations,
    }
