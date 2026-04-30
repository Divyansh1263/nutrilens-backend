import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

from services.meal_generator_service import MealGeneratorService
import json

def test_knn_validation():
    svc = MealGeneratorService()
    
    plan = {
        "user_target_calories": 1500,
        "user_target_protein": 80,
        "actual_calories": 1500,
        "actual_protein": 80.0,
        "meals": {
            "breakfast": [
                {"mealName": "Plain Oats", "quantity": 1.0, "calories": 150, "protein": 5, "carbs": 27, "fat": 3}
            ],
            "lunch": [
                {"mealName": "Plain Roti", "quantity": 2.0, "calories": 240, "protein": 8, "carbs": 44, "fat": 4},
                {"mealName": "Chicken Curry", "quantity": 1.0, "calories": 300, "protein": 25, "carbs": 10, "fat": 15}  # INVALID for Vegan
            ],
            "snack": [
                {"mealName": "Peanut Butter (2 tbsp)", "quantity": 1.0, "calories": 190, "protein": 8, "carbs": 6, "fat": 16} # INVALID for Nut-Free
            ],
            "dinner": [
                {"mealName": "Plain Rice", "quantity": 1.0, "calories": 200, "protein": 4, "carbs": 45, "fat": 1}
            ]
        }
    }
    
    meals_db = [
        # Base invalid items
        {"mealName": "Chicken Curry", "calories": 300, "protein": 25, "carbs": 10, "fat": 15, "is_vegetarian": False, "is_vegan": False, "is_gluten_free": True, "is_nut_free": True, "category": "main course"},
        {"mealName": "Peanut Butter (2 tbsp)", "calories": 190, "protein": 8, "carbs": 6, "fat": 16, "is_vegetarian": True, "is_vegan": True, "is_gluten_free": True, "is_nut_free": False, "category": "snack"},
        # Neighbors
        {"mealName": "Tofu Curry", "calories": 280, "protein": 22, "carbs": 12, "fat": 14, "is_vegetarian": True, "is_vegan": True, "is_gluten_free": True, "is_nut_free": True, "category": "main course"},
        {"mealName": "Hummus (2 tbsp)", "calories": 180, "protein": 6, "carbs": 8, "fat": 14, "is_vegetarian": True, "is_vegan": True, "is_gluten_free": True, "is_nut_free": True, "category": "snack"}
    ]
    
    user = {"is_vegetarian": True, "is_vegan": True, "is_nut_free": True}
    
    print("\n--- KNN VALIDATION TEST ---")
    print(f"Initial Calories: {plan['actual_calories']}, Protein: {plan['actual_protein']}")
    
    validated_plan = svc.apply_knn_validation(plan, meals_db, user)
    
    print(f"\nFinal Calories: {validated_plan['actual_calories']}")
    print(f"Final Protein: {validated_plan['actual_protein']}")
    print("\nMeal Structure After KNN Validation:")
    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        print(f"[{slot.upper()}]")
        for i in validated_plan["meals"].get(slot, []):
            print(f" - {i['mealName']} ({i['quantity']}x, {i['protein']}g prot, {i['calories']} kcal)")

if __name__ == "__main__":
    test_knn_validation()
