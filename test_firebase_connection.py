"""Quick test: Firebase connection + model loading"""
import firebase_admin
from firebase_admin import credentials, firestore

print("[1/4] Connecting to Firebase...")
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
print("  ✅ Firebase connected!")

print("[2/4] Testing Firestore read (3 meals)...")
docs = list(db.collection("meals").limit(3).stream())
print(f"  ✅ Found {len(docs)} meals")
for d in docs:
    m = d.to_dict()
    print(f"    - {m.get('mealName', 'unknown')} ({m.get('calories', 0)} cal)")

print("[3/4] Loading ML models...")
import joblib
nlp = joblib.load("models/nlp_meal_classifier.joblib")
cat = joblib.load("models/food_category_classifier.joblib")
knn = joblib.load("models/knn_meal_swap.joblib")
print("  ✅ All 3 models loaded!")

print("[4/4] Quick model prediction test...")
pred = cat.predict(["roti"])[0]
print(f"  ✅ Category of 'roti': {pred}")

print("\n🎉 All checks passed! Backend is ready.")
