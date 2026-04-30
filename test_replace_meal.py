import json
import requests

url = "http://localhost:8080/replace-meal"
data = {"mealName": "Egg Omelette", "userId": "veg_user"}

try:
    from app import app
    client = app.test_client()
    resp = client.post("/replace-meal", json=data)
    print("Status:", resp.status_code)
    print("Body:", resp.get_data(as_text=True))
except Exception as e:
    print("Error:", e)
