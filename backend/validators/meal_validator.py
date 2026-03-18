# validators/meal_validator.py

def validate_log_meal(data):
    """Validate payload for manual meal logging."""
    user_id = data.get("userId")
    date_str = data.get("date")
    meal_name = data.get("mealName")
    quantity = data.get("quantity", 1)
    meal_type = data.get("mealType")

    if not all([user_id, date_str, meal_name]):
        return False, "userId, date, and mealName are required fields"
        
    try:
        qty = float(quantity)
        if qty <= 0:
            return False, "quantity must be positive"
    except ValueError:
        return False, "quantity must be a number"

    valid_types = ["Breakfast", "Lunch", "Dinner", "Snack", "breakfast", "lunch", "dinner", "snack"]
    if meal_type and meal_type not in valid_types:
        return False, "Invalid mealType provided"

    return True, ""

def validate_update_log(data):
    """Validate payload to update log quantity."""
    log_id = data.get("logId") or data.get("log_id")
    quantity = data.get("quantity")
    
    if not log_id:
        return False, "log_id or logId is required"
    if quantity is None:
         return False, "quantity is required"
    
    try:
        qty = float(quantity)
        if qty <= 0:
            return False, "quantity must be positive"
    except ValueError:
        return False, "quantity must be a number"
        
    return True, ""

def validate_delete_log(data):
    """Validate payload to delete a log."""
    log_id = data.get("logId") or data.get("log_id")
    if not log_id:
        return False, "log_id or logId is required"
    return True, ""
    
def validate_generate_plan(data):
    user_id = data.get("userId")
    date_str = data.get("date") # Optional but good practice
    
    if not user_id:
        return False, "userId is required"
    return True, ""
