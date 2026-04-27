import os
import json
import firebase_admin
from firebase_admin import firestore

def export_meals():
    print("[export] Connecting to Firestore...")
    if not firebase_admin._apps:
        possible_keys = ["serviceAccountKey.json", "d:/nutrilens/backend/serviceAccountKey.json"]
        key_path = next((key for key in possible_keys if os.path.exists(key)), None)
        if key_path:
            from firebase_admin import credentials
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, {"projectId": "nutrilens-b5e81"})
        else:
            firebase_admin.initialize_app(options={"projectId": "nutrilens-b5e81"})

    db = firestore.client()
    print("[export] Fetching documents from 'meals' collection...")
    docs = db.collection("meals").stream()
    
    meals_list = []
    for doc in docs:
        data = doc.to_dict()
        
        # Clean explanations
        explanations_raw = data.get("explanations") or {}
        
        meal = {
            "mealName": str(data.get("mealName") or "").strip(),
            "calories": float(data.get("calories") or 0.0),
            "protein": float(data.get("protein") or 0.0),
            "carbs": float(data.get("carbs") or 0.0),
            "fat": float(data.get("fat") or 0.0),
            "category": str(data.get("category") or "").strip(),
            "searchKeywords": list(data.get("searchKeywords") or []),
            "servingSize": str(data.get("servingSize") or "1 plate").strip(),
            "servingGrams": float(data.get("servingGrams") or 0.0),
            "validMealTypes": list(data.get("validMealTypes") or []),
            "glycemic_index": str(data.get("glycemic_index") or "Medium").strip(),
            "is_vegetarian": bool(data.get("is_vegetarian", False)),
            "is_vegan": bool(data.get("is_vegan", False)),
            "is_gluten_free": bool(data.get("is_gluten_free", False)),
            "is_nut_free": bool(data.get("is_nut_free", False)),
            "is_sick_friendly": bool(data.get("is_sick_friendly", False)),
            "explanations": {
                "default": str(explanations_raw.get("default") or "").strip(),
                "diabetes": str(explanations_raw.get("diabetes") or "").strip(),
                "weight_loss": str(explanations_raw.get("weight_loss") or "").strip(),
                "muscle_gain": str(explanations_raw.get("muscle_gain") or "").strip(),
                "fever": str(explanations_raw.get("fever") or "").strip()
            }
        }
        meals_list.append(meal)
        
    output_path = "meals_export.json"
    print(f"[export] Saving to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(meals_list, f, indent=2, ensure_ascii=False)
        
    print(f"[export] exported {len(meals_list)} meals")

if __name__ == "__main__":
    export_meals()
