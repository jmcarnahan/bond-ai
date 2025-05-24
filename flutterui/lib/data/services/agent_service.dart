import 'dart:convert';
import 'dart:typed_data'; // For Uint8List in file upload
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart'; // For MediaType

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/agent_model.dart'; // Contains AgentListItemModel, AgentDetailModel etc.
import 'package:flutterui/data/models/api_response_models.dart'; // For FileUploadResponseModel, AgentResponseModel
import 'package:flutterui/data/services/auth_service.dart'; // To get authenticated headers

// Note: For a more robust app, you might inject AuthService or just the token
// instead of having AuthService as a direct dependency if AgentService
// is provided independently. However, for simplicity and given AuthService
// already handles token retrieval, we can use it.

@immutable
class AgentService {
  final http.Client _httpClient;
  final AuthService _authService; // To access authenticated headers

  AgentService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? http.Client(),
      _authService = authService;

  Future<List<AgentListItemModel>> getAgents() async {
    print("[AgentService] getAgents called.");
    try {
      final headers =
          await _authService.authenticatedHeaders; // Corrected: call the getter
      print("[AgentService] Got authenticated headers for getAgents.");

      final response = await _httpClient.get(
        Uri.parse(ApiConstants.baseUrl + ApiConstants.agentsEndpoint),
        headers: headers,
      );

      print("[AgentService] getAgents response status: ${response.statusCode}");
      // print("[AgentService] getAgents response body: ${response.body}"); // Potentially long

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<AgentListItemModel> agents = // Changed to AgentListItemModel
            data
                .map(
                  (item) =>
                      AgentListItemModel.fromJson(item as Map<String, dynamic>),
                ) // Changed to AgentListItemModel
                .toList();
        print("[AgentService] Parsed ${agents.length} agents.");
        return agents;
      } else {
        print(
          "[AgentService] Failed to load agents. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load agents: ${response.statusCode}');
      }
    } catch (e) {
      print("[AgentService] Error in getAgents: ${e.toString()}");
      // Re-throw the exception to be handled by the provider/UI
      throw Exception('Failed to fetch agents: ${e.toString()}');
    }
  }

  // TODO: Add methods for createAgent, updateAgent, deleteAgent as needed

  Future<AgentDetailModel> getAgentDetails(String agentId) async {
    print("[AgentService] getAgentDetails called for ID: $agentId.");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/$agentId',
        ),
        headers: headers,
      );

      print(
        "[AgentService] getAgentDetails response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        return AgentDetailModel.fromJson(data);
      } else {
        print(
          "[AgentService] Failed to load agent details for $agentId. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load agent details: ${response.statusCode}');
      }
    } catch (e) {
      print(
        "[AgentService] Error in getAgentDetails for $agentId: ${e.toString()}",
      );
      throw Exception('Failed to fetch agent details: ${e.toString()}');
    }
  }

  Future<AgentResponseModel> createAgent(AgentDetailModel agentData) async {
    print("[AgentService] createAgent called for: ${agentData.name}");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.post(
        Uri.parse(ApiConstants.baseUrl + ApiConstants.agentsEndpoint),
        headers:
            headers, // Ensure Content-Type is application/json, which authenticatedHeaders should include
        body: json.encode(agentData.toJson()),
      );

      print(
        "[AgentService] createAgent response status: ${response.statusCode}",
      );
      if (response.statusCode == 201) {
        // HTTP 201 Created
        final Map<String, dynamic> data = json.decode(response.body);
        return AgentResponseModel.fromJson(data);
      } else {
        print(
          "[AgentService] Failed to create agent ${agentData.name}. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to create agent: ${response.statusCode} ${response.body}',
        );
      }
    } catch (e) {
      print(
        "[AgentService] Error in createAgent for ${agentData.name}: ${e.toString()}",
      );
      throw Exception('Failed to create agent: ${e.toString()}');
    }
  }

  Future<AgentResponseModel> updateAgent(
    String agentId,
    AgentDetailModel agentData,
  ) async {
    print(
      "[AgentService] updateAgent called for ID: $agentId, Name: ${agentData.name}",
    );
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.put(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}/$agentId',
        ),
        headers: headers,
        body: json.encode(agentData.toJson()),
      );

      print(
        "[AgentService] updateAgent response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        return AgentResponseModel.fromJson(data);
      } else {
        print(
          "[AgentService] Failed to update agent $agentId. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to update agent: ${response.statusCode} ${response.body}',
        );
      }
    } catch (e) {
      print(
        "[AgentService] Error in updateAgent for $agentId: ${e.toString()}",
      );
      throw Exception('Failed to update agent: ${e.toString()}');
    }
  }

  Future<FileUploadResponseModel> uploadFile(
    String fileName,
    Uint8List fileBytes,
  ) async {
    print("[AgentService] uploadFile called for: $fileName");
    try {
      final headers = await _authService.authenticatedHeaders;
      // For multipart, we don't set Content-Type globally to application/json
      // http.MultipartRequest handles it. We just need Authorization.
      final token = headers['Authorization'];
      if (token == null) {
        throw Exception('Authentication token not found for file upload.');
      }

      var request = http.MultipartRequest(
        'POST',
        Uri.parse(ApiConstants.baseUrl + ApiConstants.filesEndpoint),
      );
      request.headers['Authorization'] = token;
      request.files.add(
        http.MultipartFile.fromBytes(
          'file', // This 'file' key must match the FastAPI backend parameter name (UploadFile = File(...))
          fileBytes,
          filename: fileName,
          contentType: MediaType(
            'application',
            'octet-stream',
          ), // Or a more specific type if known
        ),
      );

      final streamedResponse = await _httpClient.send(request);
      final response = await http.Response.fromStream(streamedResponse);

      print(
        "[AgentService] uploadFile response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        // FastAPI returns 200 for this endpoint on success
        final Map<String, dynamic> data = json.decode(response.body);
        return FileUploadResponseModel.fromJson(data);
      } else {
        print(
          "[AgentService] Failed to upload file $fileName. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to upload file: ${response.statusCode} ${response.body}',
        );
      }
    } catch (e) {
      print(
        "[AgentService] Error in uploadFile for $fileName: ${e.toString()}",
      );
      throw Exception('Failed to upload file: ${e.toString()}');
    }
  }

  Future<void> deleteFile(String providerFileId) async {
    print("[AgentService] deleteFile called for ID: $providerFileId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.delete(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.filesEndpoint}/$providerFileId',
        ),
        headers: headers,
      );

      print(
        "[AgentService] deleteFile response status: ${response.statusCode}",
      );
      if (response.statusCode == 200) {
        // Backend returns 200 with FileDeleteResponse
        print(
          "[AgentService] File $providerFileId deleted successfully from backend.",
        );
        // final Map<String, dynamic> data = json.decode(response.body); // Could parse FileDeleteResponseModel if needed
        return;
      } else if (response.statusCode == 204) {
        // Some APIs might return 204 No Content
        print(
          "[AgentService] File $providerFileId deleted successfully (204 No Content).",
        );
        return;
      } else {
        print(
          "[AgentService] Failed to delete file $providerFileId. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to delete file: ${response.statusCode} ${response.body}',
        );
      }
    } catch (e) {
      print(
        "[AgentService] Error in deleteFile for $providerFileId: ${e.toString()}",
      );
      throw Exception('Failed to delete file: ${e.toString()}');
    }
  }

  // TODO: Add method for deleteAgent if needed
}
