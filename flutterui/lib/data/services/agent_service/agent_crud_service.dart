import 'dart:convert';
import 'package:flutter/foundation.dart';

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/models/model_info.dart';
import 'agent_http_client.dart';
import '../../../core/utils/logger.dart';

@immutable
class AgentCrudService {
  final AgentHttpClient _httpClient;

  const AgentCrudService({required AgentHttpClient httpClient})
      : _httpClient = httpClient;

  Future<List<AgentListItemModel>> getAgents() async {
    try {
      final url = ApiConstants.baseUrl + ApiConstants.agentsEndpoint;
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<AgentListItemModel> agents = data
            .map((item) => AgentListItemModel.fromJson(item as Map<String, dynamic>))
            .toList();
        
        return agents;
      } else {
        final errorMsg = 'Failed to load agents: ${response.statusCode}';
        logger.e("[AgentCrudService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in getAgents: ${e.toString()}");
      throw Exception('Failed to fetch agents: ${e.toString()}');
    }
  }

  Future<AgentDetailModel> getAgentDetails(String agentId) async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/$agentId';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        return AgentDetailModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to load agent details: ${response.statusCode}';
        logger.e("[AgentCrudService] $errorMsg for $agentId, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in getAgentDetails for $agentId: ${e.toString()}");
      throw Exception('Failed to fetch agent details: ${e.toString()}');
    }
  }

  Future<AgentResponseModel> createAgent(AgentDetailModel agentData) async {
    try {
      final url = ApiConstants.baseUrl + ApiConstants.agentsEndpoint;
      final response = await _httpClient.post(url, agentData.toJson());

      if (response.statusCode == 201) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[AgentCrudService] Created agent: ${agentData.name}");
        return AgentResponseModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to create agent: ${response.statusCode} ${response.body}';
        logger.e("[AgentCrudService] $errorMsg for ${agentData.name}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in createAgent for ${agentData.name}: ${e.toString()}");
      throw Exception('Failed to create agent: ${e.toString()}');
    }
  }

  Future<AgentResponseModel> updateAgent(String agentId, AgentDetailModel agentData) async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/$agentId';
      final response = await _httpClient.put(url, agentData.toJson());

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[AgentCrudService] Updated agent: ${agentData.name}");
        return AgentResponseModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to update agent: ${response.statusCode} ${response.body}';
        logger.e("[AgentCrudService] $errorMsg for $agentId");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in updateAgent for $agentId: ${e.toString()}");
      throw Exception('Failed to update agent: ${e.toString()}');
    }
  }

  Future<void> deleteAgent(String agentId) async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/$agentId';
      final response = await _httpClient.delete(url);

      if (response.statusCode == 200 || response.statusCode == 204) {
        logger.i("[AgentCrudService] Deleted agent: $agentId");
        return;
      } else {
        final errorMsg = 'Failed to delete agent: ${response.statusCode} ${response.body}';
        logger.e("[AgentCrudService] $errorMsg for $agentId");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in deleteAgent for $agentId: ${e.toString()}");
      throw Exception('Failed to delete agent: ${e.toString()}');
    }
  }

  Future<List<AvailableGroup>> getAvailableGroups([String? agentId]) async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/available-groups';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<AvailableGroup> groups = data
            .map((item) => AvailableGroup.fromJson(item as Map<String, dynamic>))
            .toList();
        
        logger.i("[AgentCrudService] Fetched ${groups.length} available groups");
        return groups;
      } else {
        final errorMsg = 'Failed to load available groups: ${response.statusCode}';
        logger.e("[AgentCrudService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in getAvailableGroups: ${e.toString()}");
      throw Exception('Failed to fetch available groups: ${e.toString()}');
    }
  }

  Future<List<ModelInfo>> getAvailableModels() async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/models';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<ModelInfo> models = data
            .map((item) => ModelInfo.fromJson(item as Map<String, dynamic>))
            .toList();
        
        logger.i("[AgentCrudService] Fetched ${models.length} available models");
        return models;
      } else {
        final errorMsg = 'Failed to load available models: ${response.statusCode}';
        logger.e("[AgentCrudService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in getAvailableModels: ${e.toString()}");
      throw Exception('Failed to fetch available models: ${e.toString()}');
    }
  }

  Future<AgentResponseModel> getDefaultAgent() async {
    try {
      final url = '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/default';
      final response = await _httpClient.get(url);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        logger.i("[AgentCrudService] Fetched default agent: ${data['name']}");
        return AgentResponseModel.fromJson(data);
      } else {
        final errorMsg = 'Failed to load default agent: ${response.statusCode}';
        logger.e("[AgentCrudService] $errorMsg, Body: ${response.body}");
        throw Exception(errorMsg);
      }
    } catch (e) {
      logger.e("[AgentCrudService] Error in getDefaultAgent: ${e.toString()}");
      throw Exception('Failed to fetch default agent: ${e.toString()}');
    }
  }
}