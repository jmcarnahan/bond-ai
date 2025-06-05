import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
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
    final Uri loginUri = Uri.parse(
      '${ApiConstants.baseUrl}/login/$provider',
    );
    if (await canLaunchUrl(loginUri)) {
      await launchUrl(loginUri, webOnlyWindowName: '_self');
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
    await _sharedPreferences.setString(_tokenStorageKey, accessToken);
  }

  Future<String?> retrieveToken() async {
    final token = _sharedPreferences.getString(_tokenStorageKey);
    return token;
  }

  Future<void> clearToken() async {
    await _sharedPreferences.remove(_tokenStorageKey);
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
