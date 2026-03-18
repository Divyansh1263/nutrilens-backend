import os
os.environ["WERKZEUG_RUN_MAIN"] = "true"

from app import app
import json

client = app.test_client()

print("\n--- Running direct NLP Pipeline for roti and dal ---")
res = client.post("/log-meal-nlp-ml", json={
    "userId": "test",
    "date": "2026-03-15",
    "text": "roti"
})

print(f"Status: {res.status_code}")
try:
    data = res.json
    print("Response Data:", json.dumps(data, indent=2))
except Exception as e:
    print("Failed to parse json:", res.data)
