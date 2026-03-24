import os
from firebase_admin import credentials, firestore
import firebase_admin

# Let's ensure default auth works
if not firebase_admin._apps:
    try:
         cred = credentials.Certificate("d:/NutriLens/backend/firebase-key.json")
         firebase_admin.initialize_app(cred)
    except Exception:
         firebase_admin.initialize_app()
         
db = firestore.client()

from ai.nlp_pipeline import init_pipeline, log_meal_nlp
from ai.hybrid_matcher import get_all_meals

print("Fetching meals...")
meal_docs = db.collection("meals").stream()
MEALS = []
for d in meal_docs:
    m = d.to_dict()
    m["id"] = d.id
    MEALS.append(m)

print(f"Loaded {len(MEALS)} meals")
init_pipeline(MEALS, db=db)

# Run raw text test
print("\n--- Testing Roti and Dal ---")
res, msg = log_meal_nlp("test_user_id", "2026-03-15", "I ate 2 chapatis and dal")
print("Result Items:")
for i in res.get("items", []):
    print(i)
    
print("\n--- Testing Roti Alone ---")
res2, msg2 = log_meal_nlp("test_user_id", "2026-03-15", "roti")
print("Result Items:")
for i in res2.get("items", []):
    print(i)
