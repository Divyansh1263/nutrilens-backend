# train_knn.py
import firebase_admin
from firebase_admin import credentials, firestore
from ai.smart_swap_knn import SmartSwapKNN

# Firebase init
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Fetch meals
meals = []
docs = db.collection("meals").stream()
for d in docs:
    m = d.to_dict()
    meals.append(m)

print(f"Loaded {len(meals)} meals")

# Train model
model = SmartSwapKNN()
model.fit(meals)

# Save model
model.save("models/knn_meal_swap.joblib")
print("✅ k-NN model trained and saved")
