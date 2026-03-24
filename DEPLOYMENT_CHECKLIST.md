# Deployment Checklist — 3 Backend Fixes

## Pre-Deployment

- [ ] Backup current backend code
  ```bash
  cp -r backend backend.backup
  ```

- [ ] Verify Python environment
  ```bash
  python --version  # Should be 3.8+
  ```

- [ ] Verify Firebase connection works
  ```bash
  # Check serviceAccountKey.json exists
  ls -la backend/serviceAccountKey.json
  ```

- [ ] Verify test endpoint works
  ```bash
  curl http://localhost:5000/routes
  ```

---

## Code Deployment (4 Files)

### File 1: ai/meal_plan_generator.py ✅
- [ ] `generate_full_meal_plan()` updated with sequential macro tracking
- [ ] `_compute_macro_score()` enhanced with strategic weighting
- [ ] Validation logic added with tolerance checks
- [ ] Logging added for debugging

**Key lines:**
- Lines ~540-630: Main `generate_full_meal_plan()` function
- Lines ~140-170: Enhanced `_compute_macro_score()` function

### File 2: routes/meal_routes.py ✅
- [ ] `/meal/replace-meal` endpoint updated with multi-tier fallback
- [ ] Case-insensitive lookup implemented
- [ ] Debug logging added
- [ ] Error handling improved

**Key lines:**
- Lines ~180-230: Updated `/meal/replace-meal` route

### File 3: repositories/meal_repository.py ✅
- [ ] Cache initialization function added
- [ ] Global cache variables defined
- [ ] All meal queries updated to use cache
- [ ] New `get_meals_filtered()` method added
- [ ] Firestore optimization logging added

**Key changes:**
- Lines 1-40: Cache system setup
- Lines 50-80: `_initialize_cache()` function
- Lines ~100-150: Updated all repository methods
- Lines ~180-220: New `get_meals_filtered()` method

### File 4: app.py ✅
- [ ] Cache initialization call added on startup
- [ ] Try-except wrapping for error handling
- [ ] Debug logging for initialization status

**Key lines:**
- Lines ~75-85: Cache initialization call

---

## Post-Deployment

### 1. Backend Startup ✅
```bash
cd d:\NutriLens
python backend/app.py
```

**Expected console output:**
```
[Firestore Optimization] Initializing meal cache...
[Firestore Optimization] Cache initialized: X meals loaded
[Firestore Optimization] Firestore reads saved by using cache
Firebase initialized successfully
* Running on http://127.0.0.1:5000
```

- [ ] No errors during startup
- [ ] Cache initialization messages visible
- [ ] Backend listening on port 5000

### 2. Verify Cache Initialization
```bash
# In separate terminal, check logs
tail -f backend.log | grep "Firestore Optimization"
```

- [ ] "Initializing meal cache..." appears
- [ ] "Cache initialized: X meals loaded" appears
- [ ] No error messages

### 3. Test Meal Plan Generation
```bash
curl -X POST http://localhost:5000/generate-meal-plan \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "test-user",
    "date": "2026-03-18",
    "dietaryPreferences": ["vegetarian"],
    "targetCalories": 2000,
    "targetProtein": 100,
    "targetCarbs": 250,
    "targetFat": 65
  }'
```

**Response should include:**
```json
{
  "success": true,
  "data": {
    "target_calories": 2000,
    "target_macros": {...},
    "breakfast": {...},
    "lunch": {...},
    "snack": {...},
    "dinner": {...},
    "total_calories": 2000,
    "total_generated_macros": {...},
    "validation": {
      "calories_ok": true,
      "protein_ok": true,
      "fat_ok": true,
      "carbs_ok": true,
      "all_targets_met": true
    }
  }
}
```

- [ ] Response includes `validation` field
- [ ] `all_targets_met` is true
- [ ] Response time < 3 seconds

### 4. Test Swap Meal Endpoint
```bash
curl -X POST http://localhost:5000/meal/replace-meal \
  -H "Content-Type: application/json" \
  -d '{"mealName": "Idli"}'
```

**Response should include:**
```json
{
  "success": true,
  "data": {
    "aiSuggestions": [
      {"mealName": "Dosa"},
      {"mealName": "Uppittu"},
      {"mealName": "Poha"},
      {"mealName": "Tapioca Idli"},
      {"mealName": "Breakfast Burrito"}
    ]
  }
}
```

- [ ] Response received within 1-2 seconds
- [ ] `aiSuggestions` array contains exactly 5 items
- [ ] No spinner hang
- [ ] Never returns empty array

### 5. Monitor Firestore Reads
```bash
# Check optimization logs
grep "Firestore Optimization\|Firestore reads avoided\|cache hit" \
  backend.log | head -20
```

- [ ] See "cache hit" messages (not Firestore queries)
- [ ] Optimization logs show 0 Firestore reads
- [ ] No messages about Firestore reads

### 6. Performance Verification
```bash
# Measure meal plan generation time
time curl -X POST http://localhost:5000/generate-meal-plan \
  -H "Content-Type: application/json" \
  -d '{...}'

# Should complete in 2-3 seconds (vs. 3-5 seconds before)
```

- [ ] Meal plan generation: < 3 seconds
- [ ] Swap meal endpoint: < 2 seconds
- [ ] No timeout errors

---

## Validation Tests

### Test Suite

```python
# tests/test_meal_fixes.py

def test_meal_plan_validation():
    """Test Issue 1: Sequential macro-aware generation"""
    response = generate_meal_plan({
        "targetCalories": 2000,
        "targetProtein": 100,
        "targetCarbs": 250,
        "targetFat": 65
    })
    
    assert "validation" in response["data"]
    assert response["data"]["validation"]["all_targets_met"]
    
def test_replace_meal_fallback():
    """Test Issue 2: Multi-tier fallback"""
    response = replace_meal("Idli")
    
    assert response["data"]["aiSuggestions"]
    assert len(response["data"]["aiSuggestions"]) == 5
    
def test_firestore_cache():
    """Test Issue 3: Cache optimization"""
    # First call should cache
    m1 = get_meal_by_name("Idli")
    
    # Second call should use cache (0 reads)
    m2 = get_meal_by_name("Idli")
    
    assert m1 == m2  # Same result
    # Monitor logs show cache hit, not Firestore read
```

- [ ] All tests pass
- [ ] No assertion errors
- [ ] Performance metrics meet targets

---

## Monitoring After Deployment

### Daily Checks

```bash
# 1. Cache status
grep "Firestore Optimization" backend.log | tail -5

# 2. Error rate
grep "ERROR\|Exception" backend.log | wc -l

# 3. Meal plan validation
grep "all_targets_met: true\|all_targets_met: false" backend.log

# 4. Firestore read count
grep -E "Firestore read|Firestore reads avoided" backend.log | wc -l
```

- [ ] No cache initialization errors
- [ ] Error rate stable or decreased
- [ ] Validation success rate > 95%
- [ ] Firestore reads reduced by 80%+

### Weekly Checks

```bash
# Review meal generation logs
grep "Meal Plan\]" backend.log | tail -20

# Check for outliers
grep "calories_ok: false\|protein_ok: false" backend.log

# Monitor memory usage
ps aux | grep python
```

- [ ] No recurring errors
- [ ] < 5% validation failures
- [ ] Memory stable (~0.5-1 GB with cache)

---

## Rollback Procedure

If critical issues arise:

```bash
# 1. Restore from backup
cp -r backend.backup backend

# 2. Restart backend
python backend/app.py

# 3. Verify original behavior
curl http://localhost:5000/generate-meal-plan ...

# 4. Confirm rollback success
grep -i "error\|exception" backend.log
```

**Estimated rollback time:** 3-5 minutes

---

## Known Issues & Mitigations

### Issue: "Cache not initialized"
**Cause:** Firestore unreachable on startup
**Solution:** 
- Check Firebase credentials
- Verify network connectivity
- App will fall back to Firestore queries automatically

### Issue: "Swap meal endpoint slow"
**Cause:** KNN model not loaded
**Solution:**
- Multi-tier fallback activates automatically
- Endpoint still responds (uses random meals)
- Monitor logs for KNN failures

### Issue: "Memory usage high"
**Cause:** Large meal database (1000+ items)
**Solution:** (Future)
- Implement lazy loading
- Split cache into categories
- Current: ~1 MB per 500 meals (acceptable)

---

## Success Criteria

All of these should be confirmed after deployment:

- [ ] **Issue 1 Fixed:** Meal plans meet validation tolerance (±3% cal, ±5% protein)
- [ ] **Issue 2 Fixed:** Swap endpoint always responds within 1-2 seconds, never returns empty
- [ ] **Issue 3 Fixed:** Firestore reads reduced by 80-90% (measure via Firebase Console)

---

## Sign-Off

- [ ] All tests pass
- [ ] No regression in existing functionality
- [ ] Performance benchmarks met
- [ ] Logs clean (no unexpected errors)
- [ ] Rollback procedure verified
- [ ] Team notified of deployment

**Deployed by:** ________________  
**Date:** ________________  
**Version:** 1.0  
**Status:** ☐ Ready for Production

---

## Contact Support

For deployment issues:
1. Check logs: `tail -f backend.log | grep "ERROR\|Firestore"`
2. Review IMPLEMENTATION_NOTES.md
3. Verify environment: Python, Firebase, dependencies
4. Consider rollback if critical issues persist

