# services/tracker_service.py
from repositories.tracker_repository import tracker_repo
from utils.calorie_utils import get_or_calculate_user_targets
from firebase_admin import firestore

class TrackerService:
    def get_tracker_summary(self, user_id, date_str):
        # 1. Fetch user targets
        targets = get_or_calculate_user_targets(user_id, date_str)
        
        # 2. Fetch logs
        logs = tracker_repo.get_logs_by_date(user_id, date_str)
        
        total_cal = total_protein = total_carbs = total_fat = 0
        for log in logs:
            total_cal += float(log.get("calories") or 0)
            total_protein += float(log.get("protein") or 0)
            total_carbs += float(log.get("carbs") or 0)
            total_fat += float(log.get("fat") or 0)
            
        return {
            "date": date_str,
            "targets": {
                "calories": targets.get("calories", 0),
                "protein": targets.get("protein", 0),
                "carbs": targets.get("carbs", 0),
                "fat": targets.get("fat", 0)
            },
            "consumed": {
                "calories": total_cal,
                "protein": total_protein,
                "carbs": total_carbs,
                "fat": total_fat
            },
            "logs": logs
        }
        
    def recalculate_daily_tracker(self, user_id, date_str):
        summary = self.get_tracker_summary(user_id, date_str)
        
        doc_data = {
            "userId": user_id,
            "date": date_str,
            "total_calories": summary["consumed"]["calories"],
            "total_protein": summary["consumed"]["protein"],
            "total_carbs": summary["consumed"]["carbs"],
            "total_fat": summary["consumed"]["fat"],
            "target_calories": summary["targets"].get("calories", 0),
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        from config.config import COL_DAILY_TRACKER_SUMMARY
        doc_id = f"{user_id}_{date_str}"
        try:
            tracker_repo.db.collection(COL_DAILY_TRACKER_SUMMARY).document(doc_id).set(doc_data)
        except Exception as e:
            # In dev/demo fallback mode, don't crash if Firestore is rate-limited.
            if "Quota exceeded" in str(e) or "429" in str(e):
                return doc_data
            raise
        
        return doc_data

tracker_service = TrackerService()
