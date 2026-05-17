# ai/target_calculator.py
# Advanced adaptive target calculator with calorie banking

from datetime import datetime, timedelta

# -------------------------------
# BMR Calculation
# -------------------------------
def mifflin_st_jeor(sex, weight_kg, height_cm, age):
    if sex.lower().startswith("m"):
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


# -------------------------------
# Activity multipliers
# -------------------------------
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderately_active": 1.55,
    "active": 1.725,
    "very_active": 1.9
}

# -------------------------------
# Goal modifiers
# -------------------------------
GOAL_MODIFIERS = {
    "lose_weight": -500,
    "maintain": 0,
    "gain_weight": 500
}


# -------------------------------
# Base Target Calculator
# -------------------------------
def compute_base_targets(profile):
    try:
        if not isinstance(profile, dict):
            profile = {}
            
        print("PROFILE:", profile)

        def safe_float(x, default=0):
            try:
                if x is None or str(x).strip() == "":
                    return default
                return float(x)
            except:
                return default

        weight = safe_float(profile.get("weight"), 70)
        height = safe_float(profile.get("height"), 170)
        age = safe_float(profile.get("age"), 25)
        sex = str(profile.get("sex") or profile.get("gender") or "male").lower().strip()

        if sex.startswith("f"):
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age + 5

        if bmr <= 0:
            bmr = 1500

        activity = (
            profile.get("activityLevel")
            or profile.get("activity_level")
            or "sedentary"
        )

        activity_map = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "moderately_active": 1.55,
            "Moderately Active": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        multiplier = activity_map.get(activity, 1.2)

        goal = profile.get("goal") or profile.get("dietary_goal") or "maintain"

        if goal == "lose_weight":
            calories = bmr * multiplier - 400
        elif goal == "gain_weight":
            calories = bmr * multiplier + 300
        else:
            calories = bmr * multiplier

        calories = max(1200, round(calories))
        print("CALCULATED CALORIES:", calories)

        # Phase 2: Weight + Goal based protein logic
        is_sedentary = multiplier <= 1.3
        
        if goal == "lose_weight":
            base_prot_mult = 1.6 if is_sedentary else 1.8
        elif goal == "gain_weight":
            base_prot_mult = 1.4 if is_sedentary else 1.8
        else: # maintain
            base_prot_mult = 1.0 if is_sedentary else 1.4

        if age >= 50:
            base_prot_mult += 0.2
            
        protein_g = round(weight * base_prot_mult, 1)

        # Cap protein to reasonable bounds (10% - 30% of calories) to prevent anomalies
        protein_cals = protein_g * 4
        if protein_cals > 0.30 * calories:
            protein_g = round((0.30 * calories) / 4, 1)
            protein_cals = protein_g * 4
        elif protein_cals < 0.10 * calories:
            protein_g = round((0.10 * calories) / 4, 1)
            protein_cals = protein_g * 4

        # Phase 3: Recalibrate Macro Splits
        remaining_cals = calories - protein_cals
        
        # Check for diabetic flag
        flags = profile.get("dietary_restrictions", [])
        if isinstance(flags, str):
            flags = [flags]
        is_diabetic = any("diabetic" in str(r).lower() for r in flags)
        
        if is_diabetic:
            carb_ratio = 0.45
            fat_ratio = 0.55
        elif goal == "lose_weight":
            carb_ratio = 0.50
            fat_ratio = 0.50
        else:
            # Standard Indian maintenance: higher carbs (50-60%), moderate fats
            carb_ratio = 0.55
            fat_ratio = 0.45
            
        carbs_g = round((remaining_cals * carb_ratio) / 4, 1)
        fat_g = round((remaining_cals * fat_ratio) / 9, 1)

        return {
            "calories": calories,
            "protein": protein_g,
            "carbs": carbs_g,
            "fat": fat_g
        }
    except Exception as e:
        import traceback
        print("ERROR in compute_base_targets:", traceback.format_exc())
        return {
            "calories": 2000,
            "protein": 100,
            "carbs": 250,
            "fat": 60
        }


# -------------------------------
# Calorie Banking (3-day window)
# -------------------------------
def apply_calorie_banking(user_id, base_targets, db):
    today = datetime.now().date()
    total_deviation = 0
    days_counted = 0

    for i in range(1, 4):
        day = today - timedelta(days=i)

        target_doc = db.collection("daily_targets").document(
            f"{user_id}_{day}"
        ).get()

        if not target_doc.exists:
            continue

        target = target_doc.to_dict().get("calories", 0)

        # FIX 6.1: Add date filter — previously summed ALL historical logs!
        day_str = day.strftime("%Y-%m-%d")
        logs = db.collection("meal_logs") \
                 .where("userId", "==", user_id) \
                 .where("date", "==", day_str) \
                 .stream()

        consumed = sum(
            log.to_dict().get("calories", 0)
            for log in logs
        )

        total_deviation += (consumed - target)
        days_counted += 1

    if days_counted == 0:
        return base_targets

    adjustment = int(max(-150, min(150, -(total_deviation / days_counted) / 3)))
    new_calories = max(1100, base_targets["calories"] + adjustment)

    factor = new_calories / base_targets["calories"]

    return {
        "calories": round(new_calories),
        "protein": round(base_targets["protein"] * factor, 1),
        "carbs": round(base_targets["carbs"] * factor, 1),
        "fat": round(base_targets["fat"] * factor, 1)
    }
