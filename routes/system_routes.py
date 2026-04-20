# routes/system_routes.py
from flask import Blueprint, request
from utils.response_utils import success, error
from repositories.user_repository import user_repo
from utils.calorie_utils import get_or_calculate_user_targets
from utils.date_utils import get_today_str

system_bp = Blueprint('system', __name__)

@system_bp.route("/", methods=["GET"])
@system_bp.route("/health", methods=["GET"])
def health_check():
    return success({"status": "healthy"}, "NutriLens API is running")

@system_bp.route("/daily-greeting", methods=["GET"])
def daily_greeting():
    user_id = request.args.get("userId")
    if not user_id:
        return error("userId required")
        
    profile = user_repo.get_user_profile(user_id)
    if not profile:
        return error("User not found", 404)
        
    name = profile.get("name", "User")
    today = get_today_str()
    targets = get_or_calculate_user_targets(user_id, today)
    
    cal = targets.get("calories", 2000)
    
    return success({
        "message": f"Good Morning {name} 👋",
        "target_calories": cal
    })

@system_bp.route("/calculate-target", methods=["POST"])
def calculate_target():
    data = request.get_json(force=True)
    user_id = data.get("userId")
    if not user_id:
        return error("userId required")
    
    date_str = data.get("date") or get_today_str()
    
    profile = user_repo.get_user_profile(user_id)
    if not profile:
        return error("User not found", 404)
    
    targets = get_or_calculate_user_targets(user_id, date_str)
    return success(targets, "Targets calculated")

@system_bp.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    data = request.get_json(force=True)
    user_id = data.get("userId")
    message = data.get("message")
    rating = data.get("rating")
    
    if not user_id or not message:
        return error("userId and message are required")
        
    from firebase_admin import firestore
    
    doc_data = {
        "userId": user_id,
        "message": message,
        "rating": rating,
        "created_at": firestore.SERVER_TIMESTAMP
    }
    
    try:
        db = firestore.client()
        db.collection("feedback").add(doc_data)
        return success({}, "Feedback submitted successfully")
    except Exception as e:
        return error(str(e), 500)


# TASK 6 – Admin endpoint to force-reload the meals cache from Firestore
@system_bp.route("/refresh-cache", methods=["POST"])
def refresh_cache():
    """
    Force-reload the in-memory meals cache from Firestore.
    Useful after bulk meal uploads without restarting the server.

    Example:
        POST /refresh-cache
    """
    try:
        from meals_cache import refresh_meals_cache, MEALS_CACHE, MEALS_SOURCE
        refresh_meals_cache()
        return success(
            {"meals_loaded": len(MEALS_CACHE), "source": MEALS_SOURCE},
            "Meals cache refreshed successfully"
        )
    except Exception as e:
        return error(f"Cache refresh failed: {e}", 500)
