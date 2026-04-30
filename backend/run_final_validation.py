import os
import sys
import json
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = "serviceAccountKey.json"

try:
    from app import app
    from meals_cache import MEALS_CACHE, MEALS_SOURCE, load_meals_cache
    from services.meal_generator_service import meal_generator_service
    from repositories.user_repository import user_repo
    from ai.nlp_pipeline import process_meal_text
    from repositories.meal_repository import meal_repo
except Exception as e:
    print(f"Error importing app: {e}")
    traceback.print_exc()

def mock_get_user_profile(user_id):
    profiles = {
        "user1": {
            "gender": "female",
            "age": 25,
            "weight": 70,
            "height": 160,
            "activity_level": "light",
            "goal": "lose_weight",
            "is_vegetarian": True,
            "is_vegan": False
        },
        "user2": {
            "gender": "male",
            "age": 30,
            "weight": 75,
            "height": 170,
            "activity_level": "moderate",
            "goal": "maintain_weight",
            "is_vegetarian": True,
            "is_vegan": True
        },
        "user3": {
            "gender": "male",
            "age": 28,
            "weight": 80,
            "height": 175,
            "activity_level": "active",
            "goal": "muscle_gain",
            "is_vegetarian": False,
            "is_vegan": False
        }
    }
    return profiles.get(user_id)


def run_validation():
    # Override user repo for testing
    user_repo.get_user_profile = mock_get_user_profile

    all_meals = meal_repo.get_all_meals()
    
    # --- PART 1: Meal Generator Test ---
    generator_results = []
    users = ["user1", "user2", "user3"]
    generator_status = "OK"
    calorie_acc_status = "OK"
    protein_acc_status = "OK"

    for u_id in users:
        try:
            profile = user_repo.get_user_profile(u_id)
            user_type = f"{'Vegan ' if profile['is_vegan'] else 'Vegetarian ' if profile['is_vegetarian'] else ''}{profile['goal']}"
            
            # Using the app client to hit the endpoint so we get the full response exactly as the frontend sees it
            with app.test_client() as client:
                # First, ensure the profile target calories are calculated inside the generator by mimicking the endpoint
                res = client.post("/generate-meal-plan", json={
                    "userId": u_id,
                    "date": "2026-05-01",
                    "gender": profile["gender"],
                    "age": profile["age"],
                    "weight": profile["weight"],
                    "height": profile["height"],
                    "activity_level": profile["activity_level"],
                    "goal": profile["goal"],
                    "is_vegetarian": profile["is_vegetarian"],
                    "is_vegan": profile["is_vegan"]
                })
                
                data = res.json
                if not data or res.status_code != 200:
                    generator_results.append({
                        "user_type": user_type,
                        "error": "Failed to generate plan"
                    })
                    generator_status = "Issues"
                    continue

                target_cal = data.get("target_calories", 0)
                target_prot = data.get("target_macros", {}).get("protein", 0)
                
                final_cal = sum(item.get("calories", 0) for slot in ["breakfast", "lunch", "snack", "dinner"] for item in data.get(slot, []))
                final_prot = sum(item.get("protein", 0) for slot in ["breakfast", "lunch", "snack", "dinner"] for item in data.get(slot, []))

                cal_diff = abs(final_cal - target_cal) / target_cal if target_cal > 0 else 0
                prot_diff = abs(final_prot - target_prot) / target_prot if target_prot > 0 else 0
                
                if cal_diff > 0.05: calorie_acc_status = "Issues"
                if prot_diff > 0.10: protein_acc_status = "Issues"

                # Check diet rules
                diet_safe = True
                issues = []
                for slot in ["breakfast", "lunch", "snack", "dinner"]:
                    for item in data.get(slot, []):
                        meal_name = item.get("mealName", "").lower()
                        full_meal = next((m for m in all_meals if m.get("mealName", "").lower() == meal_name), None)
                        if full_meal:
                            if profile["is_vegan"] and not full_meal.get("is_vegan"):
                                diet_safe = False
                                issues.append(f"Vegan violation: {meal_name}")
                            elif profile["is_vegetarian"] and not (full_meal.get("is_vegetarian") or full_meal.get("is_vegan")):
                                diet_safe = False
                                issues.append(f"Vegetarian violation: {meal_name}")

                generator_results.append({
                    "user_type": user_type,
                    "targetCalories": target_cal,
                    "finalCalories": final_cal,
                    "calorie_diff_percent": round(cal_diff * 100, 2),
                    "targetProtein": target_prot,
                    "finalProtein": final_prot,
                    "protein_diff_percent": round(prot_diff * 100, 2),
                    "diet_safe": diet_safe,
                    "issues": issues
                })

        except Exception as e:
            generator_results.append({
                "user_type": u_id,
                "error": str(e)
            })
            generator_status = "Issues"

    # --- PART 2: NLP Pipeline Test ---
    queries = [
        "apple",
        "tea",
        "black coffee",
        "2 roti dal",
        "paneer butter masala",
        "milk oats",
        "panner butter masla",
        "2 roti aur dal",
        "chicken curry with rice",
        "1 glass milk and oats"
    ]
    
    nlp_results_list = []
    nlp_status = "OK"
    low_conf = []
    wrong_matches = []
    correct_count = 0

    for query in queries:
        try:
            res = process_meal_text(query, "test_user", "2026-05-01", db=None)
            # NLP pipeline returns: dict with status, items (list of dicts), global_score
            items = res.get("items", [])
            
            detected = []
            quants = []
            conf_scores = []
            
            # Simple heuristic for expected words
            q_lower = query.lower()
            is_correct = True
            
            for item in items:
                detected.append(item.get("meal"))
                quants.append(item.get("quantity"))
                conf = item.get("confidence", 0)
                conf_scores.append(conf)
                
                if conf < 0.6:
                    is_correct = False
                
            # Check for completely bizarre mappings OUTSIDE the loop
            if "roti" in q_lower and not any("roti" in d.lower() or "chapati" in d.lower() for d in detected):
                is_correct = False
            if "chicken" in q_lower and not any("chicken" in d.lower() for d in detected):
                is_correct = False

            if not items:
                is_correct = False
                
            if is_correct:
                correct_count += 1
            else:
                wrong_matches.append(query)
                
            if any(c < 0.6 for c in conf_scores) or not items:
                low_conf.append(query)

            avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0

            nlp_results_list.append({
                "query": query,
                "meals_detected": detected,
                "quantities": quants,
                "confidence": round(avg_conf, 2),
                "correct": is_correct
            })

        except Exception as e:
            nlp_results_list.append({
                "query": query,
                "error": str(e),
                "correct": False
            })
            nlp_status = "Issues"

    nlp_acc = (correct_count / len(queries)) * 100

    if nlp_acc < 80:
        nlp_status = "Issues"
        
    overall = "READY" if (generator_status == "OK" and nlp_status == "OK" and calorie_acc_status == "OK") else "NEEDS FIX"

    final_report = {
        "meal_generator_results": generator_results,
        "nlp_results": {
            "nlp_test_cases": nlp_results_list,
            "nlp_accuracy": f"{round(nlp_acc, 1)}%",
            "low_confidence_cases": low_conf,
            "wrong_matches": wrong_matches
        },
        "summary": {
            "meal_generator_status": generator_status,
            "nlp_status": nlp_status,
            "calorie_accuracy": calorie_acc_status,
            "protein_accuracy": protein_acc_status,
            "nlp_accuracy": f"{round(nlp_acc, 1)}%",
            "overall_system_status": overall
        }
    }

    print("\n\nFINAL_JSON_OUTPUT_START")
    print(json.dumps(final_report, indent=4))
    print("FINAL_JSON_OUTPUT_END\n")

if __name__ == "__main__":
    run_validation()
