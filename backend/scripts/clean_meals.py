import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import firestore
from utils.meal_validation import normalize_name
from utils.logger import app_logger

# Initialize Firebase
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

def clean_meals():
    print("Fetching all meals from Firestore...")
    meals_ref = db.collection("meals_v3")
    docs = list(meals_ref.stream())
    
    seen = {}
    to_delete = []
    
    print(f"Found {len(docs)} total meals.")
    
    for doc in docs:
        meal = doc.to_dict()
        doc_id = doc.id
        raw_name = meal.get("mealName")
        
        if not raw_name:
            to_delete.append(doc_id)
            print(f"Queueing deletion for meal missing name: {doc_id}")
            continue
            
        key = normalize_name(raw_name)
        calories = float(meal.get("calories") or 0)
        
        if key not in seen:
            seen[key] = {"id": doc_id, "calories": calories, "name": raw_name}
        else:
            existing = seen[key]
            if calories < existing["calories"]:
                # Keep the new one (lower calories), delete the old one
                to_delete.append(existing["id"])
                print(f"Queueing deletion for duplicate '{existing['name']}' ({existing['calories']} kcal). Keeping '{raw_name}' ({calories} kcal).")
                seen[key] = {"id": doc_id, "calories": calories, "name": raw_name}
            else:
                # Keep the existing one, delete the new one
                to_delete.append(doc_id)
                print(f"Queueing deletion for duplicate '{raw_name}' ({calories} kcal). Keeping '{existing['name']}' ({existing['calories']} kcal).")

    print(f"\nFound {len(to_delete)} duplicate/invalid meals to delete.")
    
    if not to_delete:
        print("No duplicates found. Database is clean.")
        return

    # Delete in batches
    batch = db.batch()
    count = 0
    total_deleted = 0
    
    print("Deleting duplicates in batches...")
    for doc_id in to_delete:
        batch.delete(meals_ref.document(doc_id))
        count += 1
        
        if count >= 400:
            batch.commit()
            total_deleted += count
            print(f"Deleted batch of {count} (Total: {total_deleted})")
            batch = db.batch()
            count = 0
            
    if count > 0:
        batch.commit()
        total_deleted += count
        print(f"Deleted final batch of {count} (Total: {total_deleted})")
        
    print("Cleanup complete!")

if __name__ == "__main__":
    clean_meals()
