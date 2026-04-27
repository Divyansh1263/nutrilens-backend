# routes/tracker_routes.py
from flask import Blueprint, request
from utils.response_utils import success, error
from services.tracker_service import tracker_service
from services.streak_service import streak_service
from utils.auth_middleware import firebase_auth_optional, get_user_id_from_request

tracker_bp = Blueprint('tracker', __name__)

@tracker_bp.route("/tracker-summary", methods=["GET"])
@firebase_auth_optional
def get_tracker_summary():
    user_id = get_user_id_from_request()
    date_str = request.args.get("date")

    if not user_id or not date_str:
        return error("userId and date are required")

    summary = tracker_service.get_tracker_summary(user_id, date_str)

    # Return full summary with targets, consumed, and logs
    return success(summary)

@tracker_bp.route("/get-streak", methods=["GET"])
@firebase_auth_optional
def get_streak():
    user_id = get_user_id_from_request()
    if not user_id:
        return error("userId is required")

    streak_data = streak_service.get_user_streak(user_id)
    return success(streak_data)
