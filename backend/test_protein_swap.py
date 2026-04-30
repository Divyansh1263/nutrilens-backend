import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

from services.meal_generator_service import MealGeneratorService
import json

def test_protein_swap():
    svc = MealGeneratorService()
    
    # Mock Plan
    # Target Cal: 1300. Max allowed: 1430 (+10%)
    # Target Protein: 90
    # Actual Cal: 1300
    # Actual Prot: 45
    plan = {
        "user_target_calories": 1300,
        "actual_calories": 1300,
        "actual_protein": 45.0,
        "meals": {
            "breakfast": [
                {"mealName": "Plain Oats", "quantity": 1.0, "calories": 150, "protein": 5, "carbs": 27, "fat": 3}
            ],
            "lunch": [
                {"mealName": "Plain Roti", "quantity": 2.0, "calories": 240, "protein": 8, "carbs": 44, "fat": 4},
                {"mealName": "Dal Tadka", "quantity": 1.0, "calories": 220, "protein": 12, "carbs": 28, "fat": 8}
            ],
            "snack": [
                {"mealName": "Tea (Less Sugar)", "quantity": 1.0, "calories": 50, "protein": 1, "carbs": 8, "fat": 1}
            ],
            "dinner": [
                {"mealName": "Aloo Sabzi", "quantity": 1.0, "calories": 180, "protein": 3, "carbs": 25, "fat": 7},
                {"mealName": "Plain Rice", "quantity": 1.0, "calories": 200, "protein": 4, "carbs": 45, "fat": 1}
            ]
        }
    }
    
    meals_db = [
        {"mealName": "Whey Protein Shake", "is_high_protein": True, "protein": 24, "calories": 120, "is_vegetarian": True, "is_vegan": False, "validMealTypes": ["Snack"]},
        {"mealName": "Soy Chunks", "is_high_protein": True, "protein": 25, "calories": 150, "is_vegetarian": True, "is_vegan": True, "validMealTypes": ["Lunch", "Dinner"], "category": "main course"},
        {"mealName": "Greek Yogurt", "is_high_protein": True, "protein": 10, "calories": 100, "is_vegetarian": True, "is_vegan": False, "validMealTypes": ["Breakfast"]},
        {"mealName": "Grilled Chicken Breast (100g)", "is_high_protein": True, "protein": 31, "calories": 165, "is_vegetarian": False, "is_vegan": False, "validMealTypes": ["Dinner"]},
        {"mealName": "Paneer (100g)", "is_high_protein": True, "protein": 18, "calories": 265, "is_vegetarian": True, "is_vegan": False, "validMealTypes": ["Dinner"], "category": "main course"}
    ]
    
    user = {"is_vegetarian": True, "is_vegan": False}
    target_protein = 90.0
    
    print("\n--- PROTEIN SWAP TEST ---")
    print(f"Initial Calories: {plan['actual_calories']} (Max allowed: 1430)")
    print(f"Initial Protein: {plan['actual_protein']} (Target: {target_protein})")
    
    swapped_plan = svc.apply_protein_swap(plan, meals_db, user, target_protein)
    
    print(f"\nFinal Calories: {swapped_plan['actual_calories']}")
    print(f"Final Protein: {swapped_plan['actual_protein']}")
    print("\nMeal Structure After Swap:")
    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        print(f"[{slot.upper()}]")
        for i in swapped_plan["meals"].get(slot, []):
            print(f" - {i['mealName']} ({i['protein']}g protein, {i['calories']} kcal)")

if __name__ == "__main__":
    test_protein_swap()
