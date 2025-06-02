import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/auth_service.dart';

class MockAuthService implements AuthService {
  @override
  Future<Map<String, String>> get authenticatedHeaders async => {
    'Authorization': 'Bearer test-token',
    'Content-Type': 'application/json',
  };

  String? get accessToken => 'test-token';

  bool get isAuthenticated => true;

  Future<void> signInWithGoogle() async {}

  Future<void> signOut() async {}

  Future<String> getCurrentAccessToken() async => 'test-token';

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockHttpClient extends http.BaseClient {
  final Map<String, http.Response> _responses = {};
  final List<http.BaseRequest> _requests = [];

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<http.BaseRequest> get requests => List.unmodifiable(_requests);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    _requests.add(request);
    
    final response = _responses[request.url.toString()];
    if (response != null) {
      return http.StreamedResponse(
        Stream.value(response.bodyBytes),
        response.statusCode,
        headers: response.headers,
      );
    }
    
    return http.StreamedResponse(
      Stream.value([]),
      404,
    );
  }
}

void main() {
  group('AgentService Tests', () {
    late MockAuthService mockAuthService;
    late MockHttpClient mockHttpClient;
    late AgentService agentService;

    setUp(() {
      mockAuthService = MockAuthService();
      mockHttpClient = MockHttpClient();
      agentService = AgentService(
        httpClient: mockHttpClient,
        authService: mockAuthService,
      );
    });

    tearDown(() {
      agentService.dispose();
    });

    test('constructor should create agent service with auth service', () {
      final service = AgentService(authService: mockAuthService);
      expect(service, isA<AgentService>());
      service.dispose();
    });

    test('constructor should accept custom http client', () {
      final customClient = MockHttpClient();
      final service = AgentService(
        httpClient: customClient,
        authService: mockAuthService,
      );
      expect(service, isA<AgentService>());
      service.dispose();
    });

    group('getAgents', () {
      test('should return list of agents on successful response', () async {
        const agentsJson = '''[
          {
            "agent_id": "agent-1",
            "name": "Test Agent 1",
            "description": "Test Description 1"
          },
          {
            "agent_id": "agent-2", 
            "name": "Test Agent 2",
            "description": "Test Description 2"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response(agentsJson, 200),
        );

        final agents = await agentService.getAgents();

        expect(agents, hasLength(2));
        expect(agents[0].id, equals('agent-1'));
        expect(agents[0].name, equals('Test Agent 1'));
        expect(agents[1].id, equals('agent-2'));
        expect(agents[1].name, equals('Test Agent 2'));
      });

      test('should throw exception on error response', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Server Error', 500),
        );

        expect(
          () => agentService.getAgents(),
          throwsException,
        );
      });

      test('should throw exception on network error', () async {
        expect(
          () => agentService.getAgents(),
          throwsException,
        );
      });
    });

    group('getAgentDetails', () {
      test('should return agent details on successful response', () async {
        const agentJson = '''{
          "agent_id": "agent-123",
          "name": "Test Agent",
          "description": "Test Description",
          "tools": [],
          "files": [],
          "instructions": "Test Instructions",
          "model": "gpt-4"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response(agentJson, 200),
        );

        final agent = await agentService.getAgentDetails('agent-123');

        expect(agent.id, equals('agent-123'));
        expect(agent.name, equals('Test Agent'));
        expect(agent.description, equals('Test Description'));
      });

      test('should throw exception on error response', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.getAgentDetails('agent-123'),
          throwsException,
        );
      });

      test('should handle empty agent ID', () async {
        expect(
          () => agentService.getAgentDetails(''),
          throwsException,
        );
      });
    });

    group('createAgent', () {
      test('should create agent successfully', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'New Agent',
          description: 'New Description',
          tools: [],
          files: [],
          instructions: 'New Instructions',
          model: 'gpt-4',
        );

        const responseJson = '''{
          "agent_id": "new-agent-123",
          "name": "New Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response(responseJson, 201),
        );

        final response = await agentService.createAgent(agentData);

        expect(response.agentId, equals('new-agent-123'));
        expect(response.name, equals('New Agent'));
      });

      test('should throw exception on error response', () async {
        const agentData = AgentDetailModel(
          id: '',
          name: 'New Agent',
          description: 'New Description',
          tools: [],
          files: [],
          instructions: 'New Instructions',
          model: 'gpt-4',
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Bad Request', 400),
        );

        expect(
          () => agentService.createAgent(agentData),
          throwsException,
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
          files: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4',
        );

        const responseJson = '''{
          "agent_id": "agent-123",
          "name": "Updated Agent"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response(responseJson, 200),
        );

        final response = await agentService.updateAgent('agent-123', agentData);

        expect(response.agentId, equals('agent-123'));
        expect(response.name, equals('Updated Agent'));
      });

      test('should throw exception on error response', () async {
        const agentData = AgentDetailModel(
          id: 'agent-123',
          name: 'Updated Agent',
          description: 'Updated Description',
          tools: [],
          files: [],
          instructions: 'Updated Instructions',
          model: 'gpt-4',
        );

        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.updateAgent('agent-123', agentData),
          throwsException,
        );
      });
    });

    group('deleteAgent', () {
      test('should delete agent successfully with 200 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('', 200),
        );

        await agentService.deleteAgent('agent-123');
      });

      test('should delete agent successfully with 204 status', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('', 204),
        );

        await agentService.deleteAgent('agent-123');
      });

      test('should throw exception on error response', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.deleteAgent('agent-123'),
          throwsException,
        );
      });
    });

    group('uploadFile', () {
      test('should upload file successfully', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3, 4]);
        const fileName = 'test.txt';

        const responseJson = '''{
          "provider_file_id": "file-123",
          "file_name": "test.txt",
          "message": "File uploaded successfully"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 201),
        );

        final response = await agentService.uploadFile(fileName, fileBytes);

        expect(response.providerFileId, equals('file-123'));
        expect(response.fileName, equals('test.txt'));
        expect(response.message, equals('File uploaded successfully'));
      });

      test('should handle empty file', () async {
        final fileBytes = Uint8List.fromList([]);
        const fileName = 'empty.txt';

        const responseJson = '''{
          "provider_file_id": "file-empty",
          "file_name": "empty.txt",
          "message": "Empty file uploaded"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 201),
        );

        final response = await agentService.uploadFile(fileName, fileBytes);

        expect(response.fileName, equals('empty.txt'));
      });

      test('should throw exception on upload error', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3]);
        const fileName = 'test.txt';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('Upload failed', 400),
        );

        expect(
          () => agentService.uploadFile(fileName, fileBytes),
          throwsException,
        );
      });
    });

    group('deleteFile', () {
      test('should delete file successfully', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('', 200),
        );

        await agentService.deleteFile('file-123');
      });

      test('should throw exception on delete error', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.deleteFile('file-123'),
          throwsException,
        );
      });
    });

    group('getFiles', () {
      test('should return list of files', () async {
        const filesJson = '''[
          {
            "provider_file_id": "file-1",
            "file_name": "document1.pdf",
            "file_size": 1024,
            "upload_date": "2023-01-01T10:00:00Z"
          },
          {
            "provider_file_id": "file-2",
            "file_name": "document2.txt",
            "file_size": 512,
            "upload_date": "2023-01-02T10:00:00Z"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(filesJson, 200),
        );

        final files = await agentService.getFiles();

        expect(files, hasLength(2));
        expect(files[0].providerFileId, equals('file-1'));
        expect(files[0].fileName, equals('document1.pdf'));
        expect(files[1].providerFileId, equals('file-2'));
        expect(files[1].fileName, equals('document2.txt'));
      });

      test('should handle empty file list', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('[]', 200),
        );

        final files = await agentService.getFiles();

        expect(files, isEmpty);
      });

      test('should throw exception on error response', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response('Server Error', 500),
        );

        expect(
          () => agentService.getFiles(),
          throwsException,
        );
      });
    });

    group('getFileInfo', () {
      test('should return file info successfully', () async {
        const fileInfoJson = '''{
          "provider_file_id": "file-123",
          "file_name": "document.pdf",
          "file_size": 2048,
          "upload_date": "2023-01-01T10:00:00Z"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentService.getFileInfo('file-123');

        expect(fileInfo.providerFileId, equals('file-123'));
        expect(fileInfo.fileName, equals('document.pdf'));
        expect(fileInfo.fileSize, equals(2048));
      });

      test('should throw exception on file not found', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.getFileInfo('nonexistent'),
          throwsException,
        );
      });
    });

    test('dispose should close http client', () {
      agentService.dispose();
    });
  });
}