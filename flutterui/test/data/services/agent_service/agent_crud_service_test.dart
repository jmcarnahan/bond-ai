import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service/agent_crud_service.dart';
import 'package:flutterui/data/services/agent_service/agent_http_client.dart';

class MockAgentHttpClient implements AgentHttpClient {
  final Map<String, http.Response> _responses = {};
  final List<String> _requestUrls = [];
  final List<String> _requestMethods = [];
  final List<Map<String, dynamic>?> _requestBodies = [];

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<String> get requestUrls => List.unmodifiable(_requestUrls);
  List<String> get requestMethods => List.unmodifiable(_requestMethods);
  List<Map<String, dynamic>?> get requestBodies => List.unmodifiable(_requestBodies);

  @override
  Future<http.Response> get(String url) async {
    _requestUrls.add(url);
    _requestMethods.add('GET');
    _requestBodies.add(null);
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> post(String url, Map<String, dynamic> data) async {
    _requestUrls.add(url);
    _requestMethods.add('POST');
    _requestBodies.add(data);
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> put(String url, Map<String, dynamic> data) async {
    _requestUrls.add(url);
    _requestMethods.add('PUT');
    _requestBodies.add(data);
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> delete(String url) async {
    _requestUrls.add(url);
    _requestMethods.add('DELETE');
    _requestBodies.add(null);
    
    final response = _responses[url];
    if (response != null) {
      return response;
    }
    return http.Response('Not Found', 404);
  }

  @override
  Future<http.Response> sendMultipartRequest(http.MultipartRequest request) async {
    throw UnimplementedError('Not used in CRUD service');
  }

  @override
  void dispose() {}
}

void main() {
  group('AgentCrudService Tests', () {
    late MockAgentHttpClient mockHttpClient;
    late AgentCrudService agentCrudService;

    setUp(() {
      mockHttpClient = MockAgentHttpClient();
      agentCrudService = AgentCrudService(httpClient: mockHttpClient);
    });

    test('constructor should create service with http client', () {
      final service = AgentCrudService(httpClient: mockHttpClient);
      expect(service, isA<AgentCrudService>());
    });

    group('getAgents', () {
      test('should return list of agents on successful response', () async {
        const agentsJson = '''[
          {
            "id": "agent-1",
            "name": "Test Agent 1",
            "description": "Test Description 1"
          },
          {
            "id": "agent-2", 
            "name": "Test Agent 2",
            "description": "Test Description 2"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response(agentsJson, 200),
        );

        final agents = await agentCrudService.getAgents();

        expect(agents, hasLength(2));
        expect(agents[0].id, equals('agent-1'));
        expect(agents[0].name, equals('Test Agent 1'));
        expect(agents[0].description, equals('Test Description 1'));
        expect(agents[1].id, equals('agent-2'));
        expect(agents[1].name, equals('Test Agent 2'));
        expect(mockHttpClient.requestMethods.last, equals('GET'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents'));
      });

      test('should handle empty agents list', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('[]', 200),
        );

        final agents = await agentCrudService.getAgents();

        expect(agents, isEmpty);
      });

      test('should throw exception on 500 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Internal Server Error', 500),
        );

        expect(
          () => agentCrudService.getAgents(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch agents'),
          )),
        );
      });

      test('should throw exception on 404 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentCrudService.getAgents(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to load agents: 404'),
          )),
        );
      });

      test('should throw exception on invalid JSON', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentCrudService.getAgents(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch agents'),
          )),
        );
      });

      test('should handle network error', () async {
        expect(
          () => agentCrudService.getAgents(),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('getAgentDetails', () {
      test('should return agent details on successful response', () async {
        const agentJson = '''{
          "id": "agent-123",
          "name": "Test Agent",
          "description": "Test Description",
          "tools": [],
          "instructions": "Test Instructions",
          "model": "gpt-4"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response(agentJson, 200),
        );

        final agent = await agentCrudService.getAgentDetails('agent-123');

        expect(agent.id, equals('agent-123'));
        expect(agent.name, equals('Test Agent'));
        expect(agent.description, equals('Test Description'));
        expect(agent.instructions, equals('Test Instructions'));
        expect(agent.model, equals('gpt-4'));
        expect(mockHttpClient.requestMethods.last, equals('GET'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/agent-123'));
      });

      test('should throw exception on 404 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentCrudService.getAgentDetails('nonexistent'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to load agent details: 404'),
          )),
        );
      });

      test('should throw exception on invalid JSON', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentCrudService.getAgentDetails('agent-123'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch agent details'),
          )),
        );
      });

      test('should handle empty agent ID', () async {
        const agentJson = '''{
          "id": "",
          "name": "Test Agent",
          "description": "Test Description",
          "tools": [],
          "instructions": "Test Instructions",
          "model": "gpt-4"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/',
          http.Response(agentJson, 200),
        );

        final agent = await agentCrudService.getAgentDetails('');
        expect(agent.id, equals(''));
      });

      test('should handle special characters in agent ID', () async {
        const specialId = 'agent-with-special-chars-@#%';
        const agentJson = '''{
          "id": "$specialId",
          "name": "Test Agent",
          "description": "Test Description",
          "tools": [],
          "instructions": "Test Instructions",
          "model": "gpt-4"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/$specialId',
          http.Response(agentJson, 200),
        );

        final agent = await agentCrudService.getAgentDetails(specialId);
        expect(agent.id, equals(specialId));
      });
    });

    group('createAgent', () {
      test('should create agent successfully', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'New Agent',
          description: 'New Description',
          tools: [],
          instructions: 'New Instructions',
          model: 'gpt-4', files: [],
        );

        const responseJson = '''{
          "agent_id": "new-agent-123",
          "name": "New Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response(responseJson, 201),
        );

        final response = await agentCrudService.createAgent(agentData);

        expect(response.agentId, equals('new-agent-123'));
        expect(response.name, equals('New Agent'));
        expect(mockHttpClient.requestMethods.last, equals('POST'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents'));
        expect(mockHttpClient.requestBodies.last, equals(agentData.toJson()));
      });

      test('should throw exception on 400 error', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'Invalid Agent',
          description: 'Invalid Description',
          tools: [],
          instructions: 'Invalid Instructions',
          model: 'invalid-model', files: [],
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Bad Request', 400),
        );

        expect(
          () => agentCrudService.createAgent(agentData),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to create agent: 400'),
          )),
        );
      });

      test('should handle agent with complex data', () async {
        final agentData = AgentDetailModel(
          id: '',
          name: 'Complex Agent',
          description: 'Agent with émojis 🤖 and spëcial chars',
          tools: const [
            {'type': 'tool1'},
            {'type': 'tool2'},
          ],
          instructions: 'Complex instructions with unicode: café ☕',
          model: 'gpt-4', files: [],
        );

        const responseJson = '''{
          "agent_id": "complex-agent-123",
          "name": "Complex Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response(responseJson, 201),
        );

        final response = await agentCrudService.createAgent(agentData);

        expect(response.agentId, equals('complex-agent-123'));
        expect(response.name, equals('Complex Agent'));
      });

      test('should throw exception on invalid JSON response', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'New Agent',
          description: 'New Description',
          tools: [],
          instructions: 'New Instructions',
          model: 'gpt-4', files: [],
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('invalid json', 201),
        );

        expect(
          () => agentCrudService.createAgent(agentData),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to create agent'),
          )),
        );
      });
    });

    group('updateAgent', () {
      test('should update agent successfully', () async {
        const agentData = AgentDetailModel(
          id: 'agent-123',
          name: 'Updated Agent',
          description: 'Updated Description',
          tools: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4', files: [],
        );

        const responseJson = '''{
          "agent_id": "agent-123",
          "name": "Updated Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response(responseJson, 200),
        );

        final response = await agentCrudService.updateAgent('agent-123', agentData);

        expect(response.agentId, equals('agent-123'));
        expect(response.name, equals('Updated Agent'));
        expect(mockHttpClient.requestMethods.last, equals('PUT'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/agent-123'));
        expect(mockHttpClient.requestBodies.last, equals(agentData.toJson()));
      });

      test('should throw exception on 404 error', () async {
        const agentData = AgentDetailModel(
          id: 'nonexistent',
          name: 'Updated Agent',
          description: 'Updated Description',
          tools: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4', files: [],
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentCrudService.updateAgent('nonexistent', agentData),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to update agent: 404'),
          )),
        );
      });

      test('should handle empty agent ID in update', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'Updated Agent',
          description: 'Updated Description',
          tools: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4', files: [],
        );

        const responseJson = '''{
          "agent_id": "",
          "name": "Updated Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/',
          http.Response(responseJson, 200),
        );

        final response = await agentCrudService.updateAgent('', agentData);
        expect(response.agentId, equals(''));
        expect(response.name, equals('Updated Agent'));
      });

      test('should throw exception on invalid JSON response', () async {
        const agentData = AgentDetailModel(
          id: 'agent-123',
          name: 'Updated Agent',
          description: 'Updated Description',
          tools: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4', files: [],
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('invalid json', 200),
        );

        expect(
          () => agentCrudService.updateAgent('agent-123', agentData),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to update agent'),
          )),
        );
      });
    });

    group('deleteAgent', () {
      test('should delete agent successfully with 200 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('', 200),
        );

        await agentCrudService.deleteAgent('agent-123');

        expect(mockHttpClient.requestMethods.last, equals('DELETE'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/agent-123'));
      });

      test('should delete agent successfully with 204 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('', 204),
        );

        await agentCrudService.deleteAgent('agent-123');

        expect(mockHttpClient.requestMethods.last, equals('DELETE'));
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/agent-123'));
      });

      test('should throw exception on 404 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentCrudService.deleteAgent('nonexistent'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete agent: 404'),
          )),
        );
      });

      test('should throw exception on 403 error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/protected-agent',
          http.Response('Forbidden', 403),
        );

        expect(
          () => agentCrudService.deleteAgent('protected-agent'),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete agent: 403'),
          )),
        );
      });

      test('should handle empty agent ID in delete', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/',
          http.Response('', 200),
        );

        await agentCrudService.deleteAgent('');
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/'));
      });

      test('should handle special characters in agent ID for delete', () async {
        const specialId = 'agent-with-special-@#%';
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/$specialId',
          http.Response('', 200),
        );

        await agentCrudService.deleteAgent(specialId);
        expect(mockHttpClient.requestUrls.last, equals('https://your-api-url.com/agents/$specialId'));
      });

      test('should handle network error in delete', () async {
        expect(
          () => agentCrudService.deleteAgent('agent-123'),
          throwsA(isA<Exception>()),
        );
      });
    });

    test('should handle various HTTP status codes correctly', () async {
      final testCases = [
        (200, true),
        (201, true),
        (204, true),
        (400, false),
        (401, false),
        (403, false),
        (404, false),
        (500, false),
      ];

      for (final (statusCode, shouldSucceed) in testCases) {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('[]', statusCode),
        );

        if (shouldSucceed && statusCode == 200) {
          final agents = await agentCrudService.getAgents();
          expect(agents, isEmpty);
        } else if (!shouldSucceed) {
          expect(
            () => agentCrudService.getAgents(),
            throwsA(isA<Exception>()),
          );
        }
      }
    });

    test('should maintain request order for multiple operations', () async {
      mockHttpClient.setResponse(
        'https://your-api-url.com/agents',
        http.Response('[]', 200),
      );
      mockHttpClient.setResponse(
        'https://your-api-url.com/agents/agent-1',
        http.Response('{"id": "agent-1", "name": "Test", "tools": []}', 200),
      );

      await agentCrudService.getAgents();
      await agentCrudService.getAgentDetails('agent-1');

      expect(mockHttpClient.requestUrls, hasLength(2));
      expect(mockHttpClient.requestUrls[0], equals('https://your-api-url.com/agents'));
      expect(mockHttpClient.requestUrls[1], equals('https://your-api-url.com/agents/agent-1'));
      expect(mockHttpClient.requestMethods[0], equals('GET'));
      expect(mockHttpClient.requestMethods[1], equals('GET'));
    });
  });
}
