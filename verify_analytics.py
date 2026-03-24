import requests
import json
import argparse
import sys
import time
from datetime import date

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    
def print_pass(text):
    print(f"{Colors.OKGREEN}[PASS]: {text}{Colors.ENDC}")

def print_fail(text):
    print(f"{Colors.FAIL}[FAIL]: {text}{Colors.ENDC}")

def print_header(text):
    print(f"\n{Colors.HEADER}=== {text} ==={Colors.ENDC}")

USER_ID = "verify_analytics_user"
BASE_URL = "http://localhost:8080"

def test_1_get_analytics_defaults():
    print_header("Test 1: Get Analytics (Defaults)")
    r = requests.get(f"{BASE_URL}/get-analytics", params={"user_id": USER_ID})
    if r.status_code == 200:
        data = r.json()
        if data["success"] and data["data"]["streak_count"] == 0:
            print_pass("Returns default structure correctly")
            return True
        else:
            print_fail(f"Invalid structure: {data}")
    else:
        print_fail(f"Status {r.status_code}: {r.text}")
    return False

def test_2_get_daily_ratings():
    print_header("Test 2: Get Daily Ratings")
    # Prerequisite: Create a rating (via existing API logic if possible, or just check empty)
    # We will just check empty response structure first
    r = requests.get(f"{BASE_URL}/get-daily-ratings", params={"user_id": USER_ID, "limit": 2})
    if r.status_code == 200:
        data = r.json()
        if data["success"] and isinstance(data["data"], list):
            print_pass("Returns list structure")
            return True
        else:
            print_fail(f"Invalid structure: {data}")
    else:
        print_fail(f"Status {r.status_code}: {r.text}")
    return False

def test_3_get_meal_plans():
    print_header("Test 3: Get Meal Plans (Hydrated)")
    r = requests.get(f"{BASE_URL}/get-meal-plans", params={"user_id": USER_ID})
    if r.status_code == 200:
        data = r.json()
        if data["success"] and isinstance(data["data"], list):
            print_pass("Returns list structure (Hydrated check requires data)")
            return True
        else:
            print_fail(f"Invalid structure: {data}")
    else:
        print_fail(f"Status {r.status_code}: {r.text}")
    return False

def test_4_submit_feedback():
    print_header("Test 4: Submit Feedback")
    payload = {
        "user_id": USER_ID,
        "meal_id": "test_meal_1",
        "score": 1
    }
    r = requests.post(f"{BASE_URL}/submit-feedback", json=payload)
    if r.status_code == 200:
        if r.json()["success"]:
            print_pass("Feedback submitted successfully")
            
            # Negative test
            payload["score"] = 5
            r2 = requests.post(f"{BASE_URL}/submit-feedback", json=payload)
            if r2.status_code == 400:
                print_pass("Correctly rejected invalid score")
                return True
            else:
                print_fail("Failed to reject invalid score")
        else:
             print_fail(f"Success=False: {r.json()}")
    else:
        print_fail(f"Status {r.status_code}: {r.text}")
    return False

def test_5_recalculate_analytics():
    print_header("Test 5: Recalculate Analytics")
    payload = {"user_id": USER_ID}
    r = requests.post(f"{BASE_URL}/recalculate-analytics", json=payload)
    if r.status_code == 200:
        data = r.json()
        if data["success"] and "streak_count" in data["data"]:
            print_pass("Recalculation successful")
            return True
        else:
            print_fail(f"Invalid response: {data}")
    else:
         print_fail(f"Status {r.status_code}: {r.text}")
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    args = parser.parse_args()
    BASE_URL = args.url.rstrip("/")
    
    steps = [
        test_1_get_analytics_defaults,
        test_2_get_daily_ratings,
        test_3_get_meal_plans,
        test_4_submit_feedback,
        test_5_recalculate_analytics
    ]
    
    passed = 0
    for step in steps:
        if step(): passed += 1
        
    print(f"\nPassed {passed}/{len(steps)}")
    if passed == len(steps):
        sys.exit(0)
    else:
        sys.exit(1)
