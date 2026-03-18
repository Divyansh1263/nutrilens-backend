# utils/calorie_utils.py
# (Abstracting base calculator functions if needed, otherwise defer to ai.target_calculator)
from ai.target_calculator import compute_base_targets, apply_calorie_banking
from repositories.user_repository import user_repo
from firebase_admin import firestore

def get_or_calculate_user_targets(user_id, date_str):
    """
    Fetch target from daily_targets. If not exists, calculate from profile, save, and return.
    """
    try:
        targets = user_repo.get_daily_target(user_id, date_str)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        raise
    
    if targets:
        return targets

    # Fallback Calculation
    try:
        user_profile = user_repo.get_user_profile(user_id)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        raise
    if not user_profile:
        # Emergency defaults if user doesn't exist
        return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        
    base = compute_base_targets(user_profile)
    # apply_calorie_banking requires db, we pass repo's db
    final = apply_calorie_banking(user_id, base, user_repo.db)
    
    target_data = {
        "userId": user_id,
        "date": date_str,
        **final,
        "generated_by": "ai",
        "created_at": firestore.SERVER_TIMESTAMP if hasattr(user_repo.db, 'collection') else None
    }
    # save
    try:
        user_repo.save_daily_target(user_id, date_str, target_data)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            # In dev fallback mode, skip persisting.
            return final
        raise
    
    return final
