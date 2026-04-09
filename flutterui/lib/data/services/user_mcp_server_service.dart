import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/user_mcp_server_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/web_http_client.dart' as web_client;
import '../../core/utils/logger.dart';

/// Service for managing user-defined MCP server configurations.
@immutable
class UserMcpServerService {
  final http.Client _httpClient;
  final AuthService _authService;

  UserMcpServerService({
    http.Client? httpClient,
    required AuthService authService,
  })  : _httpClient = httpClient ?? web_client.createHttpClient(),
        _authService = authService;

  /// List the current user's MCP server configurations
  Future<UserMcpServerListResponse> listServers() async {
    logger.i("[UserMcpServerService] listServers called.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = UserMcpServerListResponse.fromJson(data);
        logger.i("[UserMcpServerService] Fetched ${result.total} servers.");
        return result;
      } else {
        logger.e("[UserMcpServerService] Failed to list servers. Status: ${response.statusCode}");
        throw Exception('Failed to list servers: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in listServers: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      throw Exception('Failed to list servers: ${e.toString()}');
    }
  }

  /// Create a new user MCP server configuration
  Future<UserMcpServerModel> createServer({
    required String serverName,
    required String displayName,
    String? description,
    required String url,
    String transport = 'streamable-http',
    String authType = 'none',
    Map<String, String>? headers,
    Map<String, dynamic>? oauthConfig,
    Map<String, dynamic>? extraConfig,
  }) async {
    logger.i("[UserMcpServerService] createServer called: $serverName");
    try {
      final authHeaders = await _authService.authenticatedHeaders;
      final apiUrl = '${ApiConstants.baseUrl}/user-mcp-servers';

      final body = <String, dynamic>{
        'server_name': serverName,
        'display_name': displayName,
        'url': url,
        'transport': transport,
        'auth_type': authType,
      };
      if (description != null) body['description'] = description;
      if (headers != null) body['headers'] = headers;
      if (oauthConfig != null) body['oauth_config'] = oauthConfig;
      if (extraConfig != null) body['extra_config'] = extraConfig;

      final response = await _httpClient.post(
        Uri.parse(apiUrl),
        headers: {...authHeaders, 'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      if (response.statusCode == 201) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = UserMcpServerModel.fromJson(data);
        logger.i("[UserMcpServerService] Created server: ${result.id}");
        return result;
      } else {
        final errorBody = json.decode(response.body);
        final detail = errorBody['detail'] ?? 'Unknown error';
        logger.e("[UserMcpServerService] Failed to create. Status: ${response.statusCode}, Detail: $detail");
        throw Exception(detail);
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in createServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      rethrow;
    }
  }

  /// Get a specific user MCP server configuration
  Future<UserMcpServerModel> getServer(String serverId) async {
    logger.i("[UserMcpServerService] getServer called: $serverId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers/$serverId';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return UserMcpServerModel.fromJson(data);
      } else {
        logger.e("[UserMcpServerService] Failed to get server. Status: ${response.statusCode}");
        throw Exception('Failed to get server: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in getServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      throw Exception('Failed to get server: ${e.toString()}');
    }
  }

  /// Update a user MCP server configuration
  Future<UserMcpServerModel> updateServer(
    String serverId, {
    String? displayName,
    String? description,
    String? url,
    String? transport,
    String? authType,
    Map<String, String>? headers,
    Map<String, dynamic>? oauthConfig,
    Map<String, dynamic>? extraConfig,
    bool? isActive,
  }) async {
    logger.i("[UserMcpServerService] updateServer called: $serverId");
    try {
      final authHeaders = await _authService.authenticatedHeaders;
      final apiUrl = '${ApiConstants.baseUrl}/user-mcp-servers/$serverId';

      final body = <String, dynamic>{};
      if (displayName != null) body['display_name'] = displayName;
      if (description != null) body['description'] = description;
      if (url != null) body['url'] = url;
      if (transport != null) body['transport'] = transport;
      if (authType != null) body['auth_type'] = authType;
      if (headers != null) body['headers'] = headers;
      if (oauthConfig != null) body['oauth_config'] = oauthConfig;
      if (extraConfig != null) body['extra_config'] = extraConfig;
      if (isActive != null) body['is_active'] = isActive;

      final response = await _httpClient.put(
        Uri.parse(apiUrl),
        headers: {...authHeaders, 'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = UserMcpServerModel.fromJson(data);
        logger.i("[UserMcpServerService] Updated server: ${result.id}");
        return result;
      } else {
        final errorBody = json.decode(response.body);
        final detail = errorBody['detail'] ?? 'Unknown error';
        logger.e("[UserMcpServerService] Failed to update. Status: ${response.statusCode}, Detail: $detail");
        throw Exception(detail);
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in updateServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      rethrow;
    }
  }

  /// Delete a user MCP server configuration
  Future<void> deleteServer(String serverId) async {
    logger.i("[UserMcpServerService] deleteServer called: $serverId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers/$serverId';

      final response = await _httpClient.delete(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 204) {
        logger.i("[UserMcpServerService] Deleted server: $serverId");
      } else if (response.statusCode == 409) {
        final errorBody = json.decode(response.body);
        final detail = errorBody['detail'] ?? 'Server is referenced by agents';
        throw Exception(detail);
      } else {
        logger.e("[UserMcpServerService] Failed to delete. Status: ${response.statusCode}");
        throw Exception('Failed to delete server: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in deleteServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      rethrow;
    }
  }

  /// Test connectivity to a user MCP server
  Future<TestConnectionResponse> testServer(String serverId) async {
    logger.i("[UserMcpServerService] testServer called: $serverId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers/$serverId/test';

      final response = await _httpClient.post(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = TestConnectionResponse.fromJson(data);
        logger.i("[UserMcpServerService] Test result: success=${result.success}, tools=${result.toolCount}");
        return result;
      } else {
        logger.e("[UserMcpServerService] Failed to test. Status: ${response.statusCode}");
        throw Exception('Failed to test server: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in testServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      throw Exception('Failed to test server: ${e.toString()}');
    }
  }

  /// Import a server from JSON config (same format as BOND_MCP_CONFIG)
  Future<UserMcpServerModel> importServer({
    required String serverName,
    required Map<String, dynamic> config,
  }) async {
    logger.i("[UserMcpServerService] importServer called: $serverName");
    try {
      final authHeaders = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers/import';

      final body = {
        'server_name': serverName,
        'config': config,
      };

      final response = await _httpClient.post(
        Uri.parse(url),
        headers: {...authHeaders, 'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      if (response.statusCode == 201) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        final result = UserMcpServerModel.fromJson(data);
        logger.i("[UserMcpServerService] Imported server: ${result.id}");
        return result;
      } else {
        final errorBody = json.decode(response.body);
        final detail = errorBody['detail'] ?? 'Unknown error';
        logger.e("[UserMcpServerService] Failed to import. Status: ${response.statusCode}, Detail: $detail");
        throw Exception(detail);
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in importServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      rethrow;
    }
  }

  /// Export a server config as JSON
  Future<Map<String, dynamic>> exportServer(String serverId) async {
    logger.i("[UserMcpServerService] exportServer called: $serverId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final url = '${ApiConstants.baseUrl}/user-mcp-servers/$serverId/export';

      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        logger.i("[UserMcpServerService] Exported server: $serverId");
        return data;
      } else {
        logger.e("[UserMcpServerService] Failed to export. Status: ${response.statusCode}");
        throw Exception('Failed to export server: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[UserMcpServerService] Error in exportServer: ${e.toString()}");
      logger.e("[UserMcpServerService] Stack trace: $stackTrace");
      throw Exception('Failed to export server: ${e.toString()}');
    }
  }
}
