import json
import os
import sys
import time
import firebase_admin
from firebase_admin import credentials, firestore

# Configure stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ai.smart_swap_knn import SmartSwapKNN
from ai.nlp_pipeline import PIPELINE_CACHE, init_pipeline, process_meal_text
from meals_cache import MEALS_CACHE, _load_from_firestore, load_meals_cache, MEALS_SOURCE

# Initialize Firebase
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()

print("Initializing Firebase...")
db = init_firebase()

# Load all from Firestore meals_v3
print("Loading meals from Firestore...")
meals = _load_from_firestore()

print(f"Total meals loaded: {len(meals)}")
if len(meals) < 1500:
    print(f"WARNING: Expected > 1500 meals, got {len(meals)}!")

# Clear cache and set to Firestore
import dev_store
dev_store.set_meals_cache(meals)
import meals_cache
meals_cache.MEALS_CACHE = meals
meals_cache.MEALS_SOURCE = "firestore"

PIPELINE_CACHE["meals"] = meals
PIPELINE_CACHE["db"] = db

# RETRAIN MODELS
print("Retraining NLP Pipeline (TF-IDF)...")
# Delete old TF-IDF cache to force rebuild
tfidf_cache_path = "models/tfidf_meal_matcher.joblib"
if os.path.exists(tfidf_cache_path):
    os.remove(tfidf_cache_path)

init_pipeline(meals, db=db)

print("Retraining KNN Model...")
knn = SmartSwapKNN()
knn.fit(meals)
os.makedirs("models", exist_ok=True)
knn.save("models/knn_meal_swap.joblib")

# TEST QUERIES
test_queries = ["apple", "tea", "paneer butter masala"]
print("\n--- Testing queries with updated models ---")
for q in test_queries:
    res = process_meal_text(q, "test_user", "2026-04-30", db)
    items = res.get("items", [])
    if items:
        print(f"Query: '{q}' -> Matched: {items[0]['meal']} (Confidence: {items[0]['confidence']})")
    else:
        print(f"Query: '{q}' -> NO MATCH")

print("\n")
print(json.dumps({
    "meals_loaded": len(meals),
    "source": "Firestore",
    "nlp_updated": True,
    "knn_updated": True
}))
