import json
import re
import math

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
        
    processed_export = [normalize_meal(m) for m in export_data]
    processed_meals = [normalize_meal(m) for m in meals_data]
    
    valid_export = [m for m in processed_export if is_valid(m)]
    valid_meals = [m for m in processed_meals if is_valid(m)]
    
    print(f"Total valid in export: {len(valid_export)}")
    print(f"Total valid in meals: {len(valid_meals)}")
    
    merged_meals_dict = {}
    matched_pairs = []
    
    # First add new valid meals
    for m in valid_meals:
        doc_id = generate_doc_id(m["mealName"])
        merged_meals_dict[doc_id] = m
            
    replaced_count = 0
    added_from_export = 0
    
    # Extra qualifiers to avoid cross-matching
    qualifiers = {
        "butter", "fried", "masala", "curry", "dry", "grilled", 
        "makhani", "tadka", "jeera", "plain", "sweet", "spicy", 
        "paneer", "chicken", "mutton", "egg", "veg"
    }
    
    for old_m in valid_export:
        old_name = old_m["mealName"]
        old_name_lower = old_name.lower()
        old_keywords = set(old_m["searchKeywords"])
        old_id = generate_doc_id(old_name)
        
        match_found = False
        matched_with = None
        
        # Rule 1: Exact match ID
        if old_id in merged_meals_dict:
            match_found = True
            matched_with = merged_meals_dict[old_id]["mealName"]
            
        if not match_found:
            for new_id, new_m in merged_meals_dict.items():
                new_name = new_m["mealName"]
                new_name_lower = new_name.lower()
                
                # Rule 1 Alternative: Exact name match (case insensitive)
                if new_name_lower == old_name_lower:
                    match_found = True
                    matched_with = new_name
                    break
                
                # Rule 2: High Confidence Keyword Match
                new_keywords = set(new_m["searchKeywords"])
                intersection = old_keywords.intersection(new_keywords)
                union = old_keywords.union(new_keywords)
                
                if len(union) == 0:
                    continue
                    
                jaccard = len(intersection) / len(union)
                
                if jaccard >= 0.8:
                    len_diff = abs(len(old_name_lower) - len(new_name_lower)) / max(len(old_name_lower), len(new_name_lower))
                    
                    if len_diff <= 0.30:
                        # First keyword or main ingredient match
                        # We approximate "first keyword" / "main ingredient" by checking if the first word of the name matches
                        old_words = old_name_lower.split()
                        new_words = new_name_lower.split()
                        
                        if not old_words or not new_words:
                            continue
                            
                        first_word_match = (old_words[0] == new_words[0])
                        
                        if first_word_match:
                            # Strict avoidance of qualifier mismatch
                            old_word_set = set(old_words)
                            new_word_set = set(new_words)
                            has_extra_qualifier = False
                            
                            for q in qualifiers:
                                in_old = q in old_word_set
                                in_new = q in new_word_set
                                if in_old != in_new:
                                    has_extra_qualifier = True
                                    break
                                    
                            if not has_extra_qualifier:
                                match_found = True
                                matched_with = new_name
                                break
        
        if match_found:
            replaced_count += 1
            if len(matched_pairs) < 20:
                matched_pairs.append((old_name, matched_with))
        else:
            merged_meals_dict[old_id] = old_m
            added_from_export += 1

    final_meals = {}
    for doc_id, meal in merged_meals_dict.items():
        # Ensure no duplicates by ID (which normalizes names)
        final_meals[doc_id] = meal
        
    final_list = list(final_meals.values())
    
    print("\n--- MERGE RESULTS ---")
    print(f"Total original meals (export): {len(export_data)}")
    print(f"Total final meals: {len(final_list)}")
    print(f"Replacements count (Overwritten): {replaced_count}")
    print(f"New meals added (or retained from meals.json): {len(valid_meals)}")
    print(f"Old meals kept from export: {added_from_export}")
    
    print("\n--- SAMPLE MATCHED PAIRS (Up to 20) ---")
    for old, new in matched_pairs:
        print(f"[{old}] REPLACED BY [{new}]")
        
    with open("corrected_merged_meals.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)
    print("\nSaved corrected_merged_meals.json")

if __name__ == "__main__":
    main()
