import 'dart:convert';
import 'dart:developer';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../models/models.dart';

class ApiService {
  // Backend base URL — Google Cloud Run (asia-south1).
  //
  // Override for local dev (Android emulator):
  //   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:5000
  static const String baseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'https://nutrilens-backend-817451767836.asia-south1.run.app');

  static String? _userId;
  static bool? _onboardingComplete;

  // Secure Storage instance
  static const _secureStorage = FlutterSecureStorage();

  // Keys for SharedPreferences / Secure Storage
  static const String _keyUserId = 'userId';
  static const String _keyOnboarding = 'onboardingComplete';
  static const String _keyUserProfile = 'userProfile';

  // ── Auth helpers ──────────────────────────────────────────────────────────

  /// Returns the current Firebase idToken, or null if not signed in.
  static Future<String?> _getIdToken() async {
    try {
      return await FirebaseAuth.instance.currentUser?.getIdToken();
    } catch (_) {
      return null;
    }
  }

  /// Headers with Authorization: Bearer <idToken> when available.
  /// Falls back to Content-Type only (old APK compat).
  static Future<Map<String, String>> _authHeaders() async {
    final token = await _getIdToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Static headers (no token) — kept for methods that cannot be async easily.
  static Map<String, String> get _headers => {
    'Content-Type': 'application/json',
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

  // Cloud Run does not have Render's quota-exceeded pattern.
  // Local fallback is disabled for production.
  static bool _shouldTryLocalFallback(int statusCode, String body) => false;

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

  /// Logout: Clear data + Firebase sign-out
  static Future<void> logout() async {
    _userId = null;
    _onboardingComplete = false;
    await _secureStorage.delete(key: _keyUserId);
    await _secureStorage.delete(key: _keyOnboarding);
    await _secureStorage.delete(key: _keyUserProfile);
    try {
      await FirebaseAuth.instance.signOut();
    } catch (_) {}
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
      final payload = jsonEncode({"email": email, "password": password});
      log("POST /login Payload: $payload");
      final response = await http.post(url, headers: _headers, body: payload);
      log("Login Response: ${response.statusCode} - ${response.body}");

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        if (responseData is Map<String, dynamic> &&
            responseData['success'] == true) {
          final root = responseData['data'];
          Map<String, dynamic>? userData;
          String? customToken;

          if (root is Map<String, dynamic>) {
            // Extract custom token issued by backend (Step 2)
            customToken = root['firebaseCustomToken'] as String?;
            if (root['user'] is Map<String, dynamic>) {
              userData = root['user'] as Map<String, dynamic>;
            } else if (root['userId'] != null) {
              userData = root;
            }
          }

          if (userData != null && userData['userId'] != null) {
            await setUserId(userData['userId'].toString());
          }
          if (userData != null) {
            await writeCachedUserProfile(userData);
          }

          // ── Step 3: Sign into Firebase with the custom token ──────────────
          // This makes FirebaseAuth.currentUser non-null so _getIdToken()
          // returns a real idToken for all subsequent API calls.
          if (customToken != null && customToken.isNotEmpty) {
            try {
              await FirebaseAuth.instance.signInWithCustomToken(customToken);
              log('[auth] Firebase signInWithCustomToken succeeded');
            } catch (e) {
              // Non-fatal: old backend or network issue — app still works
              log('[auth] signInWithCustomToken failed (non-fatal): $e');
            }
          }

          return userData;
        }
      }
    } catch (e) {
      log("Error in loginUser: $e");
    }
    return null;
  }

  // --- GOOGLE SIGN-IN ---
  static Future<Map<String, dynamic>?> signInWithGoogle() async {
    try {
      final googleUser = await GoogleSignIn().signIn();
      if (googleUser == null) return null; // user cancelled

      final googleAuth = await googleUser.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      // Sign into Firebase — this sets currentUser and enables getIdToken()
      final userCredential =
          await FirebaseAuth.instance.signInWithCredential(credential);
      final firebaseUser = userCredential.user;
      if (firebaseUser == null) return null;

      // Notify backend — creates profile if new user
      final headers = await _authHeaders();
      final body = jsonEncode({
        'uid': firebaseUser.uid,
        'email': firebaseUser.email ?? '',
        'displayName': firebaseUser.displayName ?? '',
        'photoURL': firebaseUser.photoURL ?? '',
      });
      final res = await http.post(
        Uri.parse('$baseUrl/google-login'),
        headers: headers,
        body: body,
      );
      log('POST /google-login -> ${res.statusCode} ${res.body}');

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final userData = data['data']?['user'] as Map<String, dynamic>?;
        if (userData != null) {
          final uid = userData['userId'] ?? firebaseUser.uid;
          await setUserId(uid.toString());
          await writeCachedUserProfile(userData);
          return userData;
        }
      }
    } catch (e) {
      log('Error in signInWithGoogle: $e');
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

  // --- API 2.1: UPDATE PROFILE ---
  static Future<Map<String, dynamic>?> updateProfile(Map<String, dynamic> data) async {
    final url = Uri.parse('$baseUrl/update-profile');
    try {
      final headers = await _authHeaders();
      log('[ApiService] PATCH /update-profile → ${jsonEncode(data)}');
      final response = await http.patch(
        url,
        headers: headers,
        body: jsonEncode(data),
      );
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        if (json['success'] == true) {
          log('[ApiService] /update-profile ✓ success');
          return json['data'] as Map<String, dynamic>?;
        }
      }
      log('[ApiService] /update-profile ✗ ${response.statusCode}: ${response.body}');
    } catch (e) {
      log('[ApiService] /update-profile error: $e');
    }
    return null;
  }

  // --- API 2: CALCULATE DAILY TARGET ---
  static Future<Map<String, dynamic>?> calculateTarget() async {
    if (_userId == null) {
      log("calculateTarget cancelled: No UserId");
      return null;
    }
    final url = Uri.parse('$baseUrl/calculate-target');
    try {
      final headers = await _authHeaders();              // B4 FIX
      final body = {"userId": _userId};
      log("POST /calculate-target Payload: $body");
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(body),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else if (response.statusCode == 404) {
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
      final headers = await _authHeaders();              // B4 FIX
      final body = {"userId": _userId};
      log("POST /generate-meal-plan Payload: $body");
      _dbg("POST $url payload=${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(body),
      );
      log("generateMealPlan Response: ${response.statusCode} - ${response.body}");
      _dbg("POST /generate-meal-plan -> ${response.statusCode} body=${response.body}");

      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/generate-meal-plan');
        _dbg("Fallback: POST $fallbackUrl payload=${jsonEncode(body)}");
        final fb = await http.post(fallbackUrl, headers: headers, body: jsonEncode(body));
        _dbg("Fallback /generate-meal-plan -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) {
          final responseData = jsonDecode(fb.body);
          return (responseData is Map<String, dynamic>) ? responseData : null;
        }
      }

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);
        if (responseData is Map<String, dynamic> && responseData['success'] == true) {
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
      if (!mealData.containsKey('source')) mealData['source'] = 'manual';
      final headers = await _authHeaders();
      log("[ApiService] POST /log-meal → ${jsonEncode(mealData)}");
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(mealData),
      );
      final ok = response.statusCode == 200;
      log(ok
          ? '[ApiService] /log-meal ✓ success'
          : '[ApiService] /log-meal ✗ ${response.statusCode}: ${response.body}');
      return ok;
    } catch (e) {
      log("[ApiService] /log-meal error: $e");
      return false;
    }
  }

  // --- API 4.1: UPDATE LOG ---
  /// Returns the updated macro data block on success, or null on failure.
  /// Backend response: { success: true, data: { logId, mealName, quantity,
  ///   calories, protein, carbs, fat } }
  static Future<Map<String, dynamic>?> updateLog(String logId, double quantity) async {
    final url = Uri.parse('$baseUrl/update-log');
    try {
      log("Calling update-log with logId=$logId qty=$quantity");
      final headers = await _authHeaders();              // B4 FIX
      final body = {"logId": logId, "quantity": quantity};
      log("PUT /update-log Payload: ${jsonEncode(body)}");
      _dbg("PUT $url payload=${jsonEncode(body)}");
      final response = await http.put(url, headers: headers, body: jsonEncode(body));
      _dbg("PUT /update-log -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fb = await http.put(
          Uri.parse('$_localFallbackBaseUrl/update-log'),
          headers: headers,
          body: jsonEncode(body),
        );
        if (fb.statusCode == 200) {
          final fbData = jsonDecode(fb.body);
          return fbData['data'] is Map<String, dynamic>
              ? fbData['data'] as Map<String, dynamic>
              : <String, dynamic>{};
        }
      }
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          // Return updated macro block (may be empty map for legacy responses)
          return data['data'] is Map<String, dynamic>
              ? data['data'] as Map<String, dynamic>
              : <String, dynamic>{};
        }
      }
    } catch (e) {
      log("Error in updateLog: $e");
      _dbg("PUT /update-log error=$e");
    }
    return null;
  }

  // --- API 4.2: DELETE LOG ---
  static Future<bool> deleteLog(String logId) async {
    final url = Uri.parse('$baseUrl/delete-log');
    try {
      final headers = await _authHeaders();              // B4 FIX
      final body = {"logId": logId};
      log("DELETE /delete-log Payload: ${jsonEncode(body)}");
      _dbg("DELETE $url payload=${jsonEncode(body)}");
      final response = await http.delete(url, headers: headers, body: jsonEncode(body));
      _dbg("DELETE /delete-log -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fb = await http.delete(
          Uri.parse('$_localFallbackBaseUrl/delete-log'),
          headers: headers,
          body: jsonEncode(body),
        );
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
      final headers = await _authHeaders();
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode({"text": text}),
      );
      log("analyzeMealNLP Response: ${response.statusCode} - ${response.body}");
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
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
      final headers = await _authHeaders();
      final body = {"userId": _userId, "date": date, "text": text};
      log('[ApiService] POST /log-meal-nlp-ml → text="$text" date=$date');
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(body),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        log('[ApiService] /log-meal-nlp-ml ✓ success');
        return data;
      }
      log('[ApiService] /log-meal-nlp-ml ✗ ${response.statusCode}: ${response.body}');
    } catch (e) {
      log('[ApiService] /log-meal-nlp-ml error: $e');
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
      final headers = await _authHeaders();              // B4 FIX
      final response = await http.get(url, headers: headers);
      _dbg("GET /user-profile -> ${response.statusCode} body=${response.body}");
      if (_shouldTryLocalFallback(response.statusCode, response.body)) {
        final fallbackUrl = Uri.parse('$_localFallbackBaseUrl/user-profile?userId=$_userId');
        _dbg("Fallback: GET $fallbackUrl");
        final fb = await http.get(fallbackUrl, headers: headers);
        _dbg("Fallback /user-profile -> ${fb.statusCode} body=${fb.body}");
        if (fb.statusCode == 200) return jsonDecode(fb.body);
      }
      if (response.statusCode == 200) return jsonDecode(response.body);
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
      final headers = await _authHeaders();              // B4 FIX
      final response = await http.get(url, headers: headers);
      if (response.statusCode == 200) return jsonDecode(response.body);
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
      final headers = await _authHeaders();
      // Include userId so backend can resolve dietary restrictions
      final body = {"mealName": mealName, "userId": _userId};
      log("POST /replace-meal Payload: $body");
      _dbg("POST $url payload=${jsonEncode(body)}");
      final response = await http.post(
        url,
        headers: headers,
        body: jsonEncode(body),
      );
      _dbg(
        "POST /replace-meal -> ${response.statusCode} body=${response.body}",
      );
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
  // ═══════════════════════════════════════════════════════════════════════════
  // Step 3 — Typed API companions
  //
  // Rules:
  //  • Each method calls its existing raw counterpart — no new HTTP code.
  //  • Unwraps the backend envelope (success/data) and returns a typed model.
  //  • Returns null on failure so callers can guard the same way as before.
  //  • Old raw methods are untouched — zero breaking changes.
  // ═══════════════════════════════════════════════════════════════════════════

  // --- Step 3: calculateTarget → DailyTarget? ---
  static Future<DailyTarget?> calculateTargetModel() async {
    try {
      final res = await calculateTarget();
      if (res == null || res['success'] != true) return null;
      final data = res['data'];
      if (data is! Map<String, dynamic>) return null;
      final model = DailyTarget.fromJson(data);
      _dbg('[api] DailyTargetModel — calories=${model.calories}');
      return model;
    } catch (e) {
      log('[api] calculateTargetModel error: $e');
      return null;
    }
  }

  // --- Step 3: generateMealPlan → MealPlan? ---
  // DataProvider already does dual-key (data-block / top-level) parsing.
  // We replicate the same logic here so the typed path is self-contained.
  static Future<MealPlan?> generateMealPlanModel() async {
    try {
      final res = await generateMealPlan();
      if (res == null || res['success'] != true) return null;

      Map<String, dynamic>? planMap;
      final dataBlock = res['data'];
      if (dataBlock is Map<String, dynamic> &&
          (dataBlock.containsKey('breakfast') ||
           dataBlock.containsKey('lunch') ||
           dataBlock.containsKey('dinner'))) {
        planMap = dataBlock;
      } else {
        final breakfast = res['breakfast'];
        final lunch     = res['lunch'];
        final snack     = res['snack'];
        final dinner    = res['dinner'];
        if (breakfast != null || lunch != null || snack != null || dinner != null) {
          planMap = {
            'breakfast':       breakfast       ?? [],
            'lunch':           lunch           ?? [],
            'snack':           snack           ?? [],
            'dinner':          dinner          ?? [],
            'target_calories': res['target_calories'],
            'target_macros':   res['target_macros'],
            'total_calories':  res['total_calories'],
          };
        }
      }

      if (planMap == null) return null;
      final model = MealPlan.fromJson(planMap);
      _dbg('[api] MealPlanModel fetched successfully — '
          'B:${model.breakfast.length} L:${model.lunch.length} '
          'S:${model.snack.length} D:${model.dinner.length}');
      return model;
    } catch (e) {
      log('[api] generateMealPlanModel error: $e');
      return null;
    }
  }

  // --- Step 3: getTrackerSummary → TrackerSummary? ---
  static Future<TrackerSummary?> getTrackerSummaryModel(String date) async {
    try {
      final res = await getTrackerSummary(date);
      if (res == null || res['success'] != true) return null;
      final data = res['data'];
      if (data is! Map<String, dynamic>) return null;
      final model = TrackerSummary.fromJson(data);
      _dbg('[api] TrackerSummaryModel fetched — '
          'logs=${model.logs.length} cal=${model.consumed.calories.toStringAsFixed(0)}');
      return model;
    } catch (e) {
      log('[api] getTrackerSummaryModel error: $e');
      return null;
    }
  }

  // --- Step 3: generateDailyRating → DailyRating? ---
  static Future<DailyRating?> generateDailyRatingModel(String date) async {
    try {
      final res = await generateDailyRating(date);
      if (res == null || res['success'] != true) return null;
      final data = res['data'];
      if (data is! Map<String, dynamic>) return null;
      final model = DailyRating.fromJson(data);
      _dbg('[api] DailyRatingModel fetched — stars=${model.stars}');
      return model;
    } catch (e) {
      log('[api] generateDailyRatingModel error: $e');
      return null;
    }
  }

  // --- Step 3: getUserProfile → UserProfile? ---
  static Future<UserProfile?> getUserProfileModel() async {
    try {
      final res = await getUserProfile();
      if (res == null || res['success'] != true) return null;
      final data = res['data'];
      if (data is! Map<String, dynamic>) return null;
      final model = UserProfile.fromJson(data);
      _dbg('[api] UserProfileModel fetched — name=${model.displayName}');
      return model;
    } catch (e) {
      log('[api] getUserProfileModel error: $e');
      return null;
    }
  }

  // --- Step 3: getStreak → StreakData? ---
  static Future<StreakData?> getStreakModel() async {
    try {
      final res = await getStreak();
      if (res == null || res['success'] != true) return null;
      final data = res['data'];
      if (data is! Map<String, dynamic>) return null;
      final model = StreakData.fromJson(data);
      _dbg('[api] StreakDataModel fetched — streak=${model.streak}');
      return model;
    } catch (e) {
      log('[api] getStreakModel error: $e');
      return null;
    }
  }
}
