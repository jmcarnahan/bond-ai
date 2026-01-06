import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';

import 'package:flutterui/data/services/auth_service.dart';
import '../../../core/utils/logger.dart';

@immutable
class AgentHttpClient {
  final http.Client _httpClient;
  final AuthService _authService;

  AgentHttpClient({
    http.Client? httpClient,
    required AuthService authService,
  })  : _httpClient = httpClient ?? http.Client(),
        _authService = authService;

  Future<Map<String, String>> get _authenticatedHeaders async {
    try {
      final headers = await _authService.authenticatedHeaders;

      if (headers['Authorization'] == null) {
        logger.e("[AgentHttpClient] No Authorization header found!");
        throw Exception('Authentication token not found');
      }

      return headers;
    } catch (e) {
      logger.e("[AgentHttpClient] Error getting authenticated headers: $e");
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

      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] GET error for $url: ${e.toString()}");
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

      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] POST error for $url: ${e.toString()}");
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

      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] PUT error for $url: ${e.toString()}");
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

      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] DELETE error for $url: ${e.toString()}");
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

      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] Multipart request error: ${e.toString()}");
      rethrow;
    }
  }

  void dispose() {
    _httpClient.close();
  }
}
