import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

from services.meal_generator_service import MealGeneratorService
import json

def test_scaling():
    svc = MealGeneratorService()
    
    # Mock Plan
    plan = {
        "targetCalories": 1500,
        "meals": {
            "breakfast": [
                {"mealName": "Plain Oats", "quantity": 1.0, "calories": 150, "protein": 5, "carbs": 27, "fat": 3},
                {"mealName": "Boiled Eggs (2)", "quantity": 1.0, "calories": 140, "protein": 12, "carbs": 1, "fat": 10},
                {"mealName": "Tea (Less Sugar)", "quantity": 1.0, "calories": 50, "protein": 1, "carbs": 8, "fat": 1}
            ],
            "lunch": [
                {"mealName": "Plain Roti", "quantity": 2.0, "calories": 240, "protein": 8, "carbs": 44, "fat": 4},
                {"mealName": "Dal Tadka", "quantity": 1.0, "calories": 220, "protein": 12, "carbs": 28, "fat": 8}
            ],
            "snack": [
                {"mealName": "Whey Protein Shake", "quantity": 1.0, "calories": 120, "protein": 24, "carbs": 3, "fat": 1}
            ],
            "dinner": [
                {"mealName": "Plain Rice", "quantity": 1.0, "calories": 200, "protein": 4, "carbs": 45, "fat": 1},
                {"mealName": "Grilled Chicken Breast (100g)", "quantity": 1.0, "calories": 165, "protein": 31, "carbs": 0, "fat": 4}
            ]
        }
    }
    
    print("\n--- SCALING TEST: Scale Up (1500 -> 1950) Ratio 1.3 ---")
    import copy
    plan1 = copy.deepcopy(plan)
    scaled1 = svc.scale_plan(plan1, 1950)
    
    print(f"Target: 1950, Actual Scaled: {scaled1['actual_calories']}")
    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        for i in scaled1["meals"][slot]:
            print(f"{i['mealName']}: {i['quantity']}x")
            
    print("\n--- SCALING TEST: Scale Down (1500 -> 1200) Ratio 0.8 ---")
    plan2 = copy.deepcopy(plan)
    scaled2 = svc.scale_plan(plan2, 1200)
    
    print(f"Target: 1200, Actual Scaled: {scaled2['actual_calories']}")
    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        for i in scaled2["meals"][slot]:
            print(f"{i['mealName']}: {i['quantity']}x")

if __name__ == "__main__":
    test_scaling()
