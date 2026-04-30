# services/rating_service.py
from services.tracker_service import tracker_service
from config.config import COL_DAILY_RATINGS
import firebase_admin
from firebase_admin import firestore

class RatingService:
    def __init__(self):
        try:
             self.db = firestore.client()
        except ValueError:
             pass

    def generate_daily_rating(self, user_id, date_str):
        print("STEP: entering function")
        print(f"DATA: generate_daily_rating(user_id={user_id}, date_str={date_str})")
        try:
            summary = tracker_service.get_tracker_summary(user_id, date_str)
            
            def safe_float(val):
                try: return float(val or 0)
                except (ValueError, TypeError): return 0.0

            target_cal = safe_float(summary.get("targets", {}).get("calories"))
            total_cal = safe_float(summary.get("consumed", {}).get("calories"))
            
            if total_cal == 0:
                 return {"rating": 0, "message": "No meals logged yet"}, None
                 
            if target_cal == 0:
                 return {"rating": 0, "message": "Targets are not set"}, None
                 
            diff = abs(total_cal - target_cal)
            percentage_off = (diff / target_cal) * 100 if target_cal > 0 else 0
            
            # Simple Logic stub simulating Random Forest Model rating behavior
            star_rating = 5
            if percentage_off > 10: star_rating = 4
            if percentage_off > 20: star_rating = 3
            if percentage_off > 30: star_rating = 2
            if percentage_off > 40: star_rating = 1
            
            feedback = "Great job! Your intake stayed close to target."
            if star_rating < 3:
                 feedback = "You missed your targets quite a bit today. Let's try to improve tomorrow!"
                 
            # Macro Deviations
            t_prot = safe_float(summary.get("targets", {}).get("protein"))
            c_prot = safe_float(summary.get("consumed", {}).get("protein"))
            
            rating_data = {
                "userId": user_id,
                "date": date_str,
                "star_rating": star_rating,
                "feedback": feedback,
                "calories_consumed": round(total_cal, 1),
                "target_diff": round(diff, 1),
                "macro_deviation": {
                     "protein": "High" if c_prot > t_prot * 1.1 else "Low" if c_prot < t_prot * 0.9 else "Good",
                },
                "generated_at": firestore.SERVER_TIMESTAMP
            }

            # Save to DB
            self.db.collection(COL_DAILY_RATINGS).document(f"{user_id}_{date_str}").set(rating_data)
            
            # Format for API
            rating_data["generated_at"] = str(date_str)
            return rating_data, ""
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print("ERROR TRACE:", error_trace)
            return {"rating": 0, "message": "Failed to generate rating", "error": str(e), "trace": error_trace}, "Exception"

rating_service = RatingService()
