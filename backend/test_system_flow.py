#!/usr/bin/env python3
"""
test_system_flow.py — NutriLens Full System Endpoint Test
=========================================================
Runs a complete end-to-end flow against a live backend server.
Start the server first:  python app.py

Usage:
    python test_system_flow.py
    python test_system_flow.py --base-url http://localhost:5000
"""

import requests
import json
import sys
import argparse
from datetime import datetime

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:5000"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

_PASS = "✅ PASS"
_FAIL = "❌ FAIL"
_SKIP = "⚠️  SKIP"

results = []

def h(title):
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print('─' * 55)

def check(label, response, expect_success=True, expect_keys=None):
    """Assert a response is success=true and optionally check for data keys."""
    ok = True
    try:
        body = response.json()
    except Exception:
        print(f"{_FAIL} [{label}] — non-JSON response: {response.text[:120]}")
        results.append((label, False))
        return None

    if response.status_code not in (200, 201):
        print(f"{_FAIL} [{label}] HTTP {response.status_code} — {body.get('message','')}")
        results.append((label, False))
        return body

    if expect_success and not body.get("success"):
        print(f"{_FAIL} [{label}] success=false — {body.get('message','')}")
        results.append((label, False))
        return body

    if expect_keys:
        data = body.get("data") or body
        missing = [k for k in expect_keys if k not in data]
        if missing:
            print(f"{_FAIL} [{label}] missing keys {missing} in data")
            results.append((label, False))
            return body

    print(f"{_PASS} [{label}]")
    results.append((label, True))
    return body


def run(base_url):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    uid = None
    token = None

    # ──────────────────────────────────────────
    # 0. HEALTH CHECK
    # ──────────────────────────────────────────
    h("0. Health Check")
    r = s.get(f"{base_url}/health")
    check("GET /health", r, expect_keys=["status"])

    # ──────────────────────────────────────────
    # 1. REGISTER
    # ──────────────────────────────────────────
    h("1. Register")
    test_email = f"testuser_{TODAY.replace('-','')}@nutrilens.test"
    r = s.post(f"{base_url}/register", json={
        "email": test_email,
        "password": "Test@12345",
        "name": "Test User",
        "age": 25,
        "gender": "male",
        "height": 170.0,
        "weight": 70.0,
        "targetWeight": 65.0,
        "activityLevel": "moderate",
        "goal": "lose_weight",
        "dietType": "non-veg"
    })
    body = check("POST /register", r)
    if body and body.get("data"):
        uid = body["data"].get("userId") or body["data"].get("uid")
        token = body["data"].get("token")
        print(f"     userId = {uid}")
    
    if not uid:
        print(f"{_SKIP} Registration failed or user exists — attempting login")

    # ──────────────────────────────────────────
    # 2. LOGIN
    # ──────────────────────────────────────────
    h("2. Login")
    r = s.post(f"{base_url}/login", json={
        "email": test_email,
        "password": "Test@12345"
    })
    body = check("POST /login", r)
    if body and body.get("data"):
        uid = uid or body["data"].get("userId") or body["data"].get("uid")
        token = token or body["data"].get("token")
        print(f"     userId = {uid}")

    if not uid:
        print(f"\n{_FAIL} Cannot proceed without userId. Check auth routes.")
        print_summary()
        sys.exit(1)

    # Set auth header if token present
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})

    # ──────────────────────────────────────────
    # 3. CALCULATE TARGET
    # ──────────────────────────────────────────
    h("3. Calculate Target")
    r = s.post(f"{base_url}/calculate-target", json={
        "userId": uid,
        "date": TODAY
    })
    body = check("POST /calculate-target", r, expect_keys=["calories", "protein", "carbs", "fat"])
    if body:
        data = body.get("data", {})
        print(f"     calories={data.get('calories')} protein={data.get('protein')} carbs={data.get('carbs')} fat={data.get('fat')}")

    # ──────────────────────────────────────────
    # 4. GENERATE MEAL PLAN
    # ──────────────────────────────────────────
    h("4. Generate Meal Plan")
    r = s.post(f"{base_url}/generate-meal-plan", json={
        "userId": uid,
        "date": TODAY
    })
    body = check("POST /generate-meal-plan", r)
    plan_data = body.get("data", {}) if body else {}
    if plan_data:
        meals = plan_data.get("meals", [])
        print(f"     meals in plan: {len(meals)}")

    # Test caching — same call should return same plan
    r2 = s.post(f"{base_url}/generate-meal-plan", json={"userId": uid})
    body2 = check("POST /generate-meal-plan (cached, no date)", r2)

    # ──────────────────────────────────────────
    # 5. ANALYZE MEAL NLP
    # ──────────────────────────────────────────
    h("5. Analyze Meal NLP (no log)")
    r = s.post(f"{base_url}/analyze-meal-nlp", json={
        "text": "I had 2 roti and a bowl of dal for lunch"
    })
    body = check("POST /analyze-meal-nlp", r)
    nlp_items = []
    if body and isinstance(body.get("data"), list):
        nlp_items = body["data"]
        for item in nlp_items[:2]:
            print(f"     {item.get('mealName')} — cal:{item.get('calories')} p:{item.get('protein')}")
    elif body:
        print(f"     WARN: data is not a list: {type(body.get('data'))}")

    # ──────────────────────────────────────────
    # 9. SEARCH FOOD (done early to get a real meal name for log-meal)
    # ──────────────────────────────────────────
    h("9. Search Food")
    real_meal_name = None
    r = s.get(f"{base_url}/search-food", params={"q": "rice"})
    body = check("GET /search-food?q=rice", r)
    if body:
        data = body.get("data", [])
        data = data if isinstance(data, list) else []
        print(f"     results: {len(data)} items")
        if data:
            first = data[0]
            real_meal_name = first.get("mealName") or first.get("name") or first.get("meal")
            print(f"     will use for log-meal: {real_meal_name}")

    # ──────────────────────────────────────────
    # 6. LOG MEAL — Manual mode
    # ──────────────────────────────────────────
    h("6. Log Meal (manual mode)")
    log_id = None
    meal_to_log = real_meal_name or "Rice"  # use real meal from search, fallback to Rice
    r = s.post(f"{base_url}/log-meal", json={
        "userId": uid,
        "mealName": meal_to_log,
        "quantity": 1,
        "mealType": "Lunch",
        "source": "manual",
        "date": TODAY
    })
    body = check(f"POST /log-meal ({meal_to_log})", r, expect_keys=["log_id"])
    if body and body.get("data"):
        log_id = body["data"].get("log_id")
        print(f"     log_id = {log_id}")

    # ──────────────────────────────────────────
    # 7. TRACKER SUMMARY
    # ──────────────────────────────────────────
    h("7. Tracker Summary")
    r = s.get(f"{base_url}/tracker-summary", params={"userId": uid, "date": TODAY})
    body = check("GET /tracker-summary", r, expect_keys=["targets", "consumed", "logs"])
    if body and body.get("data"):
        d = body["data"]
        consumed = d.get("consumed", {})
        targets = d.get("targets", {})
        logs = d.get("logs", [])
        print(f"     targets: cal={targets.get('calories')} | consumed: cal={consumed.get('calories')} | logs: {len(logs)}")

    # ──────────────────────────────────────────
    # 8. SWAP MEAL
    # ──────────────────────────────────────────
    h("8. Swap Meal")
    if log_id:
        r = s.post(f"{base_url}/swap-meal", json={
            "mealLogId": log_id,
            "newMeal": "Chapati"
        })
        body = check("POST /swap-meal", r, expect_keys=["mealName", "calories"])
        if body and body.get("data"):
            print(f"     swapped to: {body['data'].get('mealName')} cal={body['data'].get('calories')}")
    else:
        print(f"{_SKIP} swap-meal — no log_id from step 6")
        results.append(("POST /swap-meal", None))

    # ──────────────────────────────────────────
    # (search food already done above in step 9)
    # ──────────────────────────────────────────

    # ──────────────────────────────────────────
    # 10. GET STREAK
    # ──────────────────────────────────────────
    h("10. Get Streak")
    r = s.get(f"{base_url}/get-streak", params={"userId": uid})
    check("GET /get-streak", r)

    # ──────────────────────────────────────────
    # 11. GENERATE DAILY RATING / ANALYTICS
    # ──────────────────────────────────────────
    h("11. Daily Rating / Analytics")
    r = s.post(f"{base_url}/generate-daily-rating", json={"userId": uid, "date": TODAY})
    if r.status_code == 404:
        print(f"{_SKIP} /generate-daily-rating — endpoint not found")
        results.append(("POST /generate-daily-rating", None))
    else:
        check("POST /generate-daily-rating", r)

    # ──────────────────────────────────────────
    # 12. SUBMIT FEEDBACK
    # ──────────────────────────────────────────
    h("12. Submit Feedback")
    r = s.post(f"{base_url}/submit-feedback", json={
        "userId": uid,
        "message": "System test feedback",
        "rating": 5
    })
    check("POST /submit-feedback", r)

    # ──────────────────────────────────────────
    # 13. USER PROFILE (account page)
    # ──────────────────────────────────────────
    h("13. User Profile")
    r = s.get(f"{base_url}/user-profile", params={"userId": uid})
    if r.status_code == 404:
        # Try alternate path
        r = s.get(f"{base_url}/profile", params={"userId": uid})
    check("GET /user-profile", r)

    print_summary()


def print_summary():
    h("SUMMARY")
    passed = sum(1 for _, ok in results if ok is True)
    failed = sum(1 for _, ok in results if ok is False)
    skipped = sum(1 for _, ok in results if ok is None)
    total = len(results)

    for label, ok in results:
        icon = _PASS if ok is True else (_SKIP if ok is None else _FAIL)
        print(f"  {icon}  {label}")

    print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")
    if failed == 0:
        print("\n  🎉 All tested endpoints are working!")
    else:
        print(f"\n  ⚠️  {failed} endpoint(s) need attention.")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NutriLens System Flow Test")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    args = parser.parse_args()

    print(f"\n{'═' * 55}")
    print(f"  NutriLens System Flow Test")
    print(f"  Base URL : {args.base_url}")
    print(f"  Date     : {TODAY}")
    print(f"{'═' * 55}")

    try:
        run(args.base_url)
    except requests.exceptions.ConnectionError:
        print(f"\n{_FAIL} Cannot connect to {args.base_url}")
        print("  Make sure the backend server is running: python app.py")
        sys.exit(1)
