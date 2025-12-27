import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase ONLY if not already initialized
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# Load new meals
with open("meals_100.json", "r", encoding="utf-8") as f:
    meals = json.load(f)

print(f"Uploading {len(meals)} new meals...")

for meal in meals:
    db.collection("meals").add(meal)

print("✅ New meals uploaded successfully")
