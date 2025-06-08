import 'package:http/http.dart' as http;

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'agent_http_client.dart';
import 'agent_crud_service.dart';

class AgentService {
  final AgentCrudService _crudService;
  final AgentHttpClient _httpClient;

  AgentService._({
    required AgentCrudService crudService,
    required AgentHttpClient httpClient,
  })  : _crudService = crudService,
        _httpClient = httpClient;

  factory AgentService({
    http.Client? httpClient,
    required AuthService authService,
  }) {
    final agentHttpClient = AgentHttpClient(
      httpClient: httpClient,
      authService: authService,
    );
    
    final crudService = AgentCrudService(httpClient: agentHttpClient);
    
    return AgentService._(
      crudService: crudService,
      httpClient: agentHttpClient,
    );
  }

  Future<List<AgentListItemModel>> getAgents() => _crudService.getAgents();

  Future<AgentDetailModel> getAgentDetails(String agentId) => 
      _crudService.getAgentDetails(agentId);

  Future<AgentResponseModel> createAgent(AgentDetailModel agentData) => 
      _crudService.createAgent(agentData);

  Future<AgentResponseModel> updateAgent(String agentId, AgentDetailModel agentData) => 
      _crudService.updateAgent(agentId, agentData);

  Future<void> deleteAgent(String agentId) => _crudService.deleteAgent(agentId);

  Future<List<AvailableGroup>> getAvailableGroups([String? agentId]) =>
    _crudService.getAvailableGroups(agentId);

  void dispose() {
    _httpClient.dispose();
  }
}