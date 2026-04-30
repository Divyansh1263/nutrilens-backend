import json
import firebase_admin
from firebase_admin import credentials, firestore

def normalize(name):
    if not name:
        return ""
    return name.strip().lower()

def main():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Fetching meals_v3...")
    meals_ref = db.collection("meals_v3").stream()
    meals_db = []
    for m in meals_ref:
        meals_db.append(m.to_dict())

    print("Fetching meal_plans_v1...")
    plans_ref = db.collection("meal_plans_v1").stream()
    plans = []
    for p in plans_ref:
        plans.append(p.to_dict())

    print("Extracting meal names from plans...")
    used_meals = set()
    for plan in plans:
        meals_obj = plan.get("meals", {})
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = meals_obj.get(slot, [])
            for item in items:
                name = item.get("mealName")
                if name:
                    used_meals.add(name)

    # Exact match dictionary
    exact_match_db = {normalize(m.get("mealName")): m for m in meals_db if m.get("mealName")}
    
    # Keyword overlap mapping
    db_keywords = []
    for m in meals_db:
        keywords = m.get("searchKeywords", [])
        if not isinstance(keywords, list):
            keywords = [keywords]
        kw_set = set(normalize(str(k)) for k in keywords if str(k).strip())
        name_norm = normalize(m.get("mealName"))
        if name_norm:
            kw_set.add(name_norm)
            
        # also add tokenized words
        tokens = set(name_norm.split())
        for kw in list(kw_set):
            tokens.update(kw.split())
        
        db_keywords.append((m.get("mealName"), kw_set, tokens))

    missing_meals = set()
    
    for meal_name in used_meals:
        norm_name = normalize(meal_name)
        if norm_name in exact_match_db:
            continue
        
        # Fallback keyword overlap
        query_tokens = set(norm_name.split())
        matched = False
        for db_name, kw_set, tokens in db_keywords:
            if norm_name in kw_set:
                matched = True
                break
            
            # Check overlap of words (if all query tokens are in the meal's token set)
            if len(query_tokens) > 0 and query_tokens.issubset(tokens):
                matched = True
                break
                
        if not matched:
            missing_meals.add(meal_name)

    result = {
        "totalMealsUsed": len(used_meals),
        "missingMeals": sorted(list(missing_meals)),
        "missingCount": len(missing_meals)
    }

    print("=== RESULT ===")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
