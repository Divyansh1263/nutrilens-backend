import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class DataProvider extends ChangeNotifier {
  // Data State
  Map<String, dynamic>? dailyTarget;
  Map<String, dynamic>? mealPlan;
  Map<String, dynamic>? trackerSummary;
  Map<String, dynamic>? userProfile;
  Map<String, dynamic>? streakData;
  bool isLoading = false;

  DataProvider() {
    _loadCachedMealPlan();
    _loadCachedUserProfile();
  }

  Future<void> setUserProfile(Map<String, dynamic>? profile) async {
    userProfile = profile;
    if (profile != null) {
      await ApiService.writeCachedUserProfile(profile);
    }
    notifyListeners();
  }

  Future<void> _loadCachedMealPlan() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedUserId = prefs.getString('cachedMealPlanUserId');
      final cachedDate = prefs.getString('cachedMealPlanDate');
      final cachedJson = prefs.getString('cachedMealPlanJson');

      final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
      final userId = ApiService.userId;

      if (cachedJson == null || cachedDate == null || cachedUserId == null) return;
      if (cachedDate != today) return;
      if (userId != null && cachedUserId != userId) return;

      mealPlan = Map<String, dynamic>.from(jsonDecode(cachedJson));
      notifyListeners();
    } catch (_) {
      // cache should never crash app
    }
  }

  Future<void> _loadCachedUserProfile() async {
    try {
      final cached = await ApiService.readCachedUserProfile();
      if (cached != null && userProfile == null) {
        userProfile = cached;
        notifyListeners();
      }
    } catch (_) {}
  }

  // Fetch API 2: Daily Target
  Future<void> fetchDailyTarget() async {
    if (dailyTarget != null) return; // Don't refetch if exists (as per "Do NOT recompute")
    isLoading = true;
    notifyListeners();
    final res = await ApiService.calculateTarget();
    dailyTarget = (res is Map<String, dynamic> && res['success'] == true)
        ? (res['data'] as Map<String, dynamic>?)
        : null;
    isLoading = false;
    notifyListeners();
  }

  // Fetch API 3: Meal Plan
  Future<void> fetchMealPlan({bool forceRefresh = false}) async {
    if (mealPlan != null && !forceRefresh) return; 
    isLoading = true;
    notifyListeners();
    final res = await ApiService.generateMealPlan();
    mealPlan = (res is Map<String, dynamic> && res['success'] == true)
        ? (res['data'] as Map<String, dynamic>?)
        : null;

    // Cache per-day to avoid refetching/regenerating on every cold start.
    if (mealPlan != null) {
      try {
        final prefs = await SharedPreferences.getInstance();
        final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
        await prefs.setString('cachedMealPlanDate', today);
        await prefs.setString('cachedMealPlanUserId', ApiService.userId ?? '');
        await prefs.setString('cachedMealPlanJson', jsonEncode(mealPlan));
      } catch (_) {}
    }

    isLoading = false;
    notifyListeners();
  }

  // Fetch API 5: Tracker Summary
  Future<void> fetchTrackerSummary([String? dateStr]) async {
    isLoading = true;
    notifyListeners();
    final effectiveDateStr = dateStr ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
    final response = await ApiService.getTrackerSummary(effectiveDateStr);
    // ApiService returns the full response body {success, data}
    // Extract just the data portion so UI can access targets/consumed/logs directly
    trackerSummary = response?['data'] as Map<String, dynamic>?;
    isLoading = false;
    notifyListeners();
  }

  // Fetch API 4.7: User Profile
  Future<void> fetchUserProfile({bool forceRefresh = false}) async {
    if (userProfile != null && !forceRefresh) {
      final hasRealProfileFields =
          userProfile!.containsKey('name') ||
          userProfile!.containsKey('height') ||
          userProfile!.containsKey('weight') ||
          userProfile!.containsKey('goal') ||
          userProfile!.containsKey('activity_level');
      if (hasRealProfileFields) return;
    }
    isLoading = true;
    notifyListeners();
    final res = await ApiService.getUserProfile();
    final next = (res is Map<String, dynamic> && res['success'] == true)
        ? (res['data'] as Map<String, dynamic>?)
        : null;

    // Only overwrite if we got a good response.
    if (next != null) {
      userProfile = next;
      await ApiService.writeCachedUserProfile(next);
    }
    isLoading = false;
    notifyListeners();
  }

  // Fetch API 4.8: Streak
  Future<void> fetchStreak() async {
    if (streakData != null) return;
    isLoading = true;
    notifyListeners();
    final res = await ApiService.getStreak();
    streakData = (res is Map<String, dynamic> && res['success'] == true)
        ? (res['data'] as Map<String, dynamic>?)
        : null;
    isLoading = false;
    notifyListeners();
  }

  // API 4: Log Meal (Map-based)
  Future<bool> logMeal(dynamic mealNameOrData, [double quantity = 1.0, String mealType = 'Lunch', String source = 'manual']) async {
    if (mealNameOrData is Map<String, dynamic>) {
      final success = await ApiService.logMeal(mealNameOrData);
      if (success) {
        await fetchTrackerSummary();
      }
      return success;
    } else {
      // Individual params call
      final mealData = {
        'userId': ApiService.userId,
        'date': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'mealName': mealNameOrData.toString(),
        'mealType': mealType,
        'quantity': quantity,
        'source': source,
      };
      final success = await ApiService.logMeal(mealData);
      if (success) {
        await fetchTrackerSummary();
      }
      return success;
    }
  }

  // API 4.5: Log Meal NLP
  Future<dynamic> logMealNLP(String text) async {
    final date = DateFormat('yyyy-MM-dd').format(DateTime.now());
    final result = await ApiService.logMealNLP(text, date);
    if (result != null) {
       await fetchTrackerSummary(); // Refresh tracker after NLP log
    }
    return result;
  }

  // API 6: Replace Meal
  Future<Map<String, dynamic>?> replaceMeal(String mealName) async {
    final res = await ApiService.replaceMeal(mealName);
    if (res is Map<String, dynamic> && res['success'] == true) {
      final data = res['data'];
      return (data is Map<String, dynamic>) ? data : null;
    }
    return null;
  }

  // API 7: Swap Meal
  Future<Map<String, dynamic>?> swapMeal(String mealLogId, String newMealName) async {
    final result = await ApiService.swapMeal(mealLogId, newMealName);
    if (result != null) {
      await fetchTrackerSummary(); // Refresh tracker after swap
    }
    return result;
  }
}
