import requests
import json
import time

URL = "https://nutrilens-backend-817451767836.asia-south1.run.app"
USER_ID = "live_test_user_02"
DATE_STR = "2026-05-02"

# 1. GET /
print("1. GET /")
r1 = requests.get(f"{URL}/")
print(r1.status_code, r1.text)

# 2. POST /generate-meal-plan
print("\n2. POST /generate-meal-plan")
r2 = requests.post(f"{URL}/generate-meal-plan", json={
    "userId": USER_ID,
    "date": DATE_STR,
    "profile": {
        "userId": USER_ID,
        "dietary_restrictions": {"is_vegetarian": True},
        "target_calories": 1571
    }
})
plan_res = r2.json()
print(r2.status_code, "SUCCESS" if plan_res.get("success") else "FAILED")
plan = plan_res
plan_total = 0.0

for slot in ["breakfast", "lunch", "snack", "dinner"]:
    for item in plan.get(slot, []):
        plan_total += item.get("calories", 0)
        # 3. POST /log-meal
        r3 = requests.post(f"{URL}/log-meal", json={
            "userId": USER_ID,
            "date": DATE_STR,
            "mealName": item.get("mealName"),
            "quantity": item.get("quantity", 1.0),
            "mealType": slot,
            "calories": item.get("calories"),
            "protein": item.get("protein"),
            "carbs": item.get("carbs"),
            "fat": item.get("fat")
        })
        print(f"LOG STATUS: {r3.status_code} {r3.text}")

print(f"\nPLAN TOTAL CALORIES: {plan_total}")

# 4. GET /tracker-summary
print("\n4. GET /tracker-summary")
r4 = requests.get(f"{URL}/tracker-summary?userId={USER_ID}&date={DATE_STR}")
tracker_res = r4.json()
tracker_total = tracker_res.get("consumed", {}).get("calories", 0)
print(f"TRACKER TOTAL CALORIES: {tracker_total}")

if abs(plan_total - tracker_total) < 5:
    print("\nSUCCESS: Tracker totals match plan totals!")
else:
    print("\nFAILED: Tracker mismatch!")
