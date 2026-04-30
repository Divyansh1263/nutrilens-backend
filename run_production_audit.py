import os
import sys
import json
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Setup environment to skip actual flask run but load the app
os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = "serviceAccountKey.json"

try:
    from app import app
    from meals_cache import MEALS_CACHE, MEALS_SOURCE, load_meals_cache
    from ai.smart_swap_knn import SmartSwapKNN
    from ai.nlp_pipeline import nlp_pipeline
    import joblib
except Exception as e:
    print(f"Error importing app: {e}")
    traceback.print_exc()

def run_audit():
    report = {
        "data_source": "Issues",
        "meal_planner": "Issues",
        "knn_model": "Issues",
        "nlp_pipeline": "Issues",
        "random_forest": "Issues",
        "calorie_accuracy": "Issues",
        "protein_accuracy": "Issues",
        "fallback_system": "Issues",
        "backend_integration": "Issues",
        "frontend_integration": "Issues",
        "performance": "Issues",
        "retraining_status": {
            "knn": False,
            "nlp": False,
            "random_forest": False
        },
        "issues_found": [],
        "critical_issues": [],
        "recommendations": []
    }

    print("Starting production audit...")

    # STEP 0: Data Source Validation
    print("Step 0: Validating Data Source...")
    if len(MEALS_CACHE) > 1500 and MEALS_SOURCE == "firestore":
        report["data_source"] = "OK"
    else:
        issue = f"Data source is {MEALS_SOURCE} with {len(MEALS_CACHE)} items. Expected >1500 from firestore."
        report["critical_issues"].append(issue)

    # STEP 5 & 3 & 4: Model Retraining
    print("Step 5: Validating Model Retraining...")
    try:
        knn = SmartSwapKNN()
        knn.load("models/knn_meal_swap.joblib")
        if knn.meals is not None and len(knn.meals) > 1500:
            report["retraining_status"]["knn"] = True
            report["knn_model"] = "OK"
        else:
            report["issues_found"].append(f"KNN dataset size is {len(knn.meals) if knn.meals is not None else 0}")
    except Exception as e:
        report["critical_issues"].append(f"KNN load error: {e}")

    try:
        if os.path.exists("models/tfidf_meal_matcher.joblib"):
            report["retraining_status"]["nlp"] = True
            report["nlp_pipeline"] = "OK"
        else:
            report["critical_issues"].append("NLP TFIDF models missing.")
    except Exception as e:
        report["issues_found"].append(f"NLP error: {e}")

    try:
        import joblib
        rf_model_path = "ml/daily_rater.joblib"
        if os.path.exists(rf_model_path):
            rf_model = joblib.load(rf_model_path)
            report["retraining_status"]["random_forest"] = True
            report["random_forest"] = "OK"
        else:
            report["issues_found"].append("RF model not found.")
    except Exception as e:
        report["issues_found"].append(f"RF error: {e}")

    # STEP 6: Backend Integration Check
    print("Step 6: Backend Integration...")
    try:
        from services.meal_generator_service import meal_generator_service
        # Check imports indirectly by inspecting the module
        import ast
        with open("services/meal_generator_service.py", "r") as f:
            code = f.read()
        if "meal_repo" in code and "from repositories.meal_repository import meal_repo" not in code and "import meal_repo" not in code:
            report["critical_issues"].append("meal_repo is used but not imported in meal_generator_service.py")
        else:
            report["backend_integration"] = "OK"
    except Exception as e:
        report["critical_issues"].append(f"Backend integration error: {e}")

    # STEP 1, 2, 8, 9, 10, 11
    print("Steps 1-2, 8-11: Running integration tests...")
    try:
        import time
        start_time = time.time()
        with app.test_client() as client:
            res = client.post("/generate-meal-plan", json={
                "userId": "test_audit_user",
                "date": "2026-05-01"
            })
            duration = time.time() - start_time
            if duration > 2.0:
                report["issues_found"].append(f"Performance issue: API took {duration:.2f}s (target < 2s)")
            else:
                report["performance"] = "OK"

            if res.status_code != 200:
                report["critical_issues"].append(f"Generate plan failed: {res.status_code} {res.text}")
            else:
                data = res.json
                if data and "breakfast" in data:
                    report["frontend_integration"] = "OK"
                    report["meal_planner"] = "OK"
                    
                    actual_cal = data.get("total_calories") or data.get("actual_calories") or sum(item.get("calories", 0) for slot in ["breakfast", "lunch", "snack", "dinner"] for item in data.get(slot, []))
                    target_cal = data.get("target_calories", 2000)
                    if target_cal > 0:
                        cal_diff = abs(actual_cal - target_cal) / target_cal
                        if cal_diff <= 0.05:
                            report["calorie_accuracy"] = "OK"
                        else:
                            report["issues_found"].append(f"Calorie accuracy failed: diff is {cal_diff}")

                    target_prot = data.get("target_macros", {}).get("protein", 0)
                    actual_prot = data.get("actual_protein") or sum(item.get("protein", 0) for slot in ["breakfast", "lunch", "snack", "dinner"] for item in data.get(slot, []))
                    if target_prot > 0:
                        prot_diff = abs(actual_prot - target_prot) / target_prot
                        if prot_diff <= 0.10:
                            report["protein_accuracy"] = "OK"
                        else:
                            report["issues_found"].append(f"Protein accuracy failed: diff is {prot_diff}")
                    else:
                        report["protein_accuracy"] = "OK"
                        
    except Exception as e:
        report["critical_issues"].append(f"Integration tests error: {e}")

    # Test Fallback endpoint functionality
    try:
        with app.test_client() as client:
            res = client.post("/generate-meal-plan", json={
                "userId": "test_audit_user",
                "date": "2026-05-01",
                "is_vegan": True,
                "user_target_calories": 1200
            })
            if res.status_code == 200:
                report["fallback_system"] = "OK"
    except Exception as e:
        pass

    print("\n\nFINAL REPORT:")
    print(json.dumps(report, indent=4))
    
    with open("production_audit_report.json", "w") as f:
        json.dump(report, f, indent=4)

if __name__ == "__main__":
    run_audit()
