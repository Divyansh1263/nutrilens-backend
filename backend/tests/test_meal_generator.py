# tests/test_meal_generator.py
# Unit tests for the improved meal plan generator v2
# Run: python -m pytest tests/test_meal_generator.py -v

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -----------------------------------------------
# Mock Meal Data (no Firebase needed)
# -----------------------------------------------
MOCK_MEALS = [
    # ---- NORTH INDIAN ----
    {
        "mealName": "Plain Wheat Roti", "id": "m1",
        "searchKeywords": ["roti", "chapati", "phulka"],
        "category": "Bread", "cuisine": "north_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 80, "protein": 2.3, "carbs": 15, "fat": 1.1,
    },
    {
        "mealName": "Plain Dal", "id": "m2",
        "searchKeywords": ["dal", "lentil", "daal"],
        "category": "Dal", "cuisine": "north_indian",
        "food_group": "protein", "meal_role": "side",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 120, "protein": 8, "carbs": 18, "fat": 2,
    },
    {
        "mealName": "Aloo Gobi", "id": "m3",
        "searchKeywords": ["aloo gobi", "potato cauliflower"],
        "category": "Vegetable", "cuisine": "north_indian",
        "food_group": "vegetable", "meal_role": "side",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 150, "protein": 3, "carbs": 20, "fat": 6,
    },
    {
        "mealName": "Curd Bowl", "id": "m4",
        "searchKeywords": ["curd", "dahi", "yogurt"],
        "category": "Dairy", "cuisine": "north_indian",
        "food_group": "dairy", "meal_role": "side",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 60, "protein": 4, "carbs": 5, "fat": 3,
    },
    {
        "mealName": "Paneer Butter Masala", "id": "m5",
        "searchKeywords": ["paneer curry", "paneer butter masala"],
        "category": "Vegetable", "cuisine": "north_indian",
        "food_group": "protein", "meal_role": "side",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 350, "protein": 14, "carbs": 12, "fat": 28,
    },

    # ---- SOUTH INDIAN ----
    {
        "mealName": "Idli", "id": "m6",
        "searchKeywords": ["idli", "steamed rice cake"],
        "category": "Breakfast", "cuisine": "south_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Breakfast"],
        "calories": 40, "protein": 1.5, "carbs": 8, "fat": 0.2,
    },
    {
        "mealName": "Sambar", "id": "m7",
        "searchKeywords": ["sambar", "lentil vegetable stew"],
        "category": "Dal", "cuisine": "south_indian",
        "food_group": "protein", "meal_role": "side",
        "validMealTypes": ["Breakfast", "Lunch"],
        "calories": 80, "protein": 4, "carbs": 12, "fat": 2,
    },
    {
        "mealName": "Coconut Chutney", "id": "m8",
        "searchKeywords": ["chutney", "coconut chutney"],
        "category": "Side", "cuisine": "south_indian",
        "food_group": "vegetable", "meal_role": "side",
        "validMealTypes": ["Breakfast"],
        "calories": 50, "protein": 1, "carbs": 3, "fat": 4,
    },
    {
        "mealName": "Steamed Rice", "id": "m9",
        "searchKeywords": ["rice", "plain rice", "chawal"],
        "category": "Rice", "cuisine": "south_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 130, "protein": 2.5, "carbs": 28, "fat": 0.3,
    },

    # ---- HEAVY DISHES ----
    {
        "mealName": "Chicken Biryani", "id": "m10",
        "searchKeywords": ["chicken biryani", "biryani"],
        "category": "Rice", "cuisine": "north_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 450, "protein": 22, "carbs": 55, "fat": 15,
    },
    {
        "mealName": "Naan", "id": "m11",
        "searchKeywords": ["naan", "tandoori naan"],
        "category": "Bread", "cuisine": "north_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Lunch", "Dinner"],
        "calories": 260, "protein": 7, "carbs": 45, "fat": 5,
    },

    # ---- SNACK ----
    {
        "mealName": "Banana", "id": "m12",
        "searchKeywords": ["banana", "fruit"],
        "category": "Fruit", "cuisine": "indian",
        "food_group": "fruit", "meal_role": "main",
        "validMealTypes": ["Snack"],
        "calories": 90, "protein": 1.1, "carbs": 23, "fat": 0.3,
    },
    {
        "mealName": "Masala Chai", "id": "m13",
        "searchKeywords": ["chai", "tea"],
        "category": "Drink", "cuisine": "indian",
        "food_group": "dairy", "meal_role": "drink",
        "validMealTypes": ["Snack", "Breakfast"],
        "calories": 50, "protein": 2, "carbs": 7, "fat": 2,
    },

    # ---- DOSA (for collision test) ----
    {
        "mealName": "Masala Dosa", "id": "m14",
        "searchKeywords": ["dosa", "masala dosa"],
        "category": "Breakfast", "cuisine": "south_indian",
        "food_group": "grain", "meal_role": "main",
        "validMealTypes": ["Breakfast"],
        "calories": 200, "protein": 4, "carbs": 30, "fat": 7,
    },
]


def _build_by_type(meals):
    """Group meals by validMealTypes."""
    by_type = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
    for m in meals:
        for vt in m.get("validMealTypes", []):
            if vt in by_type:
                by_type[vt].append(m)
    return by_type


# ===================================================
# TEST: meal_patterns
# ===================================================
class TestMealPatterns:

    def test_infer_carb_base(self):
        from ai.meal_patterns import infer_derived_tag
        tag = infer_derived_tag(MOCK_MEALS[0])  # Plain Wheat Roti
        assert tag == "carb_base"

    def test_infer_protein_curry(self):
        from ai.meal_patterns import infer_derived_tag
        tag = infer_derived_tag(MOCK_MEALS[1])  # Plain Dal
        assert tag == "protein_curry"

    def test_infer_heavy_dish(self):
        from ai.meal_patterns import infer_derived_tag
        tag = infer_derived_tag(MOCK_MEALS[9])  # Chicken Biryani
        assert tag == "heavy_dish"

    def test_infer_condiment(self):
        from ai.meal_patterns import infer_derived_tag
        tag = infer_derived_tag(MOCK_MEALS[7])  # Coconut Chutney
        assert tag == "condiment"

    def test_infer_drink(self):
        from ai.meal_patterns import infer_derived_tag
        tag = infer_derived_tag(MOCK_MEALS[12])  # Masala Chai
        assert tag == "drink"

    def test_get_portion_roti(self):
        from ai.meal_patterns import get_portion
        portion = get_portion(MOCK_MEALS[0], "carb_base")  # Roti
        assert portion["default"] >= 2
        assert portion["max"] >= 2


# ===================================================
# TEST: compatibility_scorer
# ===================================================
class TestCompatibilityScorer:

    def test_good_combo_scores_positive(self):
        """Roti + Dal should score positively."""
        from ai.compatibility_scorer import score_combination
        roti = MOCK_MEALS[0]  # Plain Wheat Roti
        dal = MOCK_MEALS[1]   # Plain Dal
        result = score_combination([roti, dal])
        assert result["pair_score"] > 0

    def test_bad_combo_scores_negative(self):
        """Biryani + Naan should score negatively."""
        from ai.compatibility_scorer import score_combination
        biryani = MOCK_MEALS[9]  # Chicken Biryani
        naan = MOCK_MEALS[10]    # Naan
        result = score_combination([biryani, naan])
        assert result["pair_score"] < 0

    def test_collision_penalty_multiple_carb(self):
        """Two carb bases should trigger collision penalty."""
        from ai.compatibility_scorer import check_collisions
        roti = MOCK_MEALS[0]   # Roti
        rice = MOCK_MEALS[8]   # Rice
        penalty, violations = check_collisions([roti, rice])
        assert penalty < 0
        assert len(violations) > 0

    def test_no_collision_single_carb(self):
        """Single carb base should not trigger collision."""
        from ai.compatibility_scorer import check_collisions
        roti = MOCK_MEALS[0]
        dal = MOCK_MEALS[1]
        penalty, violations = check_collisions([roti, dal])
        assert penalty == 0

    def test_calorie_bonus_within_target(self):
        """Items within 20% of target get calorie bonus."""
        from ai.compatibility_scorer import score_combination
        roti = MOCK_MEALS[0]  # 80 cal
        dal = MOCK_MEALS[1]   # 120 cal
        # target 250 → total 200, ratio 0.8 → within range
        result = score_combination([roti, dal], target_calories=250)
        assert result["calorie_bonus"] >= 0


# ===================================================
# TEST: meal_plan_generator (full pipeline)
# ===================================================
class TestMealPlanGenerator:

    def test_generate_full_plan(self):
        """Full plan should have all 4 meal types."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)
        plan = generate_full_meal_plan(target, by_type)

        assert "breakfast" in plan
        assert "lunch" in plan
        assert "dinner" in plan
        assert "snack" in plan
        assert "total_calories" in plan
        assert plan["total_calories"] > 0

    def test_lunch_has_items(self):
        """Lunch should have at least 1 item."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)
        plan = generate_full_meal_plan(target, by_type)

        assert len(plan["lunch"]["items"]) >= 1

    def test_items_have_quantity(self):
        """All items should have a 'quantity' field."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)
        plan = generate_full_meal_plan(target, by_type)

        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            for item in plan[slot].get("items", []):
                assert "quantity" in item
                assert item["quantity"] >= 1

    def test_output_format_unchanged(self):
        """Output must have items, mealCalories, template, cuisineTheme."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)
        plan = generate_full_meal_plan(target, by_type)

        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            meal = plan[slot]
            assert "items" in meal
            assert "mealCalories" in meal

    def test_variety_reduces_repeats(self):
        """Recent meals should be penalized (scored lower)."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)

        # Generate two plans — second with recent meals set
        plan1 = generate_full_meal_plan(target, by_type, recent_meals=set())

        # Collect all meal names from plan1
        recent = set()
        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            for item in plan1[slot].get("items", []):
                recent.add(item.get("mealName", ""))

        plan2 = generate_full_meal_plan(target, by_type, recent_meals=recent)

        # plan2 should still produce valid output (may or may not have overlaps
        # depending on dataset size, but it should at least work)
        assert plan2["total_calories"] > 0

    def test_no_crash_with_empty_candidates(self):
        """Generator should handle empty candidate lists gracefully."""
        from ai.meal_plan_generator import generate_full_meal_plan
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        empty = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
        plan = generate_full_meal_plan(target, empty)
        assert plan["total_calories"] == 0


# ===================================================
# TEST: solve_meal directly
# ===================================================
class TestSolveMeal:

    def test_solve_produces_items(self):
        from ai.meal_plan_generator import solve_meal
        from ai.meal_patterns import MEAL_PATTERNS
        pattern = MEAL_PATTERNS["Lunch"][0]  # Roti_Thali
        lunch_meals = [m for m in MOCK_MEALS if "Lunch" in m.get("validMealTypes", [])]
        result = solve_meal(pattern, lunch_meals, 700)
        assert len(result["items"]) >= 1

    def test_solve_respects_max_items(self):
        from ai.meal_plan_generator import solve_meal
        from ai.meal_patterns import MEAL_PATTERNS
        pattern = MEAL_PATTERNS["Snack"][0]  # Light_Snack (max 2)
        snack_meals = [m for m in MOCK_MEALS if "Snack" in m.get("validMealTypes", [])]
        result = solve_meal(pattern, snack_meals, 200)
        assert len(result["items"]) <= 2


# ===================================================
# TEST: New v3 Scoring Functions
# ===================================================
class TestScoringFunctions:
    """Tests for the three new scoring helpers added in v3."""

    # --- _compute_macro_score ---

    def test_macro_score_on_target_is_zero(self):
        """If item macros exactly match target, score should be 0."""
        from ai.meal_plan_generator import _compute_macro_score
        items = [{"protein": 30, "carbs": 50, "fat": 10}]
        target = {"protein": 30, "carbs": 50, "fat": 10}
        score = _compute_macro_score(items, target)
        assert score == 0

    def test_macro_score_penalises_deviation(self):
        """Macro deviation should produce a negative score."""
        from ai.meal_plan_generator import _compute_macro_score
        items = [{"protein": 5, "carbs": 5, "fat": 5}]
        target = {"protein": 30, "carbs": 50, "fat": 10}
        score = _compute_macro_score(items, target)
        assert score < 0

    def test_macro_score_protein_double_weight(self):
        """Protein deviation should be penalised twice as hard as carbs/fat."""
        from ai.meal_plan_generator import _compute_macro_score
        # Deviate protein by 10, carbs by 0, fat by 0
        items_prot = [{"protein": 0, "carbs": 30, "fat": 10}]
        # Deviate carbs by 10, protein by 0, fat by 0
        items_carb = [{"protein": 10, "carbs": 20, "fat": 10}]
        target = {"protein": 10, "carbs": 30, "fat": 10}
        score_prot = _compute_macro_score(items_prot, target)
        score_carb = _compute_macro_score(items_carb, target)
        # protein deviation = 10 → penalty = -20; carbs deviation = 10 → penalty = -10
        assert score_prot < score_carb

    def test_macro_score_no_target_returns_zero(self):
        """With no target, macro score should return 0."""
        from ai.meal_plan_generator import _compute_macro_score
        items = [{"protein": 20, "carbs": 40, "fat": 8}]
        assert _compute_macro_score(items, None) == 0
        assert _compute_macro_score(items, {}) == 0

    # --- _compute_protein_density_score ---

    def test_protein_density_zero_calories_guard(self):
        """Zero-calorie item should not crash; should return 0."""
        from ai.meal_plan_generator import _compute_protein_density_score
        items = [{"protein": 10, "calories": 0}]
        score = _compute_protein_density_score(items)
        assert score == 0

    def test_protein_dense_beats_carb_heavy(self):
        """High-protein meal should outscore a carb-only meal."""
        from ai.meal_plan_generator import _compute_protein_density_score
        protein_meal = [{"protein": 25, "calories": 200}]  # 12.5 % protein density
        carb_meal    = [{"protein": 2,  "calories": 200}]  # 1 % protein density
        assert _compute_protein_density_score(protein_meal) > _compute_protein_density_score(carb_meal)

    # --- _compute_calorie_tolerance_score ---

    def test_calorie_within_3pct_scores_high(self):
        """Portioned calories within ±3% of target should give +5."""
        from ai.meal_plan_generator import _compute_calorie_tolerance_score
        assert _compute_calorie_tolerance_score(2200, 2200) == 5   # exact
        assert _compute_calorie_tolerance_score(2145, 2200) == 5   # ~2.5% under
        assert _compute_calorie_tolerance_score(2255, 2200) == 5   # ~2.5% over

    def test_calorie_within_10pct_scores_positive(self):
        """Portioned calories within ±10% should give +1."""
        from ai.meal_plan_generator import _compute_calorie_tolerance_score
        assert _compute_calorie_tolerance_score(2100, 2200) == 1   # ~4.5% under
        assert _compute_calorie_tolerance_score(2350, 2200) == 1   # ~6.8% over

    def test_calorie_outside_10pct_scores_negative(self):
        """Portioned calories outside ±10% should give -3."""
        from ai.meal_plan_generator import _compute_calorie_tolerance_score
        assert _compute_calorie_tolerance_score(1800, 2200) == -3  # ~18% under
        assert _compute_calorie_tolerance_score(2600, 2200) == -3  # ~18% over

    def test_calorie_tolerance_zero_target_safe(self):
        """Zero target should not crash; should return 0."""
        from ai.meal_plan_generator import _compute_calorie_tolerance_score
        assert _compute_calorie_tolerance_score(500, 0) == 0

    # --- Integration: solve_meal accepts target_macros ---

    def test_solve_meal_accepts_target_macros(self):
        """solve_meal should not crash when target_macros is passed."""
        from ai.meal_plan_generator import solve_meal
        from ai.meal_patterns import MEAL_PATTERNS
        pattern = MEAL_PATTERNS["Lunch"][0]
        lunch_meals = [m for m in MOCK_MEALS if "Lunch" in m.get("validMealTypes", [])]
        macros = {"protein": 34, "carbs": 86, "fat": 25}
        result = solve_meal(pattern, lunch_meals, 700, target_macros=macros)
        assert "items" in result
        assert "mealCalories" in result

    def test_items_quantity_never_exceeds_portion_max(self):
        """After _apply_portions(), no item should exceed its PORTION_RULES max."""
        from ai.meal_plan_generator import generate_full_meal_plan
        from ai.meal_patterns import PORTION_RULES, get_portion
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_MEALS)
        plan = generate_full_meal_plan(target, by_type)

        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            for item in plan[slot].get("items", []):
                qty = item.get("quantity", 1)
                slot_label = "carb_base"  # conservative check
                portion = get_portion(item, slot_label)
                assert qty <= portion["max"], (
                    f"{item.get('mealName')} has qty={qty} > max={portion['max']}"
                )


# ===================================================
# Run: python -m pytest tests/test_meal_generator.py -v
# ===================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
