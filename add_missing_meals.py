import os
import sys

os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"] = "serviceAccountKey.json"

try:
    from firebase_admin import firestore, initialize_app, credentials
    
    # Check if app already initialized
    try:
        db = firestore.client()
    except ValueError:
        cred = credentials.Certificate("serviceAccountKey.json")
        initialize_app(cred)
        db = firestore.client()

    meals_to_add = [
        {
            "mealName": "Plain Tea",
            "category": "Beverage",
            "calories": 35.0,
            "protein": 1.0,
            "carbs": 5.0,
            "fat": 1.0,
            "searchKeywords": ["tea", "chai", "plain tea", "milk tea", "normal tea"],
            "meal_type": "snack"
        },
        {
            "mealName": "Plain Dal",
            "category": "Dal",
            "calories": 150.0,
            "protein": 9.0,
            "carbs": 20.0,
            "fat": 4.0,
            "searchKeywords": ["dal", "daal", "plain dal", "yellow dal"],
            "meal_type": "lunch"
        },
        {
            "mealName": "Plain Roti",
            "category": "Staple",
            "calories": 100.0,
            "protein": 3.0,
            "carbs": 15.0,
            "fat": 1.0,
            "searchKeywords": ["roti", "chapati", "plain roti", "phulka"],
            "meal_type": "lunch"
        }
    ]

    for meal in meals_to_add:
        # Check if exists
        docs = db.collection("meals_v3").where("mealName", "==", meal["mealName"]).stream()
        exists = False
        for d in docs:
            exists = True
            break
        
        if not exists:
            db.collection("meals_v3").add(meal)
            print(f"Added {meal['mealName']}")
        else:
            print(f"{meal['mealName']} already exists")
            
except Exception as e:
    print(f"Error: {e}")
