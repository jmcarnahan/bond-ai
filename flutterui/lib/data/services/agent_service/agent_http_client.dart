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
      logger.i("[AgentHttpClient] Getting authenticated headers...");
      final headers = await _authService.authenticatedHeaders;
      logger.i("[AgentHttpClient] Got headers: ${headers.keys.toList()}");
      
      if (headers['Authorization'] == null) {
        logger.e("[AgentHttpClient] No Authorization header found!");
        throw Exception('Authentication token not found');
      }
      
      final token = headers['Authorization']!;
      logger.i("[AgentHttpClient] Authorization header present: ${token.substring(0, 20)}...");
      return headers;
    } catch (e) {
      logger.e("[AgentHttpClient] Error getting authenticated headers: $e");
      rethrow;
    }
  }

  Future<http.Response> get(String url) async {
    try {
      final headers = await _authenticatedHeaders;
      logger.i("[AgentHttpClient] GET request to: $url");
      
      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );
      
      logger.i("[AgentHttpClient] GET response status: ${response.statusCode}");
      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] GET error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> post(String url, Map<String, dynamic> data) async {
    try {
      final headers = await _authenticatedHeaders;
      logger.i("[AgentHttpClient] POST request to: $url");
      
      final response = await _httpClient.post(
        Uri.parse(url),
        headers: headers,
        body: json.encode(data),
      );
      
      logger.i("[AgentHttpClient] POST response status: ${response.statusCode}");
      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] POST error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> put(String url, Map<String, dynamic> data) async {
    try {
      final headers = await _authenticatedHeaders;
      logger.i("[AgentHttpClient] PUT request to: $url");
      
      final response = await _httpClient.put(
        Uri.parse(url),
        headers: headers,
        body: json.encode(data),
      );
      
      logger.i("[AgentHttpClient] PUT response status: ${response.statusCode}");
      return response;
    } catch (e) {
      logger.e("[AgentHttpClient] PUT error for $url: ${e.toString()}");
      rethrow;
    }
  }

  Future<http.Response> delete(String url) async {
    try {
      final headers = await _authenticatedHeaders;
      logger.i("[AgentHttpClient] DELETE request to: $url");
      
      final response = await _httpClient.delete(
        Uri.parse(url),
        headers: headers,
      );
      
      logger.i("[AgentHttpClient] DELETE response status: ${response.statusCode}");
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
      logger.i("[AgentHttpClient] Sending multipart request to: ${request.url}");
      
      final streamedResponse = await _httpClient.send(request);
      final response = await http.Response.fromStream(streamedResponse);
      
      logger.i("[AgentHttpClient] Multipart response status: ${response.statusCode}");
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