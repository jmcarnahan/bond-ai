import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service/agent_service.dart';
import 'package:flutterui/data/services/auth_service.dart';

class MockAuthService implements AuthService {
  final Map<String, String> _headers;

  MockAuthService({Map<String, String>? headers}) 
    : _headers = headers ?? {
    'Authorization': 'Bearer test-token',
    'Content-Type': 'application/json',
  };

  @override
  Future<Map<String, String>> get authenticatedHeaders async => _headers;

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
      test('should delegate to CRUD service and return list of agents', () async {
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

      test('should handle empty agents list', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('[]', 200),
        );

        final agents = await agentService.getAgents();
        expect(agents, isEmpty);
      });

      test('should propagate errors from CRUD service', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('Server Error', 500),
        );

        expect(
          () => agentService.getAgents(),
          throwsException,
        );
      });
    });

    group('getAgentDetails', () {
      test('should delegate to CRUD service and return agent details', () async {
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
        expect(agent.instructions, equals('Test Instructions'));
        expect(agent.model, equals('gpt-4'));
      });

      test('should propagate errors from CRUD service', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/nonexistent',
          http.Response('Not Found', 404),
        );

        expect(
          () => agentService.getAgentDetails('nonexistent'),
          throwsException,
        );
      });
    });

    group('createAgent', () {
      test('should delegate to CRUD service and create agent', () async {
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

      test('should propagate errors from CRUD service', () async {
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
      test('should delegate to CRUD service and update agent', () async {
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

      test('should propagate errors from CRUD service', () async {
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
      test('should delegate to CRUD service and delete agent', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents/agent-123',
          http.Response('', 200),
        );

        await agentService.deleteAgent('agent-123');
      });

      test('should propagate errors from CRUD service', () async {
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
      test('should delegate to file service and upload file', () async {
        final fileBytes = Uint8List.fromList([1, 2, 3, 4]);
        const fileName = 'test.txt';

        const responseJson = '''{
          "provider_file_id": "file-123",
          "file_name": "test.txt",
          "message": "File uploaded successfully"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentService.uploadFile(fileName, fileBytes);

        expect(response.providerFileId, equals('file-123'));
        expect(response.fileName, equals('test.txt'));
        expect(response.message, equals('File uploaded successfully'));
      });

      test('should handle empty file upload', () async {
        final fileBytes = Uint8List.fromList([]);
        const fileName = 'empty.txt';

        const responseJson = '''{
          "provider_file_id": "file-empty",
          "file_name": "empty.txt",
          "message": "Empty file uploaded"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(responseJson, 200),
        );

        final response = await agentService.uploadFile(fileName, fileBytes);

        expect(response.fileName, equals('empty.txt'));
      });

      test('should propagate errors from file service', () async {
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
      test('should delegate to file service and delete file', () async {
        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response('', 200),
        );

        await agentService.deleteFile('file-123');
      });

      test('should propagate errors from file service', () async {
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
      test('should delegate to file service and return list of files', () async {
        const filesJson = '''[
          {
            "id": "file-1",
            "fileName": "document1.pdf",
            "fileSize": 1024,
            "createdAt": "2023-01-01T10:00:00Z"
          },
          {
            "id": "file-2",
            "fileName": "document2.txt",
            "fileSize": 512,
            "createdAt": "2023-01-02T10:00:00Z"
          }
        ]''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files',
          http.Response(filesJson, 200),
        );

        final files = await agentService.getFiles();

        expect(files, hasLength(2));
        expect(files[0].id, equals('file-1'));
        expect(files[0].fileName, equals('document1.pdf'));
        expect(files[1].id, equals('file-2'));
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

      test('should propagate errors from file service', () async {
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
      test('should delegate to file service and return file info', () async {
        const fileInfoJson = '''{
          "id": "file-123",
          "fileName": "document.pdf",
          "fileSize": 2048,
          "createdAt": "2023-01-01T10:00:00Z"
        }''';

        mockHttpClient.setResponse(
          'https://your-api-url.com/files/file-123',
          http.Response(fileInfoJson, 200),
        );

        final fileInfo = await agentService.getFileInfo('file-123');

        expect(fileInfo.id, equals('file-123'));
        expect(fileInfo.fileName, equals('document.pdf'));
        expect(fileInfo.fileSize, equals(2048));
      });

      test('should propagate errors from file service', () async {
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

    test('dispose should dispose http client', () {
      agentService.dispose();
    });

    test('should handle complex workflow with multiple operations', () async {
      const agentData = AgentDetailModel(
        id: '',
        name: 'Complex Agent',
        description: 'Agent for complex workflow',
        tools: [],
        files: [],
        instructions: 'Complex instructions',
        model: 'gpt-4',
      );

      final fileBytes = Uint8List.fromList([1, 2, 3, 4, 5]);
      const fileName = 'workflow.txt';

      const createAgentResponseJson = '''{
        "agent_id": "complex-agent-123",
        "name": "Complex Agent"
      }''';

      const uploadFileResponseJson = '''{
        "provider_file_id": "file-456",
        "file_name": "workflow.txt",
        "message": "File uploaded successfully"
      }''';

      const agentDetailsJson = '''{
        "agent_id": "complex-agent-123",
        "name": "Complex Agent",
        "description": "Agent for complex workflow",
        "tools": [],
        "files": [],
        "instructions": "Complex instructions",
        "model": "gpt-4"
      }''';

      mockHttpClient.setResponse(
        'https://your-api-url.com/agents',
        http.Response(createAgentResponseJson, 201),
      );

      mockHttpClient.setResponse(
        'https://your-api-url.com/files',
        http.Response(uploadFileResponseJson, 200),
      );

      mockHttpClient.setResponse(
        'https://your-api-url.com/agents/complex-agent-123',
        http.Response(agentDetailsJson, 200),
      );

      final createResponse = await agentService.createAgent(agentData);
      expect(createResponse.agentId, equals('complex-agent-123'));

      final uploadResponse = await agentService.uploadFile(fileName, fileBytes);
      expect(uploadResponse.providerFileId, equals('file-456'));

      final agentDetails = await agentService.getAgentDetails('complex-agent-123');
      expect(agentDetails.name, equals('Complex Agent'));

      mockHttpClient.setResponse(
        'https://your-api-url.com/files/file-456',
        http.Response('', 200),
      );

      mockHttpClient.setResponse(
        'https://your-api-url.com/agents/complex-agent-123',
        http.Response('', 200),
      );

      await agentService.deleteFile('file-456');
      await agentService.deleteAgent('complex-agent-123');

      expect(mockHttpClient.requests, hasLength(5));
    });

    test('should handle authentication changes', () async {
      final differentAuthService = MockAuthService(headers: {
        'Authorization': 'Bearer different-token',
        'Content-Type': 'application/json',
      });

      final serviceWithDifferentAuth = AgentService(
        httpClient: mockHttpClient,
        authService: differentAuthService,
      );

      try {
        mockHttpClient.setResponse(
          'https://your-api-url.com/agents',
          http.Response('[]', 200),
        );

        await serviceWithDifferentAuth.getAgents();

        final request = mockHttpClient.requests.last;
        expect(request.headers['Authorization'], equals('Bearer different-token'));
      } finally {
        serviceWithDifferentAuth.dispose();
      }
    });

    test('should maintain service composition correctly', () async {
      mockHttpClient.setResponse(
        'https://your-api-url.com/agents',
        http.Response('[]', 200),
      );

      await agentService.getAgents();

      final fileBytes = Uint8List.fromList([1, 2, 3]);
      mockHttpClient.setResponse(
        'https://your-api-url.com/files',
        http.Response('{"provider_file_id":"file-123","file_name":"test.txt","message":"Uploaded"}', 200),
      );

      await agentService.uploadFile('test.txt', fileBytes);

      expect(mockHttpClient.requests, hasLength(2));
      expect(mockHttpClient.requests[0] is http.Request, isTrue);
      expect(mockHttpClient.requests[1] is http.MultipartRequest, isTrue);

      final getRequest = mockHttpClient.requests[0] as http.Request;
      final uploadRequest = mockHttpClient.requests[1] as http.MultipartRequest;

      expect(getRequest.method, equals('GET'));
      expect(uploadRequest.method, equals('POST'));
      expect(getRequest.headers['Authorization'], equals('Bearer test-token'));
      expect(uploadRequest.headers['Authorization'], equals('Bearer test-token'));
    });

    test('should handle service errors gracefully', () async {
      const invalidAgentData = AgentDetailModel(
        id: '',
        name: '',
        description: '',
        tools: [],
        files: [],
        instructions: '',
        model: '',
      );

      mockHttpClient.setResponse(
        'https://your-api-url.com/agents',
        http.Response('Validation Error', 422),
      );

      expect(
        () => agentService.createAgent(invalidAgentData),
        throwsA(isA<Exception>()),
      );

      final invalidFileBytes = Uint8List.fromList([]);
      mockHttpClient.setResponse(
        'https://your-api-url.com/files',
        http.Response('File Too Small', 400),
      );

      expect(
        () => agentService.uploadFile('', invalidFileBytes),
        throwsA(isA<Exception>()),
      );
    });
  });
}