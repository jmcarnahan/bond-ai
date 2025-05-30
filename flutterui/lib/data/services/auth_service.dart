import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/token_model.dart';
import 'package:flutterui/data/models/user_model.dart';
import '../../core/utils/logger.dart';

const String _tokenStorageKey = 'bondai_auth_token';

@immutable
class AuthService {
  final http.Client _httpClient;
  final SharedPreferences _sharedPreferences;

  AuthService({
    http.Client? httpClient,
    required SharedPreferences sharedPreferences,
  }) : _httpClient = httpClient ?? http.Client(),
       _sharedPreferences = sharedPreferences;

  // 1. Initiate Login (Redirect to backend's /login endpoint)
  Future<void> launchLoginUrl() async {
    final Uri loginUri = Uri.parse(
      ApiConstants.baseUrl + ApiConstants.loginEndpoint,
    );
    if (await canLaunchUrl(loginUri)) {
      // For web, 'webOnlyWindowName: _self' will attempt to open in the same tab.
      // For mobile, it will open in an external browser or webview.
      await launchUrl(loginUri, webOnlyWindowName: '_self');
    } else {
      throw Exception('Could not launch $loginUri');
    }
  }

  // 2. Store Token (Called after token is obtained, e.g., from URL)
  Future<void> storeToken(String accessToken) async {
    logger.i("[AuthService] Storing token: $accessToken");
    await _sharedPreferences.setString(_tokenStorageKey, accessToken);
    logger.i("[AuthService] Token stored.");
  }

  // 3. Retrieve Token
  Future<String?> retrieveToken() async {
    final token = _sharedPreferences.getString(_tokenStorageKey);
    logger.i("[AuthService] Retrieving token: $token");
    return token;
  }

  // 4. Clear Token (Logout)
  Future<void> clearToken() async {
    logger.i("[AuthService] Clearing token.");
    await _sharedPreferences.remove(_tokenStorageKey);
    logger.i("[AuthService] Token cleared.");
  }

  // 5. Get Current User (Requires token)
  Future<User> getCurrentUser() async {
    logger.i("[AuthService] getCurrentUser called.");
    final token = await retrieveToken();
    if (token == null) {
      logger.i("[AuthService] No token found for getCurrentUser.");
      throw Exception('Not authenticated: No token found.');
    }
    logger.i(
      "[AuthService] Token found for getCurrentUser: $token. Making API call.",
    );

    final response = await _httpClient.get(
      Uri.parse(ApiConstants.baseUrl + ApiConstants.usersMeEndpoint),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );

    logger.i(
      "[AuthService] getCurrentUser response status: ${response.statusCode}",
    );
    logger.i("[AuthService] getCurrentUser response body: ${response.body}");

    if (response.statusCode == 200) {
      final Map<String, dynamic> data = json.decode(response.body);
      final user = User.fromJson(data);
      logger.i("[AuthService] User data parsed: ${user.email}");
      return user;
    } else if (response.statusCode == 401) {
      logger.i("[AuthService] Unauthorized (401) fetching user. Clearing token.");
      await clearToken();
      throw Exception('Unauthorized: Token may be invalid or expired.');
    } else {
      logger.i(
        "[AuthService] Failed to load user data. Status: ${response.statusCode}",
      );
      throw Exception(
        'Failed to load user data: ${response.statusCode} ${response.body}',
      );
    }
  }

  // Helper to get authenticated headers (now public)
  Future<Map<String, String>> get authenticatedHeaders async {
    logger.i("[AuthService] Getting authenticated headers...");
    final token = await retrieveToken();
    
    if (token == null) {
      logger.e("[AuthService] No token found for authenticatedHeaders.");
      throw Exception('Not authenticated for this request.');
    }
    
    logger.i("[AuthService] Token found for authenticatedHeaders: ${token.substring(0, 20)}...");
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  // Example of how other services might use _authenticatedHeaders
  // Future<void> someAuthenticatedRequest() async {
  //   final response = await _httpClient.get(
  //     Uri.parse(ApiConstants.baseUrl + '/some_protected_endpoint'),
  //     headers: await _authenticatedHeaders,
  //   );
  //   // ... handle response
  // }
}

// Riverpod provider for AuthService
// This allows us to easily access AuthService throughout the app.
// We'll need to initialize SharedPreferences first in main.dart for this to work.
// For now, this is a placeholder as we'll define providers in the /providers directory.
// final authServiceProvider = Provider<AuthService>((ref) {
//   // This will throw if SharedPreferences is not ready.
//   // Proper initialization pattern will be handled later.
//   throw UnimplementedError('SharedPreferences must be initialized and passed to AuthService provider');
// });
