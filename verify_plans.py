import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import firebase_admin
from firebase_admin import credentials, firestore
if not firebase_admin._apps:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
from meals_cache import load_meals_cache
load_meals_cache()

from services.meal_generator_service import meal_generator_service
from repositories.tracker_repository import tracker_repo

test_profiles = [
    {'userId': 't1', 'goal': 'lose_weight', 'is_vegetarian': True, 'is_vegan': False, 'target_calories': 1500, 'target_protein': 80},
    {'userId': 't2', 'goal': 'muscle_gain', 'is_vegetarian': True, 'is_vegan': False, 'target_calories': 2500, 'target_protein': 140},
    {'userId': 't3', 'goal': 'maintenance', 'is_vegetarian': False, 'is_vegan': False, 'target_calories': 2000, 'target_protein': 100, 'health_conditions': {'diabetes': True}},
    {'userId': 't4', 'goal': 'maintenance', 'is_vegetarian': False, 'is_vegan': True, 'target_calories': 1800, 'target_protein': 70},
    {'userId': 't5', 'goal': 'muscle_gain', 'is_vegetarian': False, 'is_vegan': False, 'target_calories': 2800, 'target_protein': 160}
]

def mock_get_profile(uid):
    for p in test_profiles:
        if p['userId'] == uid:
            return p
    return test_profiles[0]

tracker_repo.get_profile = mock_get_profile

for p in test_profiles:
    print(f'\n--- Testing {p["userId"]} ({p["goal"]}, vegan={p["is_vegan"]}, veg={p["is_vegetarian"]}) ---')
    plan, err = meal_generator_service.generate_daily_plan(p['userId'], '2026-05-16')
    if err:
        print('ERROR:', err)
        continue
    c = plan.get('actual_calories')
    pr = plan.get('actual_protein')
    tc = p['target_calories']
    tpr = p['target_protein']
    print(f'Calories: {c} / {tc} ({c/tc:.0%}) | Protein: {pr} / {tpr} ({pr/tpr:.0%})')
    for slot in ['breakfast', 'lunch', 'snack', 'dinner']:
        items = [i.get('mealName') for i in plan.get('breakfast', [])] # Wait! plan slots are top level now?
        # Let's check plan dict keys:
        if "meals" in plan:
            items = [i.get('mealName') for i in plan.get('meals', {}).get(slot, [])]
        else:
            items = [i.get('mealName') for i in plan.get(slot, [])]
        print(f'  {slot.capitalize()}: {", ".join(items)}')
