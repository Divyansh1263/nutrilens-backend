import json
import firebase_admin
from firebase_admin import credentials, firestore

data = [
  {
    "mealName": "Whey Protein Shake",
    "calories": 120,
    "protein": 24,
    "carbs": 3,
    "fat": 1,
    "category": "Supplement",
    "searchKeywords": ["whey protein", "protein shake", "gym shake", "protein powder", "whey"],
    "servingSize": "1 scoop",
    "servingGrams": 30,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Soy Chunks",
    "calories": 150,
    "protein": 25,
    "carbs": 10,
    "fat": 1,
    "category": "Main Course",
    "searchKeywords": ["soya chunks", "soy protein", "nutrela", "veg protein", "soya"],
    "servingSize": "1 bowl",
    "servingGrams": 50,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Amul Protein Lassi",
    "calories": 120,
    "protein": 15,
    "carbs": 10,
    "fat": 3,
    "category": "Beverage",
    "searchKeywords": ["amul protein lassi", "protein drink", "lassi protein", "amul lassi", "high protein lassi"],
    "servingSize": "1 bottle",
    "servingGrams": 200,
    "validMealTypes": ["Snack"],
    "glycemic_index": "Medium",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Amul Protein Milk",
    "calories": 110,
    "protein": 20,
    "carbs": 8,
    "fat": 2,
    "category": "Beverage",
    "searchKeywords": ["amul protein milk", "protein milk", "amul high protein milk", "milk protein", "dairy protein"],
    "servingSize": "1 bottle",
    "servingGrams": 250,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Paneer (100g)",
    "calories": 265,
    "protein": 18,
    "carbs": 6,
    "fat": 20,
    "category": "Main Course",
    "searchKeywords": ["paneer", "cottage cheese", "paneer cubes", "protein paneer", "indian cheese"],
    "servingSize": "100g",
    "servingGrams": 100,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Greek Yogurt",
    "calories": 100,
    "protein": 10,
    "carbs": 5,
    "fat": 3,
    "category": "Snack",
    "searchKeywords": ["greek yogurt", "hung curd", "high protein curd", "yogurt protein", "curd thick"],
    "servingSize": "1 bowl",
    "servingGrams": 150,
    "validMealTypes": ["Snack", "Breakfast"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Boiled Eggs (2)",
    "calories": 140,
    "protein": 12,
    "carbs": 1,
    "fat": 10,
    "category": "Snack",
    "searchKeywords": ["boiled eggs", "eggs protein", "egg snack", "2 eggs", "egg diet"],
    "servingSize": "2 eggs",
    "servingGrams": 100,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Low",
    "is_vegetarian": False,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Grilled Chicken Breast (100g)",
    "calories": 165,
    "protein": 31,
    "carbs": 0,
    "fat": 4,
    "category": "Main Course",
    "searchKeywords": ["chicken breast", "grilled chicken", "lean chicken", "protein chicken", "chicken 100g"],
    "servingSize": "100g",
    "servingGrams": 100,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": False,
    "is_vegan": False,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Tofu",
    "calories": 80,
    "protein": 10,
    "carbs": 2,
    "fat": 5,
    "category": "Main Course",
    "searchKeywords": ["tofu", "soy tofu", "vegan protein", "bean curd", "plant protein"],
    "servingSize": "100g",
    "servingGrams": 100,
    "validMealTypes": ["Lunch", "Dinner"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": True,
    "is_nut_free": True,
    "is_sick_friendly": True,
    "is_high_protein": True
  },
  {
    "mealName": "Peanut Butter (2 tbsp)",
    "calories": 190,
    "protein": 8,
    "carbs": 6,
    "fat": 16,
    "category": "Snack",
    "searchKeywords": ["peanut butter", "pb", "nuts protein", "spread protein", "peanut"],
    "servingSize": "2 tbsp",
    "servingGrams": 32,
    "validMealTypes": ["Breakfast", "Snack"],
    "glycemic_index": "Low",
    "is_vegetarian": True,
    "is_vegan": True,
    "is_gluten_free": True,
    "is_nut_free": False,
    "is_sick_friendly": False,
    "is_high_protein": True
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
