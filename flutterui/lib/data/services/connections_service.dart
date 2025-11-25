import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/connection_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import '../../core/utils/logger.dart';

/// Service for managing external service connections (e.g., Atlassian, Google Drive)
@immutable
class ConnectionsService {
  final http.Client _httpClient;
  final AuthService _authService;

  ConnectionsService({
    http.Client? httpClient,
    required AuthService authService,
  })  : _httpClient = httpClient ?? http.Client(),
        _authService = authService;

  /// Get all available connections with user's status
  Future<ConnectionsListResponse> listConnections() async {
    logger.i("[ConnectionsService] listConnections called.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/connections';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = ConnectionsListResponse.fromJson(data);
        logger.i("[ConnectionsService] Successfully fetched ${result.connections.length} connections.");
        return result;
      } else {
        logger.e("[ConnectionsService] Failed to load connections. Status: ${response.statusCode}");
        throw Exception('Failed to load connections: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[ConnectionsService] Error in listConnections: ${e.toString()}");
      logger.e("[ConnectionsService] Stack trace: $stackTrace");
      throw Exception('Failed to fetch connections: ${e.toString()}');
    }
  }

  /// Get the authorization URL for a connection
  Future<AuthorizeResponse> authorize(String connectionName) async {
    logger.i("[ConnectionsService] authorize called for: $connectionName");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/connections/$connectionName/authorize';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = AuthorizeResponse.fromJson(data);
        logger.i("[ConnectionsService] Got authorization URL for $connectionName");
        return result;
      } else {
        logger.e("[ConnectionsService] Failed to get auth URL. Status: ${response.statusCode}");
        throw Exception('Failed to get authorization URL: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[ConnectionsService] Error in authorize: ${e.toString()}");
      logger.e("[ConnectionsService] Stack trace: $stackTrace");
      throw Exception('Failed to authorize: ${e.toString()}');
    }
  }

  /// Disconnect from a connection
  Future<bool> disconnect(String connectionName) async {
    logger.i("[ConnectionsService] disconnect called for: $connectionName");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/connections/$connectionName';

      final response = await _httpClient.delete(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final disconnected = data['disconnected'] as bool? ?? false;
        logger.i("[ConnectionsService] Disconnected from $connectionName: $disconnected");
        return disconnected;
      } else {
        logger.e("[ConnectionsService] Failed to disconnect. Status: ${response.statusCode}");
        throw Exception('Failed to disconnect: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[ConnectionsService] Error in disconnect: ${e.toString()}");
      logger.e("[ConnectionsService] Stack trace: $stackTrace");
      throw Exception('Failed to disconnect: ${e.toString()}');
    }
  }

  /// Get the status of a specific connection
  Future<ConnectionStatus> getConnectionStatus(String connectionName) async {
    logger.i("[ConnectionsService] getConnectionStatus called for: $connectionName");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/connections/$connectionName/status';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = ConnectionStatus.fromJson(data);
        logger.i("[ConnectionsService] Got status for $connectionName: ${result.statusText}");
        return result;
      } else {
        logger.e("[ConnectionsService] Failed to get status. Status: ${response.statusCode}");
        throw Exception('Failed to get connection status: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[ConnectionsService] Error in getConnectionStatus: ${e.toString()}");
      logger.e("[ConnectionsService] Stack trace: $stackTrace");
      throw Exception('Failed to get connection status: ${e.toString()}');
    }
  }

  /// Check for expired connections (called after login)
  Future<CheckExpiredResponse> checkExpiredConnections() async {
    logger.i("[ConnectionsService] checkExpiredConnections called.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/connections/check-expired';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = CheckExpiredResponse.fromJson(data);
        logger.i("[ConnectionsService] Checked expired: hasExpired=${result.hasExpired}");
        return result;
      } else {
        logger.e("[ConnectionsService] Failed to check expired. Status: ${response.statusCode}");
        throw Exception('Failed to check expired connections: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[ConnectionsService] Error in checkExpiredConnections: ${e.toString()}");
      logger.e("[ConnectionsService] Stack trace: $stackTrace");
      throw Exception('Failed to check expired connections: ${e.toString()}');
    }
  }

}
