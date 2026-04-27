# routes/auth_routes.py
from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash
from firebase_admin import firestore
import firebase_admin.auth
from repositories.user_repository import user_repo
from validators.user_validator import validate_user_registration, validate_user_login
from utils.response_utils import success, error
from utils.logger import app_logger
from utils.auth_middleware import firebase_auth_optional, get_user_id_from_request

auth_bp = Blueprint('auth', __name__)


def _derive_user_id(email: str) -> str:
    """
    Derive a stable userId from email — MUST stay consistent with the
    original format so all existing Firestore documents remain valid.
    """
    return email.replace("@", "_").replace(".", "_")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True)

    # 1. Validate
    is_valid, msg = validate_user_registration(data)
    if not is_valid:
        return error(msg, 400)

    email = data.get("email")
    password = data.get("password")
    user_id = data.get("userId") or _derive_user_id(email)

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
        "activityLevel": data.get("activityLevel", data.get("activity_level")),
        "goal": data.get("goal", data.get("dietary_goal")),
        "weight_loss_speed": data.get("weight_loss_speed"),
        "dietary_restrictions": data.get("dietary_restrictions", {}),
        "health_conditions": data.get("health_conditions", {}),
        "onboarding_completed": True,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    # Cache locally for dev / Firestore quota fallback
    try:
        from dev_store import save_user_to_cache
        save_user_to_cache(user_profile)
    except Exception:
        pass

    user_repo.create_user(user_id, user_profile)
    app_logger.info("User registered: %s", user_id)

    return success({"userId": user_id, "email": email}, "User registered successfully")


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN  (email + password)
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)

    # 1. Validate inputs
    is_valid, msg = validate_user_login(data)
    if not is_valid:
        return error(msg, 400)

    email = data.get("email")
    password = data.get("password")

    # 2. Fetch user from Firestore (with cache fallback)
    user_doc = user_repo.get_user_by_email(email)

    if not user_doc or "password_hash" not in user_doc:
        return error("Invalid email or password", 401)

    if not check_password_hash(user_doc["password_hash"], password):
        return error("Invalid email or password", 401)

    # Password is correct — strip the hash before returning
    user_doc.pop("password_hash", None)
    user_id = user_doc.get("userId")
    app_logger.info("User logged in: %s", user_id)

    # ── STEP 2: Issue Firebase Custom Token ───────────────────────────────────
    # The custom token uses the existing email-derived userId as the Firebase
    # uid.  This means Firebase uid == Firestore document key == no migration.
    firebase_custom_token: str | None = None
    try:
        raw_token = firebase_admin.auth.create_custom_token(user_id)
        # create_custom_token returns bytes on some SDK versions
        firebase_custom_token = (
            raw_token.decode("utf-8")
            if isinstance(raw_token, bytes)
            else raw_token
        )
        app_logger.info("[auth] custom token issued for uid=%s", user_id)
    except Exception as e:
        # Non-fatal: old APK doesn't use this token at all
        app_logger.warning("[auth] could not issue custom token for %s: %s", user_id, e)

    return success(
        {
            "user": user_doc,
            "firebaseCustomToken": firebase_custom_token,
        },
        "Login successful",
    )


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SIGN-IN  (new users / Google-signed users)
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/google-login", methods=["POST"])
@firebase_auth_optional          # verifies idToken → sets request.firebase_uid
def google_login():
    """
    Called by Flutter after FirebaseAuth.signInWithCredential(googleCredential).

    Flow:
      1. Flutter obtains idToken from Google Sign-In.
      2. Flutter signs in with Firebase → FirebaseAuth issues its own idToken.
      3. Flutter sends that idToken in Authorization: Bearer header.
      4. This endpoint verifies it, creates/fetches the Firestore user profile.

    For NEW Google users:  userId = firebase_uid  (e.g. "Vj3kL9mNpQr...")
    For EXISTING users who previously signed up with email/password:
      Their Firebase uid (set via signInWithCustomToken) is already
      their email-derived string — so no conflict occurs.
    """
    data = request.get_json(force=True) or {}

    # B1 FIX: require a verified token — NEVER trust the body uid alone.
    # @firebase_auth_optional sets request.firebase_uid only when the token
    # is cryptographically valid. If absent or invalid, reject the request.
    firebase_uid = request.firebase_uid
    if not firebase_uid:
        return error(
            "Google login requires a valid Firebase idToken "
            "(Authorization: Bearer <idToken>)", 401
        )

    # Use the verified uid from the token — body fields are metadata only
    google_uid   = firebase_uid
    email        = data.get("email", "")
    display_name = data.get("displayName", "")
    photo_url    = data.get("photoURL", "")

    # Check if a Firestore profile already exists for this uid
    existing = user_repo.get_user_profile(google_uid)

    if existing:
        existing.pop("password_hash", None)
        app_logger.info("[auth] Google login — existing user uid=%s", google_uid)
        return success({"user": existing, "isNewUser": False}, "Google login successful")

    # New Google user — create a minimal profile
    user_profile = {
        "userId":                google_uid,
        "email":                 email,
        "name":                  display_name,
        "photoURL":              photo_url,
        "onboarding_completed":  False,   # Flutter will redirect to onboarding
        "auth_provider":         "google",
        "created_at":            firestore.SERVER_TIMESTAMP,
        "updated_at":            firestore.SERVER_TIMESTAMP,
    }

    try:
        from dev_store import save_user_to_cache
        save_user_to_cache(user_profile)
    except Exception:
        pass

    user_repo.create_user(google_uid, user_profile)
    app_logger.info("[auth] Google login — new user created uid=%s", google_uid)

    return success({"user": user_profile, "isNewUser": True}, "Google login successful")


# ─────────────────────────────────────────────────────────────────────────────
# GET USER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/user-profile", methods=["GET"])
@firebase_auth_optional
def get_profile():
    # Prefer token-derived uid; fall back to query param (old APK)
    user_id = get_user_id_from_request()
    if not user_id:
        return error("userId required", 400)

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


# ─────────────────────────────────────────────────────────────────────────────
# UPDATE USER PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/update-profile", methods=["PATCH"])
@firebase_auth_optional
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
