import 'dart:convert';
import 'dart:developer';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  // Backend base URL.
  //
  // - Default: Render (production)
  // - Override for local dev (Android emulator):
  //     flutter run --dart-define=API_BASE_URL=http://10.0.2.2:5000
  static const String baseUrl = 'https://nutrilens-backend-qmft.onrender.com';

  static String? _userId;
  static bool? _onboardingComplete;

  // Secure Storage instance
  static const _secureStorage = FlutterSecureStorage();

  // Keys for SharedPreferences / Secure Storage
  static const String _keyUserId = 'userId';
  static const String _keyOnboarding = 'onboardingComplete';
  static const String _keyUserProfile = 'userProfile';

  // Helper to get full headers
  static Map<String, String> get _headers => {
    "Content-Type": "application/json",
  };

  static void _dbg(String msg) {
    // ignore: avoid_print
    print("[ApiService] $msg");
  }

  static const String _localFallbackBaseUrl = 'http://10.0.2.2:5000';

  static bool _isQuotaExceededResponse(int statusCode, String body) {
    if (statusCode == 429) return true;
    if (statusCode == 500 && body.contains('Quota exceeded')) return true;
    if (body.contains('429 Quota exceeded')) return true;
    return false;
  }

  static bool _shouldTryLocalFallback(int statusCode, String body) {
    if (!_isQuotaExceededResponse(statusCode, body)) return false;
    return baseUrl.startsWith('https://nutrilens-backend-qmft.onrender.com');
  }

  /// Initialize Service: Load persisted user data
  static Future<void> init() async {
    _userId = await _secureStorage.read(key: _keyUserId);
    final onboardingStr = await _secureStorage.read(key: _keyOnboarding);
    _onboardingComplete = onboardingStr == 'true';
    log(
      "ApiService Initialized: UserId=$_userId, Onboarding=$_onboardingComplete",
    );
    _dbg("baseUrl=$baseUrl userId=$_userId onboarding=$_onboardingComplete");
  }

  static String? get userId => _userId;
  static bool get isOnboardingComplete => _onboardingComplete ?? false;

  /// Set User ID and persist it
  static Future<void> setUserId(String userId) async {
    _userId = userId;
    await _secureStorage.write(key: _keyUserId, value: userId);
    log("User ID saved securely: $_userId");
  }

  /// Mark onboarding as complete
  static Future<void> completeOnboarding() async {
    _onboardingComplete = true;
    await _secureStorage.write(key: _keyOnboarding, value: 'true');
    log("Onboarding marked complete");
  }

  /// Logout: Clear data
  static Future<void> logout() async {
    _userId = null;
    _onboardingComplete = false;
    await _secureStorage.delete(key: _keyUserId);
    await _secureStorage.delete(key: _keyOnboarding);
    await _secureStorage.delete(key: _keyUserProfile);
    log("User logged out");
  }

  static Future<Map<String, dynamic>?> readCachedUserProfile() async {
    try {
      final raw = await _secureStorage.read(key: _keyUserProfile);
      if (raw == null || raw.isEmpty) return null;
      final decoded = jsonDecode(raw);
      return decoded is Map<String, dynamic> ? decoded : null;
    } catch (_) {
      return null;
    }
  }

  static Future<void> writeCachedUserProfile(
    Map<String, dynamic> profile,
  ) async {
    try {
      await _secureStorage.write(
        key: _keyUserProfile,
        value: jsonEncode(profile),
      );
    } catch (_) {
      // ignore cache write failures
    }
  }

  // --- API 1: LOGIN USER ---
  static Future<Map<String, dynamic>?> loginUser(
    String email,
    String password,
  ) async {
    final url = Uri.parse('$baseUrl/login');
    try {
      final body = {"email": email, "password": password};
      final payload = jsonEncode(body);
      // Debug prints to inspect request/response end-to-end
      // (do not remove; useful when backend changes slightly)
      // ignore: avoid_print
      print("Login request payload: $payload");
      log("POST /login Payload: $payload");
      final response = await http.post(url, headers: _headers, body: payload);
      // ignore: avoid_print
      print("Login status code: ${response.statusCode}");
      // ignore: avoid_print
      print("Login response: ${response.body}");
      log("Login Response: ${response.statusCode} - ${response.body}");

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        if (responseData is Map<String, dynamic> &&
            responseData['success'] == true) {
          final root = responseData['data'];
          Map<String, dynamic>? userData;

          // Handle both possible backend shapes:
          // 1) { success: true, data: { userId, email } }
          // 2) { success: true, data: { user: { userId, ... } } }
          if (root is Map<String, dynamic>) {
            if (root['userId'] != null) {
              userData = root;
            } else if (root['user'] is Map<String, dynamic>) {
              userData = root['user'] as Map<String, dynamic>;
            }
          }

          if (userData != null && userData['userId'] != null) {
            await setUserId(userData['userId'].toString());
          }
          if (userData != null) {
            await writeCachedUserProfile(userData);
          }
          return userData;
        }
      }
    } catch (e) {
      log("Error in loginUser: $e");
    }
    return null;
  }

  // --- API 2: REGISTER USER ---
  static Future<bool> registerUser(Map<String, dynamic> userData) async {
    final url = Uri.parse('$baseUrl/register');
    try {
      log("POST /register Payload: ${jsonEncode(userData)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(userData),
      );
      log("Response Status: ${response.statusCode}");
      log("Response Body: ${response.body}");

      if (response.statusCode == 200 || response.statusCode == 201) {
        final responseData = jsonDecode(response.body);
        if (responseData is Map<String, dynamic> &&
            responseData['success'] == true) {
          final data = responseData['data'];
          if (data is Map<String, dynamic> && data['userId'] != null) {
            await setUserId(data['userId'].toString());
          }
          return true;
        }
      }
      return false;
    } catch (e) {
      log("Error in registerUser: $e");
      return false;
    }
  }

  // --- API 2: CALCULATE DAILY TARGET ---
  static Future<Map<String, dynamic>?> calculateTarget() async {
    if (_userId == null) {
      log("calculateTarget cancelled: No UserId");
      return null;
    }
    final url = Uri.parse('$baseUrl/calculate-target');
    try {
      final body = {"userId": _userId};
      log("POST /calculate-target Payload: $body");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else if (response.statusCode == 404) {
        // Check if user not found
        final errorBody = response.body;
        if (errorBody.contains("User not found")) {
          log("calculateTarget: User not found (404). Logging out.");
          await logout();
          return null;
        }
        log("calculateTarget Error: ${response.statusCode} - ${response.body}");
      } else {
        log("calculateTarget Error: ${response.statusCode} - ${response.body}");
      }
    } catch (e) {
      log("Error in calculateTarget: $e");
    }
    return null;
  }

  // --- API 3: GENERATE MEAL PLAN ---
  static Future<Map<String, dynamic>?> generateMealPlan() async {
    if (_userId == null) {
      log("generateMealPlan cancelled: No UserId");
      _dbg("POST /generate-meal-plan cancelled: userId=null");
      return null;
    }
    final url = Uri.parse('$baseUrl/generate-meal-plan');
    try {
      final body = {"userId": _userId};
      log("POST /generate-meal-plan Payload: $body");
      _dbg("POST $url payload=${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );

      log(
        "generateMealPlan Response: ${response.statusCode} - ${response.body}",
      );
      _dbg(
        "POST /generate-meal-plan -> ${response.statusCode} body=${response.body}",
      );

      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse(
          '$_localFallbackBaseUrl/generate-meal-plan',
        );
        _dbg("Fallback: POST $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.post(
          fallbackUrl,
          headers: _headers,
          body: jsonEncode(body),
        );
        _dbg(
          "Fallback /generate-meal-plan -> ${fb.statusCode} body=${fb.body}",
        );
        if (fb.statusCode == 200) {
          final responseData = jsonDecode(fb.body);
          return (responseData is Map<String, dynamic>) ? responseData : null;
        }
      }

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        if (responseData is Map<String, dynamic> &&
            responseData['success'] == true) {
          return responseData;
        }
        log("generateMealPlan Warning: unexpected response: $responseData");
        return (responseData is Map<String, dynamic>) ? responseData : null;
      } else if (response.statusCode == 404) {
        if (response.body.contains("User not found")) {
          log("generateMealPlan: User not found (404). Logging out.");
          await logout();
          return null;
        }
      }
    } catch (e) {
      log("Error in generateMealPlan: $e");
    }
    return null;
  }

  // --- API 4: LOG MEAL ---
  static Future<bool> logMeal(Map<String, dynamic> mealData) async {
    final url = Uri.parse('$baseUrl/log-meal');
    try {
      // Ensure source is added if missing, though typically passed by caller
      if (!mealData.containsKey('source')) {
        mealData['source'] = 'manual';
      }
      log("POST /log-meal Payload: ${jsonEncode(mealData)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(mealData),
      );
      return response.statusCode == 200;
    } catch (e) {
      log("Error in logMeal: $e");
      return false;
    }
  }

  // --- API 4.1: UPDATE LOG ---
  static Future<bool> updateLog(String logId, int quantity) async {
    final url = Uri.parse('$baseUrl/update-log');
    try {
      final body = {"logId": logId, "quantity": quantity};
      log("PUT /update-log Payload: ${jsonEncode(body)}");
      _dbg("PUT $url payload=${jsonEncode(body)}");
      final response = await http.put(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      _dbg("PUT /update-log -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/update-log');
        _dbg("Fallback: PUT $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.put(
          fallbackUrl,
          headers: _headers,
          body: jsonEncode(body),
        );
        _dbg("Fallback /update-log -> ${fb.statusCode} body=${fb.body}");
        return fb.statusCode == 200;
      }
      return response.statusCode == 200;
    } catch (e) {
      log("Error in updateLog: $e");
      _dbg("PUT /update-log error=$e");
      return false;
    }
  }

  // --- API 4.2: DELETE LOG ---
  static Future<bool> deleteLog(String logId) async {
    final url = Uri.parse('$baseUrl/delete-log');
    try {
      final body = {"logId": logId};
      log("DELETE /delete-log Payload: ${jsonEncode(body)}");
      _dbg("DELETE $url payload=${jsonEncode(body)}");
      final response = await http.delete(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      _dbg(
        "DELETE /delete-log -> ${response.statusCode} body=${response.body}",
      );
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/delete-log');
        _dbg("Fallback: DELETE $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.delete(
          fallbackUrl,
          headers: _headers,
          body: jsonEncode(body),
        );
        _dbg("Fallback /delete-log -> ${fb.statusCode} body=${fb.body}");
        return fb.statusCode == 200;
      }
      return response.statusCode == 200;
    } catch (e) {
      log("Error in deleteLog: $e");
      _dbg("DELETE /delete-log error=$e");
      return false;
    }
  }

  // --- API 4.4: ANALYZE MEAL NLP (no logging, preview only) ---
  // Returns: List of meal items [{mealName, calories, protein, carbs, fat, quantity}]
  static Future<List<dynamic>?> analyzeMealNLP(String text) async {
    final url = Uri.parse('$baseUrl/analyze-meal-nlp');
    try {
      final body = {"text": text};
      log("POST /analyze-meal-nlp Payload: ${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      log("analyzeMealNLP Response: ${response.statusCode} - ${response.body}");
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // data['data'] is a flat list of meal objects
        if (data['data'] is List) {
          return data['data'] as List<dynamic>;
        }
      }
    } catch (e) {
      log("Error in analyzeMealNLP: $e");
    }
    return null;
  }

  // --- API 4.5: NLP FOOD LOGGING ---
  static Future<dynamic> logMealNLP(String text, String date) async {
    if (_userId == null) return null;
    final url = Uri.parse('$baseUrl/log-meal-nlp-ml');
    try {
      final body = {"userId": _userId, "date": date, "text": text};
      log("POST /log-meal-nlp-ml Payload: ${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      log("logMealNLP Response: ${response.statusCode} - ${response.body}");
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in logMealNLP: $e");
    }
    return null;
  }

  // --- API 4.6: SEARCH FOOD ---
  static Future<List<dynamic>?> searchFood(String query) async {
    final url = Uri.parse('$baseUrl/search-food?q=$query');
    try {
      final response = await http.get(url, headers: _headers);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // Backend returns: { "success": true, "data": [...] } or similar
        return data['data'] ?? data;
      }
    } catch (e) {
      log("Error in searchFood: $e");
    }
    return null;
  }

  // --- API 4.7: GET USER PROFILE ---
  static Future<Map<String, dynamic>?> getUserProfile() async {
    if (_userId == null) return null;
    final url = Uri.parse('$baseUrl/user-profile?userId=$_userId');
    try {
      _dbg("GET $url");
      final response = await http.get(url, headers: _headers);
      _dbg("GET /user-profile -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse(
          '$_localFallbackBaseUrl/user-profile?userId=$_userId',
        );
        _dbg("Fallback: GET $fallbackUrl");
        final fb = await http.get(fallbackUrl, headers: _headers);
        _dbg("Fallback /user-profile -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) return jsonDecode(fb.body);
      }
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in getUserProfile: $e");
      _dbg("GET /user-profile error=$e");
    }
    return null;
  }

  // --- API 4.8: GET STREAK ---
  static Future<Map<String, dynamic>?> getStreak() async {
    if (_userId == null) return null;
    final url = Uri.parse('$baseUrl/get-streak?userId=$_userId');
    try {
      final response = await http.get(url, headers: _headers);
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in getStreak: $e");
    }
    return null;
  }

  // --- API 4.9: GET DAILY RATING ---
  static Future<Map<String, dynamic>?> generateDailyRating(String date) async {
    if (_userId == null) return null;
    final url = Uri.parse('$baseUrl/generate-daily-rating');
    try {
      final body = {"userId": _userId, "date": date};
      log("POST /generate-daily-rating Payload: $body");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in generateDailyRating: $e");
    }
    return null;
  }

  // --- API 5: TRACKER SUMMARY ---
  static Future<Map<String, dynamic>?> getTrackerSummary(String date) async {
    if (_userId == null) return null;
    final url = Uri.parse(
      '$baseUrl/tracker-summary?userId=$_userId&date=$date',
    );
    try {
      log("GET $url");
      _dbg("GET $url");
      final response = await http.get(url, headers: _headers);
      _dbg(
        "GET /tracker-summary -> ${response.statusCode} body=${response.body}",
      );
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse(
          '$_localFallbackBaseUrl/tracker-summary?userId=$_userId&date=$date',
        );
        _dbg("Fallback: GET $fallbackUrl");
        final fb = await http.get(fallbackUrl, headers: _headers);
        _dbg("Fallback /tracker-summary -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) return jsonDecode(fb.body);
      }
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else if (response.statusCode == 404) {
        if (response.body.contains("User not found")) {
          log("getTrackerSummary: User not found (404). Logging out.");
          await logout();
          return null;
        }
      }
    } catch (e) {
      log("Error in getTrackerSummary: $e");
      _dbg("GET /tracker-summary error=$e");
    }
    return null;
  }

  // --- API 6: REPLACE MEAL (Smart Swap) ---
  static Future<Map<String, dynamic>?> replaceMeal(String mealName) async {
    final url = Uri.parse('$baseUrl/replace-meal');
    try {
      final body = {"mealName": mealName};
      log("POST /replace-meal Payload: $body");
      _dbg("POST $url payload=${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      _dbg(
        "POST /replace-meal -> ${response.statusCode} body=${response.body}",
      );
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/replace-meal');
        _dbg("Fallback: POST $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.post(
          fallbackUrl,
          headers: _headers,
          body: jsonEncode(body),
        );
        _dbg("Fallback /replace-meal -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) return jsonDecode(fb.body);
      }
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in replaceMeal: $e");
      _dbg("POST /replace-meal error=$e");
    }
    return null;
  }

  // --- API 7: SWAP MEAL ---
  static Future<Map<String, dynamic>?> swapMeal(
    String mealLogId,
    String newMealName,
  ) async {
    final url = Uri.parse('$baseUrl/swap-meal');
    try {
      final body = {"mealLogId": mealLogId, "newMeal": newMealName};
      log("POST /swap-meal Payload: ${jsonEncode(body)}");
      _dbg("POST $url payload=${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: _headers,
        body: jsonEncode(body),
      );
      log("swapMeal Response: ${response.statusCode} - ${response.body}");
      _dbg("POST /swap-meal -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/swap-meal');
        _dbg("Fallback: POST $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.post(
          fallbackUrl,
          headers: _headers,
          body: jsonEncode(body),
        );
        _dbg("Fallback /swap-meal -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) return jsonDecode(fb.body);
      }
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      log("Error in swapMeal: $e");
      _dbg("POST /swap-meal error=$e");
    }
    return null;
  }

  // --- API 9: GET FOOD DETAILS ---
  static Future<Map<String, dynamic>?> getFoodDetails(String mealName) async {
    final url = Uri.parse(
      '$baseUrl/food-details?name=${Uri.encodeComponent(mealName)}',
    );
    try {
      log("GET $url");
      final response = await http.get(url, headers: _headers);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['data'] != null) {
          return data['data'] as Map<String, dynamic>;
        }
      }
    } catch (e) {
      log("Error in getFoodDetails: $e");
    }
    return null;
  }
}
