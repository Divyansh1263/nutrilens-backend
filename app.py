from flask import Flask, jsonify
from flask_cors import CORS
import os
import firebase_admin
from firebase_admin import credentials, firestore

from utils.response_utils import error
from utils.logger import app_logger
from dev_store import (
    set_meals_cache,
    save_meals_cache_to_disk,
    load_meals_cache_from_disk,
    load_users_cache_from_disk,
)

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
# We load MEALS into memory for the NLP pipeline cold-start
from ai.nlp_pipeline import init_pipeline
from ai.smart_swap_knn import SmartSwapKNN

try:
    db = firestore.client()
    meal_docs = db.collection("meals").stream()
    MEALS = []
    for d in meal_docs:
        m = d.to_dict()
        m["id"] = d.id
        MEALS.append(m)
        
    print(f"\nMeals loaded: {len(MEALS)}")
    if len(MEALS) == 0:
        app_logger.warning("WARNING: Zero meals fetched from Firestore db.collection('meals')! Ensure collection exists.")
        
    init_pipeline(MEALS, db=db)
    # Provide an in-memory fallback cache for local dev when Firestore is rate-limited.
    set_meals_cache(MEALS)
    try:
        save_meals_cache_to_disk()
    except Exception as e:
        app_logger.warning(f"Could not persist meals cache locally: {e}")
    app_logger.info(f"Loaded {len(MEALS)} meals into NLP memory pipeline.")
except Exception as e:
    app_logger.error(f"Failed to preload memory components: {e}")
    # If Firestore is rate-limited, try to continue using cached meals from disk
    try:
        if load_meals_cache_from_disk():
            from ai.nlp_pipeline import init_pipeline
            from dev_store import MEALS_CACHE
            init_pipeline(MEALS_CACHE, db=None)
            app_logger.warning("Loaded meals from local disk cache (Firestore unavailable).")
        else:
            # Last-resort: seed meals so local app remains usable for demos.
            from dev_store import ensure_meals_available, MEALS_CACHE
            ensure_meals_available()
            init_pipeline(MEALS_CACHE, db=None)
            app_logger.warning("Loaded seeded meals cache (Firestore unavailable).")
    except Exception as e2:
        app_logger.warning(f"Could not load meals cache from disk: {e2}")

    # Load local user cache so login/profile can work when Firestore is throttled
    try:
        load_users_cache_from_disk()
    except Exception:
        pass

# ISSUE 3: Initialize meal caching to reduce Firestore reads by 80-90%
print("[Firestore Optimization] Initializing in-memory meal cache on startup...")
try:
    from repositories.meal_repository import _initialize_cache
    _initialize_cache()
    print("[Firestore Optimization] Cache initialization complete")
except Exception as e:
    print(f"[Firestore Optimization] Cache initialization warning: {e}")

# Load KNN model for meal replacement suggestions
print("[KNN Model] Loading SmartSwapKNN model...")
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
# 4. GLOBAL ERROR HANDLING & UTILS
# ---------------------------------------------------------
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
    app.run(debug=True, port=5000)
        
