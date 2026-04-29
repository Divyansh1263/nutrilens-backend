"""
scripts/fix_meal_calories.py
────────────────────────────
TASK 4 + TASK 5: Normalize meal calorie values in Firestore and
                  delete all stale meal_plans so fresh plans regenerate.

Run once from the backend directory:
    python scripts/fix_meal_calories.py

Requires: serviceAccountKey.json present (or FIREBASE_SERVICE_ACCOUNT_PATH set)
"""

import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ──────────────────────────────────────────────────────────────
def _init():
    if not firebase_admin._apps:
        path = (
            os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
            or "serviceAccountKey.json"
            or "d:/nutrilens/backend/serviceAccountKey.json"
        )
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)
    return firestore.client()


# ── TASK 4: Per-serving calorie overrides ─────────────────────────────────────
# These represent ONE realistic serving. Values sourced from ICMR food tables.
# Only meals explicitly listed here will be touched — the rest are left alone.
CALORIE_CORRECTIONS = {
    # Grains / flatbreads
    "Roti":               {"calories": 120, "protein": 3.5, "carbs": 20.0, "fat": 3.5, "servingSize": "1 piece (40 g)"},
    "Chapati":            {"calories": 120, "protein": 3.5, "carbs": 20.0, "fat": 3.5, "servingSize": "1 piece (40 g)"},
    "Paratha":            {"calories": 200, "protein": 4.0, "carbs": 24.0, "fat": 9.0, "servingSize": "1 piece (60 g)"},
    "Naan":               {"calories": 260, "protein": 7.0, "carbs": 45.0, "fat": 5.0, "servingSize": "1 piece (90 g)"},
    "Puri":               {"calories": 130, "protein": 2.5, "carbs": 17.0, "fat": 6.0, "servingSize": "1 piece (35 g)"},
    "Plain Rice":         {"calories": 200, "protein": 4.0, "carbs": 43.0, "fat": 0.5, "servingSize": "1 cup cooked (150 g)"},
    "Jeera Rice":         {"calories": 220, "protein": 4.0, "carbs": 44.0, "fat": 4.0, "servingSize": "1 cup (150 g)"},
    "Jowar Roti":         {"calories": 110, "protein": 3.0, "carbs": 22.0, "fat": 1.5, "servingSize": "1 piece (40 g)"},
    "Bajra Roti":         {"calories": 115, "protein": 3.5, "carbs": 22.0, "fat": 1.5, "servingSize": "1 piece (40 g)"},
    "Ragi Roti":          {"calories": 108, "protein": 3.5, "carbs": 21.0, "fat": 1.0, "servingSize": "1 piece (40 g)"},
    "Makki Roti":         {"calories": 150, "protein": 3.5, "carbs": 28.0, "fat": 3.0, "servingSize": "1 piece (50 g)"},
    # Dals / lentils
    "Dal Tadka":          {"calories": 180, "protein": 9.0,  "carbs": 22.0, "fat": 6.0, "servingSize": "1 bowl (200 ml)"},
    "Dal Makhani":        {"calories": 230, "protein": 9.0,  "carbs": 23.0, "fat": 12.0,"servingSize": "1 bowl (200 ml)"},
    "Moong Dal":          {"calories": 150, "protein": 9.0,  "carbs": 22.0, "fat": 3.0, "servingSize": "1 bowl (200 ml)"},
    "Masoor Dal":         {"calories": 140, "protein": 9.0,  "carbs": 20.0, "fat": 2.5, "servingSize": "1 bowl (200 ml)"},
    "Toor Dal":           {"calories": 160, "protein": 10.0, "carbs": 22.0, "fat": 3.0, "servingSize": "1 bowl (200 ml)"},
    "Chana Dal":          {"calories": 180, "protein": 10.0, "carbs": 26.0, "fat": 4.0, "servingSize": "1 bowl (200 ml)"},
    # Proteins / curries
    "Paneer Butter Masala": {"calories": 280, "protein": 12.0, "carbs": 15.0, "fat": 20.0, "servingSize": "1 bowl (200 g)"},
    "Paneer Tikka":         {"calories": 250, "protein": 18.0, "carbs": 10.0, "fat": 16.0, "servingSize": "200 g"},
    "Rajma":                {"calories": 200, "protein": 9.0,  "carbs": 28.0, "fat": 5.0,  "servingSize": "1 bowl (200 g)"},
    "Chole":                {"calories": 210, "protein": 9.0,  "carbs": 30.0, "fat": 6.0,  "servingSize": "1 bowl (200 g)"},
    "Chicken Curry":        {"calories": 250, "protein": 22.0, "carbs": 8.0,  "fat": 15.0, "servingSize": "200 g"},
    "Egg Curry":            {"calories": 220, "protein": 14.0, "carbs": 8.0,  "fat": 15.0, "servingSize": "2 eggs + curry"},
    "Boiled Egg":           {"calories": 78,  "protein": 6.3,  "carbs": 0.6,  "fat": 5.3,  "servingSize": "1 egg (50 g)"},
    # Dairy
    "Curd":                 {"calories": 80,  "protein": 4.0,  "carbs": 7.0,  "fat": 3.5,  "servingSize": "100 g"},
    "Yogurt":               {"calories": 80,  "protein": 4.0,  "carbs": 7.0,  "fat": 3.5,  "servingSize": "100 g"},
    "Raita":                {"calories": 70,  "protein": 3.0,  "carbs": 6.0,  "fat": 3.0,  "servingSize": "100 g"},
    "Lassi":                {"calories": 150, "protein": 6.0,  "carbs": 20.0, "fat": 5.0,  "servingSize": "1 glass (250 ml)"},
    "Buttermilk":           {"calories": 60,  "protein": 3.0,  "carbs": 6.0,  "fat": 2.0,  "servingSize": "1 glass (250 ml)"},
    "Paneer":               {"calories": 260, "protein": 18.0, "carbs": 3.0,  "fat": 20.0, "servingSize": "100 g"},
    "Milk":                 {"calories": 120, "protein": 6.0,  "carbs": 9.0,  "fat": 5.0,  "servingSize": "1 glass (200 ml)"},
    # Breakfast
    "Idli":                 {"calories": 60,  "protein": 2.0,  "carbs": 12.0, "fat": 0.4,  "servingSize": "1 piece (50 g)"},
    "Dosa":                 {"calories": 130, "protein": 4.0,  "carbs": 23.0, "fat": 3.0,  "servingSize": "1 dosa (80 g)"},
    "Upma":                 {"calories": 200, "protein": 5.0,  "carbs": 30.0, "fat": 7.0,  "servingSize": "1 bowl (200 g)"},
    "Poha":                 {"calories": 180, "protein": 4.0,  "carbs": 35.0, "fat": 4.0,  "servingSize": "1 plate (150 g)"},
    "Oats":                 {"calories": 150, "protein": 5.0,  "carbs": 27.0, "fat": 3.0,  "servingSize": "1 bowl (40 g dry)"},
    "Masala Oats":          {"calories": 160, "protein": 5.0,  "carbs": 28.0, "fat": 4.0,  "servingSize": "1 bowl (40 g dry)"},
    # Fruit / snacks
    "Banana":               {"calories": 90,  "protein": 1.1,  "carbs": 23.0, "fat": 0.3,  "servingSize": "1 medium (90 g)"},
    "Apple":                {"calories": 80,  "protein": 0.4,  "carbs": 21.0, "fat": 0.2,  "servingSize": "1 medium (150 g)"},
    "Mixed Nuts":           {"calories": 170, "protein": 4.0,  "carbs": 6.0,  "fat": 15.0, "servingSize": "30 g"},
    # Combo dishes
    "Dal Chawal":           {"calories": 380, "protein": 12.0, "carbs": 65.0, "fat": 7.0,  "servingSize": "1 plate"},
    "Rajma Chawal":         {"calories": 400, "protein": 13.0, "carbs": 68.0, "fat": 8.0,  "servingSize": "1 plate"},
    "Kadhi Chawal":         {"calories": 370, "protein": 9.0,  "carbs": 60.0, "fat": 10.0, "servingSize": "1 plate"},
    "Curd Rice":            {"calories": 280, "protein": 8.0,  "carbs": 48.0, "fat": 5.0,  "servingSize": "1 plate"},
    "Idli Sambar":          {"calories": 250, "protein": 9.0,  "carbs": 45.0, "fat": 5.0,  "servingSize": "2 idli + 1 bowl sambar"},
    "Biryani":              {"calories": 380, "protein": 10.0, "carbs": 60.0, "fat": 12.0, "servingSize": "1 plate (250 g)"},
    "Chicken Biryani":      {"calories": 450, "protein": 22.0, "carbs": 55.0, "fat": 14.0, "servingSize": "1 plate (300 g)"},
}


def fix_meal_calories(db):
    """Task 4: Update calorie values for named meals in Firestore."""
    meals_col = db.collection("meals")
    updated = 0
    skipped = 0
    errors  = 0

    for meal_name, corrections in CALORIE_CORRECTIONS.items():
        try:
            # Find by mealName field (case-sensitive exact match)
            docs = meals_col.where("mealName", "==", meal_name).limit(5).stream()
            found = list(docs)

            if not found:
                print(f"  [SKIP] '{meal_name}' not found in Firestore")
                skipped += 1
                continue

            for doc in found:
                old = doc.to_dict()
                old_cal = old.get("calories", "?")
                doc.reference.update(corrections)
                updated += 1
                print(f"  [OK]   '{meal_name}': {old_cal} → {corrections['calories']} kcal")

        except Exception as e:
            print(f"  [ERR]  '{meal_name}': {e}")
            errors += 1

    print(f"\nMeals updated: {updated} | skipped: {skipped} | errors: {errors}")
    return updated


def delete_old_plans(db):
    """Task 5: Delete ALL meal_plans so the app regenerates with correct values."""
    plans_col  = db.collection("meal_plans")
    ratings_col = db.collection("daily_ratings")
    deleted = 0

    print("\nDeleting meal_plans...")
    for doc in plans_col.stream():
        doc.reference.delete()
        deleted += 1

    print(f"  Deleted {deleted} meal plan documents.")

    deleted_r = 0
    print("Deleting daily_ratings...")
    for doc in ratings_col.stream():
        doc.reference.delete()
        deleted_r += 1
    print(f"  Deleted {deleted_r} daily rating documents.")

    return deleted, deleted_r


if __name__ == "__main__":
    print("=" * 60)
    print("NutriLens — Calorie Normalization Script")
    print("=" * 60)

    db = _init()

    print("\n[TASK 4] Fixing meal calorie values...")
    fix_meal_calories(db)

    print("\n[TASK 5] Deleting stale meal plans...")
    n_plans, n_ratings = delete_old_plans(db)

    print("\n" + "=" * 60)
    print("Done.")
    print(f"  Plans deleted:   {n_plans}")
    print(f"  Ratings deleted: {n_ratings}")
    print("\nRestart the server and regenerate plans in the app.")
