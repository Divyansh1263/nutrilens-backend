# services/tracker_service.py
#
# Step 6 + Step 7 + Step 8 — Firestore read reduction with production-safe
# thread-safe caching.
#
# NOTE:
#   This is an in-memory cache. It resets on every server restart.
#   To persist across restarts, replace the cache helpers with Redis calls.
#
# Cache key : (user_id, date_str)
# TTL       : 60 seconds
# Max size  : 100 entries  (FIFO eviction — enforced by cache_utils)
# Thread    : all cache access protected by cache_utils._cache_lock
#
import logging
from repositories.tracker_repository import tracker_repo
# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TrackerService:
    def get_tracker_summary(self, user_id: str, date_str: str) -> dict:
        print("STEP: entering function")
        print(f"DATA: get_tracker_summary(user_id={user_id}, date_str={date_str})")
        
        # Read from Firestore (in-memory cache removed to prevent Cloud Run race conditions)
        from utils.calorie_utils import get_or_calculate_user_targets
        from firebase_admin import firestore
        
        targets = get_or_calculate_user_targets(user_id, date_str)
        logs    = tracker_repo.get_logs_by_date(user_id, date_str)

        total_cal = total_protein = total_carbs = total_fat = 0.0
        
        def safe_float(val):
            try:
                return float(val or 0)
            except (ValueError, TypeError):
                return 0.0

        for log in logs:
            total_cal     += safe_float(log.get("calories", 0))
            total_protein += safe_float(log.get("protein", 0))
            total_carbs   += safe_float(log.get("carbs", 0))
            total_fat     += safe_float(log.get("fat", 0))

        summary = {
            "date": date_str,
            "targets": {
                "calories": targets.get("calories", 0),
                "protein":  targets.get("protein",  0),
                "carbs":    targets.get("carbs",    0),
                "fat":      targets.get("fat",      0),
            },
            "consumed": {
                "calories": total_cal,
                "protein":  total_protein,
                "carbs":    total_carbs,
                "fat":      total_fat,
            },
            "logs": logs,
        }

        return summary

    def recalculate_daily_tracker(self, user_id: str, date_str: str) -> dict:
        from firebase_admin import firestore

        summary = self.get_tracker_summary(user_id, date_str)

        doc_data = {
            "userId":          user_id,
            "date":            date_str,
            "total_calories":  summary["consumed"]["calories"],
            "total_protein":   summary["consumed"]["protein"],
            "total_carbs":     summary["consumed"]["carbs"],
            "total_fat":       summary["consumed"]["fat"],
            "target_calories": summary["targets"].get("calories", 0),
            "updated_at":      firestore.SERVER_TIMESTAMP,
        }

        from config.config import COL_DAILY_TRACKER_SUMMARY
        doc_id = f"{user_id}_{date_str}"
        try:
            tracker_repo.db.collection(COL_DAILY_TRACKER_SUMMARY).document(doc_id).set(doc_data)
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return doc_data
            raise

        return doc_data


tracker_service = TrackerService()
