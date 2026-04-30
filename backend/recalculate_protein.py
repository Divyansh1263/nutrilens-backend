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
    meals_db = [m.to_dict() for m in meals_ref]

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
            
        tokens = set(name_norm.split())
        for kw in list(kw_set):
            tokens.update(kw.split())
        
        db_keywords.append((m.get("mealName"), kw_set, tokens, m))

    def find_meal(meal_name):
        norm_name = normalize(meal_name)
        if norm_name in exact_match_db:
            return exact_match_db[norm_name]
        
        query_tokens = set(norm_name.split())
        for db_name, kw_set, tokens, m in db_keywords:
            if norm_name in kw_set:
                return m
            if len(query_tokens) > 0 and query_tokens.issubset(tokens):
                return m
        return None

    print("Fetching meal_plans_v1...")
    plans_ref = db.collection("meal_plans_v1").stream()
    plans = []
    plan_docs = {}
    for p in plans_ref:
        plan_dict = p.to_dict()
        plans.append(plan_dict)
        plan_docs[plan_dict["planId"]] = p.reference

    checked = 0
    updated = 0
    plans_updated = []

    print("Recalculating protein...")
    for plan in plans:
        checked += 1
        actual_protein = 0.0
        
        meals_obj = plan.get("meals", {})
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = meals_obj.get(slot, [])
            for item in items:
                meal_name = item.get("mealName")
                qty = item.get("quantity", 1.0)
                
                db_meal = find_meal(meal_name)
                if db_meal:
                    meal_prot = float(db_meal.get("protein", 0))
                    actual_protein += meal_prot * qty
                else:
                    print(f"WARNING: Meal '{meal_name}' not found for plan {plan.get('planId')}")
        
        actual_protein = round(actual_protein, 1)
        target_protein = float(plan.get("targetProtein", 0))
        
        if target_protein > 0:
            diff_percent = abs(actual_protein - target_protein) / target_protein
            
            if diff_percent > 0.10:
                # Update plan
                plan_id = plan["planId"]
                plan_docs[plan_id].update({"targetProtein": actual_protein})
                updated += 1
                plans_updated.append(plan_id)
                print(f"Plan {plan_id} updated: target {target_protein} -> actual {actual_protein} (diff {diff_percent:.2%})")

    result = {
        "checked": checked,
        "updated": updated,
        "plansUpdated": sorted(plans_updated, key=lambda x: int(x.replace("p", "")) if x.startswith("p") and x[1:].isdigit() else 999999)
    }

    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
