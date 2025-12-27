import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# Load meals JSON
with open("meals_150.json", "r", encoding="utf-8") as file:
    meals = json.load(file)

print(f"Uploading {len(meals)} meals...")

# Upload meals
for meal in meals:
    db.collection("meals").add(meal)

print("✅ All meals uploaded successfully!")
