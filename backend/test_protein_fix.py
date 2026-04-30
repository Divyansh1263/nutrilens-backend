import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

from services.meal_generator_service import MealGeneratorService
import json

def test_protein_fix():
    svc = MealGeneratorService()
    
    # Mock Plan (scaled down to 1200 target, protein is only 40g but target is 90g)
    # 50g deficit
    plan = {
        "user_target_calories": 1200,
        "actual_calories": 1180,
        "actual_protein": 40.0,
        "meals": {
            "breakfast": [
                {"mealName": "Plain Oats", "quantity": 1.0, "calories": 150, "protein": 5, "carbs": 27, "fat": 3}
            ],
            "lunch": [],
            "snack": [],
            "dinner": []
        }
    }
    
    meals_db = [
        {"mealName": "Whey Protein Shake", "is_high_protein": True, "protein": 24, "calories": 120, "is_vegetarian": True, "is_vegan": False},
        {"mealName": "Soy Chunks", "is_high_protein": True, "protein": 25, "calories": 150, "is_vegetarian": True, "is_vegan": True},
        {"mealName": "Greek Yogurt", "is_high_protein": True, "protein": 10, "calories": 100, "is_vegetarian": True, "is_vegan": False},
        {"mealName": "Grilled Chicken Breast (100g)", "is_high_protein": True, "protein": 31, "calories": 165, "is_vegetarian": False, "is_vegan": False}
    ]
    
    user = {"is_vegetarian": True, "is_vegan": False}
    target_protein = 90.0
    
    print("\n--- PROTEIN FIX TEST ---")
    print(f"Initial Calories: {plan['actual_calories']} (Max allowed: 1320)")
    print(f"Initial Protein: {plan['actual_protein']} (Target: {target_protein}, Deficit: 50.0)")
    
    fixed_plan = svc.fix_protein(plan, meals_db, user, target_protein)
    
    print(f"\nFinal Calories: {fixed_plan['actual_calories']}")
    print(f"Final Protein: {fixed_plan['actual_protein']}")
    print("Snack Slot Additions:")
    for i in fixed_plan["meals"].get("snack", []):
        print(f" - {i['mealName']} (+{i['protein']}g protein, +{i['calories']} kcal)")

if __name__ == "__main__":
    test_protein_fix()
