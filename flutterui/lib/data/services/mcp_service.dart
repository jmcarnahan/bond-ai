import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/mcp_model.dart';
import 'package:flutterui/data/services/auth_service.dart'; // To get authenticated headers
import '../../core/utils/logger.dart';

@immutable
class McpService {
  final http.Client _httpClient;
  final AuthService _authService;

  McpService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? http.Client(),
      _authService = authService;

  // Fetch all MCP tools
  Future<List<McpToolModel>> getTools() async {
    logger.i("[McpService] getTools called.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse(ApiConstants.baseUrl + '/mcp/tools'),
        headers: headers,
      );

      logger.i(
        "[McpService] getTools response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<McpToolModel> tools =
            data
                .map((item) => McpToolModel.fromJson(item as Map<String, dynamic>))
                .toList();
        logger.i("[McpService] Parsed ${tools.length} MCP tools.");
        return tools;
      } else {
        logger.i(
          "[McpService] Failed to load MCP tools. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load MCP tools: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[McpService] Error in getTools: ${e.toString()}");
      throw Exception('Failed to fetch MCP tools: ${e.toString()}');
    }
  }

  // Fetch all MCP resources  
  Future<List<McpResourceModel>> getResources() async {
    logger.i("[McpService] getResources called.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse(ApiConstants.baseUrl + '/mcp/resources'),
        headers: headers,
      );

      logger.i(
        "[McpService] getResources response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<McpResourceModel> resources =
            data
                .map((item) => McpResourceModel.fromJson(item as Map<String, dynamic>))
                .toList();
        logger.i("[McpService] Parsed ${resources.length} MCP resources.");
        return resources;
      } else {
        logger.i(
          "[McpService] Failed to load MCP resources. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load MCP resources: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[McpService] Error in getResources: ${e.toString()}");
      throw Exception('Failed to fetch MCP resources: ${e.toString()}');
    }
  }
}