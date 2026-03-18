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
        summary = tracker_service.get_tracker_summary(user_id, date_str)
        
        target_cal = summary.get("targets", {}).get("calories") or 0
        total_cal = summary.get("consumed", {}).get("calories") or 0
        
        if total_cal == 0:
             return {"rating": 0, "message": "No meals logged yet"}, None
             
        if target_cal == 0:
             return {"rating": 0, "message": "Targets are not set"}, None
             
        try:
             diff = abs(total_cal - target_cal)
             percentage_off = (diff / target_cal) * 100 if target_cal > 0 else 0
        except Exception:
             return {"rating": 0, "message": "Targets issue prevented rating math block"}, None
             
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
        t_prot = summary.get("targets", {}).get("protein") or 0
        c_prot = summary.get("consumed", {}).get("protein") or 0
        
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

rating_service = RatingService()
