import json
import time
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    
from ai.nlp_pipeline import init_pipeline, process_meal_text

# Load meals
with open('meals.json', 'r', encoding='utf-8') as f:
    meals = json.load(f)

print(f"Loaded {len(meals)} meals.")

# Init pipeline
init_pipeline(meals, db=None)

# Define test cases
test_cases = [
    # Simple
    {"query": "roti", "expected": [{"meal": "Roti", "qty": 1}]},
    {"query": "dal", "expected": [{"meal": "Dal", "qty": 1}]},
    {"query": "rice", "expected": [{"meal": "Rice", "qty": 1}]},
    # Multi-item
    {"query": "2 roti and dal", "expected": [{"meal": "Roti", "qty": 2}, {"meal": "Dal", "qty": 1}]},
    {"query": "paneer with rice", "expected": [{"meal": "Paneer", "qty": 1}, {"meal": "Rice", "qty": 1}]},
    {"query": "1 apple and 2 banana", "expected": [{"meal": "Apple", "qty": 1}, {"meal": "Banana", "qty": 2}]},
    {"query": "2 eggs and toast", "expected": [{"meal": "Egg", "qty": 2}, {"meal": "Toast", "qty": 1}]},
    {"query": "milk and 1 bowl oats", "expected": [{"meal": "Milk", "qty": 1}, {"meal": "Oats", "qty": 1}]},
    # Complex
    {"query": "chicken tikka masala with butter naan", "expected": [{"meal": "Chicken Tikka Masala", "qty": 1}, {"meal": "Butter Naan", "qty": 1}]},
    {"query": "1 glass milk and oats", "expected": [{"meal": "Milk", "qty": 1}, {"meal": "Oats", "qty": 1}]},
    # Hinglish
    {"query": "2 roti aur dal", "expected": [{"meal": "Roti", "qty": 2}, {"meal": "Dal", "qty": 1}]},
    {"query": "paneer sabzi khayi", "expected": [{"meal": "Paneer", "qty": 1}]},
    {"query": "chai pee li", "expected": [{"meal": "Chai", "qty": 1}]},
    # Noisy input / spelling
    {"query": "panner butter masla", "expected": [{"meal": "Paneer Butter Masala", "qty": 1}]},
    {"query": "chiken curry", "expected": [{"meal": "Chicken Curry", "qty": 1}]},
    {"query": "masala dosa with chutny", "expected": [{"meal": "Masala Dosa", "qty": 1}, {"meal": "Chutney", "qty": 1}]},
    # Combo splitting
    {"query": "dal roti", "expected": [{"meal": "Dal", "qty": 1}, {"meal": "Roti", "qty": 1}]},
    {"query": "3 dal roti", "expected": [{"meal": "Dal", "qty": 1}, {"meal": "Roti", "qty": 3}]},
    {"query": "curd rice", "expected": [{"meal": "Curd", "qty": 1}, {"meal": "Rice", "qty": 1}]},
    # More varied
    {"query": "half pizza", "expected": [{"meal": "Pizza", "qty": 0.5}]},
    {"query": "black coffee no sugar", "expected": [{"meal": "Black Coffee", "qty": 1}]},
    {"query": "veg biryani", "expected": [{"meal": "Veg Biryani", "qty": 1}]},
    {"query": "2 idli 1 vada", "expected": [{"meal": "Idli", "qty": 2}, {"meal": "Vada", "qty": 1}]},
    {"query": "aloo paratha 2", "expected": [{"meal": "Aloo Paratha", "qty": 2}]},
    {"query": "gobhi sabzi", "expected": [{"meal": "Gobhi", "qty": 1}]}
]

results = {
    "correct_predictions": 0,
    "total": 0,
    "total_confidence": 0,
    "match_count": 0,
    "low_confidence_cases": [],
    "wrong_matches": [],
    "quantity_errors": [],
    "total_time_ms": 0
}

def matches_expected(actual, expected_list):
    # We will check if the actual meal name CONTAINS the expected meal name substring
    # For example expected "Paneer" should match "Palak Paneer" or "Paneer Butter Masala" if it's the best guess,
    # but let's be more lenient by substring.
    for exp in expected_list:
        if exp["meal"].lower() in actual["meal"].lower() or actual["meal"].lower() in exp["meal"].lower():
            # Check qty
            if abs(actual["quantity"] - exp["qty"]) < 0.1:
                return True, "OK"
            else:
                return False, f"Qty mismatch: got {actual['quantity']}, expected {exp['qty']}"
    return False, f"Meal mismatch: got {actual['meal']}, expected {[e['meal'] for e in expected_list]}"

for case in test_cases:
    query = case["query"]
    start = time.time()
    
    # Run pipeline
    res = process_meal_text(query, user_id="test_user", date="2026-04-30", db=None)
    
    elapsed = (time.time() - start) * 1000
    results["total_time_ms"] += elapsed
    
    items = res.get("items", [])
    
    if not items:
        results["wrong_matches"].append({"query": query, "reason": "No items returned"})
        results["total"] += len(case["expected"])
        continue
    
    for item in items:
        results["match_count"] += 1
        results["total_confidence"] += item["confidence"]
        
        if item["confidence"] < 0.25:
            results["low_confidence_cases"].append({"query": query, "item": item["meal"], "conf": item["confidence"]})
            
    # evaluate
    # mapping actuals to expected
    matched_expected = 0
    for exp in case["expected"]:
        results["total"] += 1
        found = False
        for actual in items:
            match_status, reason = matches_expected(actual, [exp])
            if match_status:
                results["correct_predictions"] += 1
                found = True
                break
            elif "Qty mismatch" in reason:
                results["quantity_errors"].append({"query": query, "item": actual["meal"], "expected_qty": exp["qty"], "actual_qty": actual["quantity"]})
                # if qty mismatch, we still consider it a match for meal identity, but error for qty
                # Let's count it as wrong prediction overall for strictness
                found = True
                break
        if not found:
            results["wrong_matches"].append({"query": query, "expected": exp["meal"], "actual": [i["meal"] for i in items]})

accuracy = (results["correct_predictions"] / results["total"]) * 100 if results["total"] > 0 else 0
avg_conf = (results["total_confidence"] / results["match_count"]) if results["match_count"] > 0 else 0
avg_time = results["total_time_ms"] / len(test_cases)

perf_status = "OK" if avg_time < 200 else "Slow"

print(json.dumps({
    "accuracy": f"{accuracy:.1f}%",
    "avg_confidence": round(avg_conf, 3),
    "low_confidence_cases": results["low_confidence_cases"],
    "wrong_matches": results["wrong_matches"],
    "quantity_errors": results["quantity_errors"],
    "performance": f"{perf_status} ({avg_time:.1f}ms per query)",
    "verdict": "Improved" if accuracy > 85 else "Degraded"
}, indent=2))
