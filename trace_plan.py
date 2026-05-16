import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

from meals_cache import load_meals_cache
load_meals_cache()

from services.meal_generator_service import MealGeneratorService
from repositories.tracker_repository import tracker_repo

def trace():
    svc = MealGeneratorService()
    # Mock user profile
    profile = {
        "userId": "test_user_for_trace",
        "gender": "male",
        "age": 25,
        "height": 175,
        "weight": 70,
        "activityLevel": "sedentary",
        "goal": "maintenance",
        "dietType": "vegan",
        "is_vegan": True,
        "is_vegetarian": True,
        "target_calories": 2000,
        "target_protein": 100,
        "is_gluten_free": False,
        "is_nut_free": False
    }

    # we need to mock tracker_repo.get_profile 
    def mock_get_profile(uid):
        return profile
    
    tracker_repo.get_profile = mock_get_profile

    plan, err = svc.generate_daily_plan("test_user_for_trace", "2026-05-16")
    
    print("PLAN:")
    print(json.dumps(plan, indent=2))
    print(f"ERR: {err}")
    
trace()
