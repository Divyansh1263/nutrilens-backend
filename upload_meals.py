import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Load meals JSON
with open("meal.json", "r", encoding="utf-8") as file:
    meals = json.load(file)

print(f"Uploading {len(meals)} meals safely...")

uploaded = 0
skipped = 0

for meal in meals:
    meal_name = meal.get("mealName")

    if not meal_name:
        continue

    # 🔒 Duplicate check
    existing = db.collection("meals") \
        .where("mealName", "==", meal_name) \
        .limit(1) \
        .stream()

    if any(existing):
        print(f"⏭️ Skipping duplicate: {meal_name}")
        skipped += 1
        continue

    db.collection("meals").add(meal)
    print(f"✅ Uploaded: {meal_name}")
    uploaded += 1

print("================================")
print(f"✅ Uploaded: {uploaded}")
print(f"⏭️ Skipped (duplicates): {skipped}")
print("🎉 Upload complete")
