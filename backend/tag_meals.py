import firebase_admin
from firebase_admin import firestore, credentials
import os

# Initialize Firebase
if not firebase_admin._apps:
    status_msg = "Logging into Firebase..."
    key_path = "serviceAccountKey.json"
    if os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        print("✅ Local Auth")
    else:
        firebase_admin.initialize_app()
        print("✅ Cloud Auth")

db = firestore.client()

print("--- STARTING MEAL TAGGING ---")

# RULES ENGINE
def determine_tags(meal):
    name = meal.get("mealName", "").lower()
    keywords = [k.lower() for k in meal.get("searchKeywords", [])]
    full_text = name + " " + " ".join(keywords)
    category = meal.get("category", "").lower() # Breakfast, Lunch, Dinner, Snack

    tags = {
        "cuisine": "indian", # Default
        "food_group": "grain", # Default
        "meal_role": "main"    # Default
    }

    # 1. CUISINE LOGIC
    if any(k in full_text for k in ["dosa", "idli", "sambar", "rasam", "upma", "pongal", "chettinad", "kerala", "avial", "puttu", "appam", "vada", "uttapam"]):
        tags["cuisine"] = "south_indian"
    elif any(k in full_text for k in ["roti", "chapati", "naan", "kulcha", "paneer", "dal", "rajma", "chole", "paratha", "saag", "tikka", "korma", "tandoori", "gatte", "baati", "missi", "thepla", "dhokla", "khandvi"]):
        tags["cuisine"] = "north_indian"
    elif any(k in full_text for k in ["pasta", "pizza", "burger", "sandwich", "oats", "salad", "soup", "pancake", "waffle", "macaroni", "spaghetti"]):
        tags["cuisine"] = "western"
    elif any(k in full_text for k in ["noodles", "fried rice", "manchurian", "momos", "hakka", "schezwan", "chowmein", "spring roll"]):
        tags["cuisine"] = "chinese"
    elif any(k in full_text for k in ["shawarma", "hummus", "pita"]):
        tags["cuisine"] = "middle_eastern"

    # 2. FOOD GROUP LOGIC
    # Priorities: Dairy > Protein > Vegetable > Grain
    if any(k in full_text for k in ["milk", "curd", "yogurt", "buttermilk", "lassi", "raita", "cheese", "paneer", "whey"]):
        # Paneer is special: it's dairy AND protein. We'll call it Protein for meal planning compatibility usually, or Dairy?
        # Let's stick to Protein for Paneer/Cheese in a "Main Dish" context, but Dairy for side/drink.
        # Rule: If it's Paneer -> Protein
        if "paneer" in full_text:
            tags["food_group"] = "protein"
        else:
            tags["food_group"] = "dairy"
            
    elif any(k in full_text for k in ["dal", "chicken", "fish", "egg", "mutton", "chana", "rajma", "chole", "soya", "tofu", "besan", "lentil", "beans", "legume"]):
        tags["food_group"] = "protein"
        
    elif any(k in full_text for k in ["sabzi", "saag", "bhaji", "stew", "poriyal", "kootu", "thoran", "avial", "salad", "soup", "vegetable", "gobi", "aloo", "baingan", "bhindi"]):
        tags["food_group"] = "vegetable"
        
    elif any(k in full_text for k in ["fruit", "apple", "banana", "papaya", "smoothie"]):
        tags["food_group"] = "fruit"
    
    else:
        # Defaults mostly to Grain (Rice, Roti, Bread, Oats, Dosa batter etc.)
        tags["food_group"] = "grain"

    # 3. MEAL ROLE LOGIC
    if tags["food_group"] == "grain":
        tags["meal_role"] = "main"
        
    elif tags["food_group"] == "protein":
        # Protein can be Main (Chicken Curry) or Side (Dal).
        # Usually in India: Roti (Main) + Dal (Side). Rice (Main) + Fish Curry (Side).
        # But Biryani is Main.
        if any(k in full_text for k in ["biryani", "pulao", "khichdi", "rice"]):
            tags["meal_role"] = "main"
        elif "curry" in full_text or "gravy" in full_text or "dal" in full_text or "sambar" in full_text:
             tags["meal_role"] = "side"
        elif "tikka" in full_text or "kebab" in full_text or "fry" in full_text:
             tags["meal_role"] = "side" # Appetizer/Side
        else:
             tags["meal_role"] = "side"

    elif tags["food_group"] == "vegetable":
        tags["meal_role"] = "side"
        
    elif tags["food_group"] == "dairy":
        if any(k in full_text for k in ["milk", "lassi", "buttermilk", "shake", "smoothie"]):
            tags["meal_role"] = "drink"
        else:
            tags["meal_role"] = "side" # Raita, Curd
            
    # Overrides for Standalone Mains
    if any(k in full_text for k in ["pasta", "noodles", "pizza", "burger", "sandwich", "dosa", "idli", "vada", "upma", "pongal", "khichdi", "biryani", "pulao", "wrap", "roll", "frankie", "taco", "shawarma"]):
        tags["meal_role"] = "main"
        
    # Overrides for Sides that might look like Mains
    if "chutney" in full_text or "podi" in full_text or "pickle" in full_text or "sauce" in full_text or "dip" in full_text:
        tags["meal_role"] = "side"

    return tags

# BATCH UPDATE
batch = db.batch()
count = 0
docs = db.collection("meals_v3").stream()

for doc in docs:
    meal = doc.to_dict()
    new_tags = determine_tags(meal)
    
    # Update logic
    ref = db.collection("meals_v3").document(doc.id)
    batch.update(ref, new_tags)
    count += 1
    
    if count % 400 == 0:
        batch.commit()
        batch = db.batch()
        print(f"Committed {count} tags...")

if count % 400 != 0:
    batch.commit()
    print(f"Committed final batch. Total: {count}")

print("✅ MEAL TAGGING COMPLETE")
