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
    return s.strip() if isinstance(s, str) else ""

def normalize_name(name):
    name = clean_string(name).lower()
    name = name.translate(str.maketrans('', '', string.punctuation))
    return " ".join(name.split())

def apply_aliases(name):
    words = name.split()
    return " ".join([ALIASES.get(w, w) for w in words])

def has_conflict(old_words_raw, new_words_raw):
    old_full = set(old_words_raw)
    for w in old_words_raw: old_full.add(ALIASES.get(w, w))
    new_full = set(new_words_raw)
    for w in new_words_raw: new_full.add(ALIASES.get(w, w))
        
    for mod in CONFLICTING_MODIFIERS:
        in_old = mod in old_full
        in_new = mod in new_full
        if in_old != in_new:
            return True
    return False

def generate_doc_id(meal_name):
    name = clean_string(meal_name).lower()
    name = re.sub(r'[^a-z0-9\s_]', '', name)
    return re.sub(r'\s+', '_', name)

def get_food_type(meal_name, cat):
    name = meal_name.lower()
    cat = clean_string(cat).lower()
    
    if "chai" in name or "tea" in name or "coffee" in name or "juice" in name or "shake" in name or "beverage" in cat:
        return "beverage"
    if "pizza" in name or "burger" in name or "noodles" in name or "fast food" in cat:
        return "fast_food"
    if "halwa" in name or "kheer" in name or "laddoo" in name or "dessert" in cat or "sweet" in cat:
        return "dessert"
    if "sandwich" in name or "pakora" in name or "chaat" in name or "namkeen" in name or "snack" in cat:
        return "snack"
    if "paneer" in name or "egg" in name or "chicken" in name or "mutton" in name or "soy" in name or "protein" in cat:
        return "protein"
    if "dal" in name or "lentil" in name:
        return "dal"
    if "roti" in name or "rice" in name or "bread" in name or "staple" in cat:
        return "staple"
    if "sabzi" in name or "vegetable" in name or "curry" in name:
        return "sabzi"
    return "food"

def is_merge_allowed(type1, type2):
    if type1 == type2: return True
    pair = {type1, type2}
    
    if "beverage" in pair and len(pair) == 2: return False
    
    full_meals = {"staple", "dal", "sabzi", "protein", "food"}
    if "snack" in pair and len(pair.intersection(full_meals)) > 0: return False
        
    if {"dal", "sabzi"}.issubset(pair): return False
    if {"staple", "sabzi"}.issubset(pair): return False
    if {"staple", "protein"}.issubset(pair): return False
        
    return True

def is_composite(meal_name):
    words = meal_name.lower().split()
    return any(ind in words for ind in ["with", "and", "&", "+", "combo", "thali"])

def main():
    print("Loading datasets for refinement pass...")
    try:
        with open("final_production_meals.json", "r", encoding="utf-8") as f:
            production_meals = json.load(f)
        with open("meals.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                new_meals = data.get("meals", list(data.values()))
            else:
                new_meals = data
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    new_meal_ids = set([generate_doc_id(m["mealName"]) for m in new_meals])
    
    corpus = []
    for m in production_meals:
        norm = apply_aliases(normalize_name(m["mealName"]))
        aliased_kw = [apply_aliases(k) for k in m.get("searchKeywords", [])]
        corpus.append(norm + " " + " ".join(aliased_kw))
        
    vectorizer = TfidfVectorizer().fit(corpus)
    
    # Precompute new meals matrix
    new_docs = []
    for m in new_meals:
        norm = apply_aliases(normalize_name(m["mealName"]))
        kw = [apply_aliases(k) for k in m.get("searchKeywords", [])]
        new_docs.append(norm + " " + " ".join(kw))
    new_vecs_matrix = vectorizer.transform(new_docs)

    final_refined = {}
    newly_allowed = []
    still_blocked = []

    # Filter the production meals - we only reconsider items NOT from the new dataset
    for m in production_meals:
        doc_id = generate_doc_id(m["mealName"])
        
        if doc_id in new_meal_ids:
            final_refined[doc_id] = m
            continue
            
        old_name = m["mealName"]
        old_cat_raw = m.get("category", "")
        old_norm = normalize_name(old_name)
        old_alias = apply_aliases(old_norm)
        old_words_raw = old_norm.split()
        
        old_kw = set(m.get("searchKeywords", []))
        aliased_old_kw = set([apply_aliases(k) for k in old_kw])
        
        old_doc = old_alias + " " + " ".join(aliased_old_kw)
        old_vec = vectorizer.transform([old_doc])
        sims_array = cosine_similarity(old_vec, new_vecs_matrix)[0]
        
        match_found = False
        
        for idx, new_m in enumerate(new_meals):
            new_id = generate_doc_id(new_m["mealName"])
            new_name = new_m["mealName"]
            new_cat_raw = new_m.get("category", "")
            new_norm = normalize_name(new_name)
            new_words_raw = new_norm.split()
            
            new_kw = set(new_m.get("searchKeywords", []))
            aliased_new_kw = set([apply_aliases(k) for k in new_kw])
            
            intersection = aliased_old_kw.intersection(aliased_new_kw)
            union = aliased_old_kw.union(aliased_new_kw)
            
            if len(union) == 0: continue
            
            jaccard = len(intersection) / len(union)
            tfidf_sim = sims_array[idx]
            
            option_a = (tfidf_sim >= 0.70 and jaccard >= 0.40)
            option_b = (len(intersection) >= 2 and tfidf_sim >= 0.65)
            
            if option_a or option_b:
                if has_conflict(old_words_raw, new_words_raw):
                    continue
                    
                old_comp = is_composite(old_name)
                new_comp = is_composite(new_name)
                if old_comp != new_comp:
                    still_blocked.append((old_name, new_name, "Composition Mismatch"))
                    continue

                old_type = get_food_type(old_name, old_cat_raw)
                new_type = get_food_type(new_name, new_cat_raw)
                
                if is_merge_allowed(old_type, new_type):
                    match_found = True
                    newly_allowed.append((old_name, new_name, f"{old_type} merged with {new_type}"))
                    break
                else:
                    still_blocked.append((old_name, new_name, f"Category Block: {old_type} vs {new_type}"))
                    
        if not match_found:
            final_refined[doc_id] = m

    final_list = list(final_refined.values())
    
    print("\n--- REFINEMENT PASS RESULTS ---")
    print(f"Total meals before: {len(production_meals)}")
    print(f"Total meals after: {len(final_list)}")
    print(f"Newly allowed merges: {len(newly_allowed)}")
    print(f"Still blocked matches: {len(still_blocked)}")
    
    print("\n--- NEWLY ALLOWED MERGES ---")
    for b in newly_allowed[:30]:
        print(f"[ALLOWED] {b[0]} -> {b[1]} | Reason: {b[2]}")
        
    print("\n--- STILL BLOCKED (Sample) ---")
    for b in still_blocked[:20]:
        print(f"[BLOCKED] {b[0]} -> {b[1]} | Reason: {b[2]}")
        
    with open("final_refined_meals.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)
    print("\nSaved final_refined_meals.json")

if __name__ == "__main__":
    main()
