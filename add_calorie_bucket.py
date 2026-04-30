import json
import firebase_admin
from firebase_admin import credentials, firestore

def main():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Fetching meal_plans_v1...")
    plans_ref = db.collection("meal_plans_v1").stream()
    
    updated = 0

    for p in plans_ref:
        plan_dict = p.to_dict()
        target_calories = float(plan_dict.get("targetCalories", 0))
        
        if target_calories <= 1600:
            bucket = "low"
        elif target_calories >= 1900:
            bucket = "high"
        else:
            bucket = "medium"
            
        p.reference.update({"calorieBucket": bucket})
        updated += 1

    result = {
        "updated": updated
    }

    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
