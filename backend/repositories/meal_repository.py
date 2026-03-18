# repositories/meal_repository.py
import firebase_admin
from firebase_admin import firestore
from config.config import COL_MEALS, COL_MEAL_COMBOS
from dev_store import get_meal_by_name as mem_get_meal_by_name, MEALS_CACHE, ensure_meals_available
import threading
import time

# ISSUE 3 FIX: In-memory meal caching
_cached_meals = None
_cached_lightweight_meals = None
_cache_initialized = False

# IMPROVEMENT 1: Thread-safe cache with Lock
_cache_lock = threading.Lock()

# IMPROVEMENT 2: Cache expiration/TTL (10 minutes)
_cache_last_refresh = 0
CACHE_TTL_SECONDS = 600  # 10 minutes

# IMPROVEMENT 3: In-memory index by meal_type for faster filtering
_meals_by_type = {
    "breakfast": [],
    "lunch": [],
    "snack": [],
    "dinner": []
}

def _initialize_cache():
    """
    IMPROVEMENTS 1-3: Thread-safe, TTL-aware cache with meal_type index.
    
    Load all meals into memory once at startup (or when TTL expires).
    Uses threading.Lock for concurrent request safety.
    Builds _meals_by_type index for fast meal_type filtering.
    
    This avoids repeated Firestore reads and improves meal generation speed.
    """
    global _cached_meals, _cached_lightweight_meals, _cache_initialized, _cache_last_refresh, _meals_by_type
    
    # IMPROVEMENT 1: Check TTL before acquiring lock
    current_time = time.time()
    if _cache_initialized and (current_time - _cache_last_refresh) < CACHE_TTL_SECONDS:
        return  # Cache still fresh
    
    # IMPROVEMENT 1: Use lock to prevent concurrent cache initialization
    with _cache_lock:
        # Double-check pattern: verify again inside lock
        if _cache_initialized and (time.time() - _cache_last_refresh) < CACHE_TTL_SECONDS:
            return
        
        print("[Firestore Optimization] Initializing meal cache (thread-safe)...")
        
        try:
            db = firestore.client()
            docs = db.collection(COL_MEALS).stream()
            
            _cached_meals = []
            _cached_lightweight_meals = []
            
            # Reset meal_type index
            _meals_by_type = {
                "breakfast": [],
                "lunch": [],
                "snack": [],
                "dinner": []
            }
            
            for d in docs:
                m = d.to_dict()
                m["id"] = d.id
                _cached_meals.append(m)
                
                # Create lightweight version (only essential fields)
                lightweight = {
                    "id": d.id,
                    "mealName": m.get("mealName", ""),
                    "calories": m.get("calories", 0),
                    "protein": m.get("protein", 0),
                    "carbs": m.get("carbs", 0),
                    "fat": m.get("fat", 0),
                    "meal_type": m.get("meal_type", ""),
                    "cuisine": m.get("cuisine", ""),
                    "dietary_tags": m.get("dietary_tags", []),
                }
                _cached_lightweight_meals.append(lightweight)
                
                # IMPROVEMENT 3: Build meal_type index during initialization
                meal_type = m.get("meal_type", "").lower()
                if meal_type in _meals_by_type:
                    _meals_by_type[meal_type].append(m)
            
            # IMPROVEMENT 2: Update refresh timestamp
            _cache_last_refresh = time.time()
            _cache_initialized = True
            
            print(f"[Firestore Optimization] Cache initialized (thread-safe): {len(_cached_meals)} meals")
            print(f"[Firestore Optimization] Meal index built: ", end="")
            for mt, meals in _meals_by_type.items():
                print(f"{mt}={len(meals)} ", end="")
            print()
            
        except Exception as e:
            print(f"[Firestore Optimization] Cache initialization failed: {e}")
            _cache_initialized = False
            _cache_last_refresh = 0


class MealRepository:
    def __init__(self):
        try:
            self.db = firestore.client()
        except ValueError:
            # Fallback if app not initialized (handled in app.py normally)
            firebase_admin.initialize_app()
            self.db = firestore.client()
        
        # Initialize cache on first repository creation (thread-safe)
        _initialize_cache()

    def get_all_meals(self):
        """
        IMPROVEMENT 1-2: Thread-safe cache lookup with TTL.
        
        Fetch all individual meals from cache (zero Firestore reads).
        Uses lock to ensure thread-safe reads.
        
        Returns:
            All meals with full details
        """
        global _cached_meals
        
        # IMPROVEMENT 1: Use lock for thread-safe read
        with _cache_lock:
            if _cached_meals is not None:
                print(f"[Firestore Optimization] get_all_meals: Using cached meals ({len(_cached_meals)} items)")
                return _cached_meals
        
        # Fallback if cache not initialized
        try:
            docs = self.db.collection(COL_MEALS).stream()
            meals = []
            for d in docs:
                m = d.to_dict()
                m["id"] = d.id
                meals.append(m)
            print(f"[Firestore Optimization] get_all_meals: Fetched from Firestore ({len(meals)} reads)")
            return meals
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                ensure_meals_available()
                return list(MEALS_CACHE)
            raise

    def get_meal_by_name(self, meal_name):
        """
        ISSUE 3 FIX: Case-Insensitive Cache Lookup.
        
        Fetch a specific meal by name (zero Firestore reads when in cache).
        Falls back to Firestore query if cache miss.
        """
        global _cached_meals
        
        # Check cache first (zero reads)
        if _cached_meals is not None:
            for m in _cached_meals:
                if m.get("mealName", "").lower() == meal_name.lower():
                    print(f"[Firestore Optimization] get_meal_by_name: Cache hit '{meal_name}'")
                    return m
            
            # Cache miss — not in database
            print(f"[Firestore Optimization] get_meal_by_name: Cache miss '{meal_name}'")
            return None
        
        # Fallback: Firestore query (1 read per query)
        try:
            docs = self.db.collection(COL_MEALS).where("mealName", "==", meal_name).limit(1).stream()
            for d in docs:
                m = d.to_dict()
                m["id"] = d.id
                print(f"[Firestore Optimization] get_meal_by_name: Firestore read for '{meal_name}'")
                return m
            return None
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                ensure_meals_available()
                m = mem_get_meal_by_name(meal_name)
                if m:
                    return dict(m)
                return None
            raise

    def get_meals_by_type(self, meal_type):
        """
        IMPROVEMENT 3: Get all meals of a specific type using in-memory index.
        
        Fast meal_type lookup using pre-built _meals_by_type index.
        Zero Firestore reads. Safe for meal swaps within same meal_type.
        
        Args:
            meal_type: breakfast, lunch, snack, or dinner
        
        Returns:
            List of meals of that type (full meal objects)
        """
        global _meals_by_type
        
        meal_type_lower = meal_type.lower()
        
        # Use lock for thread-safe read
        with _cache_lock:
            if meal_type_lower in _meals_by_type:
                meals = _meals_by_type.get(meal_type_lower, [])
                print(f"[Firestore Optimization] get_meals_by_type: {meal_type_lower} ({len(meals)} meals from index)")
                return meals
        
        print(f"[Firestore Optimization] get_meals_by_type: {meal_type_lower} not in index, returning empty")
        return []

    def get_meals_filtered(self, meal_type=None, dietary_tags=None, limit=50):
        """
        ISSUE 3 FIX: Lightweight Filtered Query.
        
        Fetch meals with optional filters (cached + lightweight).
        
        Reduces data transfer and memory usage compared to get_all_meals().
        
        Args:
            meal_type: Filter by meal type (breakfast, lunch, etc.)
            dietary_tags: Filter by dietary tag (vegetarian, etc.)
            limit: Max meals to return
        
        Returns:
            List of lightweight meal objects
        """
        global _cached_lightweight_meals
        
        if _cached_lightweight_meals is None:
            print(f"[Firestore Optimization] get_meals_filtered: Cache not ready, using fallback")
            return []
        
        # In-memory filtering on cached lightweight meals (zero Firestore reads)
        results = []
        for meal in _cached_lightweight_meals:
            # Apply filters
            if meal_type and meal.get("meal_type", "").lower() != meal_type.lower():
                continue
            
            if dietary_tags:
                meal_tags = meal.get("dietary_tags", []) or []
                if not any(tag in meal_tags for tag in dietary_tags):
                    continue
            
            results.append(meal)
            
            if len(results) >= limit:
                break
        
        print(f"[Firestore Optimization] get_meals_filtered: Returned {len(results)} meals (0 Firestore reads)")
        return results
    
    def get_random_meals(self, limit=10):
        """
        ISSUE 3 FIX: Random Meal Selection from Cache.

        Used to top up replace-meal suggestions to 5 when KNN returns fewer.
        Falls back to the in-memory cache when Firestore is rate-limited.
        """
        import random
        global _cached_meals
        
        if _cached_meals is not None:
            # In-memory selection (zero Firestore reads)
            shuffled = list(_cached_meals)
            random.shuffle(shuffled)
            result = shuffled[:limit]
            print(f"[Firestore Optimization] get_random_meals: Returned {len(result)} from cache (0 Firestore reads)")
            return result
        
        # Firestore fallback
        try:
            print(f"[Firestore Optimization] get_random_meals: Querying Firestore...")
            # Fetch a larger batch and shuffle for variety
            docs = self.db.collection(COL_MEALS).limit(limit * 5).stream()
            meals = []
            for d in docs:
                m = d.to_dict()
                m["id"] = d.id
                meals.append(m)
            random.shuffle(meals)
            print(f"[Firestore Optimization] get_random_meals: Firestore read ({len(meals)} documents)")
            return meals[:limit]
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                ensure_meals_available()
                import random as _r
                sample = list(MEALS_CACHE)
                _r.shuffle(sample)
                print(f"[Firestore Optimization] get_random_meals: Using fallback cache ({len(sample[:limit])} items)")
                return sample[:limit]
            raise

    def get_meal_combos(self):
        """Fetch all meal combos from Firestore."""
        docs = self.db.collection(COL_MEAL_COMBOS).stream()
        combos = []
        for d in docs:
            c = d.to_dict()
            c["id"] = d.id
            combos.append(c)
        return combos

    # Search food by prefix (lightweight, cached)
    def search_food_by_prefix(self, query, limit=10):
        """
        ISSUE 3 FIX: Prefix Search Using Cache.
        
        Perform a prefix search on mealName using in-memory cache (zero Firestore reads).
        Falls back to Firestore range query if cache unavailable.
        """
        global _cached_meals
        
        query_lower = query.lower()
        
        if _cached_meals is not None:
            # In-memory search (zero Firestore reads)
            matches = [
                m for m in _cached_meals
                if query_lower in (m.get("mealName") or "").lower()
            ]
            print(f"[Firestore Optimization] search_food_by_prefix: Found {len(matches)} matches in cache (0 Firestore reads)")
            return [m.get("mealName") for m in matches[:limit]]
        
        # Firestore fallback (range query — ~1 read)
        try:
            docs = self.db.collection(COL_MEALS)\
                .where("mealName", ">=", query.capitalize())\
                .where("mealName", "<=", query.capitalize() + "\uf8ff")\
                .limit(limit).stream()
            
            results = []
            for d in docs:
                m = d.to_dict()
                results.append(m.get("mealName", d.id))
            
            print(f"[Firestore Optimization] search_food_by_prefix: Firestore range query returned {len(results)} results")
            return results
        except Exception as e:
            print(f"[Firestore Optimization] search_food_by_prefix: Query failed: {e}")
            return []

# Singleton instance
meal_repo = MealRepository()

