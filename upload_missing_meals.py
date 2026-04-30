import json
import firebase_admin
from firebase_admin import credentials, firestore

data = [
  {
    "mealName": "Bread Jam",
    "calories": 180,
    "protein": 4,
    "carbs": 30,
    "fat": 4,
    "category": "Breakfast",
    "searchKeywords": ["bread jam", "jam toast", "bread with jam", "toast jam", "sweet bread"],
    "servingSize": "2 slices",
    "servingGrams": 70,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "High",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": False,
    "is_nut_free": True,
    "is_sick_friendly": False,
    "explanations": {
      "default": "Bread with fruit jam spread.",
      "diabetes": "High sugar.",
      "weight_loss": "Refined carbs.",
      "muscle_gain": "Low protein.",
      "fever": "Easy to eat."
    }
  },
  {
    "mealName": "Chicken Breast Grilled",
    "calories": 220,
    "protein": 40,
    "carbs": 0,
    "fat": 5,
    "category": "Main Course",
    "searchKeywords": ["grilled chicken breast", "chicken breast grilled", "lean chicken", "protein chicken", "chicken grill"],
    "servingSize": "1 piece",
    "servingGrams": 150,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": False,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Lean grilled chicken breast.",
      "diabetes": "Safe protein.",
      "weight_loss": "Excellent protein.",
      "muscle_gain": "High protein.",
      "fever": "Light protein source."
    }
  },
  {
    "mealName": "Grilled Fish",
    "calories": 200,
    "protein": 30,
    "carbs": 0,
    "fat": 8,
    "category": "Main Course",
    "searchKeywords": ["grilled fish", "fish grill", "rohu grilled", "fish protein", "grilled seafood"],
    "servingSize": "1 piece",
    "servingGrams": 150,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": False,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Grilled fish fillet.",
      "diabetes": "Safe protein.",
      "weight_loss": "Lean protein.",
      "muscle_gain": "High protein.",
      "fever": "Light and easy."
    }
  },
  {
    "mealName": "Oats (Water Based)",
    "calories": 150,
    "protein": 5,
    "carbs": 27,
    "fat": 3,
    "category": "Breakfast",
    "searchKeywords": ["plain oats", "oats water", "oatmeal", "rolled oats", "simple oats"],
    "servingSize": "1 bowl",
    "servingGrams": 40,
    "validMealTypes": ["Breakfast"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": False,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Plain oats cooked in water.",
      "diabetes": "Good fiber.",
      "weight_loss": "Low calorie.",
      "muscle_gain": "Moderate carbs.",
      "fever": "Light meal."
    }
  },
  {
    "mealName": "Sauteed Vegetables",
    "calories": 120,
    "protein": 4,
    "carbs": 15,
    "fat": 5,
    "category": "Side",
    "searchKeywords": ["saute vegetables", "stir fry veg", "light veg", "mixed veg saute", "vegetables"],
    "servingSize": "1 bowl",
    "servingGrams": 150,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Lightly cooked mixed vegetables.",
      "diabetes": "Low GI.",
      "weight_loss": "Low calorie.",
      "muscle_gain": "Low protein.",
      "fever": "Light and healthy."
    }
  },
  {
    "mealName": "Tea (No Sugar)",
    "calories": 30,
    "protein": 1,
    "carbs": 3,
    "fat": 1,
    "category": "Beverage",
    "searchKeywords": ["tea no sugar", "chai no sugar", "plain tea", "indian tea no sugar", "black tea"],
    "servingSize": "1 cup",
    "servingGrams": 120,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Tea without sugar.",
      "diabetes": "Safe.",
      "weight_loss": "Low calorie.",
      "muscle_gain": "No protein.",
      "fever": "Soothing."
    }
  },
  {
    "mealName": "Tea (Less Sugar)",
    "calories": 50,
    "protein": 1,
    "carbs": 8,
    "fat": 1,
    "category": "Beverage",
    "searchKeywords": ["tea less sugar", "chai light sugar", "tea low sugar", "indian chai light", "milk tea"],
    "servingSize": "1 cup",
    "servingGrams": 120,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Medium",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Tea with little sugar.",
      "diabetes": "Limit intake.",
      "weight_loss": "Moderate calories.",
      "muscle_gain": "No protein.",
      "fever": "Okay."
    }
  },
  {
    "mealName": "Vegetable Dalia",
    "calories": 180,
    "protein": 6,
    "carbs": 32,
    "fat": 3,
    "category": "Breakfast",
    "searchKeywords": ["veg dalia", "broken wheat veg", "dalia porridge", "healthy dalia", "vegetable porridge"],
    "servingSize": "1 bowl",
    "servingGrams": 200,
    "validMealTypes": ["Breakfast"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": False,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "explanations": {
      "default": "Broken wheat cooked with vegetables.",
      "diabetes": "Good fiber.",
      "weight_loss": "Balanced meal.",
      "muscle_gain": "Moderate carbs.",
      "fever": "Light and easy."
    }
  }
]

def main():
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    col = db.collection("meals_v3")

    print("Counting documents before upload...")
    before_count = len(list(col.stream()))
    print(f"Documents before: {before_count}")

    uploaded = 0
    skipped = 0
    errors = 0

    print("Uploading meals...")
    for meal in data:
        meal_name = meal.get("mealName")
        if not meal_name:
            skipped += 1
            continue

        doc_id = "".join([c for c in meal_name.lower() if c.isalnum() or c == " "]).replace(" ", "_")

        try:
            col.document(doc_id).set(meal)
            uploaded += 1
        except Exception as e:
            print(f"Error uploading {meal_name}: {e}")
            errors += 1

    print("Counting documents after upload...")
    after_count = len(list(col.stream()))
    print(f"Documents after: {after_count}")

    print("=== SUMMARY ===")
    print(f"Total uploaded: {uploaded}")
    print(f"Total skipped: {skipped}")
    print(f"Total errors: {errors}")

if __name__ == "__main__":
    main()
