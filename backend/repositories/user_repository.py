# repositories/user_repository.py
import firebase_admin
from firebase_admin import firestore
from config.config import COL_USERS, COL_DAILY_TARGETS
from dev_store import USERS_CACHE, get_user_from_cache, save_user_to_cache, load_users_cache_from_disk

class UserRepository:
    def __init__(self):
        try:
            self.db = firestore.client()
        except ValueError:
            firebase_admin.initialize_app()
            self.db = firestore.client()

    def get_user_profile(self, user_id):
        try:
            doc = self.db.collection(COL_USERS).document(user_id).get()
            if doc.exists:
                user = doc.to_dict()
                # Cache for offline/dev fallback
                try:
                    save_user_to_cache(user)
                except Exception:
                    pass
                return user
            return None
        except Exception as e:
            # Graceful fallback when Firestore quota is exceeded or temporarily unavailable.
            if "Quota exceeded" in str(e) or "429" in str(e):
                # Attempt to load from local cache first
                if not USERS_CACHE:
                    load_users_cache_from_disk()
                cached = get_user_from_cache(user_id)
                if cached:
                    return cached
                # Minimal synthetic profile so UI has something to render.
                return {
                    "userId": user_id,
                    "email": f"{user_id}@example.com",
                    "name": user_id.split("_")[0].capitalize() if isinstance(user_id, str) else "User",
                    "height": None,
                    "weight": None,
                    "goal": "Maintain Weight",
                    "activity_level": "Moderate",
                }
            raise

    def get_user_by_email(self, email):
        """Fetch a user by email with a cache fallback when Firestore is unavailable."""
        try:
            docs = self.db.collection(COL_USERS).where("email", "==", email).limit(1).stream()
            for d in docs:
                user = d.to_dict()
                # Cache for offline/dev fallback
                try:
                    save_user_to_cache(user)
                except Exception:
                    pass
                return user
            return None
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                if not USERS_CACHE:
                    load_users_cache_from_disk()
                # Search cached users for email match
                for u in USERS_CACHE.values():
                    if u.get("email") == email:
                        return u
                return None
            raise

    def create_user(self, user_id, user_data):
        self.db.collection(COL_USERS).document(user_id).set(user_data)
        
    def get_daily_target(self, user_id, date_str):
        doc_id = f"{user_id}_{date_str}"
        doc = self.db.collection(COL_DAILY_TARGETS).document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
        
    def save_daily_target(self, user_id, date_str, target_data):
        doc_id = f"{user_id}_{date_str}"
        self.db.collection(COL_DAILY_TARGETS).document(doc_id).set(target_data)

# Singleton instance
user_repo = UserRepository()
