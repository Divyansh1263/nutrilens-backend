import random

MEAL_SPLIT = {
    "Breakfast": 0.25,
    "Lunch": 0.35,
    "Dinner": 0.30,
    "Snack": 0.10
}

def build_meal(meal_type, foods, daily_calories):
    """
    Accumulates foods until meal calorie target is satisfied
    """

    target_calories = daily_calories * MEAL_SPLIT[meal_type]
    meal_items = []
    meal_calories = 0

    random.shuffle(foods)

    for food in foods:
        if meal_calories >= target_calories * 0.90:
            break

        meal_items.append(food)
        meal_calories += food.get("calories", 0)

    return {
        "items": meal_items,
        "mealCalories": round(meal_calories, 1)
    }


def generate_full_meal_plan(target, meals_by_type):
    """
    meals_by_type = {
        "Breakfast": [...],
        "Lunch": [...],
        "Dinner": [...],
        "Snack": [...]
    }
    """

    plan = {}
    total_calories = 0

    for meal_type, foods in meals_by_type.items():
        if not foods:
            continue

        meal = build_meal(meal_type, foods, target["calories"])
        plan[meal_type.lower()] = meal
        total_calories += meal["mealCalories"]

    plan["totalCalories"] = round(total_calories, 1)
    return plan
