# services/streak_service.py
from repositories.tracker_repository import tracker_repo
from datetime import datetime, timedelta

class StreakService:
    def get_user_streak(self, user_id):
        # Fetch all days with a meal logged for the user natively, to avoid complex index creation
        docs = tracker_repo.db.collection("daily_tracker_summary")\
             .where("userId", "==", user_id)\
             .stream()
             
        dates = set()
        for d in docs:
             dates.add(d.to_dict().get("date"))
             
        if not dates:
             return {"current_streak": 0, "longest_streak": 0}
             
        sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in dates], reverse=True)
        
        # Compute streak
        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        
        today = datetime.now().date()
        expected_date = today
        
        # Check if they logged today or yesterday
        if sorted_dates and (sorted_dates[0] == today or sorted_dates[0] == today - timedelta(days=1)):
             expected_date = sorted_dates[0]
        else:
             current_streak = 0
             expected_date = sorted_dates[0] if sorted_dates else None

        for dt in sorted_dates:
             if dt is None: continue
             if expected_date is not None and dt == expected_date:
                  temp_streak += 1
                  expected_date -= timedelta(days=1)
             else:
                  # Break in streak
                  if current_streak == 0 and temp_streak > 0: # Set current once
                       current_streak = temp_streak
                  temp_streak = 1 # start new
                  expected_date = dt - timedelta(days=1)
                  
             if temp_streak > longest_streak:
                  longest_streak = temp_streak
                  
        if current_streak == 0 and temp_streak > 0:
            current_streak = temp_streak
            
        return {
             "streak": current_streak
        }

streak_service = StreakService()
