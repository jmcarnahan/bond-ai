import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable, kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:flutterui/core/constants/api_constants.dart';
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

  Future<void> launchLoginUrl({String provider = 'google'}) async {
    // For mobile, we need to specify a redirect URI that uses our custom scheme
    String loginUrl = '${ApiConstants.baseUrl}/login/$provider';
    
    if (!kIsWeb) {
      // For mobile, append redirect_uri parameter to use our custom URL scheme
      final redirectUri = Uri.encodeComponent('bondai://auth-callback');
      loginUrl = '$loginUrl?redirect_uri=$redirectUri&platform=mobile';
      logger.i('[AuthService] Mobile login URL: $loginUrl');
    }
    
    final Uri loginUri = Uri.parse(loginUrl);
    if (await canLaunchUrl(loginUri)) {
      if (kIsWeb) {
        await launchUrl(loginUri, webOnlyWindowName: '_self');
      } else {
        // For mobile, open in external browser
        await launchUrl(loginUri, mode: LaunchMode.externalApplication);
      }
    } else {
      throw Exception('Could not launch $loginUri');
    }
  }

  Future<List<Map<String, dynamic>>> getAvailableProviders() async {
    final response = await _httpClient.get(
      Uri.parse('${ApiConstants.baseUrl}/providers'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode == 200) {
      final Map<String, dynamic> data = json.decode(response.body);
      return List<Map<String, dynamic>>.from(data['providers']);
    } else {
      logger.e("[AuthService] Failed to load providers: ${response.statusCode}");
      throw Exception('Failed to load available providers');
    }
  }

  Future<void> storeToken(String accessToken) async {
    logger.i("[AuthService] Storing token (length: ${accessToken.length})");
    await _sharedPreferences.setString(_tokenStorageKey, accessToken);
    
    // Verify storage
    final stored = _sharedPreferences.getString(_tokenStorageKey);
    logger.i("[AuthService] Token stored successfully: ${stored != null && stored.length == accessToken.length}");
  }

  Future<String?> retrieveToken() async {
    final token = _sharedPreferences.getString(_tokenStorageKey);
    // logger.d("[AuthService] Retrieved token: ${token != null ? 'Found (length: ${token.length})' : 'Not found'}");
    return token;
  }

  Future<void> clearToken() async {
    final hadToken = await retrieveToken();
    await _sharedPreferences.remove(_tokenStorageKey);
    final tokenAfterClear = await retrieveToken();
    
    // Log for debugging
    if (kIsWeb) {
      logger.i('[AuthService] Logout - Had token: ${hadToken != null}');
      logger.i('[AuthService] Logout - Token after clear: ${tokenAfterClear != null}');
    }
  }

  Future<void> performFullLogout() async {
    await clearToken();
    
    // Clear all browser storage on web without page reload
    if (kIsWeb) {
      logger.i('[AuthService] Performing logout - clearing all storage');
      
      try {
        // Clear all SharedPreferences data
        await _sharedPreferences.clear();
        logger.i('[AuthService] All storage cleared successfully');
      } catch (e) {
        logger.e('[AuthService] Error during logout: $e');
      }
    }
    
    // The auth state will automatically update when token is cleared
    // No need to reload the page - the UI will react to the state change
  }

  Future<User> getCurrentUser() async {
    final token = await retrieveToken();
    if (token == null) {
      throw Exception('Not authenticated: No token found.');
    }

    final response = await _httpClient.get(
      Uri.parse(ApiConstants.baseUrl + ApiConstants.usersMeEndpoint),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
    );


    if (response.statusCode == 200) {
      final Map<String, dynamic> data = json.decode(response.body);
      final user = User.fromJson(data);
      logger.i("[AuthService] User authenticated: ${user.email}");
      return user;
    } else if (response.statusCode == 401) {
      await clearToken();
      throw Exception('Unauthorized: Token may be invalid or expired.');
    } else {
      logger.e("[AuthService] Failed to load user data: ${response.statusCode}");
      throw Exception(
        'Failed to load user data: ${response.statusCode} ${response.body}',
      );
    }
  }

  Future<Map<String, String>> get authenticatedHeaders async {
    final token = await retrieveToken();
    
    if (token == null) {
      logger.e("[AuthService] No token found for authenticatedHeaders.");
      throw Exception('Not authenticated for this request.');
    }
    
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }
}
