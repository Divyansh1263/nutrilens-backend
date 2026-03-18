# validators/user_validator.py

def validate_user_registration(data):
    """Validate registration payload."""
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return False, "Email and password are required"
    return True, ""

def validate_user_login(data):
    """Validate login payload."""
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return False, "Email and password are required"
    return True, ""
