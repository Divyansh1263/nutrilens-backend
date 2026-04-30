import json
import firebase_admin
from firebase_admin import credentials, firestore
import random
import sys

def main():
    print("Initializing Firebase...")
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    # Step 1: Load file
    try:
        with open("meal_plans.json", "r", encoding="utf-8") as f:
            plans = json.load(f)
    except Exception as e:
        print(f"Error loading meal_plans.json: {e}")
        return

    collection_name = "meal_plans_v1"
    uploaded = 0
    errors = 0

    print(f"Loaded {len(plans)} plans. Starting upload to '{collection_name}'...")

    for plan in plans:
        # Step 2: Create document IDs
        plan_id = plan.get("planId")
        if not plan_id:
            print(f"Error: Missing planId in plan: {plan.get('planName', 'Unknown')}")
            errors += 1
            continue

        # Step 3: Validate structure
        required_keys = ["planId", "planName", "goal", "dietType", "targetCalories", "targetProtein", "meals"]
        missing_keys = [k for k in required_keys if k not in plan]
        
        if missing_keys:
            print(f"Error: Plan {plan_id} is missing required keys: {missing_keys}")
            errors += 1
            continue
            
        meals = plan.get("meals", {})
        required_meal_keys = ["breakfast", "lunch", "snack", "dinner"]
        missing_meal_keys = [k for k in required_meal_keys if k not in meals]
        
        if missing_meal_keys:
            print(f"Error: Plan {plan_id} meals object is missing keys: {missing_meal_keys}")
            errors += 1
            continue

        # Step 4: Upload to Firestore
        try:
            db.collection(collection_name).document(plan_id).set(plan)
            uploaded += 1
        except Exception as e:
            print(f"Error uploading plan {plan_id}: {e}")
            errors += 1

    # Step 5: Verify
    print("\n--- Verification ---")
    try:
        docs = list(db.collection(collection_name).stream())
        doc_count = len(docs)
        print(f"Total documents in '{collection_name}': {doc_count}")
        
        print(f"\nChecking random 5 plans:")
        random_docs = random.sample(docs, min(5, len(docs)))
        for doc in random_docs:
            data = doc.to_dict()
            print(f" - {doc.id}: {data.get('planName')} (Goal: {data.get('goal')}, Calories: {data.get('targetCalories')})")
            
    except Exception as e:
        print(f"Error verifying documents: {e}")

    # Output
    print("\n--- Summary ---")
    print(f"Total plans uploaded: {uploaded}")
    if errors > 0:
        print(f"Total errors encountered: {errors}")
    else:
        print("No errors encountered.")

if __name__ == "__main__":
    main()
