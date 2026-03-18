"""
In-memory fallback store for local development.

Used when Firestore returns quota/resource exhaustion errors so the app
remains usable for demos/tests without changing API shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import json
import os
import uuid


MEALS_CACHE: List[Dict[str, Any]] = []

# Small seed dataset used only when Firestore is unavailable and no cache exists.
SEED_MEALS: List[Dict[str, Any]] = [
    {"id": "seed_roti", "mealName": "Roti", "calories": 120, "protein": 4, "carbs": 22, "fat": 2},
    {"id": "seed_butter_roti", "mealName": "Butter Roti", "calories": 140, "protein": 4, "carbs": 22, "fat": 5},
    {"id": "seed_rice", "mealName": "Rice", "calories": 200, "protein": 4, "carbs": 45, "fat": 1},
    {"id": "seed_dal", "mealName": "Dal Tadka", "calories": 220, "protein": 12, "carbs": 28, "fat": 8},
    {"id": "seed_rajma", "mealName": "Rajma", "calories": 240, "protein": 14, "carbs": 32, "fat": 7},
    {"id": "seed_chole", "mealName": "Chole", "calories": 260, "protein": 14, "carbs": 36, "fat": 9},
    {"id": "seed_sabzi", "mealName": "Mixed Vegetable Sabzi", "calories": 180, "protein": 6, "carbs": 20, "fat": 8},
    {"id": "seed_paneer", "mealName": "Paneer Bhurji", "calories": 280, "protein": 16, "carbs": 10, "fat": 18},
    {"id": "seed_curd", "mealName": "Curd", "calories": 120, "protein": 6, "carbs": 8, "fat": 6},
    {"id": "seed_milk", "mealName": "Milk", "calories": 150, "protein": 8, "carbs": 12, "fat": 8},
    {"id": "seed_poha", "mealName": "Poha", "calories": 260, "protein": 6, "carbs": 45, "fat": 6},
    {"id": "seed_upma", "mealName": "Upma", "calories": 250, "protein": 6, "carbs": 42, "fat": 7},
    {"id": "seed_idli", "mealName": "Idli", "calories": 60, "protein": 2, "carbs": 12, "fat": 0.5},
    {"id": "seed_dosa", "mealName": "Dosa", "calories": 170, "protein": 4, "carbs": 28, "fat": 5},
    {"id": "seed_fruit", "mealName": "Fruit Bowl", "calories": 150, "protein": 2, "carbs": 35, "fat": 1},
    {"id": "seed_nuts", "mealName": "Mixed Nuts", "calories": 180, "protein": 6, "carbs": 6, "fat": 15},
    {"id": "seed_salad", "mealName": "Salad", "calories": 60, "protein": 2, "carbs": 10, "fat": 2},
    {"id": "seed_buttermilk", "mealName": "Buttermilk", "calories": 80, "protein": 4, "carbs": 10, "fat": 2},
    {"id": "seed_sprouts", "mealName": "Sprouts", "calories": 120, "protein": 8, "carbs": 14, "fat": 2},
    {"id": "seed_sandwich", "mealName": "Sandwich", "calories": 220, "protein": 8, "carbs": 30, "fat": 8},
]

# Key: (userId, dateStr) -> list[log]
LOGS_BY_USER_DATE: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

# Key: (userId, dateStr) -> meal plan dict (data payload stored in Firestore)
PLANS_BY_USER_DATE: Dict[Tuple[str, str], Dict[str, Any]] = {}

# In-memory user cache for dev mode (fallback when Firestore is rate limited)
USERS_CACHE: Dict[str, Dict[str, Any]] = {}


def set_meals_cache(meals: List[Dict[str, Any]]) -> None:
    global MEALS_CACHE
    MEALS_CACHE = meals or []


def ensure_meals_available() -> None:
    """
    Ensure MEALS_CACHE is populated for local dev even if Firestore is down.
    """
    if MEALS_CACHE:
        return
    if load_meals_cache_from_disk():
        return
    set_meals_cache(SEED_MEALS)


def _meals_cache_path() -> str:
    # Stored under backend/.cache/meals_cache.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "meals_cache.json")


def save_meals_cache_to_disk() -> None:
    """Persist meals cache so local dev keeps working even if Firestore quota is hit later."""
    path = _meals_cache_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(MEALS_CACHE, f, ensure_ascii=False)


def load_meals_cache_from_disk() -> bool:
    """Load meals cache from disk if present. Returns True if loaded."""
    path = _meals_cache_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            meals = [d for d in data if isinstance(d, dict)]
            if not meals:
                return False
            set_meals_cache(meals)
            return True
    except Exception:
        return False
    return False


# ------------------ Users Cache (dev fallback) ------------------

def _users_cache_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "users_cache.json")


def save_user_to_cache(user: Dict[str, Any]) -> None:
    """Persist a user record in local disk cache for offline/dev use."""
    if not user or "userId" not in user:
        return
    USERS_CACHE[str(user["userId"])] = user
    try:
        path = _users_cache_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(USERS_CACHE, f, ensure_ascii=False)
    except Exception:
        pass


def load_users_cache_from_disk() -> bool:
    """Load users cache from disk if available."""
    path = _users_cache_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            USERS_CACHE.clear()
            for k, v in data.items():
                if isinstance(v, dict):
                    USERS_CACHE[k] = v
            return True
    except Exception:
        return False
    return False


def get_user_from_cache(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user from the in-memory cache."""
    if not user_id:
        return None
    return USERS_CACHE.get(str(user_id))


def search_meals(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []
    results: List[Dict[str, Any]] = []
    for m in MEALS_CACHE:
        name_val = (m.get("mealName") or m.get("name") or m.get("title") or m.get("food_name") or "")
        name = str(name_val).lower()
        keywords_list = m.get("searchKeywords") or m.get("aliases") or []
        keywords_str = " ".join([str(x) for x in keywords_list]).lower() if isinstance(keywords_list, list) else str(keywords_list).lower()
        if not keywords_str:
            keywords_str = name
        if q in name or q in keywords_str:
            results.append(
                {
                    "meal_id": m.get("id"),
                    "name": name_val,
                    "calories": m.get("calories", 0),
                }
            )
            if len(results) >= limit:
                break
    return results


def get_meal_by_name(meal_name: str) -> Optional[Dict[str, Any]]:
    target = (meal_name or "").strip().lower()
    if not target:
        return None
    for m in MEALS_CACHE:
        n = (m.get("mealName") or "").strip().lower()
        if n == target:
            return m
    return None


def log_meal(log_data: Dict[str, Any]) -> str:
    user_id = str(log_data.get("userId") or "")
    date_str = str(log_data.get("date") or "")
    log_id = log_data.get("logId") or str(uuid.uuid4())
    entry = {**log_data, "logId": log_id}
    LOGS_BY_USER_DATE.setdefault((user_id, date_str), []).append(entry)
    return log_id


def get_logs_by_date(user_id: str, date_str: str) -> List[Dict[str, Any]]:
    return list(LOGS_BY_USER_DATE.get((str(user_id), str(date_str)), []))


def update_log_quantity(log_id: str, updates: Dict[str, Any]) -> bool:
    for key, logs in LOGS_BY_USER_DATE.items():
        for i, log in enumerate(logs):
            if str(log.get("logId")) == str(log_id):
                logs[i] = {**log, **updates, "logId": log_id}
                return True
    return False


def delete_log(log_id: str) -> bool:
    for key, logs in list(LOGS_BY_USER_DATE.items()):
        new_logs = [l for l in logs if str(l.get("logId")) != str(log_id)]
        if len(new_logs) != len(logs):
            if new_logs:
                LOGS_BY_USER_DATE[key] = new_logs
            else:
                del LOGS_BY_USER_DATE[key]
            return True
    return False


def save_plan(plan_data: Dict[str, Any]) -> str:
    user_id = str(plan_data.get("userId") or plan_data.get("user_id") or "")
    date_str = str(plan_data.get("date") or "")
    plan_id = str(uuid.uuid4())
    PLANS_BY_USER_DATE[(user_id, date_str)] = {**plan_data, "planId": plan_id}
    return plan_id


def get_plan_by_date(user_id: str, date_str: str) -> Optional[Dict[str, Any]]:
    return PLANS_BY_USER_DATE.get((str(user_id), str(date_str)))

