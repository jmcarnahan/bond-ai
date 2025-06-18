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
    // logger.i("[McpService] getTools called.");
    try {
      // logger.i("[McpService] Getting authenticated headers...");
      final headers = await _authService.authenticatedHeaders;
      // logger.i("[McpService] Headers obtained: ${headers.keys.toList()}");
      
      final url = '${ApiConstants.baseUrl}/mcp/tools';
      // logger.i("[McpService] Making request to: $url");
      
      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      // logger.i(
      //   "[McpService] getTools response status: ${response.statusCode}",
      // );
      
      if (response.statusCode == 200) {
        // logger.i("[McpService] Response body length: ${response.body.length}");
        // logger.i("[McpService] Response body preview: ${response.body.length > 200 ? '${response.body.substring(0, 200)}...' : response.body}");
        
        final List<dynamic> data = json.decode(response.body);
        // logger.i("[McpService] Decoded JSON array with ${data.length} items");
        
        final List<McpToolModel> tools =
            data
                .map((item) {
                  // logger.i("[McpService] Parsing tool item: ${item}");
                  return McpToolModel.fromJson(item as Map<String, dynamic>);
                })
                .toList();
        
        logger.i("[McpService] Successfully parsed ${tools.length} MCP tools.");
        
        // Log each tool for debugging
        // for (int i = 0; i < tools.length; i++) {
        //   logger.i("[McpService] Tool ${i + 1}: name='${tools[i].name}', description='${tools[i].description}'");
        // }
        
        return tools;
      } else {
        logger.e(
          "[McpService] Failed to load MCP tools. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load MCP tools: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[McpService] Error in getTools: ${e.toString()}");
      logger.e("[McpService] Stack trace: $stackTrace");
      throw Exception('Failed to fetch MCP tools: ${e.toString()}');
    }
  }

  // Fetch all MCP resources  
  Future<List<McpResourceModel>> getResources() async {
    // logger.i("[McpService] getResources called.");
    try {
      // logger.i("[McpService] Getting authenticated headers...");
      final headers = await _authService.authenticatedHeaders;
      // logger.i("[McpService] Headers obtained: ${headers.keys.toList()}");
      
      final url = '${ApiConstants.baseUrl}/mcp/resources';
      // logger.i("[McpService] Making request to: $url");
      
      final response = await _httpClient.get(
        Uri.parse(url),
        headers: headers,
      );

      // logger.i(
      //   "[McpService] getResources response status: ${response.statusCode}",
      // );
      
      if (response.statusCode == 200) {
        // logger.i("[McpService] Response body length: ${response.body.length}");
        // logger.i("[McpService] Response body preview: ${response.body.length > 200 ? '${response.body.substring(0, 200)}...' : response.body}");
        
        final List<dynamic> data = json.decode(response.body);
        // logger.i("[McpService] Decoded JSON array with ${data.length} items");
        
        final List<McpResourceModel> resources =
            data
                .map((item) {
                  // logger.i("[McpService] Parsing resource item: ${item}");
                  return McpResourceModel.fromJson(item as Map<String, dynamic>);
                })
                .toList();
        
        logger.i("[McpService] Successfully parsed ${resources.length} MCP resources.");
        
        // Log each resource for debugging
        // for (int i = 0; i < resources.length; i++) {
        //   logger.i("[McpService] Resource ${i + 1}: uri='${resources[i].uri}', name='${resources[i].name}', mime_type='${resources[i].mimeType}'");
        // }
        
        return resources;
      } else {
        logger.e(
          "[McpService] Failed to load MCP resources. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load MCP resources: ${response.statusCode}');
      }
    } catch (e, stackTrace) {
      logger.e("[McpService] Error in getResources: ${e.toString()}");
      logger.e("[McpService] Stack trace: $stackTrace");
      throw Exception('Failed to fetch MCP resources: ${e.toString()}');
    }
  }
}