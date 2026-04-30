import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class DataProvider extends ChangeNotifier {
  static const Duration _trackerCacheTtl = Duration(minutes: 5);
  static const Duration _dailyRatingCacheTtl = Duration(minutes: 5);
  static const Duration _userProfileCacheTtl = Duration(minutes: 30);
  static const int _maxDatedCacheEntries = 7;
  static const String _cachedMealPlanTimestampKey = 'cachedMealPlanFetchedAt';
  static const String _cachedUserProfileTimestampKey =
      'cachedUserProfileFetchedAt';

  // ── Step 5: Typed model fields (sole source of truth) ────────────────────
  MealPlan? mealPlanModel;
  DailyTarget? dailyTargetModel;
  TrackerSummary? trackerSummaryModel;
  DailyRating? dailyRatingModel;
  UserProfile? userProfileModel;
  StreakData? streakDataModel;

  // ── Loading flags ─────────────────────────────────────────────────────────
  bool isDailyTargetLoading = false;
  bool isMealPlanLoading = false;
  bool isTrackerLoading = false;
  bool isProfileLoading = false;
  bool isDailyRatingLoading = false;
  bool isStreakLoading = false;

  // ── Date-keyed typed model caches ─────────────────────────────────────────
  final Map<String, TrackerSummary?> _trackerModelCache = {};
  final Map<String, DailyRating?> _dailyRatingModelCache = {};
  final Map<String, DateTime> _trackerCacheTime = {};
  final Map<String, DateTime> _dailyRatingCacheTime = {};

  // ── Pending-fetch dedup futures ───────────────────────────────────────────
  Future<void>? _pendingDailyTargetFetch;
  Future<void>? _pendingMealPlanFetch;
  Future<void>? _pendingUserProfileFetch;
  Future<void>? _pendingStreakFetch;
  final Map<String, Future<void>> _pendingTrackerSummaryFetches = {};
  final Map<String, Future<void>> _pendingDailyRatingFetches = {};
  String? _currentTrackerDate;
  String? _currentDailyRatingDate;
  DateTime? _userProfileFetchedAt;
  DateTime? _mealPlanFetchedAt;

  DataProvider() {
    _loadCachedMealPlan();
    _loadCachedUserProfile();
  }

  /// Set user profile from external caller (e.g. onboarding, login).
  Future<void> setUserProfile(Map<String, dynamic>? profile) async {
    if (profile != null) {
      try {
        userProfileModel = UserProfile.fromJson(profile);
        await ApiService.writeCachedUserProfile(profile);
        await _writeUserProfileTimestamp(DateTime.now());
        _userProfileFetchedAt = DateTime.now();
        debugPrint('[provider] setUserProfile — name=${userProfileModel!.displayName}');
      } catch (e) {
        debugPrint('[model] UserProfileModel parse error (setUserProfile): $e');
      }
    } else {
      userProfileModel = null;
    }
    _notifySafely();
  }

  Future<void> _loadCachedMealPlan() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedUserId = prefs.getString('cachedMealPlanUserId');
      final cachedDate = prefs.getString('cachedMealPlanDate');
      final cachedJson = prefs.getString('cachedMealPlanJson');
      final fetchedAtRaw = prefs.getString(_cachedMealPlanTimestampKey);

      final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
      final userId = ApiService.userId;

      if (cachedJson == null || cachedDate == null || cachedUserId == null) return;
      if (cachedDate != today) return;
      if (userId != null && cachedUserId != userId) return;
      if (fetchedAtRaw == null) return;

      // Step 5 — parse directly into model; no intermediate Map field
      final rawMap = Map<String, dynamic>.from(jsonDecode(cachedJson));
      _mealPlanFetchedAt = DateTime.tryParse(fetchedAtRaw);
      try {
        mealPlanModel = MealPlan.fromJson(rawMap);
        debugPrint('[model] MealPlanModel restored from SharedPreferences cache');
        _notifySafely();
      } catch (e) {
        debugPrint('[model] MealPlanModel parse error (cache): $e');
      }
    } catch (e) {
      debugPrint('DataProvider._loadCachedMealPlan error: $e');
    }
  }

  Future<void> _loadCachedUserProfile() async {
    try {
      final cached = await ApiService.readCachedUserProfile();
      final prefs = await SharedPreferences.getInstance();
      final fetchedAtRaw = prefs.getString(_cachedUserProfileTimestampKey);
      // Step 5 — parse directly into model; no intermediate Map field
      if (cached != null && userProfileModel == null) {
        _userProfileFetchedAt = fetchedAtRaw != null
            ? DateTime.tryParse(fetchedAtRaw)
            : null;
        try {
          userProfileModel = UserProfile.fromJson(cached);
          debugPrint('[model] UserProfileModel restored from SecureStorage cache');
          _notifySafely();
        } catch (e) {
          debugPrint('[model] UserProfileModel parse error (cache): $e');
        }
      }
    } catch (e) {
      debugPrint('DataProvider._loadCachedUserProfile error: $e');
    }
  }

  // Fetch API 2: Daily Target
  Future<void> fetchDailyTarget() async {
    // Step 5 — guard on model field
    if (dailyTargetModel != null) return;
    if (_pendingDailyTargetFetch != null) {
      await _pendingDailyTargetFetch;
      return;
    }
    final future = _fetchDailyTargetInternal();
    _pendingDailyTargetFetch = future;
    await future;
    _pendingDailyTargetFetch = null;
  }

  Future<void> _fetchDailyTargetInternal() async {
    _setDailyTargetLoading(true);
    try {
      // Step 5 — typed companion only; no Map fallback
      final model = await ApiService.calculateTargetModel();
      if (model != null) {
        dailyTargetModel = model;
        debugPrint('[api] DailyTargetModel fetched successfully — calories=${model.calories}');
      }
    } catch (e) {
      debugPrint('DataProvider.fetchDailyTarget error: $e');
    } finally {
      _setDailyTargetLoading(false);
    }
  }

  // Fetch API 3: Meal Plan
  Future<void> fetchMealPlan({bool forceRefresh = false}) async {
    // Step 5 — guard on model field
    if (!forceRefresh &&
        mealPlanModel != null &&
        _isMealPlanCacheFreshForToday()) {
      return;
    }
    if (_pendingMealPlanFetch != null && !forceRefresh) {
      await _pendingMealPlanFetch;
      return;
    }
    final future = _fetchMealPlanInternal();
    _pendingMealPlanFetch = future;
    await future;
    _pendingMealPlanFetch = null;
  }

  Future<void> _fetchMealPlanInternal() async {
    _setMealPlanLoading(true);
    try {
      final res = await ApiService.generateMealPlan();

      // TASK 1: log raw API response for debugging
      debugPrint('[meal-plan] RAW API RESPONSE keys: ${res is Map ? (res as Map).keys.toList() : res}');

      if (res is! Map<String, dynamic> || res['success'] != true) {
        debugPrint('[meal-plan] fetchMealPlan: unsuccessful or malformed response');
        return;
      }

      // TASK 2 & 8: dual-key parsing with safe fallback
      // Backend returns BOTH res['data']['breakfast'] AND res['breakfast'] (top-level).
      // Prefer res['data'] (structured), fall back to top-level keys.
      Map<String, dynamic>? nextMealPlan;

      final dataBlock = res['data'];
      if (dataBlock is Map<String, dynamic> &&
          (dataBlock.containsKey('breakfast') ||
           dataBlock.containsKey('lunch') ||
           dataBlock.containsKey('dinner'))) {
        nextMealPlan = dataBlock;
        debugPrint('[meal-plan] parsed from res["data"] block');
      } else {
        // Fallback: pick slot keys directly from top-level response
        final breakfast = res['breakfast'];
        final lunch     = res['lunch'];
        final snack     = res['snack'];
        final dinner    = res['dinner'];

        if (breakfast != null || lunch != null || snack != null || dinner != null) {
          nextMealPlan = {
            'breakfast':       breakfast       ?? [],
            'lunch':           lunch           ?? [],
            'snack':           snack           ?? [],
            'dinner':          dinner          ?? [],
            'target_calories': res['target_calories'],
            'target_macros':   res['target_macros'],
            'total_calories':  res['total_calories'],
          };
          debugPrint('[meal-plan] parsed from top-level keys (backward-compat path)');
        }
      }

      // TASK 6: log slot sizes before assigning
      if (nextMealPlan != null) {
        final bLen = (nextMealPlan['breakfast'] as List?)?.length ?? 0;
        final lLen = (nextMealPlan['lunch']     as List?)?.length ?? 0;
        final sLen = (nextMealPlan['snack']     as List?)?.length ?? 0;
        final dLen = (nextMealPlan['dinner']    as List?)?.length ?? 0;
        debugPrint('[meal-plan] Breakfast items: $bLen');
        debugPrint('[meal-plan] Lunch items: $lLen');
        debugPrint('[meal-plan] Snack items: $sLen');
        debugPrint('[meal-plan] Dinner items: $dLen');
      }

      if (nextMealPlan != null) {
        // Step 5 — parse directly into model; no Map field assignment
        try {
          mealPlanModel = MealPlan.fromJson(nextMealPlan);
          debugPrint(
            '[api] MealPlanModel fetched successfully — '
            'B:${mealPlanModel!.breakfast.length} '
            'L:${mealPlanModel!.lunch.length} '
            'S:${mealPlanModel!.snack.length} '
            'D:${mealPlanModel!.dinner.length}',
          );
          _notifySafely();
          await _persistMealPlanCache(nextMealPlan);
        } catch (e) {
          debugPrint('[model] MealPlanModel parse error: $e');
        }
      } else {
        debugPrint(
          '[meal-plan] fetchMealPlan: no slots found in response — '
          '${mealPlanModel != null ? "keeping existing cache" : "mealPlan remains null"}',
        );
      }
    } catch (e) {
      debugPrint('[meal-plan] fetchMealPlan error: $e');
    } finally {
      _setMealPlanLoading(false);
    }
  }


  // Fetch API 5: Tracker Summary
  Future<void> fetchTrackerSummary([String? dateStr, bool forceRefresh = false]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _currentTrackerDate = effectiveDateStr;

    if (!forceRefresh && _isTrackerCacheFresh(effectiveDateStr)) {
      _syncTrackerFromCache(effectiveDateStr);
      _notifySafely();
      return;
    }

    final pending = _pendingTrackerSummaryFetches[effectiveDateStr];
    if (pending != null && !forceRefresh) {
      await pending;
      if (_currentTrackerDate == effectiveDateStr) {
        _syncTrackerFromCache(effectiveDateStr);
        _notifySafely();
      }
      return;
    }

    final future = _fetchTrackerSummaryInternal(effectiveDateStr);
    _pendingTrackerSummaryFetches[effectiveDateStr] = future;
    await future;
    _pendingTrackerSummaryFetches.remove(effectiveDateStr);

    if (_currentTrackerDate == effectiveDateStr) {
      _syncTrackerFromCache(effectiveDateStr);
      _notifySafely();
    }
  }

  /// Step 5 — syncs model field from the typed cache.
  void _syncTrackerFromCache(String dateStr) {
    trackerSummaryModel = _trackerModelCache[dateStr];
  }

  Future<void> _fetchTrackerSummaryInternal(String dateStr) async {
    _setTrackerLoading(true);
    try {
      // Step 5 — typed model cache only
      final model = await ApiService.getTrackerSummaryModel(dateStr);
      if (model != null) {
        _trackerModelCache[dateStr] = model;
        _trackerCacheTime[dateStr] = DateTime.now();
        _trimTypedDatedCache(_trackerModelCache, _trackerCacheTime);
        debugPrint('[api] TrackerSummaryModel fetched successfully — '
            'logs=${model.logs.length} '
            'cal=${model.consumed.calories.toStringAsFixed(0)}');
      }
    } catch (e) {
      debugPrint('DataProvider.fetchTrackerSummary($dateStr) error: $e');
    } finally {
      _setTrackerLoading(false);
    }
  }

  Future<void> fetchDailyRating([String? dateStr, bool forceRefresh = false]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _currentDailyRatingDate = effectiveDateStr;

    if (!forceRefresh && _isDailyRatingCacheFresh(effectiveDateStr)) {
      _syncDailyRatingFromCache(effectiveDateStr);
      _notifySafely();
      return;
    }

    final pending = _pendingDailyRatingFetches[effectiveDateStr];
    if (pending != null && !forceRefresh) {
      await pending;
      if (_currentDailyRatingDate == effectiveDateStr) {
        _syncDailyRatingFromCache(effectiveDateStr);
        _notifySafely();
      }
      return;
    }

    final future = _fetchDailyRatingInternal(effectiveDateStr);
    _pendingDailyRatingFetches[effectiveDateStr] = future;
    await future;
    _pendingDailyRatingFetches.remove(effectiveDateStr);

    if (_currentDailyRatingDate == effectiveDateStr) {
      _syncDailyRatingFromCache(effectiveDateStr);
      _notifySafely();
    }
  }

  /// Step 5 — syncs model field from the typed cache.
  void _syncDailyRatingFromCache(String dateStr) {
    dailyRatingModel = _dailyRatingModelCache[dateStr];
  }

  Future<void> _fetchDailyRatingInternal(String dateStr) async {
    _setDailyRatingLoading(true);
    try {
      // Step 5 — typed model cache only
      final model = await ApiService.generateDailyRatingModel(dateStr);
      if (model != null) {
        _dailyRatingModelCache[dateStr] = model;
        _dailyRatingCacheTime[dateStr] = DateTime.now();
        _trimTypedDatedCache(_dailyRatingModelCache, _dailyRatingCacheTime);
        debugPrint('[api] DailyRatingModel fetched successfully — stars=${model.stars}');
      }
    } catch (e) {
      debugPrint('DataProvider.fetchDailyRating($dateStr) error: $e');
    } finally {
      _setDailyRatingLoading(false);
    }
  }

  Future<void> refreshDietData() async {
    // Step 5 — clear model fields only
    dailyTargetModel = null;
    mealPlanModel = null;
    await fetchDailyTarget();
    await fetchMealPlan(forceRefresh: true);
    await fetchTrackerSummary(DateFormat('yyyy-MM-dd').format(DateTime.now()), true);
  }

  Future<void> ensureHomeTabData() async {
    await fetchUserProfile();
    debugPrint('DataProvider.ensureHomeTabData userProfile: '
        '${userProfileModel != null ? 'available' : 'missing'}');

    await fetchDailyTarget();
    debugPrint('DataProvider.ensureHomeTabData dailyTarget: '
        '${dailyTargetModel != null ? 'available' : 'missing'}');

    await fetchMealPlan();
    debugPrint('DataProvider.ensureHomeTabData mealPlan: '
        '${mealPlanModel != null ? 'available' : 'missing'}');

    fetchStreak();
    fetchTrackerSummary();
  }

  Future<void> invalidateTrackerSummary([String? dateStr]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _trackerModelCache.remove(effectiveDateStr);
    _trackerCacheTime.remove(effectiveDateStr);
    if (_currentTrackerDate == effectiveDateStr) {
      trackerSummaryModel = null;
      _notifySafely();
    }
  }

  Future<void> invalidateDailyRating([String? dateStr]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _dailyRatingModelCache.remove(effectiveDateStr);
    _dailyRatingCacheTime.remove(effectiveDateStr);
    if (_currentDailyRatingDate == effectiveDateStr) {
      dailyRatingModel = null;
      _notifySafely();
    }
  }

  Future<void> refreshTrackerDataForDate(String dateStr, {bool force = false}) async {
    // TTL guard: skip refresh if cache is still fresh (unless forced).
    if (!force && _isTrackerCacheFresh(dateStr)) return;
    await invalidateTrackerSummary(dateStr);
    await invalidateDailyRating(dateStr);
    await Future.wait([
      fetchTrackerSummary(dateStr, true),
      fetchDailyRating(dateStr, true),
    ]);
  }

  // Step 5 — typed-only date getters (Map getters removed)
  TrackerSummary? getTrackerModelForDate(String dateStr) =>
      _trackerModelCache[dateStr];

  DailyRating? getDailyRatingModelForDate(String dateStr) =>
      _dailyRatingModelCache[dateStr];

  /// Replaces the meal plan model and notifies listeners.
  void setMealPlan(Map<String, dynamic> newPlan) {
    try {
      mealPlanModel = MealPlan.fromJson(newPlan);
      debugPrint('[provider] setMealPlan — model updated');
    } catch (e) {
      debugPrint('[model] MealPlanModel parse error (setMealPlan): $e');
    }
    _notifySafely();
  }

  // Fetch API 4.7: User Profile
  Future<void> fetchUserProfile({bool forceRefresh = false}) async {
    // Step 5 — guard on model field; check model has real content
    if (userProfileModel != null && !forceRefresh && _isUserProfileCacheFresh()) {
      final hasRealFields = userProfileModel!.height != null ||
          userProfileModel!.weight != null ||
          (userProfileModel!.goal?.isNotEmpty ?? false);
      if (hasRealFields) return;
    }
    if (_pendingUserProfileFetch != null && !forceRefresh) {
      await _pendingUserProfileFetch;
      return;
    }
    final future = _fetchUserProfileInternal();
    _pendingUserProfileFetch = future;
    await future;
    _pendingUserProfileFetch = null;
  }

  Future<void> _fetchUserProfileInternal() async {
    _setProfileLoading(true);
    try {
      // Step 5 — typed companion only; no Map fallback
      final model = await ApiService.getUserProfileModel();
      if (model != null) {
        userProfileModel = model;
        _userProfileFetchedAt = DateTime.now();
        await ApiService.writeCachedUserProfile(model.toJson());
        await _writeUserProfileTimestamp(_userProfileFetchedAt!);
        debugPrint('[api] UserProfileModel fetched successfully — name=${model.displayName}');
      }
      debugPrint('DataProvider.fetchUserProfile availability: '
          '${userProfileModel != null ? 'available' : 'missing'}');
    } catch (e) {
      debugPrint('DataProvider.fetchUserProfile error: $e');
    } finally {
      _setProfileLoading(false);
    }
  }

  // API 4.7.1: Update User Profile
  Future<bool> updateUserProfile(Map<String, dynamic> data) async {
    final updated = await ApiService.updateProfile(data);

    if (updated != null && userProfileModel != null) {
      userProfileModel = userProfileModel!.copyWith(
        height: updated["height"] != null ? (updated["height"] as num).toDouble() : null,
        weight: updated["weight"] != null ? (updated["weight"] as num).toDouble() : null,
        activityLevel: updated["activityLevel"],
        goal: updated["goal"],
      );

      _notifySafely();
      
      // Also write back to cache so it persists locally
      await ApiService.writeCachedUserProfile(userProfileModel!.toJson());
      
      // Refresh targets using the new stats
      await fetchDailyTarget();

      return true;
    }

    return false;
  }

  // Fetch API 4.8: Streak
  Future<void> fetchStreak() async {
    // Step 5 — guard on model field
    if (streakDataModel != null) return;
    if (_pendingStreakFetch != null) {
      await _pendingStreakFetch;
      return;
    }
    final future = _fetchStreakInternal();
    _pendingStreakFetch = future;
    await future;
    _pendingStreakFetch = null;
  }

  Future<void> _fetchStreakInternal() async {
    _setStreakLoading(true);
    try {
      // Step 5 — model only; no Map field
      final model = await ApiService.getStreakModel();
      if (model != null) {
        streakDataModel = model;
        debugPrint('[api] StreakDataModel fetched successfully — streak=${model.streak}');
      }
    } catch (e) {
      debugPrint('DataProvider.fetchStreak error: $e');
    } finally {
      _setStreakLoading(false);
    }
  }

  // API 4: Log Meal (Map-based)
  // Set [refresh] to false when batch-logging to defer the tracker refresh.
  Future<bool> logMeal(
    dynamic mealNameOrData, [
    double quantity = 1.0,
    String mealType = 'Lunch',
    String source = 'manual',
    bool refresh = true,
  ]) async {
    final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      if (mealNameOrData is Map<String, dynamic>) {
        final success = await ApiService.logMeal(mealNameOrData);
        if (success && refresh) {
          await refreshTrackerDataForDate(today, force: true);
        }
        return success;
      }

      final mealData = {
        'userId': ApiService.userId,
        'date': today,
        'mealName': mealNameOrData.toString(),
        'mealType': mealType,
        'quantity': quantity,
        'source': source,
      };
      final success = await ApiService.logMeal(mealData);
      if (success && refresh) {
        await refreshTrackerDataForDate(today, force: true);
      }
      return success;
    } catch (e) {
      debugPrint('DataProvider.logMeal error: $e');
      return false;
    }
  }

  // API 4.5: Log Meal NLP
  Future<dynamic> logMealNLP(String text) async {
    final date = DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      final result = await ApiService.logMealNLP(text, date);
      if (result != null) {
         await refreshTrackerDataForDate(date);
      }
      return result;
    } catch (e) {
      debugPrint('DataProvider.logMealNLP error: $e');
      return null;
    }
  }

  // API 6: Replace Meal
  Future<Map<String, dynamic>?> replaceMeal(String mealName) async {
    try {
      final res = await ApiService.replaceMeal(mealName);
      if (res is Map<String, dynamic> && res['success'] == true) {
        final data = res['data'];
        return (data is Map<String, dynamic>) ? data : null;
      }
    } catch (e) {
      debugPrint('DataProvider.replaceMeal error: $e');
    }
    return null;
  }

  // API 7: Swap Meal
  // [dateKey] should be the date that the swapped log belongs to.
  Future<Map<String, dynamic>?> swapMeal(
      String mealLogId, String newMealName, [String? dateKey]) async {
    final effectiveKey =
        dateKey ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      final result = await ApiService.swapMeal(mealLogId, newMealName);
      if (result != null) {
        await refreshTrackerDataForDate(effectiveKey, force: true);
      }
      return result;
    } catch (e) {
      debugPrint('DataProvider.swapMeal error: $e');
      return null;
    }
  }

  // API 8: Update Log Quantity
  // All UI quantity controls must go through this method — never call
  // ApiService.updateLog directly from a widget.
  //
  // FIX v2.7: Two-phase update:
  //   Phase 1 — instant optimistic patch from API response (server-computed,
  //             no frontend multiplication, no drift).
  //   Phase 2 — delayed full tracker re-fetch (300 ms) so the server state
  //             overwrites the optimistic patch without causing a visible reset.
  Future<bool> updateLog(String logId, double newQuantity, [String? dateKey]) async {
    final effectiveKey =
        dateKey ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      final updatedData = await ApiService.updateLog(logId, newQuantity);
      if (updatedData != null) {
        debugPrint('[provider] updateLog received: logId=$logId qty=${updatedData["quantity"]} cal=${updatedData["calories"]}');
        // Phase 1: instant optimistic patch using server-returned values.
        // NEVER recompute calories here — use exactly what the server sent.
        _applyOptimisticLogUpdate(effectiveKey, logId, updatedData);
        // Phase 2: delayed refresh — prevents the background fetch from
        // landing before the optimistic patch and reverting the UI.
        Future.delayed(const Duration(milliseconds: 300), () {
          debugPrint('[provider] delayed tracker refresh — logId=$logId date=$effectiveKey');
          fetchTrackerSummary(effectiveKey, true);
          fetchDailyRating(effectiveKey, true);
        });
        return true;
      }
      return false;
    } catch (e) {
      debugPrint('DataProvider.updateLog error: $e');
      return false;
    }
  }

  /// Patches a single [MealLog] entry in the in-memory tracker cache and
  /// recomputes consumed macro totals.  Called immediately after a successful
  /// /update-log response so the UI reacts with zero additional latency.
  void _applyOptimisticLogUpdate(
    String dateKey,
    String logId,
    Map<String, dynamic> updated,
  ) {
    final current = _trackerModelCache[dateKey];
    if (current == null) return;

    // Rebuild the logs list, replacing the matching entry.
    // FIX v2.7: Read quantity as num (not int) — server returns fractional
    // values like 1.3, 0.8 which must not be truncated to int.
    // All macro values come directly from the server response — never
    // recomputed on the client to avoid double-scaling.
    final newLogs = current.logs.map((log) {
      if (log.logId != logId) return log;

      // Server quantity may be int or double — preserve as double
      final qty = (updated['quantity'] as num?)?.toDouble() ?? log.quantity;

      return MealLog(
        logId:    log.logId,
        mealName: log.mealName,
        mealType: log.mealType,
        // Use server-computed totals verbatim — no frontend multiplication.
        calories: (updated['calories'] as num?)?.toDouble() ?? log.calories,
        protein:  (updated['protein']  as num?)?.toDouble() ?? log.protein,
        carbs:    (updated['carbs']    as num?)?.toDouble() ?? log.carbs,
        fat:      (updated['fat']      as num?)?.toDouble() ?? log.fat,
        quantity: qty,
        date:     log.date,
        source:   log.source,
        servingSize: log.servingSize,
        servingGrams: log.servingGrams,
      );
    }).toList();

    // Recompute consumed totals from the updated log list.
    final totalCal   = newLogs.fold<double>(0, (s, l) => s + l.calories);
    final totalProt  = newLogs.fold<double>(0, (s, l) => s + l.protein);
    final totalCarbs = newLogs.fold<double>(0, (s, l) => s + l.carbs);
    final totalFat   = newLogs.fold<double>(0, (s, l) => s + l.fat);

    _trackerModelCache[dateKey] = TrackerSummary(
      date:     current.date,
      targets:  current.targets,
      consumed: NutrientTotals(
        calories: totalCal,
        protein:  totalProt,
        carbs:    totalCarbs,
        fat:      totalFat,
      ),
      logs: newLogs,
    );

    debugPrint('[provider] optimistic log update applied — '
        'logId=$logId qty=${updated["quantity"]} '
        'cal=${updated["calories"]}');
    _notifySafely();
  }

  // API 9: Delete Log
  // All UI delete actions must go through this method — never call
  // ApiService.deleteLog directly from a widget.
  Future<bool> deleteLog(String logId, [String? dateKey]) async {
    final effectiveKey =
        dateKey ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      final ok = await ApiService.deleteLog(logId);
      if (ok) {
        // Also apply a background refresh without clearing the cache instantly
        fetchTrackerSummary(effectiveKey, true);
        fetchDailyRating(effectiveKey, true);
      }
      return ok;
    } catch (e) {
      debugPrint('DataProvider.deleteLog error: $e');
      return false;
    }
  }

  bool get isLoading =>
      isDailyTargetLoading ||
      isMealPlanLoading ||
      isTrackerLoading ||
      isProfileLoading ||
      isDailyRatingLoading ||
      isStreakLoading;

  bool _isTrackerCacheFresh(String key) =>
      _isCacheFresh(_trackerCacheTime[key], _trackerCacheTtl) &&
      _trackerModelCache.containsKey(key);

  bool _isDailyRatingCacheFresh(String key) =>
      _isCacheFresh(_dailyRatingCacheTime[key], _dailyRatingCacheTtl) &&
      _dailyRatingModelCache.containsKey(key);

  bool _isUserProfileCacheFresh() =>
      _isCacheFresh(_userProfileFetchedAt, _userProfileCacheTtl);

  bool _isMealPlanCacheFreshForToday() {
    if (mealPlanModel == null || _mealPlanFetchedAt == null) return false;
    final now = DateTime.now();
    final fetchedAt = _mealPlanFetchedAt!;
    return fetchedAt.year == now.year &&
        fetchedAt.month == now.month &&
        fetchedAt.day == now.day;
  }

  bool _isCacheFresh(DateTime? cachedAt, Duration ttl) {
    if (cachedAt == null) return false;
    return DateTime.now().difference(cachedAt) <= ttl;
  }

  Future<void> _persistMealPlanCache(Map<String, dynamic> plan) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final now = DateTime.now();
      _mealPlanFetchedAt = now;
      await prefs.setString(
        'cachedMealPlanDate',
        DateFormat('yyyy-MM-dd').format(now),
      );
      await prefs.setString('cachedMealPlanUserId', ApiService.userId ?? '');
      await prefs.setString('cachedMealPlanJson', jsonEncode(plan));
      await prefs.setString(_cachedMealPlanTimestampKey, now.toIso8601String());
    } catch (e) {
      debugPrint('DataProvider._persistMealPlanCache error: $e');
    }
  }

  Future<void> _writeUserProfileTimestamp(DateTime timestamp) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _cachedUserProfileTimestampKey,
        timestamp.toIso8601String(),
      );
    } catch (e) {
      debugPrint('DataProvider._writeUserProfileTimestamp error: $e');
    }
  }

  /// Step 5 — generic trim: evicts oldest entries from any dated model cache.
  void _trimTypedDatedCache<T>(
    Map<String, T?> dataCache,
    Map<String, DateTime> timeCache,
  ) {
    if (timeCache.length <= _maxDatedCacheEntries) return;
    final sortedKeys = timeCache.keys.toList()
      ..sort((a, b) => timeCache[a]!.compareTo(timeCache[b]!));
    while (sortedKeys.length > _maxDatedCacheEntries) {
      final oldestKey = sortedKeys.removeAt(0);
      timeCache.remove(oldestKey);
      dataCache.remove(oldestKey);
    }
  }

  void _setDailyTargetLoading(bool value) {
    if (isDailyTargetLoading == value) return;
    isDailyTargetLoading = value;
    _notifySafely();
  }

  void _setMealPlanLoading(bool value) {
    if (isMealPlanLoading == value) return;
    isMealPlanLoading = value;
    _notifySafely();
  }

  void _setTrackerLoading(bool value) {
    if (isTrackerLoading == value) return;
    isTrackerLoading = value;
    _notifySafely();
  }

  void _setProfileLoading(bool value) {
    if (isProfileLoading == value) return;
    isProfileLoading = value;
    _notifySafely();
  }

  void _setDailyRatingLoading(bool value) {
    if (isDailyRatingLoading == value) return;
    isDailyRatingLoading = value;
    _notifySafely();
  }

  void _setStreakLoading(bool value) {
    if (isStreakLoading == value) return;
    isStreakLoading = value;
    _notifySafely();
  }

  void _notifySafely() {
    notifyListeners();
  }
}
