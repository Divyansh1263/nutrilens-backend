import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

class DataProvider extends ChangeNotifier {
  static const Duration _trackerCacheTtl = Duration(minutes: 5);
  static const Duration _dailyRatingCacheTtl = Duration(minutes: 5);
  static const Duration _userProfileCacheTtl = Duration(minutes: 30);
  static const int _maxDatedCacheEntries = 7;
  static const String _cachedMealPlanTimestampKey = 'cachedMealPlanFetchedAt';
  static const String _cachedUserProfileTimestampKey =
      'cachedUserProfileFetchedAt';

  // Data State
  Map<String, dynamic>? dailyTarget;
  Map<String, dynamic>? mealPlan;
  Map<String, dynamic>? trackerSummary;
  Map<String, dynamic>? dailyRating;
  Map<String, dynamic>? userProfile;
  Map<String, dynamic>? streakData;
  bool isDailyTargetLoading = false;
  bool isMealPlanLoading = false;
  bool isTrackerLoading = false;
  bool isProfileLoading = false;
  bool isDailyRatingLoading = false;
  bool isStreakLoading = false;

  // Date-keyed caches keep recent tracker/rating responses in memory.
  final Map<String, Map<String, dynamic>?> _trackerSummaryCache = {};
  final Map<String, Map<String, dynamic>?> _dailyRatingCache = {};
  final Map<String, DateTime> _trackerCacheTime = {};
  final Map<String, DateTime> _dailyRatingCacheTime = {};
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

  Future<void> setUserProfile(Map<String, dynamic>? profile) async {
    userProfile = profile;
    if (profile != null) {
      await ApiService.writeCachedUserProfile(profile);
      await _writeUserProfileTimestamp(DateTime.now());
      _userProfileFetchedAt = DateTime.now();
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

      mealPlan = Map<String, dynamic>.from(jsonDecode(cachedJson));
      _mealPlanFetchedAt = DateTime.tryParse(fetchedAtRaw);
      _notifySafely();
    } catch (e) {
      debugPrint('DataProvider._loadCachedMealPlan error: $e');
      // cache should never crash app
    }
  }

  Future<void> _loadCachedUserProfile() async {
    try {
      final cached = await ApiService.readCachedUserProfile();
      final prefs = await SharedPreferences.getInstance();
      final fetchedAtRaw = prefs.getString(_cachedUserProfileTimestampKey);
      if (cached != null && userProfile == null) {
        userProfile = cached;
        _userProfileFetchedAt = fetchedAtRaw != null
            ? DateTime.tryParse(fetchedAtRaw)
            : null;
        _notifySafely();
      }
    } catch (e) {
      debugPrint('DataProvider._loadCachedUserProfile error: $e');
    }
  }

  // Fetch API 2: Daily Target
  Future<void> fetchDailyTarget() async {
    if (dailyTarget != null) return;
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
      final res = await ApiService.calculateTarget();
      dailyTarget = (res is Map<String, dynamic> && res['success'] == true)
          ? (res['data'] as Map<String, dynamic>?)
          : null;
      debugPrint(
        'DataProvider.fetchDailyTarget availability: '
        '${dailyTarget != null ? 'available' : 'missing'}',
      );
    } catch (e) {
      debugPrint('DataProvider.fetchDailyTarget error: $e');
    } finally {
      _setDailyTargetLoading(false);
    }
  }

  // Fetch API 3: Meal Plan
  Future<void> fetchMealPlan({bool forceRefresh = false}) async {
    if (!forceRefresh &&
        mealPlan != null &&
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
      debugPrint('DataProvider.fetchMealPlan response: $res');
      final nextMealPlan =
          (res is Map<String, dynamic> && res['success'] == true)
          ? (res['data'] as Map<String, dynamic>?)
          : null;

      if (nextMealPlan != null) {
        mealPlan = nextMealPlan;
      } else {
        debugPrint(
          'DataProvider.fetchMealPlan availability: '
          '${mealPlan != null ? 'using-existing-cache' : 'missing'}',
        );
      }

      if (mealPlan != null) {
        await _persistMealPlanCache(mealPlan!);
      }
    } catch (e) {
      debugPrint('DataProvider.fetchMealPlan error: $e');
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
      trackerSummary = _trackerSummaryCache[effectiveDateStr];
      _notifySafely();
      return;
    }

    final pending = _pendingTrackerSummaryFetches[effectiveDateStr];
    if (pending != null && !forceRefresh) {
      await pending;
      if (_currentTrackerDate == effectiveDateStr) {
        trackerSummary = _trackerSummaryCache[effectiveDateStr];
        _notifySafely();
      }
      return;
    }

    final future = _fetchTrackerSummaryInternal(effectiveDateStr);
    _pendingTrackerSummaryFetches[effectiveDateStr] = future;
    await future;
    _pendingTrackerSummaryFetches.remove(effectiveDateStr);

    if (_currentTrackerDate == effectiveDateStr) {
      trackerSummary = _trackerSummaryCache[effectiveDateStr];
      _notifySafely();
    }
  }

  Future<void> _fetchTrackerSummaryInternal(String dateStr) async {
    _setTrackerLoading(true);
    try {
      final response = await ApiService.getTrackerSummary(dateStr);
      _trackerSummaryCache[dateStr] =
          response?['data'] as Map<String, dynamic>?;
      _trackerCacheTime[dateStr] = DateTime.now();
      _trimDatedCache(_trackerSummaryCache, _trackerCacheTime);
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
      dailyRating = _dailyRatingCache[effectiveDateStr];
      _notifySafely();
      return;
    }

    final pending = _pendingDailyRatingFetches[effectiveDateStr];
    if (pending != null && !forceRefresh) {
      await pending;
      if (_currentDailyRatingDate == effectiveDateStr) {
        dailyRating = _dailyRatingCache[effectiveDateStr];
        _notifySafely();
      }
      return;
    }

    final future = _fetchDailyRatingInternal(effectiveDateStr);
    _pendingDailyRatingFetches[effectiveDateStr] = future;
    await future;
    _pendingDailyRatingFetches.remove(effectiveDateStr);

    if (_currentDailyRatingDate == effectiveDateStr) {
      dailyRating = _dailyRatingCache[effectiveDateStr];
      _notifySafely();
    }
  }

  Future<void> _fetchDailyRatingInternal(String dateStr) async {
    _setDailyRatingLoading(true);
    try {
      final response = await ApiService.generateDailyRating(dateStr);
      final payload =
          (response is Map<String, dynamic> && response['success'] == true)
          ? (response['data'] as Map<String, dynamic>?)
          : response;
      _dailyRatingCache[dateStr] = payload;
      _dailyRatingCacheTime[dateStr] = DateTime.now();
      _trimDatedCache(_dailyRatingCache, _dailyRatingCacheTime);
    } catch (e) {
      debugPrint('DataProvider.fetchDailyRating($dateStr) error: $e');
    } finally {
      _setDailyRatingLoading(false);
    }
  }

  Future<void> refreshDietData() async {
    dailyTarget = null;
    mealPlan = null;
    await fetchDailyTarget();
    await fetchMealPlan(forceRefresh: true);
    await fetchTrackerSummary(DateFormat('yyyy-MM-dd').format(DateTime.now()), true);
  }

  Future<void> ensureHomeTabData() async {
    await fetchUserProfile();
    debugPrint(
      'DataProvider.ensureHomeTabData userProfile: '
      '${userProfile != null ? 'available' : 'missing'}',
    );

    await fetchDailyTarget();
    debugPrint(
      'DataProvider.ensureHomeTabData dailyTarget: '
      '${dailyTarget != null ? 'available' : 'missing'}',
    );

    await fetchMealPlan();
    debugPrint(
      'DataProvider.ensureHomeTabData mealPlan: '
      '${mealPlan != null ? 'available' : 'missing'}',
    );

    fetchStreak();
    fetchTrackerSummary();
  }

  Future<void> invalidateTrackerSummary([String? dateStr]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _trackerSummaryCache.remove(effectiveDateStr);
    _trackerCacheTime.remove(effectiveDateStr);
    if (_currentTrackerDate == effectiveDateStr) {
      trackerSummary = null;
      _notifySafely();
    }
  }

  Future<void> invalidateDailyRating([String? dateStr]) async {
    final effectiveDateStr =
        dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    _dailyRatingCache.remove(effectiveDateStr);
    _dailyRatingCacheTime.remove(effectiveDateStr);
    if (_currentDailyRatingDate == effectiveDateStr) {
      dailyRating = null;
      _notifySafely();
    }
  }

  Future<void> refreshTrackerDataForDate(String dateStr) async {
    await invalidateTrackerSummary(dateStr);
    await invalidateDailyRating(dateStr);
    await Future.wait([
      fetchTrackerSummary(dateStr, true),
      fetchDailyRating(dateStr, true),
    ]);
  }

  Map<String, dynamic>? getTrackerSummaryForDate(String dateStr) {
    return _trackerSummaryCache[dateStr];
  }

  Map<String, dynamic>? getDailyRatingForDate(String dateStr) {
    return _dailyRatingCache[dateStr];
  }

  // Fetch API 4.7: User Profile
  Future<void> fetchUserProfile({bool forceRefresh = false}) async {
    if (userProfile != null &&
        !forceRefresh &&
        _isUserProfileCacheFresh()) {
      final hasRealProfileFields =
          userProfile!.containsKey('name') ||
          userProfile!.containsKey('height') ||
          userProfile!.containsKey('weight') ||
          userProfile!.containsKey('goal') ||
          userProfile!.containsKey('activity_level');
      if (hasRealProfileFields) return;
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
      final res = await ApiService.getUserProfile();
      final next = (res is Map<String, dynamic> && res['success'] == true)
          ? (res['data'] as Map<String, dynamic>?)
          : null;

      if (next != null) {
        userProfile = next;
        _userProfileFetchedAt = DateTime.now();
        await ApiService.writeCachedUserProfile(next);
        await _writeUserProfileTimestamp(_userProfileFetchedAt!);
      }
      debugPrint(
        'DataProvider.fetchUserProfile availability: '
        '${userProfile != null ? 'available' : 'missing'}',
      );
    } catch (e) {
      debugPrint('DataProvider.fetchUserProfile error: $e');
    } finally {
      _setProfileLoading(false);
    }
  }

  // Fetch API 4.8: Streak
  Future<void> fetchStreak() async {
    if (streakData != null) return;
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
      final res = await ApiService.getStreak();
      streakData = (res is Map<String, dynamic> && res['success'] == true)
          ? (res['data'] as Map<String, dynamic>?)
          : streakData;
    } catch (e) {
      debugPrint('DataProvider.fetchStreak error: $e');
    } finally {
      _setStreakLoading(false);
    }
  }

  // API 4: Log Meal (Map-based)
  Future<bool> logMeal(dynamic mealNameOrData, [double quantity = 1.0, String mealType = 'Lunch', String source = 'manual']) async {
    final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      if (mealNameOrData is Map<String, dynamic>) {
        final success = await ApiService.logMeal(mealNameOrData);
        if (success) {
          await refreshTrackerDataForDate(today);
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
      if (success) {
        await refreshTrackerDataForDate(today);
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
  Future<Map<String, dynamic>?> swapMeal(String mealLogId, String newMealName) async {
    try {
      final result = await ApiService.swapMeal(mealLogId, newMealName);
      if (result != null) {
        await refreshTrackerDataForDate(DateFormat('yyyy-MM-dd').format(DateTime.now()));
      }
      return result;
    } catch (e) {
      debugPrint('DataProvider.swapMeal error: $e');
      return null;
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
      _trackerSummaryCache.containsKey(key);

  bool _isDailyRatingCacheFresh(String key) =>
      _isCacheFresh(_dailyRatingCacheTime[key], _dailyRatingCacheTtl) &&
      _dailyRatingCache.containsKey(key);

  bool _isUserProfileCacheFresh() =>
      _isCacheFresh(_userProfileFetchedAt, _userProfileCacheTtl);

  bool _isMealPlanCacheFreshForToday() {
    if (mealPlan == null || _mealPlanFetchedAt == null) return false;
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

  void _trimDatedCache(
    Map<String, Map<String, dynamic>?> dataCache,
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
