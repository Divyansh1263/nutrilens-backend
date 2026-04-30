# config/config.py
import os

# Firebase Database
# Assuming initialization happens in app.py

# ---------------------------------------------------------
# MEAL GENERATOR CONFIGURATION
# ---------------------------------------------------------
BREAKFAST_RANGE = (350, 450)
LUNCH_RANGE = (450, 600)
DINNER_RANGE = (400, 550)
SNACK_RANGE = (150, 200)

CALORIE_TOLERANCE = 80
MAX_DISHES_PER_MEAL = 2

# Variety Scoring Rules
PENALTY_YESTERDAY = 200
PENALTY_LAST_3_DAYS = 50
PENALTY_WEEK_FREQ_3 = 3
PENALTY_WEEK_FREQ_2 = 1

PREFERENCE_MULTIPLIER = 0.5

# Meal Type Fallbacks
MEAL_SPLIT_RATIOS = {
    "Breakfast": 0.25,
    "Lunch": 0.35,
    "Dinner": 0.30,
    "Snack": 0.10,
}

# ---------------------------------------------------------
# COLLECTION NAMES (Constant mapping to prevent typos)
# ---------------------------------------------------------
COL_USERS = "users"
COL_MEALS = "meals_v3"
COL_MEAL_PLANS = "meal_plans"
COL_MEAL_LOGS = "meal_logs"
COL_DAILY_TARGETS = "daily_targets"
COL_DAILY_RATINGS = "daily_ratings"
COL_MEAL_COMBOS = "meal_combos"
COL_USER_MEAL_HISTORY = "user_meal_history"
COL_DAILY_TRACKER_SUMMARY = "daily_tracker_summary"

