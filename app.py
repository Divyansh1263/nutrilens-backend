from flask import Flask, jsonify
from flask_cors import CORS
import os
import firebase_admin
from firebase_admin import credentials, firestore

from utils.response_utils import error
from utils.logger import app_logger
from dev_store import load_users_cache_from_disk

FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "nutrilens-b5e81")
FIREBASE_STORAGE_BUCKET = os.environ.get(
    "FIREBASE_STORAGE_BUCKET", "nutrilens-b5e81.firebasestorage.app"
)


def _load_firebase_credential():
    service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
    if service_account_path:
        if os.path.exists(service_account_path):
            return credentials.Certificate(service_account_path)
        raise RuntimeError(
            f"FIREBASE_SERVICE_ACCOUNT_PATH points to a missing file: {service_account_path}"
        )

    # Backward compatibility: treat legacy env var as a file path only.
    legacy_service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if legacy_service_account_path:
        if os.path.exists(legacy_service_account_path):
            return credentials.Certificate(legacy_service_account_path)
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT is set but does not point to a valid file. "
            "Use FIREBASE_SERVICE_ACCOUNT_PATH with a Render Secret File path."
        )

    possible_keys = ["serviceAccountKey.json", "d:/nutrilens/backend/serviceAccountKey.json"]
    key_path = next((key for key in possible_keys if os.path.exists(key)), None)
    if key_path:
        return credentials.Certificate(key_path)

    raise RuntimeError(
        "Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT_PATH "
        "(recommended for Render Secret Files) to your service account JSON file path."
    )

# ---------------------------------------------------------
# 1. INITIALIZE APP & CONFIG
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)

try:
    cred = _load_firebase_credential()
except Exception as e:
    raise RuntimeError(f"Firebase credential loading failed: {e}") from e


try:
    firebase_app = firebase_admin.get_app()
except ValueError:
    try:
        firebase_app = firebase_admin.initialize_app(
            cred,
            {
                "projectId": FIREBASE_PROJECT_ID,
                "storageBucket": FIREBASE_STORAGE_BUCKET,
            },
        )
    except Exception as e:
        raise RuntimeError(f"Firebase initialization failed: {e}") from e

if firebase_app.project_id and firebase_app.project_id != FIREBASE_PROJECT_ID:
    raise RuntimeError(
        f"Firebase app project mismatch. Expected {FIREBASE_PROJECT_ID}, got {firebase_app.project_id}."
    )

app_logger.info(
    "Firebase initialized successfully for project %s (storage bucket: %s)",
    firebase_app.project_id,
    FIREBASE_STORAGE_BUCKET,
)

# ---------------------------------------------------------
# 2. STARTUP PRE-LOADING (Global Models & NLP Pipeline)
# ---------------------------------------------------------
# TASK 3: Load meals ONCE into global in-memory cache before any route fires.
from meals_cache import load_meals_cache, MEALS_CACHE as _MEALS_CACHE_REF
from ai.nlp_pipeline import init_pipeline
from ai.smart_swap_knn import SmartSwapKNN

print("[cache-init] Loading meals into global in-memory cache …")
try:
    load_meals_cache()
except Exception as _e:
    app_logger.error("[cache-init] load_meals_cache failed: %s", _e)

from meals_cache import MEALS_CACHE as MEALS  # re-import after load
print(f"[cache-init] {len(MEALS)} meals ready in memory (source: "
      f"{__import__('meals_cache').MEALS_SOURCE})")

if not MEALS:
    app_logger.warning(
        "[cache-init] Meals cache is empty after startup — "
        "NLP pipeline will use seed meals."
    )

# Initialise the NLP pipeline with the in-memory meals list
try:
    db = firestore.client()
except Exception:
    db = None

try:
    init_pipeline(MEALS, db=db)
except Exception as _e:
    app_logger.error("[startup] NLP pipeline init failed: %s", _e)

# Load local user cache so login/profile can work when Firestore is throttled
try:
    load_users_cache_from_disk()
except Exception:
    pass

# Load KNN model for meal replacement suggestions
print("[KNN Model] Loading SmartSwapKNN model …")
try:
    knn_model = SmartSwapKNN()
    knn_model.load("models/knn_meal_swap.joblib")
    print("[KNN Model] KNN model loaded successfully")
except Exception as e:
    print(f"[KNN Model] Warning: Could not load KNN model: {e}")
    knn_model = None

# If this index is missing, /generate-meal-plan will return a 400 error
# with a URL to auto-create the index. Create it in Firebase Console:
#   Firestore → Indexes → Composite → Add Index
# ---------------------------------------------------------
app_logger.warning(
    "REMINDER: Firestore composite index required — "
    "Collection: 'meal_plans', Fields: userId ASC, date DESC. "
    "Create it in Firebase Console if not already done."
)


# ---------------------------------------------------------
# 3. REGISTER BLUEPRINTS (Service-Based Architecture)
# ---------------------------------------------------------
from routes.auth_routes import auth_bp
from routes.meal_routes import meal_bp
from routes.tracker_routes import tracker_bp
from routes.analytics_routes import analytics_bp
from routes.system_routes import system_bp

app.register_blueprint(auth_bp)
app.register_blueprint(meal_bp)
app.register_blueprint(tracker_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(system_bp)

# ---------------------------------------------------------
# 4. ROOT HEALTH-CHECK & GLOBAL ERROR HANDLING
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "NutriLens Backend Running",
        "service": "AI Diet Planner",
        "version": "v1"
    })


@app.errorhandler(Exception)
def handle_exception(e):
    app_logger.error(f"Unhandled Server Error: {e}")
    return error(str(e), 500)

@app.errorhandler(404)
def resource_not_found(e):
    return error("Resource not found", 404)
    
@app.route("/routes")
def list_routes():
    return {
        "routes":[str(rule) for rule in app.url_map.iter_rules()]
    }

@app.route("/routes-debug")
def routes_debug():
    return {
        str(rule): list(rule.methods)
        for rule in app.url_map.iter_rules()
    }


@app.route("/firebase-debug")
def firebase_debug():
    current_app = firebase_admin.get_app()
    return {
        "expected_project_id": FIREBASE_PROJECT_ID,
        "connected_project_id": current_app.project_id,
        "storage_bucket": FIREBASE_STORAGE_BUCKET,
        "credential_project_id": getattr(cred, "project_id", None),
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
