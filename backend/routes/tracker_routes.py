# routes/tracker_routes.py
from flask import Blueprint, request
from utils.response_utils import success, error
from services.tracker_service import tracker_service
from services.streak_service import streak_service

tracker_bp = Blueprint('tracker', __name__)

@tracker_bp.route("/tracker-summary", methods=["GET"])
def get_tracker_summary():
    user_id = request.args.get("userId")
    date_str = request.args.get("date")
    
    if not user_id or not date_str:
        return error("userId and date are required")
        
    summary = tracker_service.get_tracker_summary(user_id, date_str)
    
    # Return full summary with targets, consumed, and logs
    return success(summary)

@tracker_bp.route("/get-streak", methods=["GET"])
def get_streak():
    user_id = request.args.get("userId")
    if not user_id:
        return error("userId is required")
        
    streak_data = streak_service.get_user_streak(user_id)
    return success(streak_data)
