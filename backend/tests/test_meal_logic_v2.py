# tests/test_meal_logic_v2.py
# Legacy test file — updated for meal_plan_generator v2
# Tests cuisine consistency and food pairing logic
#
# Run: python -m pytest tests/test_meal_logic_v2.py -v

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.meal_plan_generator import generate_full_meal_plan, get_tags

# MOCK DATA
MOCK_FOODS = [
    # South Indian
    {"mealName": "Plain Dosa", "id": "t1", "calories": 200,
     "searchKeywords": ["dosa", "south indian"], "cuisine": "south_indian",
     "food_group": "grain", "meal_role": "main",
     "validMealTypes": ["Breakfast"], "protein": 4, "carbs": 30, "fat": 7},
    {"mealName": "Idli", "id": "t2", "calories": 100,
     "searchKeywords": ["steamed cake"], "cuisine": "south_indian",
     "food_group": "grain", "meal_role": "main",
     "validMealTypes": ["Breakfast"], "protein": 2, "carbs": 15, "fat": 0.5},
    {"mealName": "Sambar", "id": "t3", "calories": 150,
     "searchKeywords": ["lentil stew", "sambar"], "cuisine": "south_indian",
     "food_group": "protein", "meal_role": "side",
     "validMealTypes": ["Breakfast", "Lunch"], "protein": 6, "carbs": 18, "fat": 3},
    {"mealName": "Coconut Chutney", "id": "t4", "calories": 50,
     "searchKeywords": ["condiment", "chutney"], "cuisine": "south_indian",
     "food_group": "vegetable", "meal_role": "side",
     "validMealTypes": ["Breakfast"], "protein": 1, "carbs": 3, "fat": 4},

    # North Indian
    {"mealName": "Roti", "id": "t5", "calories": 100,
     "searchKeywords": ["wheat bread", "roti", "chapati"], "cuisine": "north_indian",
     "food_group": "grain", "meal_role": "main",
     "validMealTypes": ["Lunch", "Dinner"], "protein": 3, "carbs": 18, "fat": 1},
    {"mealName": "Paneer Butter Masala", "id": "t6", "calories": 300,
     "searchKeywords": ["curry", "paneer"], "cuisine": "north_indian",
     "food_group": "protein", "meal_role": "side",
     "validMealTypes": ["Lunch", "Dinner"], "protein": 14, "carbs": 10, "fat": 22},
    {"mealName": "Dal Tadka", "id": "t7", "calories": 200,
     "searchKeywords": ["lentils", "dal"], "cuisine": "north_indian",
     "food_group": "protein", "meal_role": "side",
     "validMealTypes": ["Lunch", "Dinner"], "protein": 8, "carbs": 20, "fat": 5},
    {"mealName": "Aloo Sabzi", "id": "t8", "calories": 120,
     "searchKeywords": ["sabzi", "vegetable"], "cuisine": "north_indian",
     "food_group": "vegetable", "meal_role": "side",
     "validMealTypes": ["Lunch", "Dinner"], "protein": 2, "carbs": 15, "fat": 5},

    # Snack
    {"mealName": "Fruit Salad", "id": "t9", "calories": 100,
     "searchKeywords": ["fruit"], "cuisine": "indian",
     "food_group": "fruit", "meal_role": "main",
     "validMealTypes": ["Snack"], "protein": 1, "carbs": 25, "fat": 0.3},
    {"mealName": "Chai", "id": "t10", "calories": 50,
     "searchKeywords": ["tea", "chai"], "cuisine": "indian",
     "food_group": "dairy", "meal_role": "drink",
     "validMealTypes": ["Snack", "Breakfast"], "protein": 2, "carbs": 7, "fat": 2},
]


def _build_by_type(meals):
    by_type = {"Breakfast": [], "Lunch": [], "Dinner": [], "Snack": []}
    for m in meals:
        for vt in m.get("validMealTypes", []):
            if vt in by_type:
                by_type[vt].append(m)
    return by_type


class TestMealLogic(unittest.TestCase):

    def test_cuisine_consistency(self):
        """All items in a meal slot should share the same cuisine theme."""
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_FOODS)

        for _ in range(5):
            plan = generate_full_meal_plan(target, by_type)

            for slot in ["breakfast", "lunch", "dinner"]:
                meal = plan[slot]
                items = meal.get("items", [])
                if len(items) < 2:
                    continue

                theme = meal.get("cuisineTheme", "")
                for item in items:
                    item_cuisine = get_tags(item)["cuisine"]
                    self.assertEqual(
                        item_cuisine, theme,
                        f"Item '{item['mealName']}' has cuisine "
                        f"'{item_cuisine}' but theme is '{theme}'"
                    )

    def test_plan_has_all_slots(self):
        """Plan should have breakfast, lunch, dinner, snack."""
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_FOODS)
        plan = generate_full_meal_plan(target, by_type)

        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            self.assertIn(slot, plan)

    def test_items_have_quantity(self):
        """All items should have a quantity >= 1."""
        target = {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        by_type = _build_by_type(MOCK_FOODS)
        plan = generate_full_meal_plan(target, by_type)

        for slot in ["breakfast", "lunch", "dinner", "snack"]:
            for item in plan[slot].get("items", []):
                self.assertIn("quantity", item)
                self.assertGreaterEqual(item["quantity"], 1)


if __name__ == '__main__':
    unittest.main()
