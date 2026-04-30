import json
import re
import math
import sys
import firebase_admin
from firebase_admin import credentials, firestore

def clean_string(s):
    if not isinstance(s, str):
        return ""
    return s.strip()

def clean_number(n):
    try:
        val = float(n)
        if math.isnan(val):
            return 0.0
        return val
    except:
        return 0.0

def normalize_meal(meal):
    normalized = {}
    normalized["mealName"] = clean_string(meal.get("mealName", "Unknown Meal"))
    normalized["calories"] = clean_number(meal.get("calories", 0))
    normalized["protein"] = clean_number(meal.get("protein", 0))
    normalized["carbs"] = clean_number(meal.get("carbs", 0))
    normalized["fat"] = clean_number(meal.get("fat", 0))
    normalized["category"] = clean_string(meal.get("category", "Main Course"))
    
    raw_keywords = meal.get("searchKeywords", [])
    if not isinstance(raw_keywords, list):
        if isinstance(raw_keywords, str):
            raw_keywords = raw_keywords.split()
        else:
            raw_keywords = []
    
    keywords = list(set([clean_string(k).lower() for k in raw_keywords if clean_string(k)]))
    
    base_keywords = [clean_string(w).lower() for w in normalized["mealName"].split()]
    for bk in base_keywords:
        if bk and bk not in keywords:
            keywords.append(bk)
            
    pad_idx = 1
    while len(keywords) < 5:
        kw = f"{normalized['mealName'].lower().replace(' ', '')}_k{pad_idx}"
        if kw not in keywords:
            keywords.append(kw)
        pad_idx += 1
    
    normalized["searchKeywords"] = list(set(keywords))
    
    normalized["servingSize"] = clean_string(meal.get("servingSize", "1 serving"))
    
    serving_grams = clean_number(meal.get("servingGrams", 100))
    if serving_grams <= 0:
        serving_grams = 100.0
    normalized["servingGrams"] = serving_grams
    
    valid_types = meal.get("validMealTypes", [])
    if not isinstance(valid_types, list):
        valid_types = [valid_types] if isinstance(valid_types, str) else []
    valid_types = [clean_string(t) for t in valid_types if clean_string(t)]
    if not valid_types:
        valid_types = ["Lunch", "Dinner"]
    normalized["validMealTypes"] = valid_types
    
    normalized["glycemic_index"] = clean_string(meal.get("glycemic_index", "Medium"))
    normalized["is_vegetarian"] = bool(meal.get("is_vegetarian", False))
    normalized["is_vegan"] = bool(meal.get("is_vegan", False))
    
    if normalized["is_vegan"]:
        normalized["is_vegetarian"] = True
        
    normalized["is_gluten_free"] = bool(meal.get("is_gluten_free", False))
    normalized["is_nut_free"] = bool(meal.get("is_nut_free", False))
    normalized["is_sick_friendly"] = bool(meal.get("is_sick_friendly", False))
    
    explanations = meal.get("explanations", {})
    if not isinstance(explanations, dict):
        explanations = {}
    normalized["explanations"] = explanations
    
    return normalized

def is_valid(meal):
    if not (50 <= meal["calories"] <= 1000): return False
    if not (0 <= meal["protein"] <= 60): return False
    if not (0 <= meal["carbs"] <= 150): return False
    if not (0 <= meal["fat"] <= 80): return False
    return True

def generate_doc_id(meal_name):
    name = clean_string(meal_name).lower()
    name = re.sub(r'[^a-z0-9\s_]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name

def load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                if "meals" in data:
                    return data["meals"]
                else:
                    return list(data.values())
            return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def main():
    print("Loading datasets...")
    export_data = load_json("meals_export.json")
    meals_data = load_json("meals.json")
        
    print(f"Total in meals_export: {len(export_data)}")
    print(f"Total in meals.json: {len(meals_data)}")
    
    processed_export = [normalize_meal(m) for m in export_data]
    processed_meals = [normalize_meal(m) for m in meals_data]
    
    valid_export = [m for m in processed_export if is_valid(m)]
    valid_meals = [m for m in processed_meals if is_valid(m)]
    
    print(f"Valid in export: {len(valid_export)} (Skipped: {len(export_data) - len(valid_export)})")
    print(f"Valid in meals: {len(valid_meals)} (Skipped: {len(meals_data) - len(valid_meals)})")
    
    merged_meals_dict = {}
    
    # Add new valid meals
    for m in valid_meals:
        doc_id = generate_doc_id(m["mealName"])
        merged_meals_dict[doc_id] = m
            
    replaced_count = 0
    added_from_export = 0
    
    for old_m in valid_export:
        old_name_lower = old_m["mealName"].lower()
        old_keywords = set(old_m["searchKeywords"])
        old_id = generate_doc_id(old_m["mealName"])
        
        match_found = False
        if old_id in merged_meals_dict:
            match_found = True
            
        if not match_found:
            for new_id, new_m in merged_meals_dict.items():
                if new_m["mealName"].lower() == old_name_lower:
                    match_found = True
                    break
                new_keywords = set(new_m["searchKeywords"])
                if len(old_keywords.intersection(new_keywords)) >= 2:
                    match_found = True
                    break
        
        if match_found:
            replaced_count += 1
        else:
            merged_meals_dict[old_id] = old_m
            added_from_export += 1

    final_meals = {}
    for doc_id, meal in merged_meals_dict.items():
        final_doc_id = generate_doc_id(meal["mealName"])
        final_meals[final_doc_id] = meal
        
    final_list = list(final_meals.values())
    
    print(f"\nTotal meals after merge: {len(final_list)}")
    print(f"Replaced/Matched meals count: {replaced_count}")
    print(f"New meals added (or retained from meals.json): {len(valid_meals)}")
    print(f"Old meals kept from export: {added_from_export}")
    
    with open("merged_meals.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)
    print("Saved merged_meals.json")

    # Firestore Migration
    print("\n--- Starting Firestore Upload ---")
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass # Already initialized
    
    db = firestore.client()
    collection_name = "meals_v2"
    
    batch = db.batch()
    batch_count = 0
    total_uploaded = 0
    
    print(f"Uploading to {collection_name}...")
    for doc_id, meal in final_meals.items():
        doc_ref = db.collection(collection_name).document(doc_id)
        batch.set(doc_ref, meal)
        batch_count += 1
        total_uploaded += 1
        
        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"Uploaded {total_uploaded}...")
            
    if batch_count > 0:
        batch.commit()
        print(f"Uploaded {total_uploaded}...")
        
    print(f"\nTotal meals uploaded: {total_uploaded}")
    print(f"Total replaced meals: {replaced_count}")
    print(f"Total skipped meals: {(len(export_data) - len(valid_export)) + (len(meals_data) - len(valid_meals))}")
    
    # Verification
    print("\n--- Post-Upload Verification ---")
    try:
        count_query = db.collection(collection_name).count()
        count_res = count_query.get()
        doc_count = count_res[0][0].value
        print(f"Total documents in {collection_name}: {doc_count}")
    except Exception as e:
        print(f"Count verification failed (maybe old firebase-admin version): {e}")
        # fallback to get all
        docs = list(db.collection(collection_name).stream())
        print(f"Total documents in {collection_name}: {len(docs)}")
        
    sample_docs = db.collection(collection_name).limit(10).stream()
    print("\nVerifying 10 random meals:")
    valid = True
    for doc in sample_docs:
        d = doc.to_dict()
        name = d.get("mealName", "Unknown")
        kw = d.get("searchKeywords", [])
        cals = d.get("calories", 0)
        if len(kw) < 5:
            print(f"X {name} has less than 5 keywords ({len(kw)})")
            valid = False
        if not (50 <= cals <= 1000):
            print(f"X {name} has invalid calories ({cals})")
            valid = False
            
    if valid:
        print("All sampled meals passed verification!")

if __name__ == "__main__":
    main()
