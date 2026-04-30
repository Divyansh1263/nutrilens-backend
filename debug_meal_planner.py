import json
import traceback
from app import app

# We need to simulate the requests
def run_debug():
    report = {
        "plan_correct": False,
        "tracker_correct": False,
        "diet_filter_correct": False,
        "main_issue": "",
        "exact_root_cause": "",
        "confidence": "high"
    }

    with app.test_client() as client:
        # STEP 1: GENERATE PLAN
        # Since auth is optional, we just pass userId in JSON
        user_id = "test_user_1571"
        
        # We need to register or just mock the user in the DB
        from firebase_admin import firestore
        db = firestore.client()
        
        db.collection("users").document(user_id).set({
            "userId": user_id,
            "name": "Test User",
            "weight": 72.5,
            "height": 170,
            "age": 30,
            "gender": "male",
            "activityLevel": "sedentary",
            "goal": "lose_weight",
            "is_vegetarian": True,
            "is_vegan": False,
            "dietType": "vegetarian"
        })

        date_str = "2026-05-01"

        print("Generating meal plan...")
        res = client.post("/generate-meal-plan", json={
            "userId": user_id,
            "date": date_str
        })
        
        if res.status_code != 200:
            print("Failed to generate plan:", res.get_json())
            return
            
        plan_data = res.get_json()
        target_calories = plan_data.get("target_calories")
        print("Generated target calories:", target_calories)
        
        # STEP 2: VERIFY PLAN TOTAL
        manual_sum = 0
        slots = ["breakfast", "lunch", "snack", "dinner"]
        
        for slot in slots:
            for item in plan_data.get(slot, []):
                item_cal = float(item.get("calories", 0))
                qty = float(item.get("quantity", 1))
                # Wait, does item_cal represent the base or total? 
                # Let's sum (item_cal * qty) as requested by the prompt
                manual_sum += (item_cal * qty)
        
        diff_plan = abs(manual_sum - target_calories)
        within_5_percent = diff_plan <= (0.05 * target_calories)
        
        print("--- STEP 2: PLAN TOTAL ---")
        print(json.dumps({
            "plan_total": manual_sum,
            "target": target_calories,
            "difference": diff_plan,
            "within_5_percent": within_5_percent
        }, indent=2))
        
        # STEP 3: LOG ALL MEALS
        # Simulate logging all meals once
        print("Logging all meals...")
        for slot in slots:
            for item in plan_data.get(slot, []):
                # The log_meal endpoint expects calories to be provided_macros
                client.post("/log-meal", json={
                    "userId": user_id,
                    "mealName": item.get("mealName"),
                    "quantity": float(item.get("quantity", 1)),
                    "mealType": slot,
                    "source": "plan",
                    "date": date_str,
                    "calories": item.get("calories"),
                    "protein": item.get("protein"),
                    "carbs": item.get("carbs"),
                    "fat": item.get("fat")
                })
        
        # STEP 4: TRACKER VALIDATION
        print("Fetching tracker summary...")
        tracker_res = client.get(f"/tracker-summary?userId={user_id}&date={date_str}")
        tracker_data = tracker_res.get_json().get("data", {})
        
        tracker_consumed = tracker_data.get("consumed", {}).get("calories", 0)
        
        # What is plan_total? It's the sum(item_calories) since the plan says actual_calories
        plan_actual_total = plan_data.get("total_calories", 0) 
        # Actually the tracker is summing provided calories. 
        # But if log-meal multiplies provided calories * quantity, it'll double scale.
        
        diff_tracker = tracker_consumed - manual_sum
        double_scaling = False
        if abs(tracker_consumed - manual_sum) > 10: # Some tolerance
            double_scaling = True

        print("--- STEP 4: TRACKER VALIDATION ---")
        print(json.dumps({
            "plan_total": manual_sum,
            "tracker_total": tracker_consumed,
            "difference": diff_tracker,
            "double_scaling_present": double_scaling
        }, indent=2))

        # STEP 6: DIET FILTER CHECK
        # Use vegetarian user (which we did). Verify ANY non-veg item exists.
        from utils.diet_utils import _NON_VEG_KWS
        diet_violation = False
        offending_items = []
        for slot in slots:
            for item in plan_data.get(slot, []):
                name = item.get("mealName", "").lower()
                for kw in _NON_VEG_KWS:
                    if kw in name:
                        diet_violation = True
                        offending_items.append(name)
                        break

        print("--- STEP 6: DIET FILTER CHECK ---")
        print(json.dumps({
            "diet_violation": diet_violation,
            "offending_items": list(set(offending_items))
        }, indent=2))
        
        # FIND ROOT CAUSE
        # Double scaling is present if tracker_total == manual_sum, 
        # but wait: if item_cal in the plan is ALREADY scaled (e.g. 300 kcal for qty=2), 
        # then manual_sum = item_cal * qty = 600.
        # If tracker logs item_cal * qty, tracker will be 600.
        # But the actual calories should be 300.
        
        plan_cal_sum_no_qty = 0
        for slot in slots:
            for item in plan_data.get(slot, []):
                plan_cal_sum_no_qty += float(item.get("calories", 0))
                
        print("Sum of item['calories'] without multiplying qty:", plan_cal_sum_no_qty)

        # Let's see what is exactly happening.
        # We will just print everything out first to analyze before writing final report.

if __name__ == "__main__":
    try:
        run_debug()
    except Exception as e:
        traceback.print_exc()
