# routes/auth_routes.py
#
# Google-only authentication routes.
# Custom email/password auth has been REMOVED (Phase 4 migration).
#
from flask import Blueprint, request
from firebase_admin import firestore
from repositories.user_repository import user_repo
from utils.response_utils import success, error
from utils.logger import app_logger
from utils.auth_middleware import firebase_auth_required, get_user_id_from_request

auth_bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# GOOGLE SIGN-IN  (sole authentication entry point)
# ---------------------------------------------------------------------------
@auth_bp.route("/google-login", methods=["POST"])
@firebase_auth_required
def google_login():
    """
    Called by Flutter after FirebaseAuth.signInWithCredential(googleCredential).

    Flow:
      1. Flutter obtains idToken from Google Sign-In.
      2. Flutter signs in with Firebase -> FirebaseAuth issues its own idToken.
      3. Flutter sends that idToken in Authorization: Bearer header.
      4. This endpoint verifies it, creates/fetches the Firestore user profile.

    userId = firebase_uid (e.g. "I8ydLGD6i7SKcq86LRh4oD3WcL83")
    """
    data = request.get_json(force=True) or {}

    # Token is verified by @firebase_auth_required — uid is guaranteed
    firebase_uid = request.firebase_uid
    email = data.get("email", "")
    display_name = data.get("displayName", "")
    photo_url = data.get("photoURL", "")

    # Check if a Firestore profile already exists for this uid
    existing = user_repo.get_user_profile(firebase_uid)

    if existing:
        existing.pop("password_hash", None)
        app_logger.info("[auth] Google login -- existing user uid=%s", firebase_uid)
        return success({"user": existing, "isNewUser": False}, "Google login successful")

    # New Google user -- create a minimal profile
    user_profile = {
        "userId": firebase_uid,
        "email": email,
        "name": display_name,
        "photoURL": photo_url,
        "onboarding_completed": False,
        "auth_provider": "google",
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    try:
        from dev_store import save_user_to_cache
        save_user_to_cache(user_profile)
    except Exception:
        pass

    user_repo.create_user(firebase_uid, user_profile)
    app_logger.info("[auth] Google login -- new user created uid=%s", firebase_uid)

    return success({"user": user_profile, "isNewUser": True}, "Google login successful")


# ---------------------------------------------------------------------------
# COMPLETE ONBOARDING (save profile data after onboarding screens)
# ---------------------------------------------------------------------------
@auth_bp.route("/complete-onboarding", methods=["POST"])
@firebase_auth_required
def complete_onboarding():
    """
    Called after onboarding screens are completed.
    Saves all profile data collected during onboarding.
    """
    data = request.get_json(force=True) or {}
    firebase_uid = request.firebase_uid

    update_fields = {}
    for field in ["name", "age", "gender", "height", "weight", "target_weight",
                  "activityLevel", "goal", "weight_loss_speed",
                  "dietary_restrictions", "health_conditions"]:
        if field in data:
            update_fields[field] = data[field]

    update_fields["onboarding_completed"] = True
    update_fields["updated_at"] = firestore.SERVER_TIMESTAMP

    try:
        db = firestore.client()
        db.collection("users").document(firebase_uid).update(update_fields)
        app_logger.info("[auth] Onboarding completed for uid=%s", firebase_uid)
    except Exception as e:
        app_logger.error("[auth] Onboarding save failed for uid=%s: %s", firebase_uid, e)
        return error("Failed to save onboarding data", 500)

    return success({"userId": firebase_uid, "onboarding_completed": True},
                   "Onboarding completed successfully")


# ---------------------------------------------------------------------------
# GET USER PROFILE
# ---------------------------------------------------------------------------
@auth_bp.route("/user-profile", methods=["GET"])
@firebase_auth_required
def get_profile():
    user_id = request.firebase_uid
    if not user_id:
        return error("Unauthorized", 401)

    profile = user_repo.get_user_profile(user_id)
    if not profile:
        return error("User not found", 404)

    # Map Firestore snake_case fields to camelCase for Flutter frontend.
    mapped = {
        **profile,
        "activityLevel":   profile.get("activityLevel", profile.get("activity_level")),
        "goal":            profile.get("goal", profile.get("dietary_goal")),
        "weightLossSpeed": profile.get("weight_loss_speed"),
    }
    for key in ("activity_level", "dietary_goal", "weight_loss_speed"):
        mapped.pop(key, None)
    # Never send the password hash to the client
    mapped.pop("password_hash", None)

    return success(mapped)


# ---------------------------------------------------------------------------
# UPDATE USER PROFILE
# ---------------------------------------------------------------------------
@auth_bp.route("/update-profile", methods=["PATCH"])
@firebase_auth_required
def update_profile():
    data = request.get_json()

    user_id = request.firebase_uid
    if not user_id:
        return {"success": False, "message": "Unauthorized"}, 401

    update_fields = {}

    for field in ["height", "weight", "activityLevel", "goal"]:
        if field in data:
            update_fields[field] = data[field]

    if not update_fields:
        return {"success": False, "message": "No valid fields"}, 400

    from firebase_admin import firestore
    db = firestore.client()
    db.collection("users").document(user_id).update(update_fields)
    
    app_logger.info(f"[profile] update user={user_id} data={update_fields}")
    
    try:
        from utils.calorie_utils import invalidate_user_target_cache
        invalidate_user_target_cache(user_id)
    except Exception as e:
        app_logger.error(f"[update-profile] Error invalidating cache: {e}")

    # Return the fields exactly as they were provided for frontend consumption
    return success(data)
