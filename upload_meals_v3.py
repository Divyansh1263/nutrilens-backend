import json
import re
import firebase_admin
from firebase_admin import credentials, firestore

def generate_doc_id(meal_name):
    name = meal_name.strip().lower()
    name = re.sub(r'[^a-z0-9\s_]', '', name)
    return re.sub(r'\s+', '_', name)

def is_valid(meal):
    try:
        if not (50 <= float(meal.get("calories", 0)) <= 1000): return False
        if not (0 <= float(meal.get("protein", 0)) <= 60): return False
        if not (0 <= float(meal.get("carbs", 0)) <= 150): return False
        if not (0 <= float(meal.get("fat", 0)) <= 80): return False
        if float(meal.get("servingGrams", 0)) <= 0: return False
        if len(meal.get("searchKeywords", [])) < 3: return False
        if len(meal.get("validMealTypes", [])) == 0: return False
        return True
    except:
        return False

def main():
    try:
        app = firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        
    db = firestore.client()
    
    print("Loading final_refined_meals.json...")
    with open("final_refined_meals.json", "r", encoding="utf-8") as f:
        meals = json.load(f)
        
    print(f"Loaded {len(meals)} meals.")
    
    valid_meals = []
    skipped_count = 0
    
    unique_ids = set()
    for m in meals:
        if is_valid(m):
            doc_id = generate_doc_id(m["mealName"])
            if doc_id not in unique_ids:
                m["id"] = doc_id
                valid_meals.append((doc_id, m))
                unique_ids.add(doc_id)
            else:
                # duplicate id handled
                skipped_count += 1
        else:
            skipped_count += 1
            
    print(f"Valid meals to upload: {len(valid_meals)}")
    print(f"Skipped meals: {skipped_count}")
    
    col_ref = db.collection("meals_v3")
    
    print("Uploading to Firestore meals_v3 using batches...")
    batch = db.batch()
    count = 0
    
    for doc_id, m in valid_meals:
        doc_ref = col_ref.document(doc_id)
        batch.set(doc_ref, m)
        count += 1
        
        if count % 400 == 0:
            batch.commit()
            print(f"Committed batch of 400...")
            batch = db.batch()
            
    if count % 400 != 0:
        batch.commit()
        
    print(f"[OK] Total meals uploaded: {count}")
    print(f"[OK] Total valid meals: {len(valid_meals)}")
    print(f"[OK] Skipped meals: {skipped_count}")
    print(f"[OK] Errors: None")
    
    print("\n--- VERIFY DATABASE ---")
    docs = list(col_ref.limit(5).stream())
    print(f"Fetched {len(docs)} sample meals from meals_v3:")
    for d in docs:
        data = d.to_dict()
        print(f" - {data['mealName']} (Cal: {data['calories']}, Pro: {data['protein']}, Kwds: {len(data['searchKeywords'])})")

if __name__ == "__main__":
    main()
