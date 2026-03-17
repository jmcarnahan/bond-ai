import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable, kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/cookie_helper.dart' as cookie_helper;
import 'package:flutterui/data/services/web_http_client.dart' as web_client;
import '../../core/utils/logger.dart';

const String _tokenStorageKey = 'bondai_auth_token';

@immutable
class AuthService {
  final http.Client _httpClient;
  final SharedPreferences _sharedPreferences;

  AuthService({
    http.Client? httpClient,
    required SharedPreferences sharedPreferences,
  }) : _httpClient = httpClient ?? web_client.createHttpClient(),
       _sharedPreferences = sharedPreferences;

  Future<void> launchLoginUrl({String provider = 'google'}) async {
    // For mobile, we need to specify a redirect URI that uses our custom scheme
    String loginUrl = '${ApiConstants.baseUrl}/login/$provider';

    if (!kIsWeb) {
      // For mobile, append redirect_uri parameter to use our custom URL scheme
      final redirectUri = Uri.encodeComponent('bondai://auth-callback');
      loginUrl = '$loginUrl?redirect_uri=$redirectUri&platform=mobile';
      logger.i('[AuthService] Mobile login URL: $loginUrl');
    } else {
      // On web, resolve relative URLs (e.g. /rest/login/cognito) to absolute
      // URLs using the current origin. url_launcher requires absolute URLs.
      final parsed = Uri.parse(loginUrl);
      if (!parsed.hasScheme) {
        loginUrl = Uri.base.resolve(loginUrl).toString();
      }
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

  Future<void> exchangeCodeForToken(String code) async {
    final platform = kIsWeb ? 'web' : 'mobile';
    final url = '${ApiConstants.baseUrl}${ApiConstants.tokenExchangeEndpoint}';
    logger.i('[AuthService] Exchanging auth code for token (platform: $platform)');

    final response = await _httpClient.post(
      Uri.parse(url),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'code': code}),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      if (kIsWeb) {
        // On web, the response sets HttpOnly cookies automatically.
        // We just need to flag that we're using cookie-based auth.
        cookie_helper.setWebCookieAuth(true);
        logger.i('[AuthService] Web cookie auth established');
      } else {
        // On mobile, extract access_token from the response body
        final accessToken = data['access_token'] as String?;
        if (accessToken == null || accessToken.isEmpty) {
          throw Exception('No access_token in response');
        }
        await storeToken(accessToken);
        logger.i('[AuthService] Mobile bearer token stored');
      }
    } else {
      logger.e('[AuthService] Token exchange failed: ${response.statusCode} ${response.body}');
      throw Exception('Token exchange failed: ${response.statusCode}');
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
    return token;
  }

  Future<void> clearToken() async {
    final hadToken = await retrieveToken();
    await _sharedPreferences.remove(_tokenStorageKey);
    final tokenAfterClear = await retrieveToken();

    // Clear web cookie auth flag
    if (kIsWeb) {
      cookie_helper.setWebCookieAuth(false);
      logger.i('[AuthService] Logout - Had token: ${hadToken != null}');
      logger.i('[AuthService] Logout - Token after clear: ${tokenAfterClear != null}');
    }
  }

  Future<void> performFullLogout() async {
    // Call the backend logout endpoint before clearing local storage
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.logoutEndpoint}';
      final headers = await authenticatedHeaders;
      await _httpClient.post(
        Uri.parse(url),
        headers: headers,
      );
      logger.i('[AuthService] Backend logout successful');
    } catch (e) {
      logger.e('[AuthService] Backend logout failed (continuing with local cleanup): $e');
    }

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
  }

  Future<User> getCurrentUser() async {
    final url = ApiConstants.baseUrl + ApiConstants.usersMeEndpoint;
    final Map<String, String> headers;

    if (kIsWeb && cookie_helper.isWebCookieAuth) {
      // On web with cookie auth, cookies are sent automatically by BrowserClient.
      // Only need Content-Type header.
      headers = {'Content-Type': 'application/json'};
    } else {
      final token = await retrieveToken();
      if (token == null) {
        throw Exception('Not authenticated: No token found.');
      }
      headers = {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };
    }

    final response = await _httpClient.get(
      Uri.parse(url),
      headers: headers,
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
    if (kIsWeb && cookie_helper.isWebCookieAuth) {
      // On web with cookie auth, cookies are sent automatically.
      // Include CSRF token for state-changing requests.
      final headers = <String, String>{
        'Content-Type': 'application/json',
      };
      final csrfToken = cookie_helper.getCsrfToken();
      if (csrfToken != null) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return headers;
    }

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
