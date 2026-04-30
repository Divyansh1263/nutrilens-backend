import json
from ai.plan_selector import PlanSelector
from utils.diet_utils import annotate_plan_item

# Test 1: PlanSelector Diet Filter
class MockDB:
    def collection(self, name):
        return self
    def stream(self):
        class MockDoc:
            def __init__(self, data):
                self.data = data
            def to_dict(self):
                return self.data
        return [
            MockDoc({"mealName": "Chicken", "dietType": "non-veg", "targetCalories": 2000, "calorieBucket": "medium", "goal": "maintain"}),
            MockDoc({"mealName": "Salad", "dietType": "vegan", "targetCalories": 2000, "calorieBucket": "medium", "goal": "maintain"}),
            MockDoc({"mealName": "Paneer", "dietType": "vegetarian", "targetCalories": 2000, "calorieBucket": "medium", "goal": "maintain"}),
            MockDoc({"mealName": "Unknown", "dietType": "", "targetCalories": 2000, "calorieBucket": "medium", "goal": "maintain"})
        ]

selector = PlanSelector(MockDB())
veg_user = {"is_vegetarian": True, "goal": "maintain", "weight": 70, "height": 170, "age": 30, "gender": "male"}
vegan_user = {"is_vegan": True, "goal": "maintain", "weight": 70, "height": 170, "age": 30, "gender": "male"}

veg_plan = selector.select_plan(veg_user)
vegan_plan = selector.select_plan(vegan_user)
print("Veg User got:", veg_plan["mealName"])
print("Vegan User got:", vegan_plan["mealName"])

# Test 4: Serving Size Scaling
item = {"quantity": 2.5, "calories": 300, "protein": 10, "carbs": 20, "fat": 5}
source = {"servingSize": "2 slices", "servingGrams": "50"}
annotated = annotate_plan_item(item, source, {})
print("Serving Size:", annotated["servingSize"])
print("Serving Grams:", annotated["servingGrams"])
