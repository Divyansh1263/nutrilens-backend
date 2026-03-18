# ai/meal_patterns.py
# Realistic Indian meal patterns + portion rules
#
# This module defines WHAT a realistic meal looks like structurally,
# beyond the old template system which just had generic slots.
# Each pattern specifies exact slot types, compatible food groups,
# and realistic portion presets.

# ==============================================================================
# 1. MEAL PATTERNS — Realistic structures for Indian meals
# ==============================================================================
# Each pattern defines:
#   slots:        ordered list of {role, group, required}
#   cuisine:      list of compatible cuisines
#   constraints:  rules to prevent bad combos (max_heavy, max_carb_base, etc.)

MEAL_PATTERNS = {
    "Breakfast": [
        {
            "name": "North_Indian_Breakfast",
            "cuisine": ["north_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": "protein", "required": False, "label": "protein_side"},
                {"role": "drink", "group": None, "required": False, "label": "drink"},
            ],
            "max_items": 3,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
        {
            "name": "South_Indian_Breakfast",
            "cuisine": ["south_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": None, "required": True, "label": "condiment"},
                {"role": "drink", "group": None, "required": False, "label": "drink"},
            ],
            "max_items": 3,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
        {
            "name": "Western_Breakfast",
            "cuisine": ["western"],
            "slots": [
                {"role": "main", "group": None, "required": True, "label": "carb_base"},
                {"role": "side", "group": "fruit", "required": False, "label": "fruit"},
                {"role": "drink", "group": None, "required": False, "label": "drink"},
            ],
            "max_items": 3,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
    ],

    "Lunch": [
        {
            "name": "Roti_Thali",
            "cuisine": ["north_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": "protein", "required": True, "label": "protein_curry"},
                {"role": "side", "group": "vegetable", "required": True, "label": "dry_sabzi"},
                {"role": "side", "group": "dairy", "required": False, "label": "condiment"},
            ],
            "max_items": 5,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 1},
        },
        {
            "name": "Rice_Dal_Meal",
            "cuisine": ["north_indian", "south_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": "protein", "required": True, "label": "protein_curry"},
                {"role": "side", "group": "vegetable", "required": False, "label": "dry_sabzi"},
                {"role": "side", "group": "dairy", "required": False, "label": "condiment"},
            ],
            "max_items": 4,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 1},
        },
        {
            "name": "One_Pot_Meal",
            "cuisine": ["north_indian", "south_indian", "western", "chinese"],
            "slots": [
                {"role": "main", "group": None, "required": True, "label": "carb_base"},
                {"role": "side", "group": None, "required": False, "label": "condiment"},
            ],
            "max_items": 2,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
    ],

    "Dinner": [
        {
            "name": "Roti_Curry_Light",
            "cuisine": ["north_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": "protein", "required": True, "label": "protein_curry"},
                {"role": "side", "group": "vegetable", "required": False, "label": "dry_sabzi"},
            ],
            "max_items": 3,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 1},
        },
        {
            "name": "South_Indian_Dinner",
            "cuisine": ["south_indian"],
            "slots": [
                {"role": "main", "group": "grain", "required": True, "label": "carb_base"},
                {"role": "side", "group": "protein", "required": True, "label": "protein_curry"},
                {"role": "side", "group": None, "required": False, "label": "condiment"},
            ],
            "max_items": 3,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 1},
        },
        {
            "name": "Light_Dinner",
            "cuisine": ["north_indian", "south_indian", "western", "chinese"],
            "slots": [
                {"role": "main", "group": None, "required": True, "label": "carb_base"},
                {"role": "side", "group": None, "required": False, "label": "condiment"},
            ],
            "max_items": 2,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
    ],

    "Snack": [
        {
            "name": "Light_Snack",
            "cuisine": ["all"],
            "slots": [
                {"role": "main", "group": None, "required": True, "label": "snack_item"},
                {"role": "drink", "group": None, "required": False, "label": "drink"},
            ],
            "max_items": 2,
            "constraints": {"max_carb_base": 1, "max_heavy_curry": 0},
        },
    ],
}


# ==============================================================================
# 2. PORTION RULES — Realistic quantities per food type
# ==============================================================================
# Maps (food_group, meal_role, label) combinations to default quantities.
# The generator uses these instead of always defaulting to 1.

PORTION_RULES = {
    # Roti/Chapati/Paratha type items (grain + main)
    ("grain", "main", "carb_base"): {"min": 2, "max": 4, "default": 2},

    # Rice type items (grain + main)
    ("grain", "main", "one_pot"): {"min": 1, "max": 1, "default": 1},

    # Dal/Curry items (protein + side)
    ("protein", "side", "protein_curry"): {"min": 1, "max": 1, "default": 1},

    # Sabzi/Vegetable sides
    ("vegetable", "side", "dry_sabzi"): {"min": 1, "max": 1, "default": 1},

    # Dairy sides (curd, raita)
    ("dairy", "side", "condiment"): {"min": 1, "max": 1, "default": 1},

    # Drinks
    (None, "drink", "drink"): {"min": 1, "max": 1, "default": 1},

    # Snack items
    (None, "main", "snack_item"): {"min": 1, "max": 2, "default": 1},

    # Breakfast items (idli, dosa, etc.)
    ("grain", "main", "breakfast_main"): {"min": 2, "max": 3, "default": 2},
}


def get_portion(meal, slot_label):
    """
    Get the recommended portion for a meal in a given slot.

    Returns a quantity dict: {min, max, default}
    """
    group = meal.get("food_group", "grain").lower()
    role = meal.get("meal_role", "main").lower()

    # Try exact match
    key = (group, role, slot_label)
    if key in PORTION_RULES:
        return PORTION_RULES[key]

    # Try group+role match (any label)
    for (g, r, l), portion in PORTION_RULES.items():
        if g == group and r == role:
            return portion

    # Fallback default
    return {"min": 1, "max": 1, "default": 1}


# ==============================================================================
# 3. DERIVED TAGS — Infer sub-types from existing meal data
# ==============================================================================
# These help classify meals more precisely for pattern filling.

# Keywords indicating a "heavy" dish (curries, biryanis, etc.)
HEAVY_DISH_KEYWORDS = {
    "biryani", "pulao", "curry", "masala", "korma", "nihari",
    "rogan", "butter", "tikka", "mughlai", "hyderabadi",
    "dum", "keema",
}

# Keywords indicating a carb-base item
CARB_BASE_KEYWORDS = {
    "roti", "chapati", "naan", "paratha", "rice", "biryani",
    "pulao", "dosa", "idli", "upma", "poha", "bread", "pasta",
    "noodles", "puri", "kulcha", "bhatura", "appam", "puttu",
}

# Keywords indicating a condiment/light side
CONDIMENT_KEYWORDS = {
    "chutney", "pickle", "raita", "papad", "salad", "achaar",
    "curd", "buttermilk", "lassi",
}


def infer_derived_tag(meal):
    """
    Infer a derived tag for a meal based on its name and keywords.

    Returns one of:
        "carb_base", "protein_curry", "dry_sabzi",
        "condiment", "heavy_dish", "drink", "snack_item"
    """
    name = meal.get("mealName", "").lower()
    keywords = [k.lower() for k in meal.get("searchKeywords", [])]
    full_text = name + " " + " ".join(keywords)
    role = meal.get("meal_role", "main").lower()
    group = meal.get("food_group", "grain").lower()

    # Drinks
    if role == "drink":
        return "drink"

    # Condiments
    if any(k in full_text for k in CONDIMENT_KEYWORDS):
        return "condiment"

    # Heavy dishes
    if any(k in full_text for k in HEAVY_DISH_KEYWORDS):
        return "heavy_dish"

    # Carb base
    if any(k in full_text for k in CARB_BASE_KEYWORDS):
        return "carb_base"

    # Protein curry (protein food group + side role)
    if group == "protein":
        return "protein_curry"

    # Vegetable sides
    if group == "vegetable":
        return "dry_sabzi"

    # Default
    if role == "side":
        return "condiment"

    return "carb_base"
