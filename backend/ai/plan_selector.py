import random
from utils.logger import app_logger

class PlanSelector:
    def __init__(self, db_client):
        self.db = db_client

    def calculate_targets(self, user):
        """
        Calculate BMR using Mifflin-St Jeor equation.
        """
        weight = float(user.get("weight", 70))
        height = float(user.get("height", 170))
        age = int(user.get("age", 30))
        gender = user.get("gender", "male").lower()

        # Base BMR
        bmr = 10 * weight + 6.25 * height - 5 * age
        if gender == "female":
            bmr -= 161
        else:
            bmr += 5

        # Activity Multiplier
        activity = user.get("activityLevel", "sedentary").lower()
        multipliers = {
            "sedentary": 1.2,
            "lightly_active": 1.375,
            "moderately_active": 1.55,
            "very_active": 1.725
        }
        tdee = bmr * multipliers.get(activity, 1.2)

        # Goal Adjustment & Protein
        goal = user.get("goal", "maintain").lower()
        
        if "lose" in goal:
            tdee -= 400
            target_protein = weight * 1.3
        elif "gain" in goal:
            tdee += 400
            target_protein = weight * 1.8
        else:
            target_protein = weight * 1.2
            
        target_calories = round(tdee)
        target_protein = round(target_protein)
        
        return target_calories, target_protein

    def get_calorie_bucket(self, target_calories):
        if target_calories <= 1600:
            return "low"
        elif target_calories > 1900:
            return "high"
        else:
            return "medium"

    def is_diet_safe(self, plan, is_vegan, is_veg):
        diet_type = plan.get("dietType", "").lower()
        if not diet_type:
            return False  # Missing or empty dietType is strictly unsafe
            
        if is_vegan:
            return diet_type == "vegan"
            
        if is_veg:
            return diet_type in ["vegan", "vegetarian"]
            
        # Non-vegetarian users can eat anything
        return True

    def select_plan(self, user):
        target_calories, target_protein = self.calculate_targets(user)
        bucket = self.get_calorie_bucket(target_calories)
        
        user_goal = user.get("goal", "maintain").lower()
        is_veg = bool(user.get("is_vegetarian", False))
        is_vegan = bool(user.get("is_vegan", False))

        print(f"[DEBUG] Target Calories: {target_calories}, Target Protein: {target_protein}")

        # Fetch all plans once
        plans_ref = self.db.collection("meal_plans_v1").stream()
        all_plans = [p.to_dict() for p in plans_ref]
        
        if not all_plans:
            return None # Database is completely empty, impossible to fulfill

        valid_plans = []
        
        # STEP 1 - STRICT FILTER
        for plan in all_plans:
            if plan.get("goal", "").lower() != user_goal:
                continue
            if plan.get("calorieBucket") != bucket:
                continue
            if not self.is_diet_safe(plan, is_vegan, is_veg):
                continue
            valid_plans.append(plan)

        print(f"[DEBUG] strict match: {len(valid_plans)}")

        # STEP 2 - RELAX CALORIE BUCKET ONLY
        if not valid_plans:
            for plan in all_plans:
                if plan.get("goal", "").lower() != user_goal:
                    continue
                if not self.is_diet_safe(plan, is_vegan, is_veg):
                    continue
                valid_plans.append(plan)
            print(f"[DEBUG] relaxed bucket: {len(valid_plans)}")

        # STEP 3 - RELAX GOAL
        if not valid_plans:
            nearby_goals = {
                "lose_weight": ["lose_weight", "maintain_weight"],
                "maintain_weight": ["maintain_weight", "lose_weight"],
                "maintain": ["maintain", "lose_weight"],
                "muscle_gain": ["muscle_gain", "weight_gain"],
                "weight_gain": ["weight_gain", "muscle_gain"]
            }
            allowed_goals = nearby_goals.get(user_goal, [user_goal])
            
            for plan in all_plans:
                if plan.get("goal", "").lower() not in allowed_goals:
                    continue
                if not self.is_diet_safe(plan, is_vegan, is_veg):
                    continue
                valid_plans.append(plan)
            print(f"[DEBUG] relaxed goal: {len(valid_plans)}")

        # STEP 4 - FINAL SAFE FALLBACK
        if not valid_plans:
            for plan in all_plans:
                if not self.is_diet_safe(plan, is_vegan, is_veg):
                    continue
                valid_plans.append(plan)
            print(f"[DEBUG] final fallback: {len(valid_plans)}")

        # Absolute Emergency Fallback (Should never happen if DB is healthy)
        if not valid_plans:
            print("[DEBUG] CRITICAL: No diet-safe plans found in entire DB. System cannot proceed safely.")
            # If no safe plans exist, filter all plans using diet safety (if ANY exist). 
            # If absolutely 0 exist, we must still return None to avoid serving meat to vegans.
            safe_only = [p for p in all_plans if self.is_diet_safe(p, is_vegan, is_veg)]
            if not safe_only:
                return None
            valid_plans = [safe_only[0]]

        # Score Plans
        scored_plans = []
        for plan in valid_plans:
            plan_cal = float(plan.get("targetCalories", 0))
            plan_prot = float(plan.get("targetProtein", 0))
            
            cal_diff = abs(plan_cal - target_calories)
            prot_diff = abs(plan_prot - target_protein)
            
            score = 0.7 * cal_diff + 0.3 * prot_diff
            scored_plans.append((score, plan))

        # Select Plan
        scored_plans.sort(key=lambda x: x[0])
        top_3 = [p for score, p in scored_plans[:3]]
        selected = random.choice(top_3)
        
        selected["user_target_calories"] = target_calories
        selected["user_target_protein"] = target_protein
        
        return selected
