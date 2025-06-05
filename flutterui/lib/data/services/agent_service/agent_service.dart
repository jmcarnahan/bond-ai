import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'agent_http_client.dart';
import 'agent_crud_service.dart';
import 'agent_file_service.dart';

class AgentService {
  final AgentCrudService _crudService;
  final AgentFileService _fileService;
  final AgentHttpClient _httpClient;

  AgentService._({
    required AgentCrudService crudService,
    required AgentFileService fileService,
    required AgentHttpClient httpClient,
  })  : _crudService = crudService,
        _fileService = fileService,
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
    final fileService = AgentFileService(httpClient: agentHttpClient);
    
    return AgentService._(
      crudService: crudService,
      fileService: fileService,
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

  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) => 
      _fileService.uploadFile(fileName, fileBytes);

  Future<void> deleteFile(String providerFileId) => 
      _fileService.deleteFile(providerFileId);

  Future<List<FileInfoModel>> getFiles() => _fileService.getFiles();

  Future<FileInfoModel> getFileInfo(String providerFileId) => 
      _fileService.getFileInfo(providerFileId);

  Future<List<FileDetailsResponseModel>> getFileDetails(List<String> fileIds) => 
      _fileService.getFileDetails(fileIds);

  void dispose() {
    _httpClient.dispose();
  }
}