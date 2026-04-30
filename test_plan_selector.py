import firebase_admin
from firebase_admin import credentials, firestore
from ai.plan_selector import PlanSelector
import json

def test_selector():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    selector = PlanSelector(db)

    print("\n--- TEST 1: Veg Weight Loss (Female) ---")
    u1 = {
        "weight": 65,
        "height": 160,
        "age": 28,
        "gender": "female",
        "activityLevel": "lightly_active",
        "goal": "lose_weight",
        "is_vegetarian": True,
        "is_vegan": False
    }
    p1 = selector.select_plan(u1)
    if p1:
        print(f"Selected: {p1.get('planName')} ({p1.get('dietType')}, goal={p1.get('goal')})")
    
    print("\n--- TEST 2: Non-Veg Muscle Gain (Male) ---")
    u2 = {
        "weight": 80,
        "height": 180,
        "age": 25,
        "gender": "male",
        "activityLevel": "very_active",
        "goal": "muscle_gain",
        "is_vegetarian": False,
        "is_vegan": False
    }
    p2 = selector.select_plan(u2)
    if p2:
        print(f"Selected: {p2.get('planName')} ({p2.get('dietType')}, goal={p2.get('goal')})")

    print("\n--- TEST 3: Vegan (Male) ---")
    u3 = {
        "weight": 70,
        "height": 175,
        "age": 30,
        "gender": "male",
        "activityLevel": "moderately_active",
        "goal": "maintain",
        "is_vegetarian": True,
        "is_vegan": True
    }
    p3 = selector.select_plan(u3)
    if p3:
        print(f"Selected: {p3.get('planName')} ({p3.get('dietType')}, goal={p3.get('goal')})")
        
    print("\n--- TESTS COMPLETE ---")

if __name__ == "__main__":
    test_selector()
