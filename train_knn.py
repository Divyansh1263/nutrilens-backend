# train_knn.py
import firebase_admin
from firebase_admin import credentials, firestore
from ai.smart_swap_knn import SmartSwapKNN
import os

print("🔥 Training SmartSwap KNN Model 🔥")

# ---------------------------------
# Firebase Init (LOCAL SAFE)
# ---------------------------------
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------------------------
# Fetch ALL meals from Firestore
# ---------------------------------
meals = []
docs = db.collection("meals").stream()

for d in docs:
    meal = d.to_dict()

    # Safety check: must have numeric features
    if all(k in meal for k in ["calories", "protein", "carbs", "fat", "mealName"]):
        meals.append(meal)

print(f"✅ Loaded {len(meals)} meals from Firestore")

if len(meals) < 10:
    raise Exception("❌ Not enough meals to train KNN")

# ---------------------------------
# Train KNN Model
# ---------------------------------
model = SmartSwapKNN()
model.fit(meals)

# ---------------------------------
# Save Model
# ---------------------------------
os.makedirs("models", exist_ok=True)
model.save("models/knn_meal_swap.joblib")

print("✅ KNN model retrained and saved successfully")
