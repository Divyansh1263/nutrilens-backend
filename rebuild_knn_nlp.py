import json
import random
import os
import sys
from pathlib import Path

from ai.smart_swap_knn import SmartSwapKNN

BASE_DIR = Path(__file__).resolve().parent
MEALS_JSON = BASE_DIR / "meals.json"
MODELS_DIR = BASE_DIR / "models"

KNN_MODEL_PATH = MODELS_DIR / "knn_meal_swap.joblib"
TFIDF_CACHE_PATH = MODELS_DIR / "tfidf_meal_matcher.joblib"

# Load meals
with open(MEALS_JSON, "r", encoding="utf-8") as f:
    meals = json.load(f)

print(f"Loaded {len(meals)} meals from {MEALS_JSON.name}")

# Rebuild KNN
print("Rebuilding KNN Model...")
knn = SmartSwapKNN()
knn.fit(meals)

os.makedirs(MODELS_DIR, exist_ok=True)
knn.save(KNN_MODEL_PATH)
print("KNN Model saved to", KNN_MODEL_PATH)

# Rebuild TF-IDF cache since NLP matcher uses vector search
print("Rebuilding TF-IDF cache for NLP vector search...")
# Since build_tfidf_cache is in retrain_models_pipeline.py, we can import it
sys.path.append(str(BASE_DIR))
try:
    from retrain_models_pipeline import build_tfidf_cache
    build_tfidf_cache(meals, TFIDF_CACHE_PATH)
    print("TF-IDF Cache rebuilt and saved.")
except ImportError:
    print("Could not import build_tfidf_cache from retrain_models_pipeline.")

# Verify KNN
print("\n--- Verifying KNN Model ---")
random_meals = random.sample(meals, 5)
for i, test_meal in enumerate(random_meals):
    print(f"\n[{i+1}] Query: {test_meal.get('mealName')} (Cal: {test_meal.get('calories')}, Pro: {test_meal.get('protein')}, Fat: {test_meal.get('fat')}, Carbs: {test_meal.get('carbs')})")
    replacements = knn.find_replacements(test_meal, k=3)
    for j, rep in enumerate(replacements):
        print(f"   -> Match {j+1}: {rep.get('mealName')} (Cal: {rep.get('calories')}, Pro: {rep.get('protein')}, Fat: {rep.get('fat')}, Carbs: {rep.get('carbs')})")

print("\n")
print(json.dumps({
    "knn_rebuilt": True,
    "total_meals_indexed": len(meals)
}))
