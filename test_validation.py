import json
import sys

from services.meal_generator_service import meal_generator_service

with open('meals.json', 'r', encoding='utf-8') as f:
    all_meals = json.load(f)

users = [
    {
        'userId': 'u1',
        'dietary_preference': 'Vegetarian',
        'goal': 'Weight Loss',
        'target_calories': 1500,
        'target_protein': 80,
        'target_macros': {'protein': 80, 'carbs': 150, 'fat': 40}
    },
    {
        'userId': 'u2',
        'dietary_preference': 'Vegan',
        'goal': 'Maintenance',
        'target_calories': 2000,
        'target_protein': 100,
        'target_macros': {'protein': 100, 'carbs': 200, 'fat': 50}
    },
    {
        'userId': 'u3',
        'dietary_preference': 'Non-Vegetarian',
        'goal': 'Muscle Gain',
        'target_calories': 2500,
        'target_protein': 150,
        'target_macros': {'protein': 150, 'carbs': 250, 'fat': 80}
    },
    {
        'userId': 'u4',
        'dietary_preference': 'Vegetarian',
        'goal': 'Weight Loss',
        'target_calories': 1200,
        'target_protein': 100,
        'target_macros': {'protein': 100, 'carbs': 100, 'fat': 30}
    }
]

def mock_select_plan(user):
    return {
        "targetCalories": 1500,
        "meals": {
            "breakfast": [{"mealName": "Poha", "quantity": 1}],
            "lunch": [{"mealName": "Plain Roti", "quantity": 3}, {"mealName": "Dal Tadka", "quantity": 1}],
            "snack": [{"mealName": "Tea", "quantity": 1}],
            "dinner": [{"mealName": "Vegetable Pulao", "quantity": 1}]
        }
    }

for u in users:
    print(f"\n--- Testing User: {u['goal']} {u['dietary_preference']} ({u['target_calories']} cals, {u['target_protein']} prot) ---")
    
    best_plan_raw = mock_select_plan(u)
        
    import copy
    best_plan = copy.deepcopy(best_plan_raw)
    
    user_target_calories = u['target_calories']
    target_protein = u['target_protein']
    
    scaled_plan = meal_generator_service.scale_plan(best_plan, user_target_calories, all_meals)
    scaled_plan = meal_generator_service._recompute_totals(scaled_plan)
    
    corrected_plan = meal_generator_service.fix_protein(scaled_plan, all_meals, u, target_protein)
    corrected_plan = meal_generator_service._recompute_totals(corrected_plan)
    
    # Skip apply_knn_validation because it might require the model/DB
    validated_plan = corrected_plan # meal_generator_service.apply_knn_validation(corrected_plan, all_meals, u)
    validated_plan = meal_generator_service._recompute_totals(validated_plan)
    
    adjusted_plan = meal_generator_service.micro_adjust_plan(validated_plan, user_target_calories)
    adjusted_plan = meal_generator_service._recompute_totals(adjusted_plan)
    
    final_plan = meal_generator_service.final_protein_check(adjusted_plan, all_meals, u, target_protein, user_target_calories)
    final_plan = meal_generator_service._recompute_totals(final_plan)
    
    for i in range(3):
        final_plan = meal_generator_service._recompute_totals(final_plan)
        
    from utils.diet_utils import annotate_plan_item
    
    sum_cal = 0
    sum_prot = 0
    portions = []
    
    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        for item in final_plan.get("meals", {}).get(slot, []):
            qty = item.get("quantity", 1.0)
            annotated = annotate_plan_item(item, qty, u, all_meals)
            sum_cal += annotated["calories"]
            sum_prot += annotated["protein"]
            portions.append(f"{qty}x {annotated['mealName']} ({annotated.get('servingSize', 'serving')})")
            
    print(f"Final Calories: {sum_cal:.1f} (Target: {user_target_calories})")
    print(f"Final Protein: {sum_prot:.1f} (Target: {target_protein})")
    print("Portions:")
    for p in portions:
        print(f"  {p}")
