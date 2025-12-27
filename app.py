from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import random
from ai.target_calculator import compute_base_targets, apply_calorie_banking
from ai.smart_swap_knn import SmartSwapKNN
from ai.meal_plan_generator import generate_full_meal_plan
import os
from datetime import date

print("🔥 THIS IS THE APP.PY BEING RUN 🔥")

app = Flask(__name__)

# Firebase Init (Render-safe)
import json
import os

firebase_key = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()


# -------------------------------
# Load k-NN Smart Swap Model
# -------------------------------
knn_model = SmartSwapKNN()
knn_model.load("models/knn_meal_swap.joblib")




app = Flask(__name__)

# ======================================================
# 1. USER REGISTRATION / PROFILE API (UPGRADED)
# ======================================================
@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json(force=True)

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user_profile = {
        "name": data.get("name"),
        "age": data.get("age"),
        "gender": data.get("gender"),

        "height": data.get("height"),
        "weight": data.get("weight"),
        "target_weight": data.get("target_weight"),

        "activity_level": data.get("activity_level"),
        "dietary_goal": data.get("dietary_goal"),
        "weight_loss_speed": data.get("weight_loss_speed"),

        "dietary_restrictions": data.get("dietary_restrictions", {}),
        "health_conditions": data.get("health_conditions", {}),

        "onboarding_completed": True,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    }

    db.collection("users").document(user_id).set(user_profile)

    return jsonify({
        "message": "User registered successfully",
        "userId": user_id
    })


# ======================================================
# 2. TARGET CALCULATOR API (MATCHES YOUR DESIGN)
# ======================================================
from datetime import date

@app.route("/calculate-target", methods=["POST"])
def calculate_target():
    data = request.get_json(force=True)
    user_id = data.get("userId")

    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
        return jsonify({"error": "User not found"}), 404

    profile = user_doc.to_dict()

    base_targets = compute_base_targets(profile)
    final_targets = apply_calorie_banking(user_id, base_targets, db)

    today = str(date.today())

    db.collection("daily_targets").document(
        f"{user_id}_{today}"
    ).set({
        "userId": user_id,
        "date": today,
        **final_targets,
        "generated_by": "ai",
        "created_at": firestore.SERVER_TIMESTAMP
    })

    return jsonify(final_targets)


# ======================================================
# 3. MEAL GENERATOR API (RESTRICTION-AWARE)
# ======================================================
@app.route("/generate-meal-plan", methods=["POST"])
def generate_meal_plan():
    data = request.get_json(force=True)
    user_id = data.get("userId")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # -------------------------------
    # Fetch user profile
    # -------------------------------
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
        return jsonify({"error": "User not found"}), 404

    user = user_doc.to_dict()
    restrictions = user.get("dietary_restrictions", {})
    health = user.get("health_conditions", {})

    # -------------------------------
    # Helper: fetch meals per type
    # -------------------------------
    def fetch_meals(meal_type):
        query = db.collection("meals").where(
            "validMealTypes", "array_contains", meal_type
        )

        # Dietary restrictions
        if restrictions.get("vegetarian"):
            query = query.where("is_vegetarian", "==", True)
        if restrictions.get("vegan"):
            query = query.where("is_vegan", "==", True)
        if restrictions.get("gluten_free"):
            query = query.where("is_gluten_free", "==", True)
        if restrictions.get("nut_allergy"):
            query = query.where("is_nut_free", "==", True)

        # Health conditions
        if health.get("diabetes"):
            query = query.where("glycemic_index", "in", ["Low", "Medium"])

        meals = []
        for doc in query.stream():
            m = doc.to_dict()
            m["source"] = "ai"   # 🔑 IMPORTANT FOR LOGGING
            meals.append(m)

        return meals

    # -------------------------------
    # Fetch candidates
    # -------------------------------
    breakfast_list = fetch_meals("Breakfast")
    lunch_list = fetch_meals("Lunch")
    dinner_list = fetch_meals("Dinner")

    # Safety fallback
    if not breakfast_list or not lunch_list or not dinner_list:
        return jsonify({
            "error": "Not enough meals available for selected preferences"
        }), 400
    # -------------------------------
    # Fetch user target calories
    # -------------------------------
    today = str(date.today())
    target_doc = db.collection("daily_targets").document(
        f"{user_id}_{today}"
    ).get()

    if not target_doc.exists:
        return jsonify({"error": "Daily target not found"}), 400

    target = target_doc.to_dict()

    # -------------------------------
    # Build structured meal pool
    # -------------------------------
    meals_by_type = {
        "Breakfast": breakfast_list,
        "Lunch": lunch_list,
        "Dinner": dinner_list,
        "Snack": fetch_meals("Snack")
    }

    # -------------------------------
    # Generate FULL meal plan (FIX)
    # -------------------------------
    meal_plan = generate_full_meal_plan(target, meals_by_type)

    return jsonify(meal_plan)


# ======================================================
# 4. MEAL LOGGING API
# ======================================================
@app.route("/log-meal", methods=["POST"])
def log_meal():
    data = request.get_json(force=True)

    log_data = {
        "userId": data.get("userId"),
        "date": data.get("date"),  # YYYY-MM-DD

        "mealName": data.get("mealName"),
        "mealType": data.get("mealType"),

        "calories": data.get("calories"),
        "protein": data.get("protein"),
        "carbs": data.get("carbs"),
        "fat": data.get("fat"),

        "source": data.get("source", "manual"),  # ai | knn_swap | manual
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    db.collection("meal_logs").add(log_data)

    return jsonify({"message": "Meal logged successfully"})

# ======================================================
# 5. USER PROFILE FETCH API
# ======================================================
@app.route("/user-profile", methods=["GET"])
def get_user_profile():
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "userId required"}), 400

    doc = db.collection("users").document(user_id).get()
    if not doc.exists:
        return jsonify({"error": "User not found"}), 404

    return jsonify(doc.to_dict())

#====================================================
# Replace Meal API using k-NN Smart Swap 
#====================================================
@app.route("/replace-meal", methods=["POST"])
def replace_meal():
    data = request.get_json(force=True)
    meal_name = data.get("mealName")

    if not meal_name:
        return jsonify({"error": "mealName is required"}), 400

    # 1️⃣ Fetch the original meal from Firestore
    docs = db.collection("meals") \
             .where("mealName", "==", meal_name) \
             .limit(1) \
             .stream()

    original_meal = None
    for d in docs:
        original_meal = d.to_dict()

    if not original_meal:
        return jsonify({"error": "Meal not found"}), 404

    # 2️⃣ Find k-NN replacements
    replacements = knn_model.find_replacements(original_meal, k=3)

    if not replacements:
        return jsonify({"error": "No replacement found"}), 404

    # 3️⃣ Return AI suggestions
    return jsonify({
        "originalMeal": original_meal["mealName"],
        "aiSuggestions": replacements
    })

@app.route("/routes", methods=["GET"])
def routes():
    return jsonify([str(r) for r in app.url_map.iter_rules()])

#======================================================
# 6. Tracker Summary API
#======================================================

@app.route("/tracker-summary", methods=["GET"])
def tracker_summary():
    user_id = request.args.get("userId")
    date = request.args.get("date")  # YYYY-MM-DD

    if not user_id or not date:
        return jsonify({"error": "userId and date are required"}), 400

    # -------------------------------
    # Fetch meal logs for the day
    # -------------------------------
    logs_ref = db.collection("meal_logs") \
        .where("userId", "==", user_id) \
        .where("date", "==", date)

    logs = []
    total_cal = total_protein = total_carbs = total_fat = 0

    for doc in logs_ref.stream():
        log = doc.to_dict()
        logs.append(log)

        total_cal += log.get("calories", 0)
        total_protein += log.get("protein", 0)
        total_carbs += log.get("carbs", 0)
        total_fat += log.get("fat", 0)

    # -------------------------------
    # Fetch daily targets
    # -------------------------------
    target_doc = db.collection("daily_targets").document(
        f"{user_id}_{date}"
    ).get()

    targets = {}
    if target_doc.exists:
        targets = target_doc.to_dict()

    # -------------------------------
    # Final response
    # -------------------------------
    return jsonify({
        "date": date,
        "targets": {
            "calories": targets.get("calories", 0),
            "protein": targets.get("protein", 0),
            "carbs": targets.get("carbs", 0),
            "fat": targets.get("fat", 0)
        },
        "consumed": {
            "calories": total_cal,
            "protein": total_protein,
            "carbs": total_carbs,
            "fat": total_fat
        },
        "logs": logs
    })




# RUN SERVER (LOCAL + CLOUD RUN SAFE)
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)