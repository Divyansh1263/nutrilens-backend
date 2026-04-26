# routes/auth_routes.py
from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_admin import firestore
from repositories.user_repository import user_repo
from validators.user_validator import validate_user_registration, validate_user_login
from utils.response_utils import success, error
from utils.logger import app_logger

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    
    # 1. Validate
    is_valid, msg = validate_user_registration(data)
    if not is_valid:
        return error(msg, 400)
        
    email = data.get("email")
    password = data.get("password")
    user_id = data.get("userId")
    
    if not user_id:
        user_id = email.replace("@", "_").replace(".", "_")

    password_hash = generate_password_hash(password)

    user_profile = {
        "userId": user_id,
        "email": email,
        "password_hash": password_hash,
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

    # Cache user locally so development/test still works when Firestore is rate limited.
    try:
        from dev_store import save_user_to_cache
        save_user_to_cache(user_profile)
    except Exception:
        pass

    # 3. Call Service/Repo
    user_repo.create_user(user_id, user_profile)
    app_logger.info(f"User registered: {user_id}")
    
    # 4. Return
    return success({
        "userId": user_id,
        "email": email
    }, "User registered successfully")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    
    # 1. Validate
    is_valid, msg = validate_user_login(data)
    if not is_valid:
        return error(msg, 400)
        
    email = data.get("email")
    password = data.get("password")

    # 3. Call Repo
    # Use repository method with cache fallback to handle Firestore quota limits.
    user_doc = user_repo.get_user_by_email(email)
        
    if user_doc and "password_hash" in user_doc:
        if check_password_hash(user_doc["password_hash"], password):
            user_doc.pop("password_hash", None)
            app_logger.info(f"User logged in: {user_doc.get('userId')}")
            return success({
                "user": user_doc
            }, "Login successful")
            
    return error("Invalid email or password", 401)


@auth_bp.route("/user-profile", methods=["GET"])
def get_profile():
    user_id = request.args.get("userId")
    if not user_id:
        return error("userId required", 400)
        
    profile = user_repo.get_user_profile(user_id)
    if not profile:
        return error("User not found", 404)

    # FIX 5: Map Firestore snake_case fields to camelCase for Flutter frontend.
    # Firestore stores: activity_level, dietary_goal, weight_loss_speed
    # Flutter expects: activityLevel, dietaryGoal, weightLossSpeed
    # We do NOT rename Firestore fields — only transform the API response.
    mapped = {
        **profile,  # include all existing fields as-is
        "activityLevel":   profile.get("activity_level"),
        "dietaryGoal":     profile.get("dietary_goal"),
        "weightLossSpeed": profile.get("weight_loss_speed"),
        # Flutter Account page fields
        "goal":            profile.get("dietary_goal"),
    }
    # Remove the snake_case duplicates to keep the response clean
    for key in ("activity_level", "dietary_goal", "weight_loss_speed"):
        mapped.pop(key, None)

    return success(mapped)


# TODO (Fix F — audit): When a PATCH /user-profile endpoint is added to allow
# users to update weight/goal/activity, call:
#
#   from utils.calorie_utils import invalidate_user_target_cache
#   invalidate_user_target_cache(user_id)
#
# immediately after saving the updated profile to Firestore.
# Without this, the 10-minute user_target_cache will serve stale calorie
# targets until it naturally expires.
