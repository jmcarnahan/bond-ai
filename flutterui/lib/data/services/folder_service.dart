import 'dart:convert';

import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/agent_service/agent_http_client.dart';
import '../../core/utils/logger.dart';

class FolderService {
  final AgentHttpClient _httpClient;

  FolderService._({required AgentHttpClient httpClient})
      : _httpClient = httpClient;

  factory FolderService({
    http.Client? httpClient,
    required AuthService authService,
  }) {
    final agentHttpClient = AgentHttpClient(
      httpClient: httpClient,
      authService: authService,
    );
    return FolderService._(httpClient: agentHttpClient);
  }

  String get _baseUrl => ApiConstants.baseUrl + ApiConstants.agentFoldersEndpoint;

  Future<List<FolderModel>> getFolders() async {
    try {
      final response = await _httpClient.get(_baseUrl);
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data
            .map((item) => FolderModel.fromJson(item as Map<String, dynamic>))
            .toList();
      } else {
        final errorMsg = 'Failed to load folders: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in getFolders: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to fetch folders: $e');
    }
  }

  Future<FolderModel> createFolder(String name) async {
    try {
      final response = await _httpClient.post(_baseUrl, {'name': name});
      if (response.statusCode == 201) {
        final Map<String, dynamic> data = json.decode(response.body);
        return FolderModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to create folder: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in createFolder: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to create folder: $e');
    }
  }

  Future<FolderModel> updateFolder(String folderId, {String? name, int? sortOrder}) async {
    try {
      final body = <String, dynamic>{};
      if (name != null) body['name'] = name;
      if (sortOrder != null) body['sort_order'] = sortOrder;

      final response = await _httpClient.put('$_baseUrl/$folderId', body);
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        return FolderModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to update folder: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in updateFolder: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to update folder: $e');
    }
  }

  Future<void> deleteFolder(String folderId) async {
    try {
      final response = await _httpClient.delete('$_baseUrl/$folderId');
      if (response.statusCode != 204) {
        final errorMsg = 'Failed to delete folder: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in deleteFolder: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to delete folder: $e');
    }
  }

  Future<void> assignAgent(String agentId, String? folderId) async {
    try {
      final response = await _httpClient.put(
        '$_baseUrl/assign',
        {'agent_id': agentId, 'folder_id': folderId},
      );
      if (response.statusCode != 200) {
        final errorMsg = 'Failed to assign agent: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in assignAgent: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to assign agent to folder: $e');
    }
  }

  Future<void> reorderAgents(String? folderId, List<String> agentIds) async {
    try {
      final response = await _httpClient.put(
        '$_baseUrl/reorder-agents',
        {'folder_id': folderId, 'agent_ids': agentIds},
      );
      if (response.statusCode != 200) {
        final errorMsg = 'Failed to reorder agents: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in reorderAgents: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to reorder agents: $e');
    }
  }

  Future<void> reorderFolders(List<String> folderIds) async {
    try {
      final response = await _httpClient.put(
        '$_baseUrl/reorder-folders',
        {'folder_ids': folderIds},
      );
      if (response.statusCode != 200) {
        final errorMsg = 'Failed to reorder folders: ${response.statusCode}';
        logger.e("[FolderService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[FolderService] Error in reorderFolders: ${e.toString()}");
      if (e is Exception) rethrow;
      throw Exception('Failed to reorder folders: $e');
    }
  }

  void dispose() {
    _httpClient.dispose();
  }
}
