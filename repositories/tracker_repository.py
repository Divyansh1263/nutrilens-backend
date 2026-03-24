# repositories/tracker_repository.py
import firebase_admin
from firebase_admin import firestore
from config.config import (
    COL_MEAL_LOGS, COL_MEAL_PLANS, COL_DAILY_RATINGS, 
    COL_DAILY_TRACKER_SUMMARY, COL_USER_MEAL_HISTORY
)
from dev_store import (
    log_meal as mem_log_meal,
    get_logs_by_date as mem_get_logs_by_date,
    update_log_quantity as mem_update_log_quantity,
    delete_log as mem_delete_log,
    save_plan as mem_save_plan,
    get_plan_by_date as mem_get_plan_by_date,
)

class TrackerRepository:
    def __init__(self):
        try:
            self.db = firestore.client()
        except ValueError:
            firebase_admin.initialize_app()
            self.db = firestore.client()

    # ------------------ LOGS ------------------
    def log_meal(self, log_data):
        """Create a new meal log."""
        try:
            doc_ref = self.db.collection(COL_MEAL_LOGS).document()
            log_data["logId"] = doc_ref.id
            doc_ref.set(log_data)
            # Mirror into in-memory store for dev/demo tracker UI.
            # This keeps tracker-summary responsive even if subsequent Firestore reads fail.
            try:
                mem_log_meal(log_data)
            except Exception:
                pass
            return doc_ref.id
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return mem_log_meal(log_data)
            raise

    def get_log(self, log_id):
        """Fetch a specific log by ID."""
        try:
            doc = self.db.collection(COL_MEAL_LOGS).document(log_id).get()
            if doc.exists:
                data = doc.to_dict()
                data["logId"] = doc.id
                return data
            return None
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                # Not used heavily in UI; return None in fallback mode.
                return None
            raise

    def update_log_quantity(self, log_id, updates):
        """Update an existing meal log (quantity, macros)."""
        try:
            doc_ref = self.db.collection(COL_MEAL_LOGS).document(log_id)
            if doc_ref.get().exists:
                doc_ref.update(updates)
                return True
            return False
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return mem_update_log_quantity(log_id, updates)
            raise
        
    def delete_log(self, log_id):
        """Delete an existing log by ID."""
        try:
            doc_ref = self.db.collection(COL_MEAL_LOGS).document(log_id)
            if doc_ref.get().exists:
                doc_ref.delete()
                return True
            return False
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return mem_delete_log(log_id)
            raise

    def get_logs_by_date(self, user_id, date_str):
        """Get all logs for a user on a specific date."""
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            
            # Avoid composite index by filtering just user_id, testing dates natively
            docs = self.db.collection(COL_MEAL_LOGS)\
                .where(filter=FieldFilter("userId", "==", user_id))\
                .stream()
                
            logs = []
            for d in docs:
                data = d.to_dict()
                if data.get("date") == date_str:
                    data["id"] = d.id
                    logs.append(data)
                    
            return logs
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return mem_get_logs_by_date(user_id, date_str)
            raise

    def get_weekly_logs(self, user_id, start_date, end_date):
        # Placeholder for new method, actual implementation would go here
        pass

    # ------------------ PLANS ------------------
    def get_plan_by_date(self, user_id, date_str):
        try:
            docs = self.db.collection(COL_MEAL_PLANS)\
                .where("userId", "==", user_id)\
                .where("date", "==", date_str).limit(1).stream()
            for d in docs:
                p = d.to_dict()
                p["planId"] = d.id
                return p
            return None
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return mem_get_plan_by_date(user_id, date_str)
            raise
        
    def save_plan(self, plan_data):
        try:
            self.db.collection(COL_MEAL_PLANS).add(plan_data)
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                mem_save_plan(plan_data)
                return
            raise
        # Mirror into in-memory store for dev/demo stability
        try:
            mem_save_plan(plan_data)
        except Exception:
            pass

    def get_recent_plans(self, user_id, limit=3):
        """Fetch last N days of meal plans for variety control."""
        try:
            docs = self.db.collection(COL_MEAL_PLANS)\
                .where("userId", "==", user_id)\
                .order_by("date", direction=firestore.Query.DESCENDING)\
                .limit(limit).stream()
            
            plans = []
            for d in docs:
                plans.append(d.to_dict())
            return plans
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return []
            raise

    # ------------------ HISTORY (Personalization) ------------------
    def update_user_meal_frequency(self, user_id, meal_name, date_str):
        doc_id = f"{user_id}_{meal_name.replace(' ', '_')}"
        doc_ref = self.db.collection(COL_USER_MEAL_HISTORY).document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_ref.update({
                "count": firestore.Increment(1),
                "last_eaten": date_str
            })
        else:
            doc_ref.set({
                "userId": user_id,
                "meal_name": meal_name,
                "count": 1,
                "last_eaten": date_str
            })

    def get_user_meal_history(self, user_id):
        """Fetch frequency counts for preference scoring."""
        try:
            docs = self.db.collection(COL_USER_MEAL_HISTORY)\
                .where("userId", "==", user_id).stream()
            history = {}
            for d in docs:
                data = d.to_dict()
                history[data["meal_name"]] = data
            return history
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return {}
            raise

# Singleton instance
tracker_repo = TrackerRepository()
