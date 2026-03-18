# TTL Cache Monitoring & Operations Guide

## Overview

The NutriLens backend now implements a TTL (Time-To-Live) based caching system with automatic refresh every 10 minutes. This guide covers operational procedures, monitoring, and troubleshooting.

---

## How TTL Cache Works

### Refresh Cycle

```
Time    Event
────    ─────────────────────────────────────────────────
0:00    Cache initialized
        _cache_last_refresh = 0:00

0:01    Request arrives
        → Check: now - last_refresh (1 min) < 600 sec?
        → YES: Use cache ✓

5:00    Request arrives
        → Check: now - last_refresh (5 min) < 600 sec?
        → YES: Use cache ✓

10:00   Request arrives  
        → Check: now - last_refresh (10 min) >= 600 sec?
        → NO: Acquire lock, refresh cache
        → Load 500 meals from Firestore
        → Build meal_type index
        → _cache_last_refresh = 10:00

10:01   Request arrives
        → Check: now - last_refresh (1 sec) < 600 sec?
        → YES: Use cache ✓
```

### Key Parameter
```python
CACHE_TTL_SECONDS = 600  # 10 minutes in seconds

Current TTL cycle: 10 minutes (configurable)
```

---

## Monitoring Indicators

### ✓ Healthy Cache Signs

**Logs (expect these):**
```
[Firestore Optimization] Initializing meal cache (thread-safe)...
[Firestore Optimization] Cache initialized (thread-safe): 500 meals
[Firestore Optimization] Meal index built: breakfast=100 lunch=120 snack=50 dinner=130
```

Every 10 minutes:
```
[Firestore Optimization] Cache refreshed at 1702500000.123
[Firestore Optimization] Meal index built: breakfast=100 lunch=120 snack=50 dinner=130
```

Most requests:
```
[Firestore Optimization] Cache still fresh, skipping refresh
```

**Metrics (expected):**
```
Firestore reads per request: ~0 (except cache refresh every 10 min)
Response time: 1-3 seconds (consistent)
Error rate: <1%
```

### ⚠ Warning Signs

**Problem:** Cache never refreshes (always shows "Cache still fresh")
```
Cause: TTL parameter set too high (e.g., 3600+ seconds)
Action: Reduce CACHE_TTL_SECONDS to 600 (10 minutes)
```

**Problem:** Cache refreshes too frequently (every minute)
```
Cause: TTL parameter set too low (e.g., 60 seconds)
Action: Increase CACHE_TTL_SECONDS to 600 (10 minutes)
```

**Problem:** High Firestore reads (100+ per request)
```
Cause: Cache not initialized or refreshing
Action: Check logs for "[Firestore Optimization]" messages
       Check Python errors in Flask logs
       Verify Firestore credentials
```

**Problem:** Slow meal plan generation (>5 seconds)
```
Cause: Cache lock contention (too many concurrent requests)
Action: Monitor concurrent request count
       Consider reducing TTL if heavy usage
       Scale backend horizontally
```

---

## Operational Procedures

### Adjusting TTL

Edit `repositories/meal_repository.py`:

```python
# Current (10 minutes)
CACHE_TTL_SECONDS = 600

# Adjust to:
CACHE_TTL_SECONDS = 300   # 5 minutes (more frequent refresh, more Firestore reads)
CACHE_TTL_SECONDS = 1800  # 30 minutes (stale data risk, fewer Firestore reads)
CACHE_TTL_SECONDS = 3600  # 1 hour (very stale data risk, minimal Firestore reads)
```

After changing:
1. Save file
2. Restart Flask backend
3. Verify cache refresh rate in logs

### Forcing Cache Refresh

To force an immediate refresh (e.g., after bulk meal edits in Firestore):

**Option 1: Restart backend** (cleanest)
```bash
# On Linux/Mac
pkill -f "flask run"
python app.py

# On Windows
# Use task manager or Ctrl+C then restart
```

**Option 2: Lower TTL temporarily**
```
Edit CACHE_TTL_SECONDS = 1 (force refresh on next request)
Wait for "Cache refreshed" log
Restore CACHE_TTL_SECONDS = 600
```

**Option 3: Add manual refresh endpoint** (optional)
```python
@app.route("/admin/refresh-cache", methods=["POST"])
def refresh_cache():
    from repositories.meal_repository import _initialize_cache
    _initialize_cache()
    return {"status": "Cache refreshed"}
```

---

## Performance Baseline

### Expected Firestore Read Pattern

**With TTL caching (current):**

Per 10-minute cycle:
```
Minutes 0-10:
  Request 1: 1 Firestore read (init) + all meals now cached
  Request 2-100: 0 Firestore reads (using cache)
  
Minute 10 (refresh):
  Request N: 1 Firestore read (refresh) + cache rebuilt
  
Total: ~2 Firestore reads per 10 minutes (at scale)
```

**Without caching (if needed for comparison):**
```
Every request: 50-100 Firestore reads
500 requests/hour: 25,000-50,000 reads/hour
```

### Savings Calculation
```
Improvement: 99% reduction in Firestore reads

Before TTL: 50,000 reads/hour
After TTL: ~500 reads/hour (only refresh cycles)

Monthly savings:
- Reads: 1.2M → 12K reads (98% reduction)
- Cost: ~$0.18 → $0.002/month per million reads
```

---

## Troubleshooting

### Issue: Cache Initialization Hangs

**Symptoms:**
- Backend startup slow (>30 seconds)
- Logs show "[Firestore Optimization] Initializing..." but never completes
- Large timeout/blocked state in logs

**Causes:**
1. Firestore connection slow/blocked
2. Large dataset (1000+ meals) taking time to load
3. Double-check lock contention

**Solutions:**
```bash
# 1. Check Firestore connectivity
gcloud firestore databases list  # Verify database exists

# 2. Check dataset size
# In Firestore Console → meals collection → count documents

# 3. If >5000 meals, may need to increase timeout or paginate
# Consider: Load only active/enabled meals

# 4. Restart backend with verbose logging
# Add print() statements to _initialize_cache()
```

### Issue: Cache Index Missing Meal Type

**Symptoms:**
```
[Firestore Optimization] Meal index built: breakfast=100 lunch=120 snack=0 dinner=130
```

Snack meals returning 0 (expected > 0)

**Causes:**
1. No meals with `meal_type: "snack"` in Firestore
2. Meals have different meal_type casing (e.g., "Snack" vs "snack")
3. `meal_type` field null/missing

**Solutions:**
```python
# 1. Add test data to Firestore
db.collection("meals").add({
    "mealName": "Banana",
    "meal_type": "snack",  # lowercase
    "calories": 89,
    ...
})

# 2. Verify casing consistency
# All meals should have lowercase meal_type

# 3. Check field existence
# In _initialize_cache(), add validation:
for meal in _cached_meals:
    if "meal_type" not in meal:
        print(f"Warning: Meal '{meal.get('mealName')}' missing meal_type field")
```

### Issue: Lock Timeout (Race Condition)

**Symptoms:**
```
RuntimeError: Lock acquisition timeout
Multiple concurrent requests to same endpoint
```

**Causes:**
- Very high concurrency (100+ simultaneous requests)
- Firestore very slow to respond during refresh
- Lock contention on other operations

**Solutions:**
```python
# Current: No timeout
with _cache_lock:
    # Initialize cache

# With timeout (optional enhancement):
if not _cache_lock.acquire(timeout=30):
    print("Lock timeout, using stale cache")
    return _cached_meals
try:
    # Initialize cache
finally:
    _cache_lock.release()
```

### Issue: Stale Data Detected

**Symptoms:**
- Meals in app don't match Firestore console
- New meals not appearing after several minutes

**Expected Delay:**
- New meals appear within 10 minutes (TTL cycle)

**If longer:**
```
1. Check if meal has meal_type field (required for index)
2. Force refresh (see "Forcing Cache Refresh" section)
3. Verify TTL_SECONDS not set too high
4. Check backend logs for initialization errors
```

---

## Performance Monitoring

### Key Metrics to Track

**1. Cache Hit Rate**
```python
# Currently not measured, but can be added:
_cache_hits = 0
_cache_misses = 0

def _initialize_cache():
    global _cache_hits, _cache_misses
    if cache_fresh:
        _cache_hits += 1
    else:
        _cache_misses += 1
```

**2. Refresh Frequency**
```
Expected: Every 600 seconds (10 minutes)
Monitor: Count "[Firestore Optimization] Cache refreshed" log messages

Example: 6 refreshes/hour = healthy
         12 refreshes/hour = TTL too low (increase to 1200)
         1 refresh/hour = TTL too high (decrease to 300)
```

**3. Initialization Time**
```
Expected: <5 seconds (500 meals → ~5ms per meal)
Monitor: Timestamp difference between init start/end log messages

If >10 seconds:
  - Firestore slow
  - Large dataset (>5000 meals)
  - Network bottleneck
```

**4. Firestore Reads**
```
Expected: ~2 reads per 10 minutes (only refresh)
Current: Use Google Cloud Console → Firestore → Usage

Target: 99% reduction from pre-cache baseline
```

---

## Maintenance Schedule

### Daily
- [ ] Check backend logs for initialization errors
- [ ] Verify response times (1-3 second target)
- [ ] No excessive "[Firestore Optimization]" warnings

### Weekly
- [ ] Review Firestore read counts (should be minimal)
- [ ] Check for cache-related errors
- [ ] Verify meal_type index completeness

### Monthly
- [ ] Analyze performance trends
- [ ] Adjust TTL if needed (based on usage patterns)
- [ ] Review correction pass effectiveness (meal swaps per plan)

---

## Configuration Summary

**File:** `repositories/meal_repository.py`

**Variables:**
```python
_cache_lock = threading.Lock()              # Lock for thread safety
_cache_last_refresh = 0                     # Timestamp of last refresh
CACHE_TTL_SECONDS = 600                     # 10 minutes
_meals_by_type = {"breakfast": [], ...}     # Index by meal_type
```

**Tuning Parameters:**
```
Conservative (stale data acceptable):
  CACHE_TTL_SECONDS = 3600   # 1 hour refresh

Balanced (current):
  CACHE_TTL_SECONDS = 600    # 10 minutes refresh

Aggressive (up-to-date meals critical):
  CACHE_TTL_SECONDS = 60     # 1 minute refresh
```

---

## Emergency Procedures

### Cache Completely Corrupted

**Symptoms:**
- Errors on every request
- Meal data not found
- Index empty

**Recovery:**
```bash
# 1. Stop backend
pkill -f "python app.py"

# 2. Edit repositories/meal_repository.py:
_cache_initialized = False  # Force reinit

# 3. Restart backend
python app.py

# Backend will auto-reinitialize on first request
```

### Firestore Connection Failed

**Symptoms:**
```
[Firestore Optimization] Failed to initialize cache: Connection timeout
```

**Recovery:**
```bash
# 1. Verify Firestore service account credentials
ls -la /path/to/serviceAccountKey.json

# 2. Verify Firestore is accessible
gcloud firestore databases list

# 3. Restart with fallback to dev_store
# (Already implemented in code)

# 4. Check network connectivity
curl https://firestore.googleapis.com/v1/
```

---

## Logging Examples

### Successful Startup
```
[Firestore Optimization] Initializing meal cache (thread-safe)...
[Firestore Optimization] Cache initialized (thread-safe): 487 meals
[Firestore Optimization] Meal index built: breakfast=98 lunch=115 snack=47 dinner=127
```

### Successful Request (Using Cache)
```
[Firestore Optimization] Cache still fresh, skipping refresh
[Meal Plan] Generated plan with 4 meals
[Meals] Suggestions generated: 5 from KNN + 2 from cache fallback
```

### Cache Refresh
```
[Firestore Optimization] Cache refreshed at 1702500600.500
[Firestore Optimization] Meal index built: breakfast=98 lunch=115 snack=47 dinner=127
```

### Correction Pass Activity
```
[Meal Plan] Validation failed, attempting correction pass...
[Meal Plan] Correction: protein deviates by 8.2%
[Meal Plan] Correction: Swapped 'Brown Rice' with 'Biryani' in Lunch (safe, same meal_type)
```

---

## References

- **PRODUCTION_IMPROVEMENTS.md** — Full technical details of all 5 improvements
- **repositories/meal_repository.py** — Cache implementation code
- **routes/meal_routes.py** — Swap endpoint using cache fallback
- **ai/meal_plan_generator.py** — Correction pass implementation

---

**Last Updated:** November 2024  
**TTL Cache System Version:** 1.0  
**Status:** Production Ready

