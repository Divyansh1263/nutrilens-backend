import json
import os

collection = {
    "info": {
        "name": "NutriLens API - Full Collection",
        "description": "Complete collection of all 27 NutriLens backend routes.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "variable": [
        {
            "key": "base_url",
            "value": "https://your-app-url.onrender.com",
            "type": "string"
        },
        {
            "key": "user_id",
            "value": "test_user_777",
            "type": "string"
        },
        {
            "key": "date",
            "value": "2023-11-20",
            "type": "string"
        }
    ],
    "item": []
}

def create_request(name, method, path, body=None, params=None):
    req = {
        "name": name,
        "request": {
            "method": method,
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "url": {
                "raw": f"{{{{base_url}}}}/{path}",
                "host": ["{{base_url}}"],
                "path": path.split("/")
            }
        }
    }
    
    if body:
        req["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=4)
        }
        
    if params:
        query = [{"key": k, "value": v} for k, v in params.items()]
        req["request"]["url"]["query"] = query
        req["request"]["url"]["raw"] += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
    return req

# ==============================
# AUTH
# ==============================
auth_items = [
    create_request("Register", "POST", "register", {
        "userId": "{{user_id}}", "email": "test777@example.com", "password": "password123",
        "name": "Postman Tester", "age": 25, "gender": "Male", "height": 175, "weight": 70,
        "activity_level": "Moderately Active", "dietary_goal": "Maintenance"
    }),
    create_request("Login", "POST", "login", {"email": "test777@example.com", "password": "password123"}),
    create_request("User Profile", "GET", "user-profile", params={"userId": "{{user_id}}"})
]

# ==============================
# MEAL PLANNING
# ==============================
planning_items = [
    create_request("Generate Meal Plan", "POST", "generate-meal-plan", {"userId": "{{user_id}}", "date": "{{date}}"}),
    create_request("Replace Meal (AI)", "POST", "replace-meal", {"mealName": "Paneer Tikka"}),
    create_request("Swap Meal", "POST", "swap-meal", {"mealLogId": "REPLACE_LOG_ID", "newMeal": "Roti"})
]

# ==============================
# LOGGING
# ==============================
logging_items = [
    create_request("Log Meal (Manual)", "POST", "log-meal", {"userId": "{{user_id}}", "date": "{{date}}", "mealName": "Paneer Tikka", "mealType": "Lunch", "quantity": 1, "source": "manual"}),
    create_request("Log Meal (NLP)", "POST", "log-meal-nlp-ml", {"userId": "{{user_id}}", "date": "{{date}}", "text": "I ate 2 chapatis and dal"}),
    create_request("Update Log Quantity", "PUT", "update-log", {"log_id": "REPLACE_LOG_ID", "quantity": 2.5}),
    create_request("Delete Log", "DELETE", "delete-log", {"log_id": "REPLACE_LOG_ID"})
]

# ==============================
# FOOD SEARCH
# ==============================
search_items = [
    create_request("Search Food Autocomplete", "GET", "search-food", params={"query": "pan"}),
    create_request("Food Details", "GET", "food-details", params={"food_name": "Paneer Tikka"})
]

# ==============================
# TRACKER
# ==============================
tracker_items = [
    create_request("Tracker Summary", "GET", "tracker-summary", params={"userId": "{{user_id}}", "date": "{{date}}"}),
    create_request("Get Streak", "GET", "get-streak", params={"userId": "{{user_id}}"})
]

# ==============================
# ANALYTICS
# ==============================
analytics_items = [
    create_request("Get Gamification Analytics", "POST", "get-analytics", {"userId": "{{user_id}}"}),
    create_request("Generate Daily Rating", "POST", "generate-daily-rating", {"userId": "{{user_id}}", "date": "{{date}}"}),
    create_request("Get Daily Ratings History", "GET", "get-daily-ratings", params={"userId": "{{user_id}}"}),
    create_request("Recalculate Analytics", "POST", "recalculate-analytics", {"userId": "{{user_id}}"})
]

# ==============================
# SYSTEM & DEBUG
# ==============================
system_items = [
    create_request("Daily Greeting", "GET", "daily-greeting", params={"userId": "{{user_id}}"}),
    create_request("Health Check", "GET", "health"),
    create_request("Get Meal Combos", "GET", "get-meal-combos"),
    create_request("Get Meal Patterns", "GET", "get-meal-patterns")
]

collection["item"] = [
    {"name": "1. Authentication", "item": auth_items},
    {"name": "2. Meal Planning", "item": planning_items},
    {"name": "3. Meal Logging", "item": logging_items},
    {"name": "4. Food Search", "item": search_items},
    {"name": "5. Daily Tracker", "item": tracker_items},
    {"name": "6. Analytics & Gamification", "item": analytics_items},
    {"name": "7. System & Debug", "item": system_items}
]

out_path = r"C:\Users\Divyansh Tyagi\.gemini\antigravity\brain\bb947c5a-cd38-4a52-b7ab-44cae5abdf3b\NutriLens_Postman_Collection.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=4)
    
print(f"Generated Postman Collection at {out_path}")
