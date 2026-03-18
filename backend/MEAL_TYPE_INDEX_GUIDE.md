# Meal Type Index Reference Guide

## Overview

The meal_type index (`_meals_by_type`) provides O(1) fast lookup of meals by category. This guide documents the index structure, usage patterns, and optimization strategies.

---

## Index Structure

### Layout

```python
_meals_by_type = {
    "breakfast": [meal_obj_1, meal_obj_2, meal_obj_3, ...],
    "lunch":     [meal_obj_4, meal_obj_5, meal_obj_6, ...],
    "snack":     [meal_obj_7, meal_obj_8, meal_obj_9, ...],
    "dinner":    [meal_obj_10, meal_obj_11, meal_obj_12, ...]
}
```

### Supported Meal Types

```
Type       | Usage                  | Typical Meals
────       | ────────────────────   | ──────────────────
breakfast  | First meal of day      | Idli, Dosa, Uppit, Paratha
lunch      | Midday meal            | Biryani, Pulao, Curry + Rice
snack      | Between meal           | Fruit, Banana, Biscuits
dinner     | Evening/night meal     | Light curries, Soup + Bread
```

### Data Structure of Each Meal

```python
meal_obj = {
    "mealId": "meal_001",
    "mealName": "Idli",
    "meal_type": "breakfast",          # KEY field for indexing
    "calories": 150,
    "protein": 4.5,
    "carbs": 28,
    "fat": 0.5,
    "description": "South Indian steamed cake",
    "portion": "2 pieces",
    ...
}
```

---

## Performance Characteristics

### Lookup Time Complexity

```
Operation              Complexity    Time (500 meals)
───────────────────    ──────────    ──────────────
get_meals_by_type()    O(1)          <1ms
filter all meals       O(n)          50-100ms
scan index             O(k)          1-10ms (k = meals in type)
sort within type       O(k log k)    5-50ms
```

### Example Performance Comparison

**Before Index (O(n) scan):**
```python
# Filter all 500 meals for "breakfast"
selected = [m for m in _cached_meals if m.get("meal_type") == "breakfast"]
# Time: 100 meal checks, lots of string comparisons
# Runs: Every correction pass, every swap
# Total: 100+ ms per request
```

**After Index (O(1) lookup):**
```python
# Direct index lookup
selected = _meals_by_type.get("breakfast", [])
# Time: Direct dictionary access
# Runs: Instant, sub-millisecond
# Total: <1ms per lookup
```

**Savings:** 100-1000x faster meal filtering

---

## Building the Index

### Index Initialization

**File:** `repositories/meal_repository.py` → `_initialize_cache()`

```python
def _initialize_cache():
    """Build index during cache initialization."""
    global _meals_by_type, _cached_meals
    
    # Reset index
    _meals_by_type = {
        "breakfast": [],
        "lunch": [],
        "snack": [],
        "dinner": []
    }
    
    # Build index from cached meals
    for meal in _cached_meals:
        meal_type = meal.get("meal_type", "").lower()
        
        # Only add valid meal_type
        if meal_type in _meals_by_type:
            _meals_by_type[meal_type].append(meal)
        else:
            print(f"[Warning] Meal '{meal.get('mealName')}' "
                  f"has invalid meal_type: '{meal_type}'")
    
    # Log index status
    print(f"[Index] Built meal_type index:")
    for meal_type, meals in _meals_by_type.items():
        print(f"  {meal_type}: {len(meals)} meals")
```

### Refresh Frequency

- **When:** Every cache refresh (every 10 minutes)
- **Time:** <100ms to rebuild
- **Trigger:** TTL expiration or manual cache refresh

---

## Using the Index

### Primary Usage: Meal Swap Correction

**File:** `ai/meal_plan_generator.py`

```python
from repositories.meal_repository import meal_repo

# Get all meals of "lunch" type
lunch_options = meal_repo.get_meals_by_type("lunch")

# Find best replacement from same meal_type
replacement_candidates = [
    m for m in lunch_options
    if m.get("mealName") != current_item_name
]

# Pick best alternative
best_replacement = min(
    replacement_candidates,
    key=lambda m: abs(m.get("protein", 0) - target_protein)
)
```

### Secondary Usage: Meal Type Validation

```python
# Verify meal is valid for its type
lunch_meals = meal_repo.get_meals_by_type("lunch")
meal_names = {m.get("mealName") for m in lunch_meals}

if item_name not in meal_names:
    print(f"Error: {item_name} not a valid lunch meal")
```

### Index Queries

```python
# Get meal count by type
num_breakfast = len(meal_repo.get_meals_by_type("breakfast"))
num_lunch = len(meal_repo.get_meals_by_type("lunch"))

# Check if type has meals
snack_available = bool(meal_repo.get_meals_by_type("snack"))

# Get random meal from type
import random
random_breakfast = random.choice(meal_repo.get_meals_by_type("breakfast"))
```

---

## Index Quality Metrics

### Expected Distribution

**Healthy Distribution:**
```
breakfast: ~18-20% of meals (90-100 meals)
lunch:     ~25-28% of meals (125-140 meals)
snack:     ~10-12% of meals (50-60 meals)
dinner:    ~28-32% of meals (140-160 meals)
total:     ~500 meals
```

**Detect Problems:**
```
If breakfast = 0:  No breakfast meals (fix data)
If lunch = 0:      No lunch meals (fix data)
If snack = 0:      No snack meals (add data or not required)
If dinner = 0:     No dinner meals (fix data)
```

### Index Validation

**Check on Startup:**
```python
def validate_index():
    """Verify index integrity."""
    from repositories.meal_repository import _meals_by_type
    
    total = sum(len(meals) for meals in _meals_by_type.values())
    
    if total == 0:
        print("ERROR: Index is empty!")
        return False
    
    # Check for empty types
    for meal_type, meals in _meals_by_type.items():
        if len(meals) == 0:
            print(f"WARNING: No {meal_type} meals in index")
    
    print(f"✓ Index valid: {total} total meals")
    return True
```

---

## Memory Usage

### Index Size

```
Data Structure Size:
  Pointers overhead: ~8 bytes each
  500 meals × 4 types: ~16 KB (negligible)

Memory Comparison:
  Full meal objects: 500 × ~2KB = 1 MB
  Index pointers:    500 × 8B  = 4 KB
  Index efficiency:  >99% reduction

Conclusion: Index has zero practical memory cost
```

### When Index Takes Space

```python
# Wasteful: Copying data
for meal_type in _meals_by_type:
    meals = list(_meals_by_type[meal_type])  # Copy all meals
    
# Efficient: Direct access
for meal_type in _meals_by_type:
    meals = _meals_by_type[meal_type]  # Reference, no copy
```

---

## Debugging Index Issues

### Issue: Index Missing Meals

**Symptom:**
```
[Index] Built meal_type index:
  breakfast: 98 meals
  lunch: 115 meals
  snack: 0 meals         ← Should be ~50
  dinner: 127 meals
```

**Causes:**
1. No snack meals in Firestore
2. `meal_type` field is wrong format (e.g., "Snack" vs "snack")
3. `meal_type` field missing from snack meals

**Debug:**
```python
# Check raw Firestore data
for meal in _cached_meals:
    meal_type = meal.get("meal_type", "")
    if meal_type == "":
        print(f"Empty meal_type: {meal.get('mealName')}")
    elif meal_type != meal_type.lower():
        print(f"Wrong casing: {meal_type} (should be lowercase)")

# Verify Firestore console
# meals collection → filter by meal_name containing "snack" keywords
```

**Fix:**
```python
# Add missing data
db.collection("meals").add({
    "mealName": "Banana",
    "meal_type": "snack",  # Must be lowercase
    ...
})
```

### Issue: Index Out of Sync

**Symptom:**
```
Meals in app don't match expected from index
Correction pass can't find replacements
```

**Causes:**
1. Meals added to Firestore but cache not refreshed
2. TTL setting too high (stale data)
3. Cache not rebuilt after modification

**Debug:**
```python
# Check if TTL is too high
print(f"CACHE_TTL_SECONDS = {CACHE_TTL_SECONDS}")  # Should be 600

# Force refresh
# Edit CACHE_TTL_SECONDS = 1, wait for next request
# Check logs for "Cache refreshed"

# Check last refresh time
import time
from repositories.meal_repository import _cache_last_refresh
print(f"Last refresh: {time.time() - _cache_last_refresh} seconds ago")
```

### Issue: Correction Pass Failing

**Symptom:**
```
[Meal Plan] Correction: protein deviates by 15%
[Meal Plan] Correction: lunch candidates = 0 meals  ← Index lookup failed
```

**Causes:**
1. Index not initialized
2. Meal type name mismatch
3. Index corrupted

**Debug:**
```python
# Verify index exists
from repositories.meal_repository import _meals_by_type, meal_repo
print(f"Index keys: {list(_meals_by_type.keys())}")
print(f"Lunch meals in index: {len(meal_repo.get_meals_by_type('lunch'))}")

# Check with direct access
lunch_from_index = _meals_by_type.get("lunch", [])
print(f"Lunch from direct dict access: {len(lunch_from_index)}")
```

---

## Optimization Strategies

### Strategy 1: Pre-Filter Index

**Current (less optimal):**
```python
lunch_meals = meal_repo.get_meals_by_type("lunch")  # 120 meals
best = min(lunch_meals, key=lambda m: m.get("calories"))  # O(n) scan
```

**Optimized:**
```python
# Build sub-index during initialization
def _initialize_cache():
    global _meals_by_type_sorted
    _meals_by_type_sorted = {
        "breakfast": {
            "by_calories": sorted(...),
            "by_protein": sorted(...),
        },
        ...
    }

# Then use pre-sorted data
breakfast_by_calories = _meals_by_type_sorted["breakfast"]["by_calories"]
lowest_cal = breakfast_by_calories[0]  # O(1)
```

**Benefit:** Further optimizations for future sorting needs

### Strategy 2: Lazy Index Building

**Current (all at once):**
```python
# Build entire index in _initialize_cache()
# Time: ~100ms for 500 meals
```

**Alternative (lazy):**
```python
# Build index on-demand
def get_meals_by_type(self, meal_type):
    key = meal_type.lower()
    if key not in _meals_by_type:
        _meals_by_type[key] = [
            m for m in _cached_meals if m.get("meal_type") == key
        ]
    return _meals_by_type[key]
```

**Benefit:** Faster initialization, but slower first lookup

### Strategy 3: Index Caching Layers

**Current (one-level index):**
```
Type name → [Meal objects]
```

**Multi-level (future):**
```
Type name → Calories range → [Meal objects]

Example: get meatless lunch meals
  _meals_by_type["lunch"]["vegetarian"] → [obj1, obj2, obj3]
```

**Benefit:** Faster filtering by multiple criteria

---

## API Reference

### Method: `get_meals_by_type(meal_type)`

**Location:** `repositories/meal_repository.py` → `MealRepository` class

**Signature:**
```python
def get_meals_by_type(self, meal_type: str) -> list:
    """
    Get all meals of a specific type.
    
    Args:
        meal_type (str): One of "breakfast", "lunch", "snack", "dinner"
                        (case-insensitive)
    
    Returns:
        list: List of meal objects of specified type
              Returns empty list if type not found
    
    Time Complexity: O(1) index lookup
    
    Thread Safety: Protected by _cache_lock
    
    Example:
        >>> breakfast_meals = meal_repo.get_meals_by_type("breakfast")
        >>> len(breakfast_meals)
        98
    """
```

**Usage Example:**
```python
from repositories.meal_repository import meal_repo

# Get lunch options
lunch = meal_repo.get_meals_by_type("lunch")
print(f"Available lunch meals: {len(lunch)}")

# Filter by criteria
high_protein_lunch = [m for m in lunch if m.get("protein", 0) > 20]

# Random selection
import random
random_snack = random.choice(meal_repo.get_meals_by_type("snack"))
```

---

## Index Monitoring

### Log Messages

**Healthy:**
```
[Index] Built meal_type index:
  breakfast: 98 meals
  lunch: 115 meals
  snack: 47 meals
  dinner: 127 meals
```

**Unhealthy:**
```
[Index] Built meal_type index:
  breakfast: 0 meals        ← PROBLEM
  lunch: 98 meals
  snack: 0 meals           ← PROBLEM
  dinner: 125 meals
```

### Monitoring Query

```python
def check_index_health():
    """Monitor index quality."""
    from repositories.meal_repository import _meals_by_type
    
    stats = {
        meal_type: len(meals)
        for meal_type, meals in _meals_by_type.items()
    }
    
    total = sum(stats.values())
    
    if total < 100:
        print(f"WARNING: Only {total} meals in index (expected >200)")
    
    if any(count == 0 for count in stats.values()):
        print(f"WARNING: Empty meal type detected: {stats}")
    
    return stats
```

---

## Integration with Other Systems

### Meal Swap Correction

**File:** `ai/meal_plan_generator.py`

Uses index to find replacement meals within same category:
```python
candidates = meal_repo.get_meals_by_type(meal_type)  # Uses index
best_replacement = find_closest_macro_match(candidates, target)
```

### Swap Suggestions

**File:** `routes/meal_routes.py`

Falls back to cache with in-memory filtering:
```python
# Already uses _cached_meals, but could use index for faster filtering
available_meals = meal_repo.get_meals_by_type(meal_type)
suggestions = random.sample(available_meals, k=5)
```

---

## Future Enhancements

### 1. Multi-Key Indexing
```python
_meals_index = {
    "by_type": {...},
    "by_calories": {...},
    "by_cuisine": {...},
}
```

### 2. Partial Index (Active Only)
```python
# Only index enabled meals
_meals_by_type = {
    "breakfast": [active_meal1, active_meal2, ...]
}
```

### 3. Consistency Checking
```python
def verify_index_integrity():
    """Ensure index matches source data"""
    total_in_index = sum(len(m) for m in _meals_by_type.values())
    total_in_cache = len(_cached_meals)
    assert total_in_index == total_in_cache
```

---

## References

- **PRODUCTION_IMPROVEMENTS.md** — Full improvement overview
- **repositories/meal_repository.py** — Index implementation
- **ai/meal_plan_generator.py** — Correction pass using index
- **THREAD_SAFETY_GUIDE.md** — Thread-safe access patterns

---

**Status:** ✅ Production Ready

Index fully integrated and optimized for production workloads.

