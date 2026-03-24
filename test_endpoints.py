import requests
import json
import time

BASE_URL = "http://localhost:5000"

# Mock IDs
USER_ID = "gmail_divyansh_006"
DATE_STR = "2026-03-15"

def print_result(name, res):
    print(f"\n--- {name} ---")
    print(f"Status: {res.status_code}")
    try:
        print(json.dumps(res.json(), indent=2))
        return res.json()
    except:
        print(res.text)
        return None

print("Running Automated Endpoint Tests...\n")

# 1. search-food
print_result("Search Food (roti)", requests.get(f"{BASE_URL}/search-food?query=roti"))

# 2. search-food (dal)
print_result("Search Food (dal)", requests.get(f"{BASE_URL}/search-food?query=dal"))

# 3. log-meal-nlp-ml
nlp_payload = {
    "userId": USER_ID,
    "date": DATE_STR,
    "text": "I ate 2 chapatis and dal"
}
nlp_res = print_result("Log Meal NLP (2 chapatis and dal)", requests.post(f"{BASE_URL}/log-meal-nlp-ml", json=nlp_payload))

nlp_payload_2 = {
    "userId": USER_ID,
    "date": DATE_STR,
    "text": "roti"
}
print_result("Log Meal NLP (roti)", requests.post(f"{BASE_URL}/log-meal-nlp-ml", json=nlp_payload_2))

# 4. update-log (We'll use a mocked ID since we can't easily extract one dynamically yet)
update_payload = {
    "logId": "test_mock_id",
    "quantity": 3
}
print_result("Update Log", requests.put(f"{BASE_URL}/update-log", json=update_payload))

# 5. delete-log
delete_payload = {
    "log_id": "test_mock_id"
}
print_result("Delete Log", requests.delete(f"{BASE_URL}/delete-log", json=delete_payload))

# 6. get-streak
print_result("Get Streak", requests.get(f"{BASE_URL}/get-streak?userId={USER_ID}"))

# 7. generate-daily-rating
rating_payload = {"userId": USER_ID, "date": DATE_STR}
print_result("Generate Daily Rating", requests.post(f"{BASE_URL}/generate-daily-rating", json=rating_payload))

# 8. get-analytics
analytics_payload = {"userId": USER_ID}
print_result("Get Analytics", requests.post(f"{BASE_URL}/get-analytics", json=analytics_payload))

# 9. submit-feedback
feedback_payload = {"userId": USER_ID, "message": "Test analytics script"}
print_result("Submit Feedback", requests.post(f"{BASE_URL}/submit-feedback", json=feedback_payload))
