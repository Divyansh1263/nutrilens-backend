import json
import re
import math
import string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ALIASES = {
    "dahi": "curd",
    "chawal": "rice",
    "bhindi": "okra",
    "paneer": "cottage cheese",
    "aloo": "potato",
    "mutter": "peas",
    "gobi": "cauliflower",
    "palak": "spinach",
    "baingan": "eggplant",
    "pyaaz": "onion",
    "tamatar": "tomato",
    "murgh": "chicken",
    "gosht": "mutton",
    "machli": "fish",
    "dal": "lentil",
    "sabzi": "vegetable",
    "veg": "vegetable",
    "roti": "flatbread",
    "chapati": "flatbread",
    "phulka": "flatbread",
    "anda": "egg",
    "jeera": "cumin",
    "mirch": "chilli",
    "adrak": "ginger",
    "lahsun": "garlic"
}

CONFLICTING_MODIFIERS_RAW = [
    "fried", "plain", "curry", "dry", "grilled", "roasted", "baked", "steamed", "boiled", "raw",
    "butter", "masala", "spicy", "sweet", "sour", "tadka", "makhani", "jeera", "garlic", "cheese",
    "roti", "rice", "dal", "sabzi", "chicken", "mutton", "paneer", "fish", "egg", "beef", "pork",
    "pulao", "biryani", "burger", "pizza", "sandwich", "wrap", "salad", "soup", "shake", "smoothie",
    "veg", "vegetable", "aloo", "potato", "gobi", "cauliflower", "palak", "spinach", "mutter", "peas",
    "bhindi", "okra", "baingan", "eggplant", "pyaaz", "onion", "tamatar", "tomato", "chana", "chickpea",
    "tandoori", "wheat", "ragi", "jowar", "bajra", "sooji", "besan", "atta", "maida", "oats", "samak", 
    "moong", "toor", "arhar", "urad", "masoor", "chana"
]

CONFLICTING_MODIFIERS = set()
for mod in CONFLICTING_MODIFIERS_RAW:
    CONFLICTING_MODIFIERS.add(mod)
    CONFLICTING_MODIFIERS.add(ALIASES.get(mod, mod))

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

def normalize_name(name):
    name = clean_string(name).lower()
    name = name.translate(str.maketrans('', '', string.punctuation))
    name = " ".join(name.split())
    return name

def apply_aliases(name):
    words = name.split()
    return " ".join([ALIASES.get(w, w) for w in words])

def has_conflict(old_words_raw, new_words_raw):
    old_full = set(old_words_raw)
    for w in old_words_raw:
        old_full.add(ALIASES.get(w, w))
        
    new_full = set(new_words_raw)
    for w in new_words_raw:
        new_full.add(ALIASES.get(w, w))
        
    for mod in CONFLICTING_MODIFIERS:
        in_old = mod in old_full
        in_new = mod in new_full
        if in_old != in_new:
            return True
    return False

def clean_keywords(raw_keywords, meal_name):
    if not isinstance(raw_keywords, list):
        if isinstance(raw_keywords, str):
            raw_keywords = raw_keywords.split()
        else:
            raw_keywords = []
            
    kws = [clean_string(k).lower() for k in raw_keywords if clean_string(k)]
    kws = [k for k in kws if not re.search(r'_k\d+', k)]
    kws = [k for k in kws if k not in ["meal", "food", "dish", "recipe"]]
    
    unique_kws = []
    for k in kws:
        if k not in unique_kws:
            unique_kws.append(k)
            
    if len(unique_kws) < 3:
        name_parts = normalize_name(meal_name).split()
        for w in name_parts:
            if w not in unique_kws:
                unique_kws.append(w)
                
    return unique_kws

def get_category(meal_name, original_category):
    name = meal_name.lower()
    cat = clean_string(original_category).lower()
    
    if "drink" in cat or "beverage" in cat or "shake" in name or "tea" in name or "coffee" in name or "chai" in name or "lassi" in name or "juice" in name:
        return "beverage"
    if "dessert" in cat or "sweet" in cat or "halwa" in name or "barfi" in name or "jalebi" in name or "kheer" in name:
        return "dessert"
    if "snack" in cat or "biscuit" in name or "pakora" in name or "samosa" in name or "chaat" in name:
        return "snack"
    if "dal" in name or "lentil" in name:
        return "dal"
    if "paneer" in name or "chicken" in name or "egg" in name or "mutton" in name or "fish" in name or "anda" in name:
        return "protein"
    if "sabzi" in name or "vegetable" in name or "aloo" in name or "gobi" in name or "palak" in name or "curry" in name:
        return "sabzi"
    if "burger" in name or "pizza" in name or "roll" in name or "fast food" in cat:
        return "fast_food"
    if "roti" in name or "rice" in name or "bread" in name or "dosa" in name or "idli" in name or "naan" in name or "paratha" in name or "chawal" in name:
        return "staple"
    
    return "other"

def is_composite(meal_name):
    name = meal_name.lower()
    words = name.split()
    composite_indicators = ["with", "and", "&", "+", "combo", "thali"]
    for ind in composite_indicators:
        if ind in words:
            return True
    return False

def normalize_meal(meal):
    normalized = {}
    normalized["mealName"] = clean_string(meal.get("mealName", "Unknown Meal"))
    normalized["calories"] = clean_number(meal.get("calories", 0))
    normalized["protein"] = clean_number(meal.get("protein", 0))
    normalized["carbs"] = clean_number(meal.get("carbs", 0))
    normalized["fat"] = clean_number(meal.get("fat", 0))
    normalized["category"] = clean_string(meal.get("category", "Main Course"))
    
    normalized["searchKeywords"] = clean_keywords(meal.get("searchKeywords", []), normalized["mealName"])
    
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
    
    corpus = []
    for m in valid_export + valid_meals:
        norm = apply_aliases(normalize_name(m["mealName"]))
        aliased_kw = [apply_aliases(k) for k in m["searchKeywords"]]
        doc = norm + " " + " ".join(aliased_kw)
        corpus.append(doc)
        
    vectorizer = TfidfVectorizer()
    vectorizer.fit(corpus)
    
    merged_meals_dict = {}
    matched_pairs = []
    
    replacements_count = 0
    alias_matches_count = 0
    semantic_matches_count = 0
    
    category_rejections = 0
    composition_rejections = 0
    bad_merges_prevented = []
    
    new_vecs_dict = {}
    new_ids_list = []
    new_docs_list = []
    
    for m in valid_meals:
        doc_id = generate_doc_id(m["mealName"])
        merged_meals_dict[doc_id] = m
        new_norm = normalize_name(m["mealName"])
        new_alias = apply_aliases(new_norm)
        new_kw = set(m["searchKeywords"])
        aliased_new_kw = [apply_aliases(k) for k in new_kw]
        new_doc = new_alias + " " + " ".join(aliased_new_kw)
        
        new_ids_list.append(doc_id)
        new_docs_list.append(new_doc)
        
    new_vecs_matrix = vectorizer.transform(new_docs_list)
            
    for old_m in valid_export:
        old_name = old_m["mealName"]
        old_cat_in = old_m["category"]
        old_norm = normalize_name(old_name)
        old_alias = apply_aliases(old_norm)
        old_words_raw = old_norm.split()
        
        old_kw = set(old_m["searchKeywords"])
        aliased_old_kw = set([apply_aliases(k) for k in old_kw])
        
        old_doc = old_alias + " " + " ".join(aliased_old_kw)
        old_vec = vectorizer.transform([old_doc])
        sims_array = cosine_similarity(old_vec, new_vecs_matrix)[0]
        
        match_found = False
        matched_with = None
        match_type = ""
        
        for idx, new_m in enumerate(valid_meals):
            new_id = generate_doc_id(new_m["mealName"])
            new_name = new_m["mealName"]
            new_cat_in = new_m["category"]
            new_norm = normalize_name(new_name)
            new_alias = apply_aliases(new_norm)
            new_words_raw = new_norm.split()
            
            # TIER 1: Exact Match
            if old_norm == new_norm:
                match_found = True
                matched_with = new_name
                match_type = "EXACT"
                break
                
            # For Alias and Semantic, apply Category & Composition guard
            old_cat = get_category(old_name, old_cat_in)
            new_cat = get_category(new_name, new_cat_in)
            
            old_comp = is_composite(old_name)
            new_comp = is_composite(new_name)
            
            # TIER 3: Alias Match (names match after aliasing)
            if old_alias == new_alias:
                if old_cat != new_cat:
                    category_rejections += 1
                    if len(bad_merges_prevented) < 15:
                        bad_merges_prevented.append((old_name, new_name, f"Category Mismatch: {old_cat} vs {new_cat}"))
                    continue
                if old_comp != new_comp:
                    composition_rejections += 1
                    if len(bad_merges_prevented) < 15:
                        bad_merges_prevented.append((old_name, new_name, f"Composition Mismatch: {'Composite' if old_comp else 'Single'} vs {'Composite' if new_comp else 'Single'}"))
                    continue
                    
                match_found = True
                matched_with = new_name
                match_type = "ALIAS"
                alias_matches_count += 1
                break
                
            # TIER 2: Relaxed Semantic Match
            new_kw = set(new_m["searchKeywords"])
            aliased_new_kw = set([apply_aliases(k) for k in new_kw])
            
            intersection = aliased_old_kw.intersection(aliased_new_kw)
            union = aliased_old_kw.union(aliased_new_kw)
            
            if len(union) > 0:
                jaccard = len(intersection) / len(union)
                tfidf_sim = sims_array[idx]
                
                option_a = (tfidf_sim >= 0.70 and jaccard >= 0.40)
                option_b = (len(intersection) >= 2 and tfidf_sim >= 0.65)
                
                if option_a or option_b:
                    if old_cat != new_cat:
                        category_rejections += 1
                        if len(bad_merges_prevented) < 15:
                            bad_merges_prevented.append((old_name, new_name, f"Category Mismatch: {old_cat} vs {new_cat}"))
                        continue
                        
                    if old_comp != new_comp:
                        composition_rejections += 1
                        if len(bad_merges_prevented) < 15:
                            bad_merges_prevented.append((old_name, new_name, f"Composition Mismatch: {'Composite' if old_comp else 'Single'} vs {'Composite' if new_comp else 'Single'}"))
                        continue
                        
                    if not has_conflict(old_words_raw, new_words_raw):
                        match_found = True
                        matched_with = new_name
                        match_type = f"SEMANTIC (TFIDF={tfidf_sim:.2f}, Jac={jaccard:.2f})"
                        semantic_matches_count += 1
                        break
        
        if match_found:
            replacements_count += 1
            if len(matched_pairs) < 50:
                matched_pairs.append((old_name, matched_with, match_type))
        else:
            old_id = generate_doc_id(old_name)
            if old_id not in merged_meals_dict:
                merged_meals_dict[old_id] = old_m

    final_list = list(merged_meals_dict.values())
    
    print("\n--- PRODUCTION MERGE RESULTS ---")
    print(f"Total meals before: {len(export_data)}")
    print(f"Total meals after: {len(final_list)}")
    print(f"Replacements count: {replacements_count}")
    print(f"Alias matches count: {alias_matches_count}")
    print(f"Semantic matches count: {semantic_matches_count}")
    
    print(f"\nRejected due to category mismatch: {category_rejections}")
    print(f"Rejected due to composition mismatch: {composition_rejections}")
    
    print("\n--- BAD MERGES PREVENTED (Sample) ---")
    for b in bad_merges_prevented:
        print(f"[PREVENTED] {b[0]} -> {b[1]} | Reason: {b[2]}")
    
    print("\n--- SAMPLE MATCHED PAIRS (Up to 50) ---")
    for old, new, mtype in matched_pairs:
        print(f"[{old}] -> [{new}] ({mtype})")
        
    with open("final_production_meals.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)
    print("\nSaved final_production_meals.json")

if __name__ == "__main__":
    main()
