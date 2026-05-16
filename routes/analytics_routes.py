# routes/analytics_routes.py
from flask import Blueprint, request
from utils.response_utils import success, error
from services.rating_service import rating_service
from utils.auth_middleware import firebase_auth_required, get_user_id_from_request

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route("/generate-daily-rating", methods=["POST"])
@firebase_auth_required
def generate_rating():
    data = request.get_json(force=True)
    user_id  = get_user_id_from_request()
    date_str = data.get("date")

    if not user_id or not date_str:
        return error("userId and date are required")

    rating_data, err = rating_service.generate_daily_rating(user_id, date_str)
    if err:
        return error(err, 400)

    return success(rating_data, "Daily rating generated")

@analytics_bp.route("/get-analytics", methods=["POST"])
@firebase_auth_required
def get_analytics():
    data = request.get_json(force=True)
    user_id = get_user_id_from_request()
    if not user_id:
        return error("userId required")

    from repositories.tracker_repository import tracker_repo
    analytics_ref = tracker_repo.db.collection("analytics").document(user_id)
    doc = analytics_ref.get()

    result = {
        "streak_count": 0,
        "weekly_summary": {},
        "monthly_summary": {},
        "badges": []
    }
    if doc.exists:
        result = doc.to_dict()

    return success(result, "Analytics retrieved")

@analytics_bp.route("/get-daily-ratings", methods=["GET"])
@firebase_auth_required
def get_daily_ratings():
    user_id = get_user_id_from_request()
    if not user_id:
        return error("userId required")
    from repositories.tracker_repository import tracker_repo
    from config.config import COL_DAILY_RATINGS
    docs = tracker_repo.db.collection(COL_DAILY_RATINGS).where("userId", "==", user_id).stream()
    ratings = [d.to_dict() for d in docs]
    return success({"ratings": ratings}, "Ratings fetched")

@analytics_bp.route("/recalculate-analytics", methods=["POST"])
@firebase_auth_required
def recalculate_analytics():
    data = request.get_json(force=True)
    user_id = get_user_id_from_request()
    if not user_id:
        return error("userId required")
    from services.streak_service import streak_service
    streak_data = streak_service.calculate_streak(user_id)
    return success(streak_data, "Analytics recalculated")
