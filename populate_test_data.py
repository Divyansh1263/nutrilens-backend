"""
NutriLens - Firestore Test Data Populator
==========================================
Populates Firestore with realistic Indian-diet-based user profiles,
meal plans, meal logs, and daily ratings for research paper demonstration.

Run from /backend directory:
    python populate_test_data.py
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, date
import os
import sys

# ── Firebase Init ──────────────────────────────────────────────────────────────
print("[1/6] Connecting to Firebase...")
try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("  ✅ Firebase connected!\n")


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

users = {
    # ── test_user1–5 ──────────────────────────────────────────────────────────
    "test_user1": {
        "age": 24,
        "gender": "male",
        "height": 175,
        "weight": 72,
        "activity_level": "moderately active",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 1, 10, 9, 0, 0),
    },
    "test_user2": {
        "age": 34,
        "gender": "female",
        "height": 162,
        "weight": 68,
        "activity_level": "sedentary",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": True,
        },
        "health_conditions": {
            "diabetic": True,
            "hypertension": False,
        },
        "created_at": datetime(2025, 1, 15, 10, 30, 0),
    },
    "test_user3": {
        "age": 28,
        "gender": "male",
        "height": 180,
        "weight": 85,
        "activity_level": "active",
        "dietary_goal": "gain_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 1, 18, 8, 0, 0),
    },
    "test_user4": {
        "age": 45,
        "gender": "female",
        "height": 158,
        "weight": 76,
        "activity_level": "sedentary",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": True,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": True,
            "hypertension": True,
        },
        "created_at": datetime(2025, 1, 22, 11, 0, 0),
    },
    "test_user5": {
        "age": 30,
        "gender": "male",
        "height": 172,
        "weight": 70,
        "activity_level": "active",
        "dietary_goal": "maintain_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 2, 1, 7, 30, 0),
    },

    # ── simulated_user1–10 ────────────────────────────────────────────────────
    "simulated_user1": {
        "age": 22,
        "gender": "female",
        "height": 155,
        "weight": 52,
        "activity_level": "moderately active",
        "dietary_goal": "maintain_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 2, 5, 9, 15, 0),
    },
    "simulated_user2": {
        "age": 38,
        "gender": "male",
        "height": 182,
        "weight": 92,
        "activity_level": "active",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": True,
        },
        "created_at": datetime(2025, 2, 8, 10, 0, 0),
    },
    "simulated_user3": {
        "age": 55,
        "gender": "female",
        "height": 160,
        "weight": 78,
        "activity_level": "sedentary",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": True,
        },
        "health_conditions": {
            "diabetic": True,
            "hypertension": True,
        },
        "created_at": datetime(2025, 2, 10, 8, 45, 0),
    },
    "simulated_user4": {
        "age": 26,
        "gender": "male",
        "height": 178,
        "weight": 65,
        "activity_level": "active",
        "dietary_goal": "gain_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 2, 14, 7, 0, 0),
    },
    "simulated_user5": {
        "age": 42,
        "gender": "female",
        "height": 163,
        "weight": 60,
        "activity_level": "moderately active",
        "dietary_goal": "maintain_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": True,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 2, 18, 9, 30, 0),
    },
    "simulated_user6": {
        "age": 19,
        "gender": "male",
        "height": 170,
        "weight": 58,
        "activity_level": "moderately active",
        "dietary_goal": "gain_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 2, 20, 11, 0, 0),
    },
    "simulated_user7": {
        "age": 47,
        "gender": "male",
        "height": 174,
        "weight": 88,
        "activity_level": "sedentary",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": True,
            "hypertension": True,
        },
        "created_at": datetime(2025, 2, 25, 8, 0, 0),
    },
    "simulated_user8": {
        "age": 31,
        "gender": "female",
        "height": 166,
        "weight": 63,
        "activity_level": "active",
        "dietary_goal": "maintain_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": True,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 3, 1, 10, 15, 0),
    },
    "simulated_user9": {
        "age": 60,
        "gender": "male",
        "height": 168,
        "weight": 80,
        "activity_level": "sedentary",
        "dietary_goal": "lose_weight",
        "dietary_restrictions": {
            "is_vegetarian": True,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": True,
        },
        "health_conditions": {
            "diabetic": True,
            "hypertension": False,
        },
        "created_at": datetime(2025, 3, 5, 9, 0, 0),
    },
    "simulated_user10": {
        "age": 18,
        "gender": "female",
        "height": 152,
        "weight": 50,
        "activity_level": "active",
        "dietary_goal": "gain_weight",
        "dietary_restrictions": {
            "is_vegetarian": False,
            "is_vegan": False,
            "is_gluten_free": False,
            "is_nut_free": False,
        },
        "health_conditions": {
            "diabetic": False,
            "hypertension": False,
        },
        "created_at": datetime(2025, 3, 10, 8, 30, 0),
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# MEAL PLAN DATA
# Each plan has realistic Indian meals with calorie/macro values
# ═══════════════════════════════════════════════════════════════════════════════

meal_plans = [
    # ── test_user1 (veg, lose weight, 1800 cal target) ───────────────────────
    {
        "id": "mp_test_user1_01",
        "user_id": "test_user1",
        "date": "2025-03-01",
        "target_calories": 1800,
        "target_macros": {"carbs": 225, "protein": 90, "fat": 50},
        "breakfast": {
            "name": "Oats Upma with vegetables",
            "calories": 320,
            "carbs": 48,
            "protein": 10,
            "fat": 8,
        },
        "lunch": {
            "name": "2 Rotis + Dal Tadka + Mixed Sabzi + Raita",
            "calories": 580,
            "carbs": 78,
            "protein": 28,
            "fat": 14,
        },
        "dinner": {
            "name": "1 Roti + Palak Paneer + Brown Rice (small bowl)",
            "calories": 520,
            "carbs": 62,
            "protein": 26,
            "fat": 16,
        },
        "snack": {
            "name": "Sprouts Chaat + Buttermilk",
            "calories": 230,
            "carbs": 32,
            "protein": 12,
            "fat": 4,
        },
    },
    {
        "id": "mp_test_user1_02",
        "user_id": "test_user1",
        "date": "2025-03-02",
        "target_calories": 1800,
        "target_macros": {"carbs": 225, "protein": 90, "fat": 50},
        "breakfast": {
            "name": "Moong Dal Chilla with mint chutney",
            "calories": 295,
            "carbs": 38,
            "protein": 14,
            "fat": 7,
        },
        "lunch": {
            "name": "Rajma Chawal (1 cup rice + 1 cup rajma) + Cucumber Salad",
            "calories": 610,
            "carbs": 88,
            "protein": 24,
            "fat": 10,
        },
        "dinner": {
            "name": "2 Rotis + Lauki Sabzi + Dal + Low-fat Curd",
            "calories": 505,
            "carbs": 68,
            "protein": 22,
            "fat": 12,
        },
        "snack": {
            "name": "Apple + 5 Almonds",
            "calories": 195,
            "carbs": 32,
            "protein": 4,
            "fat": 6,
        },
    },

    # ── test_user2 (non-veg, diabetic, lose weight, 1750 cal) ─────────────────
    {
        "id": "mp_test_user2_01",
        "user_id": "test_user2",
        "date": "2025-03-01",
        "target_calories": 1750,
        "target_macros": {"carbs": 190, "protein": 100, "fat": 52},
        "breakfast": {
            "name": "Besan Cheela (2 pcs) + Green Chutney",
            "calories": 280,
            "carbs": 30,
            "protein": 14,
            "fat": 9,
        },
        "lunch": {
            "name": "Grilled Chicken (150g) + 2 Rotis + Stir-fried Vegetables",
            "calories": 570,
            "carbs": 56,
            "protein": 38,
            "fat": 14,
        },
        "dinner": {
            "name": "Egg Bhurji (3 eggs) + 2 Multigrain Rotis + Salad",
            "calories": 500,
            "carbs": 50,
            "protein": 28,
            "fat": 16,
        },
        "snack": {
            "name": "Roasted Chana + Herbal Tea",
            "calories": 185,
            "carbs": 30,
            "protein": 10,
            "fat": 3,
        },
    },
    {
        "id": "mp_test_user2_02",
        "user_id": "test_user2",
        "date": "2025-03-03",
        "target_calories": 1750,
        "target_macros": {"carbs": 190, "protein": 100, "fat": 52},
        "breakfast": {
            "name": "Vegetable Daliya (Broken Wheat Porridge)",
            "calories": 260,
            "carbs": 38,
            "protein": 8,
            "fat": 6,
        },
        "lunch": {
            "name": "Fish Curry (100g) + 1 cup Brown Rice + Salad",
            "calories": 580,
            "carbs": 64,
            "protein": 34,
            "fat": 12,
        },
        "dinner": {
            "name": "Chicken Soup + 2 Rotis + Sabzi",
            "calories": 520,
            "carbs": 52,
            "protein": 32,
            "fat": 14,
        },
        "snack": {
            "name": "Low-fat Curd (200ml) + Flaxseeds",
            "calories": 160,
            "carbs": 18,
            "protein": 8,
            "fat": 6,
        },
    },

    # ── test_user3 (non-veg, gain weight, 2800 cal) ────────────────────────────
    {
        "id": "mp_test_user3_01",
        "user_id": "test_user3",
        "date": "2025-03-01",
        "target_calories": 2800,
        "target_macros": {"carbs": 320, "protein": 140, "fat": 78},
        "breakfast": {
            "name": "4 Egg Omelette with whole wheat toast (3 slices) + Banana",
            "calories": 620,
            "carbs": 68,
            "protein": 32,
            "fat": 18,
        },
        "lunch": {
            "name": "Mutton Curry (200g) + 3 Rotis + Rice (1.5 cups) + Dal",
            "calories": 980,
            "carbs": 110,
            "protein": 52,
            "fat": 28,
        },
        "dinner": {
            "name": "Chicken Biryani (2 cups, home style) + Raita",
            "calories": 800,
            "carbs": 96,
            "protein": 42,
            "fat": 22,
        },
        "snack": {
            "name": "Peanut Butter Banana Shake + Whole wheat rusk (2 pcs)",
            "calories": 480,
            "carbs": 56,
            "protein": 18,
            "fat": 18,
        },
    },

    # ── test_user4 (veg, diabetic + hypertension, lose weight, 1700 cal) ─────
    {
        "id": "mp_test_user4_01",
        "user_id": "test_user4",
        "date": "2025-03-01",
        "target_calories": 1700,
        "target_macros": {"carbs": 195, "protein": 85, "fat": 48},
        "breakfast": {
            "name": "Idli (2 small) + Sambhar (low sodium) + Coconut Chutney (small)",
            "calories": 290,
            "carbs": 52,
            "protein": 8,
            "fat": 5,
        },
        "lunch": {
            "name": "2 Gluten-free Rotis (Bajra) + Moong Dal + Methi Sabzi",
            "calories": 530,
            "carbs": 68,
            "protein": 22,
            "fat": 12,
        },
        "dinner": {
            "name": "Vegetable Khichdi (small bowl) + Low-fat Curd",
            "calories": 480,
            "carbs": 62,
            "protein": 18,
            "fat": 10,
        },
        "snack": {
            "name": "Cucumber sticks + Hummus (2 tbsp)",
            "calories": 140,
            "carbs": 18,
            "protein": 5,
            "fat": 6,
        },
    },

    # ── test_user5 (non-veg, maintain, active, 2200 cal) ─────────────────────
    {
        "id": "mp_test_user5_01",
        "user_id": "test_user5",
        "date": "2025-03-01",
        "target_calories": 2200,
        "target_macros": {"carbs": 255, "protein": 110, "fat": 62},
        "breakfast": {
            "name": "Poha with peas + 2 Boiled Eggs + Chai",
            "calories": 450,
            "carbs": 60,
            "protein": 20,
            "fat": 12,
        },
        "lunch": {
            "name": "Chicken Curry (150g) + 3 Rotis + Salad + Lassi",
            "calories": 760,
            "carbs": 84,
            "protein": 38,
            "fat": 20,
        },
        "dinner": {
            "name": "Dal Makhani + 2 Rotis + Paneer Bhurji",
            "calories": 650,
            "carbs": 72,
            "protein": 32,
            "fat": 20,
        },
        "snack": {
            "name": "Mixed fruits (1 bowl) + Roasted Makhana",
            "calories": 260,
            "carbs": 44,
            "protein": 6,
            "fat": 6,
        },
    },

    # ── simulated_user1 (vegan, maintain, 1900 cal) ────────────────────────────
    {
        "id": "mp_sim_user1_01",
        "user_id": "simulated_user1",
        "date": "2025-03-05",
        "target_calories": 1900,
        "target_macros": {"carbs": 240, "protein": 80, "fat": 55},
        "breakfast": {
            "name": "Rava Upma with vegetables + Black coffee",
            "calories": 340,
            "carbs": 52,
            "protein": 8,
            "fat": 8,
        },
        "lunch": {
            "name": "Tofu Stir-fry + Brown Rice (1 cup) + Tomato Soup",
            "calories": 580,
            "carbs": 78,
            "protein": 26,
            "fat": 14,
        },
        "dinner": {
            "name": "Chana Masala + 2 Rotis + Salad",
            "calories": 570,
            "carbs": 76,
            "protein": 24,
            "fat": 14,
        },
        "snack": {
            "name": "Mixed nuts (small handful) + Coconut water",
            "calories": 250,
            "carbs": 22,
            "protein": 6,
            "fat": 16,
        },
    },

    # ── simulated_user2 (non-veg, hypertension, lose weight, 1900 cal) ────────
    {
        "id": "mp_sim_user2_01",
        "user_id": "simulated_user2",
        "date": "2025-03-05",
        "target_calories": 1900,
        "target_macros": {"carbs": 210, "protein": 110, "fat": 55},
        "breakfast": {
            "name": "Oats Porridge (low sodium) + 2 Boiled Eggs + Orange",
            "calories": 380,
            "carbs": 46,
            "protein": 20,
            "fat": 10,
        },
        "lunch": {
            "name": "Steamed Fish (150g) + 2 Rotis + Stir-fried Spinach",
            "calories": 580,
            "carbs": 58,
            "protein": 40,
            "fat": 14,
        },
        "dinner": {
            "name": "Chicken Salad (grilled, 150g) + 1 Roti + Vegetable Soup",
            "calories": 520,
            "carbs": 44,
            "protein": 38,
            "fat": 14,
        },
        "snack": {
            "name": "Banana + Low-fat Curd",
            "calories": 210,
            "carbs": 38,
            "protein": 8,
            "fat": 4,
        },
    },

    # ── simulated_user3 (veg + nut-free, diabetic+hypertension, 1650 cal) ────
    {
        "id": "mp_sim_user3_01",
        "user_id": "simulated_user3",
        "date": "2025-03-06",
        "target_calories": 1650,
        "target_macros": {"carbs": 185, "protein": 80, "fat": 46},
        "breakfast": {
            "name": "Steamed Idli (2) + Sambhar (low sodium, no coconut)",
            "calories": 265,
            "carbs": 48,
            "protein": 8,
            "fat": 4,
        },
        "lunch": {
            "name": "Bajra Roti (2) + Lauki Dal + Methi Sabzi",
            "calories": 520,
            "carbs": 68,
            "protein": 20,
            "fat": 12,
        },
        "dinner": {
            "name": "Vegetable Daliya Khichdi + Low-fat Curd (small)",
            "calories": 440,
            "carbs": 58,
            "protein": 16,
            "fat": 10,
        },
        "snack": {
            "name": "Roasted Chana (30g) + Herbal Tea",
            "calories": 155,
            "carbs": 24,
            "protein": 8,
            "fat": 3,
        },
    },

    # ── simulated_user4 (non-veg, gain weight, active, 2900 cal) ──────────────
    {
        "id": "mp_sim_user4_01",
        "user_id": "simulated_user4",
        "date": "2025-03-06",
        "target_calories": 2900,
        "target_macros": {"carbs": 330, "protein": 145, "fat": 80},
        "breakfast": {
            "name": "Paratha (2 aloo) + Curd + 3 Egg Omelette + Milk (250ml)",
            "calories": 680,
            "carbs": 76,
            "protein": 34,
            "fat": 22,
        },
        "lunch": {
            "name": "Chicken Curry (200g) + 3 Rotis + 1 cup Rice + Dal + Salad",
            "calories": 1020,
            "carbs": 114,
            "protein": 56,
            "fat": 28,
        },
        "dinner": {
            "name": "Egg Curry (3 eggs) + 3 Rotis + Paneer Sabzi",
            "calories": 780,
            "carbs": 84,
            "protein": 40,
            "fat": 22,
        },
        "snack": {
            "name": "Banana Shake with full-fat milk + Handful of Cashews",
            "calories": 480,
            "carbs": 60,
            "protein": 16,
            "fat": 18,
        },
    },

    # ── simulated_user5 (non-veg, gluten-free, maintain, 2000 cal) ─────────
    {
        "id": "mp_sim_user5_01",
        "user_id": "simulated_user5",
        "date": "2025-03-07",
        "target_calories": 2000,
        "target_macros": {"carbs": 225, "protein": 100, "fat": 60},
        "breakfast": {
            "name": "Rice Flour Dosa (2) + Sambhar + Tomato Chutney",
            "calories": 380,
            "carbs": 56,
            "protein": 10,
            "fat": 10,
        },
        "lunch": {
            "name": "Grilled Fish (150g) + Brown Rice (1 cup) + Stir-fried Veggies",
            "calories": 620,
            "carbs": 72,
            "protein": 38,
            "fat": 14,
        },
        "dinner": {
            "name": "Chicken Tikka (grilled, 150g) + Rice (small bowl) + Raita",
            "calories": 580,
            "carbs": 52,
            "protein": 38,
            "fat": 16,
        },
        "snack": {
            "name": "Fruit Salad + Pumpkin Seeds",
            "calories": 240,
            "carbs": 38,
            "protein": 6,
            "fat": 8,
        },
    },

    # ── simulated_user6 (veg, gain weight, 2500 cal) ───────────────────────────
    {
        "id": "mp_sim_user6_01",
        "user_id": "simulated_user6",
        "date": "2025-03-07",
        "target_calories": 2500,
        "target_macros": {"carbs": 300, "protein": 110, "fat": 72},
        "breakfast": {
            "name": "Aloo Paratha (2) + Curd (200ml) + Lassi (250ml)",
            "calories": 620,
            "carbs": 84,
            "protein": 18,
            "fat": 20,
        },
        "lunch": {
            "name": "Dal Makhani + 3 Butter Rotis + Paneer Masala + Rice (1 cup)",
            "calories": 870,
            "carbs": 96,
            "protein": 38,
            "fat": 28,
        },
        "dinner": {
            "name": "Chole Bhature (1 serving) + Raita",
            "calories": 640,
            "carbs": 80,
            "protein": 22,
            "fat": 20,
        },
        "snack": {
            "name": "Peanut Chikki (2 pcs) + Banana",
            "calories": 340,
            "carbs": 48,
            "protein": 10,
            "fat": 10,
        },
    },

    # ── simulated_user7 (non-veg, diabetic+hypertension, sedentary, 1700 cal)
    {
        "id": "mp_sim_user7_01",
        "user_id": "simulated_user7",
        "date": "2025-03-08",
        "target_calories": 1700,
        "target_macros": {"carbs": 185, "protein": 95, "fat": 48},
        "breakfast": {
            "name": "Vegetable Oats Porridge (low sodium) + 1 Boiled Egg",
            "calories": 295,
            "carbs": 42,
            "protein": 14,
            "fat": 6,
        },
        "lunch": {
            "name": "Grilled Chicken (100g) + 2 Multigrain Rotis + Moong Dal + Salad",
            "calories": 560,
            "carbs": 60,
            "protein": 34,
            "fat": 14,
        },
        "dinner": {
            "name": "Baked Fish (100g) + Stir-fried Spinach + 1 Bajra Roti",
            "calories": 440,
            "carbs": 36,
            "protein": 32,
            "fat": 12,
        },
        "snack": {
            "name": "Roasted Flaxseeds + Green Tea",
            "calories": 120,
            "carbs": 8,
            "protein": 5,
            "fat": 8,
        },
    },

    # ── simulated_user8 (vegan, active, maintain, 2100 cal) ───────────────────
    {
        "id": "mp_sim_user8_01",
        "user_id": "simulated_user8",
        "date": "2025-03-08",
        "target_calories": 2100,
        "target_macros": {"carbs": 270, "protein": 90, "fat": 58},
        "breakfast": {
            "name": "Vegetable Poha + Coconut Milk Smoothie",
            "calories": 420,
            "carbs": 64,
            "protein": 10,
            "fat": 12,
        },
        "lunch": {
            "name": "Rajma + 2 Rotis + Brown Rice (1 cup) + Salad",
            "calories": 680,
            "carbs": 90,
            "protein": 28,
            "fat": 14,
        },
        "dinner": {
            "name": "Tofu Palak Curry + 2 Rotis + Sautéed Mushrooms",
            "calories": 600,
            "carbs": 68,
            "protein": 28,
            "fat": 18,
        },
        "snack": {
            "name": "Trail Mix (pumpkin seeds, sunflower seeds, raisins)",
            "calories": 280,
            "carbs": 32,
            "protein": 10,
            "fat": 14,
        },
    },

    # ── simulated_user9 (veg + nut-free, diabetic, sedentary, 1720 cal) ───────
    {
        "id": "mp_sim_user9_01",
        "user_id": "simulated_user9",
        "date": "2025-03-09",
        "target_calories": 1720,
        "target_macros": {"carbs": 195, "protein": 85, "fat": 48},
        "breakfast": {
            "name": "Moong Dal Chilla (2) + Green Chutney + Herbal Tea",
            "calories": 290,
            "carbs": 38,
            "protein": 14,
            "fat": 6,
        },
        "lunch": {
            "name": "Bajra Roti (2) + Palak Dal + Sabzi + Low-fat Curd",
            "calories": 550,
            "carbs": 70,
            "protein": 24,
            "fat": 14,
        },
        "dinner": {
            "name": "Mixed Vegetable Soup + Vegetable Khichdi (small bowl)",
            "calories": 460,
            "carbs": 60,
            "protein": 18,
            "fat": 12,
        },
        "snack": {
            "name": "Cucumber + Carrot sticks + Lemon water",
            "calories": 80,
            "carbs": 16,
            "protein": 2,
            "fat": 1,
        },
    },

    # ── simulated_user10 (non-veg, gain weight, active, 2700 cal) ─────────────
    {
        "id": "mp_sim_user10_01",
        "user_id": "simulated_user10",
        "date": "2025-03-09",
        "target_calories": 2700,
        "target_macros": {"carbs": 310, "protein": 135, "fat": 75},
        "breakfast": {
            "name": "Omelette (3 eggs) + 2 Parathas + Banana + Milk (250ml)",
            "calories": 670,
            "carbs": 72,
            "protein": 34,
            "fat": 22,
        },
        "lunch": {
            "name": "Egg Curry (3 eggs) + Chicken (100g) + 2 Rotis + Rice (1 cup) + Dal",
            "calories": 950,
            "carbs": 100,
            "protein": 54,
            "fat": 26,
        },
        "dinner": {
            "name": "Grilled Chicken (200g) + 2 Rotis + Sabzi + Curd",
            "calories": 680,
            "carbs": 60,
            "protein": 48,
            "fat": 18,
        },
        "snack": {
            "name": "Protein Ladoo (homemade besan, 2 pcs) + Milk",
            "calories": 420,
            "carbs": 48,
            "protein": 16,
            "fat": 16,
        },
    },

    # ── simulated_user4 – Day 2 (variety) ─────────────────────────────────────
    {
        "id": "mp_sim_user4_02",
        "user_id": "simulated_user4",
        "date": "2025-03-07",
        "target_calories": 2900,
        "target_macros": {"carbs": 330, "protein": 145, "fat": 80},
        "breakfast": {
            "name": "Masala Omelette (4 eggs) + Brown Bread (3 slices) + Banana",
            "calories": 700,
            "carbs": 74,
            "protein": 38,
            "fat": 24,
        },
        "lunch": {
            "name": "Mutton Keema (150g) + 3 Rotis + Arhar Dal + Salad",
            "calories": 980,
            "carbs": 108,
            "protein": 54,
            "fat": 30,
        },
        "dinner": {
            "name": "Chicken Soup (hearty) + 2 Rotis + Paneer Bhurji",
            "calories": 720,
            "carbs": 72,
            "protein": 44,
            "fat": 22,
        },
        "snack": {
            "name": "Full-fat Milk Banana Shake + Roasted Peanuts",
            "calories": 480,
            "carbs": 54,
            "protein": 18,
            "fat": 18,
        },
    },

    # ── test_user3 – Day 2 (variety) ──────────────────────────────────────────
    {
        "id": "mp_test_user3_02",
        "user_id": "test_user3",
        "date": "2025-03-02",
        "target_calories": 2800,
        "target_macros": {"carbs": 320, "protein": 140, "fat": 78},
        "breakfast": {
            "name": "Aloo Paratha (3) + Butter + Lassi (large) + Banana (2)",
            "calories": 720,
            "carbs": 100,
            "protein": 20,
            "fat": 24,
        },
        "lunch": {
            "name": "Fish Curry (200g) + White Rice (2 cups) + Dal + Salad",
            "calories": 880,
            "carbs": 110,
            "protein": 48,
            "fat": 22,
        },
        "dinner": {
            "name": "Egg Curry (4 eggs) + 3 Rotis + Raita + Kheer (small)",
            "calories": 810,
            "carbs": 96,
            "protein": 38,
            "fat": 24,
        },
        "snack": {
            "name": "Peanut Butter Toast (2 slices) + Milk (300ml)",
            "calories": 450,
            "carbs": 46,
            "protein": 20,
            "fat": 18,
        },
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# BONUS: MEAL LOGS
# ═══════════════════════════════════════════════════════════════════════════════

meal_logs = [
    {
        "id": "log_test_user1_01",
        "user_id": "test_user1",
        "meal_plan_id": "mp_test_user1_01",
        "date": "2025-03-01",
        "meal_type": "breakfast",
        "meal_name": "Oats Upma with vegetables",
        "calories_consumed": 315,
        "carbs": 46,
        "protein": 10,
        "fat": 8,
        "logged_at": datetime(2025, 3, 1, 8, 30, 0),
        "notes": "Felt light and energetic after breakfast",
    },
    {
        "id": "log_test_user2_01",
        "user_id": "test_user2",
        "meal_plan_id": "mp_test_user2_01",
        "date": "2025-03-01",
        "meal_type": "lunch",
        "meal_name": "Grilled Chicken + 2 Rotis + Stir-fried Vegetables",
        "calories_consumed": 565,
        "carbs": 54,
        "protein": 37,
        "fat": 14,
        "logged_at": datetime(2025, 3, 1, 13, 15, 0),
        "notes": "Had slightly less chicken than plan",
    },
    {
        "id": "log_sim_user1_01",
        "user_id": "simulated_user1",
        "meal_plan_id": "mp_sim_user1_01",
        "date": "2025-03-05",
        "meal_type": "dinner",
        "meal_name": "Chana Masala + 2 Rotis + Salad",
        "calories_consumed": 580,
        "carbs": 78,
        "protein": 25,
        "fat": 14,
        "logged_at": datetime(2025, 3, 5, 20, 0, 0),
        "notes": "Added extra coriander, tasted great",
    },
    {
        "id": "log_sim_user4_01",
        "user_id": "simulated_user4",
        "meal_plan_id": "mp_sim_user4_01",
        "date": "2025-03-06",
        "meal_type": "breakfast",
        "meal_name": "Paratha + Curd + 3 Egg Omelette + Milk",
        "calories_consumed": 692,
        "carbs": 78,
        "protein": 35,
        "fat": 23,
        "logged_at": datetime(2025, 3, 6, 7, 30, 0),
        "notes": "Had on schedule, post-morning run",
    },
    {
        "id": "log_sim_user7_01",
        "user_id": "simulated_user7",
        "meal_plan_id": "mp_sim_user7_01",
        "date": "2025-03-08",
        "meal_type": "snack",
        "meal_name": "Roasted Flaxseeds + Green Tea",
        "calories_consumed": 120,
        "carbs": 8,
        "protein": 5,
        "fat": 8,
        "logged_at": datetime(2025, 3, 8, 16, 0, 0),
        "notes": "Kept sodium low as advised",
    },
    {
        "id": "log_test_user5_01",
        "user_id": "test_user5",
        "meal_plan_id": "mp_test_user5_01",
        "date": "2025-03-01",
        "meal_type": "lunch",
        "meal_name": "Chicken Curry + 3 Rotis + Salad + Lassi",
        "calories_consumed": 750,
        "carbs": 82,
        "protein": 37,
        "fat": 20,
        "logged_at": datetime(2025, 3, 1, 13, 0, 0),
        "notes": "Very satisfying. Skipped lassi.",
    },
    {
        "id": "log_sim_user3_01",
        "user_id": "simulated_user3",
        "meal_plan_id": "mp_sim_user3_01",
        "date": "2025-03-06",
        "meal_type": "lunch",
        "meal_name": "Bajra Roti + Lauki Dal + Methi Sabzi",
        "calories_consumed": 510,
        "carbs": 66,
        "protein": 20,
        "fat": 12,
        "logged_at": datetime(2025, 3, 6, 12, 45, 0),
        "notes": "Blood sugar stable after meal",
    },
    {
        "id": "log_sim_user2_01",
        "user_id": "simulated_user2",
        "meal_plan_id": "mp_sim_user2_01",
        "date": "2025-03-05",
        "meal_type": "dinner",
        "meal_name": "Chicken Salad + 1 Roti + Vegetable Soup",
        "calories_consumed": 510,
        "carbs": 42,
        "protein": 37,
        "fat": 14,
        "logged_at": datetime(2025, 3, 5, 19, 30, 0),
        "notes": "Very low sodium diet maintained",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# BONUS: DAILY RATINGS
# ═══════════════════════════════════════════════════════════════════════════════

daily_ratings = [
    {
        "id": "rating_test_user1_01",
        "user_id": "test_user1",
        "meal_plan_id": "mp_test_user1_01",
        "date": "2025-03-01",
        "overall_rating": 4,
        "energy_level": 4,
        "hunger_level": 2,
        "meal_satisfaction": 4,
        "adherence_score": 0.95,
        "feedback": "Felt full and satisfied. The upma was delicious.",
        "rated_at": datetime(2025, 3, 1, 22, 0, 0),
    },
    {
        "id": "rating_test_user2_01",
        "user_id": "test_user2",
        "meal_plan_id": "mp_test_user2_01",
        "date": "2025-03-01",
        "overall_rating": 3,
        "energy_level": 3,
        "hunger_level": 3,
        "meal_satisfaction": 4,
        "adherence_score": 0.88,
        "feedback": "Good variety. Slightly hungry after dinner. Blood sugar was normal.",
        "rated_at": datetime(2025, 3, 1, 21, 30, 0),
    },
    {
        "id": "rating_sim_user1_01",
        "user_id": "simulated_user1",
        "meal_plan_id": "mp_sim_user1_01",
        "date": "2025-03-05",
        "overall_rating": 5,
        "energy_level": 5,
        "hunger_level": 1,
        "meal_satisfaction": 5,
        "adherence_score": 1.0,
        "feedback": "Excellent plan! Felt energized all day. The tofu stir-fry was amazing.",
        "rated_at": datetime(2025, 3, 5, 22, 0, 0),
    },
    {
        "id": "rating_sim_user4_01",
        "user_id": "simulated_user4",
        "meal_plan_id": "mp_sim_user4_01",
        "date": "2025-03-06",
        "overall_rating": 5,
        "energy_level": 5,
        "hunger_level": 1,
        "meal_satisfaction": 4,
        "adherence_score": 0.97,
        "feedback": "Great calorie intake. Gym performance was peak today.",
        "rated_at": datetime(2025, 3, 6, 22, 30, 0),
    },
    {
        "id": "rating_sim_user7_01",
        "user_id": "simulated_user7",
        "meal_plan_id": "mp_sim_user7_01",
        "date": "2025-03-08",
        "overall_rating": 4,
        "energy_level": 3,
        "hunger_level": 3,
        "meal_satisfaction": 4,
        "adherence_score": 0.92,
        "feedback": "Low sodium plan helping with BP. A bit hungry by evening.",
        "rated_at": datetime(2025, 3, 8, 21, 0, 0),
    },
    {
        "id": "rating_test_user3_01",
        "user_id": "test_user3",
        "meal_plan_id": "mp_test_user3_01",
        "date": "2025-03-01",
        "overall_rating": 5,
        "energy_level": 5,
        "hunger_level": 1,
        "meal_satisfaction": 5,
        "adherence_score": 0.99,
        "feedback": "Perfect for bulking! Felt very strong at the gym. Biryani was spot on.",
        "rated_at": datetime(2025, 3, 1, 22, 0, 0),
    },
    {
        "id": "rating_sim_user3_01",
        "user_id": "simulated_user3",
        "meal_plan_id": "mp_sim_user3_01",
        "date": "2025-03-06",
        "overall_rating": 4,
        "energy_level": 3,
        "hunger_level": 2,
        "meal_satisfaction": 4,
        "adherence_score": 0.95,
        "feedback": "Good plan for my conditions. BP and sugar both stable today.",
        "rated_at": datetime(2025, 3, 6, 21, 0, 0),
    },
    {
        "id": "rating_sim_user2_01",
        "user_id": "simulated_user2",
        "meal_plan_id": "mp_sim_user2_01",
        "date": "2025-03-05",
        "overall_rating": 4,
        "energy_level": 4,
        "hunger_level": 2,
        "meal_satisfaction": 4,
        "adherence_score": 0.93,
        "feedback": "Very balanced. Low sodium lunches are making a difference.",
        "rated_at": datetime(2025, 3, 5, 21, 30, 0),
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# FIRESTORE UPLOAD FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def upload_users():
    print("[2/6] Uploading users...")
    batch = db.batch()
    for uid, data in users.items():
        ref = db.collection("users").document(uid)
        batch.set(ref, data)
    batch.commit()
    print(f"  ✅ {len(users)} users uploaded.")

def upload_meal_plans():
    print("[3/6] Uploading meal_plans...")
    batch = db.batch()
    for plan in meal_plans:
        plan_copy = plan.copy()
        doc_id = plan_copy.pop("id")
        ref = db.collection("meal_plans").document(doc_id)
        batch.set(ref, plan_copy)
    batch.commit()
    print(f"  ✅ {len(meal_plans)} meal plans uploaded.")

def upload_meal_logs():
    print("[4/6] Uploading meal_logs...")
    batch = db.batch()
    for log in meal_logs:
        log_copy = log.copy()
        doc_id = log_copy.pop("id")
        ref = db.collection("meal_logs").document(doc_id)
        batch.set(ref, log_copy)
    batch.commit()
    print(f"  ✅ {len(meal_logs)} meal logs uploaded.")

def upload_daily_ratings():
    print("[5/6] Uploading daily_ratings...")
    batch = db.batch()
    for rating in daily_ratings:
        rating_copy = rating.copy()
        doc_id = rating_copy.pop("id")
        ref = db.collection("daily_ratings").document(doc_id)
        batch.set(ref, rating_copy)
    batch.commit()
    print(f"  ✅ {len(daily_ratings)} daily ratings uploaded.")

def verify_upload():
    print("[6/6] Verifying upload...")
    u_count = len(list(db.collection("users").stream()))
    mp_count = len(list(db.collection("meal_plans").stream()))
    ml_count = len(list(db.collection("meal_logs").stream()))
    dr_count = len(list(db.collection("daily_ratings").stream()))
    print(f"  📊 users        → {u_count} documents")
    print(f"  📊 meal_plans   → {mp_count} documents")
    print(f"  📊 meal_logs    → {ml_count} documents")
    print(f"  📊 daily_ratings→ {dr_count} documents")
    print("\n🎉 All test data populated successfully!")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  NutriLens – Firestore Test Data Populator")
    print("=" * 60)

    # Allow skipping certain collections via CLI flags
    args = sys.argv[1:]
    skip_verify = "--no-verify" in args

    upload_users()
    upload_meal_plans()
    upload_meal_logs()
    upload_daily_ratings()

    if not skip_verify:
        verify_upload()
