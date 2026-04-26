# repositories/meal_repository.py
#
# All meal fetch operations read from the global in-memory cache that is
# loaded ONCE at server startup (meals_cache.py).
# Firestore is NEVER queried for individual meal reads — ZERO reads per request.

import random
import firebase_admin
from firebase_admin import firestore
from config.config import COL_MEALS, COL_MEAL_COMBOS
import threading

# ── Global cache (single source of truth) ──────────────────────────────────
# meals_cache.load_meals_cache() is called in app.py before blueprints register.
from meals_cache import get_meals, get_meals_by_type, MEALS_CACHE

# Legacy dev_store helpers (quota fallback / seed)
from dev_store import get_meal_by_name as mem_get_meal_by_name, ensure_meals_available

# Thread-safe lock used only for combo-cache (not for MEALS_CACHE reads)
_cache_lock = threading.Lock()


def _initialize_cache():
    """
    Legacy shim – kept so existing call-sites in app.py still work.
    The real initialisation now happens via meals_cache.load_meals_cache()
    which is called earlier in the startup sequence.
    """
    from meals_cache import MEALS_CACHE as _mc
    count = len(_mc)
    print(
        f"[meal_repository] _initialize_cache(): global cache already holds "
        f"{count} meals — no Firestore read needed."
    )


class MealRepository:
    def __init__(self):
        try:
            self.db = firestore.client()
        except ValueError:
            firebase_admin.initialize_app()
            self.db = firestore.client()

    # ------------------------------------------------------------------ #
    # TASK 4 – Use MEALS_CACHE everywhere                                 #
    # ------------------------------------------------------------------ #

    def get_all_meals(self):
        """
        Return all meals from the in-memory global cache.
        Firestore is NOT queried — zero reads per call.
        """
        meals = get_meals(context="get_all_meals")
        print(
            f"[cache] Using {len(meals)} meals from {self._source()} "
            f"(get_all_meals, 0 Firestore reads)"
        )
        return meals

    def get_meal_by_name(self, meal_name: str):
        """
        Case-insensitive name lookup against the in-memory cache.
        Zero Firestore reads.
        """
        target = (meal_name or "").strip().lower()
        if not target:
            return None

        meals = get_meals(context="get_meal_by_name")
        for m in meals:
            doc_name = (m.get("mealName") or "").lower().strip()
            if target == doc_name or target in doc_name or doc_name in target:
                print(f"[cache] get_meal_by_name hit: '{meal_name}' (0 Firestore reads)")
                return m

        print(f"[cache] get_meal_by_name miss: '{meal_name}' not in cache")
        from utils.logger import app_logger
        app_logger.warning(f"[swap] meal not found: {meal_name}")
        return {
            "mealName": meal_name,
            "calories": 120,
            "protein": 5,
            "carbs": 20,
            "fat": 3
        }

    def get_meals_by_type(self, meal_type: str):
        """
        Fast meal-type lookup using the pre-built in-memory index.
        Zero Firestore reads.
        """
        meals = get_meals_by_type(meal_type)
        print(
            f"[cache] get_meals_by_type '{meal_type}': {len(meals)} meals "
            f"(0 Firestore reads)"
        )
        return meals

    def get_meals_filtered(self, meal_type=None, dietary_tags=None, limit=50):
        """
        In-memory filtering over the global cache.
        Zero Firestore reads.
        """
        all_meals = get_meals(context="get_meals_filtered")
        results = []
        for meal in all_meals:
            if meal_type and meal.get("meal_type", "").lower() != meal_type.lower():
                continue
            if dietary_tags:
                tags = meal.get("dietary_tags") or []
                if not any(tag in tags for tag in dietary_tags):
                    continue
            results.append(meal)
            if len(results) >= limit:
                break

        print(
            f"[cache] get_meals_filtered: returned {len(results)} meals "
            f"(0 Firestore reads)"
        )
        return results

    def get_random_meals(self, limit=10):
        """
        Random meal selection from the global cache.
        Zero Firestore reads.
        """
        all_meals = get_meals(context="get_random_meals")
        shuffled = list(all_meals)
        random.shuffle(shuffled)
        result = shuffled[:limit]
        print(f"[cache] get_random_meals: {len(result)} meals (0 Firestore reads)")
        return result

    def search_food_by_prefix(self, query: str, limit: int = 10):
        """
        In-memory prefix/substring search.
        Zero Firestore reads.
        """
        q = query.lower()
        all_meals = get_meals(context="search_food_by_prefix")
        matches = [
            m for m in all_meals
            if q in (m.get("mealName") or "").lower()
        ]
        print(
            f"[cache] search_food_by_prefix '{query}': "
            f"{len(matches)} matches (0 Firestore reads)"
        )
        return [m.get("mealName") for m in matches[:limit]]

    # ------------------------------------------------------------------ #
    # Combo collection – still reads Firestore (small, infrequent)        #
    # ------------------------------------------------------------------ #

    def get_meal_combos(self):
        """Fetch all meal combos from Firestore (not part of meals cache)."""
        docs = self.db.collection(COL_MEAL_COMBOS).stream()
        combos = []
        for d in docs:
            c = d.to_dict()
            c["id"] = d.id
            combos.append(c)
        return combos

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _source() -> str:
        from meals_cache import MEALS_SOURCE
        return MEALS_SOURCE or "unknown"


# Singleton instance
meal_repo = MealRepository()
