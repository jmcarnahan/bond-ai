import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';

import 'package:flutterui/data/services/auth_service.dart';
import '../../core/utils/logger.dart';

/// A generic HTTP client with authentication support that can be used by any service
@immutable
class AuthenticatedHttpClient {
  final http.Client _httpClient;
  final AuthService _authService;

  AuthenticatedHttpClient({
    http.Client? httpClient,
    required AuthService authService,
  })  : _httpClient = httpClient ?? http.Client(),
        _authService = authService;

  Future<Map<String, String>> get _authenticatedHeaders async {
    try {
      final headers = await _authService.authenticatedHeaders;
      
      if (headers['Authorization'] == null) {
        logger.e("[AuthenticatedHttpClient] No Authorization header found!");
        throw Exception('Authentication token not found');
      }
      
      return headers;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] Error getting authenticated headers: $e");
      rethrow;
    }
  }

  Future<http.Response> get(String url) async {
    try {
      final headers = await _authenticatedHeaders;
      
      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );
      
      _checkAuthenticationError(response);
      return response;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] GET error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> post(String url, Map<String, dynamic> data) async {
    try {
      final headers = await _authenticatedHeaders;
      
      final response = await _httpClient.post(
        Uri.parse(url),
        headers: headers,
        body: json.encode(data),
      );
      
      _checkAuthenticationError(response);
      return response;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] POST error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> put(String url, Map<String, dynamic> data) async {
    try {
      final headers = await _authenticatedHeaders;
      
      final response = await _httpClient.put(
        Uri.parse(url),
        headers: headers,
        body: json.encode(data),
      );
      
      _checkAuthenticationError(response);
      return response;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] PUT error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> delete(String url) async {
    try {
      final headers = await _authenticatedHeaders;
      
      final response = await _httpClient.delete(
        Uri.parse(url),
        headers: headers,
      );
      
      _checkAuthenticationError(response);
      return response;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] DELETE error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> sendMultipartRequest(http.MultipartRequest request) async {
    try {
      final headers = await _authenticatedHeaders;
      final token = headers['Authorization'];
      if (token == null) {
        throw Exception('Authentication token not found for multipart request');
      }
      
      request.headers['Authorization'] = token;
      
      final streamedResponse = await _httpClient.send(request);
      final response = await http.Response.fromStream(streamedResponse);
      
      _checkAuthenticationError(response);
      return response;
    } catch (e) {
      logger.e("[AuthenticatedHttpClient] Multipart request error: ${e.toString()}");
      rethrow;
    }
  }

  void dispose() {
    _httpClient.close();
  }
  
  void _checkAuthenticationError(http.Response response) {
    if (response.statusCode == 401) {
      throw Exception('401 Unauthorized: Authentication token expired or invalid');
    }
  }
}