import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'package:flutterui/data/services/agent_service/agent_http_client.dart';
import 'package:flutterui/data/services/auth_service.dart';

class MockAuthService implements AuthService {
  final Map<String, String> _headers;
  final bool _shouldThrow;

  MockAuthService({
    Map<String, String>? headers,
    bool shouldThrow = false,
  }) : _headers = headers ?? {
    'Authorization': 'Bearer test-token',
    'Content-Type': 'application/json',
  }, _shouldThrow = shouldThrow;

  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    if (_shouldThrow) {
      throw Exception('Auth failed');
    }
    return _headers;
  }

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
  final bool _shouldThrow;

  MockHttpClient({bool shouldThrow = false}) : _shouldThrow = shouldThrow;

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<http.BaseRequest> get requests => List.unmodifiable(_requests);

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (_shouldThrow) {
      throw Exception('Network error');
    }

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
  group('AgentHttpClient Tests', () {
    late MockAuthService mockAuthService;
    late MockHttpClient mockHttpClient;
    late AgentHttpClient agentHttpClient;

    setUp(() {
      mockAuthService = MockAuthService();
      mockHttpClient = MockHttpClient();
      agentHttpClient = AgentHttpClient(
        httpClient: mockHttpClient,
        authService: mockAuthService,
      );
    });

    tearDown(() {
      agentHttpClient.dispose();
    });

    test('constructor should create client with auth service', () {
      final client = AgentHttpClient(authService: mockAuthService);
      expect(client, isA<AgentHttpClient>());
      client.dispose();
    });

    test('constructor should accept custom http client', () {
      final customClient = MockHttpClient();
      final client = AgentHttpClient(
        httpClient: customClient,
        authService: mockAuthService,
      );
      expect(client, isA<AgentHttpClient>());
      client.dispose();
    });

    group('authenticated headers', () {
      test('should return headers with authorization', () async {
        final headers = {'Authorization': 'Bearer valid-token', 'Content-Type': 'application/json'};
        final authService = MockAuthService(headers: headers);
        final client = AgentHttpClient(authService: authService);

        try {
          mockHttpClient.setResponse('https://test.com', http.Response('{}', 200));
          await client.get('https://test.com');

          final request = mockHttpClient.requests.first;
          expect(request.headers['Authorization'], equals('Bearer valid-token'));
        } finally {
          client.dispose();
        }
      });

      test('should throw exception when no authorization header', () async {
        final authService = MockAuthService(headers: {'Content-Type': 'application/json'});
        final client = AgentHttpClient(authService: authService);

        try {
          expect(
            () => client.get('https://test.com'),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });

      test('should throw exception when auth service fails', () async {
        final authService = MockAuthService(shouldThrow: true);
        final client = AgentHttpClient(authService: authService);

        try {
          expect(
            () => client.get('https://test.com'),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    group('GET requests', () {
      test('should make successful GET request', () async {
        const testUrl = 'https://test.com/api';
        const responseBody = '{"message": "success"}';
        
        mockHttpClient.setResponse(testUrl, http.Response(responseBody, 200));

        final response = await agentHttpClient.get(testUrl);

        expect(response.statusCode, equals(200));
        expect(response.body, equals(responseBody));
        expect(mockHttpClient.requests, hasLength(1));
        expect(mockHttpClient.requests.first.url.toString(), equals(testUrl));
        expect(mockHttpClient.requests.first.method, equals('GET'));
      });

      test('should include authorization headers in GET request', () async {
        const testUrl = 'https://test.com/api';
        mockHttpClient.setResponse(testUrl, http.Response('{}', 200));

        await agentHttpClient.get(testUrl);

        final request = mockHttpClient.requests.first;
        expect(request.headers['Authorization'], equals('Bearer test-token'));
      });

      test('should handle GET request errors', () async {
        const testUrl = 'https://test.com/api';
        mockHttpClient.setResponse(testUrl, http.Response('Error', 500));

        final response = await agentHttpClient.get(testUrl);
        expect(response.statusCode, equals(500));
      });

      test('should handle network errors in GET', () async {
        final throwingClient = MockHttpClient(shouldThrow: true);
        final client = AgentHttpClient(
          httpClient: throwingClient,
          authService: mockAuthService,
        );

        try {
          expect(
            () => client.get('https://test.com'),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    group('POST requests', () {
      test('should make successful POST request', () async {
        const testUrl = 'https://test.com/api';
        const requestData = {'name': 'test', 'value': 123};
        const responseBody = '{"id": "created"}';
        
        mockHttpClient.setResponse(testUrl, http.Response(responseBody, 201));

        final response = await agentHttpClient.post(testUrl, requestData);

        expect(response.statusCode, equals(201));
        expect(response.body, equals(responseBody));
        expect(mockHttpClient.requests, hasLength(1));
        
        final request = mockHttpClient.requests.first;
        expect(request.url.toString(), equals(testUrl));
        expect(request.method, equals('POST'));
        
        if (request is http.Request) {
          expect(request.body, equals(json.encode(requestData)));
        }
      });

      test('should include authorization headers in POST request', () async {
        const testUrl = 'https://test.com/api';
        mockHttpClient.setResponse(testUrl, http.Response('{}', 201));

        await agentHttpClient.post(testUrl, {'test': 'data'});

        final request = mockHttpClient.requests.first;
        expect(request.headers['Authorization'], equals('Bearer test-token'));
      });

      test('should handle POST request errors', () async {
        const testUrl = 'https://test.com/api';
        mockHttpClient.setResponse(testUrl, http.Response('Bad Request', 400));

        final response = await agentHttpClient.post(testUrl, {'test': 'data'});
        expect(response.statusCode, equals(400));
      });

      test('should handle network errors in POST', () async {
        final throwingClient = MockHttpClient(shouldThrow: true);
        final client = AgentHttpClient(
          httpClient: throwingClient,
          authService: mockAuthService,
        );

        try {
          expect(
            () => client.post('https://test.com', {'test': 'data'}),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    group('PUT requests', () {
      test('should make successful PUT request', () async {
        const testUrl = 'https://test.com/api/1';
        const requestData = {'name': 'updated', 'value': 456};
        const responseBody = '{"updated": true}';
        
        mockHttpClient.setResponse(testUrl, http.Response(responseBody, 200));

        final response = await agentHttpClient.put(testUrl, requestData);

        expect(response.statusCode, equals(200));
        expect(response.body, equals(responseBody));
        expect(mockHttpClient.requests, hasLength(1));
        
        final request = mockHttpClient.requests.first;
        expect(request.url.toString(), equals(testUrl));
        expect(request.method, equals('PUT'));
        
        if (request is http.Request) {
          expect(request.body, equals(json.encode(requestData)));
        }
      });

      test('should include authorization headers in PUT request', () async {
        const testUrl = 'https://test.com/api/1';
        mockHttpClient.setResponse(testUrl, http.Response('{}', 200));

        await agentHttpClient.put(testUrl, {'test': 'data'});

        final request = mockHttpClient.requests.first;
        expect(request.headers['Authorization'], equals('Bearer test-token'));
      });

      test('should handle PUT request errors', () async {
        const testUrl = 'https://test.com/api/1';
        mockHttpClient.setResponse(testUrl, http.Response('Not Found', 404));

        final response = await agentHttpClient.put(testUrl, {'test': 'data'});
        expect(response.statusCode, equals(404));
      });

      test('should handle network errors in PUT', () async {
        final throwingClient = MockHttpClient(shouldThrow: true);
        final client = AgentHttpClient(
          httpClient: throwingClient,
          authService: mockAuthService,
        );

        try {
          expect(
            () => client.put('https://test.com/1', {'test': 'data'}),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    group('DELETE requests', () {
      test('should make successful DELETE request', () async {
        const testUrl = 'https://test.com/api/1';
        
        mockHttpClient.setResponse(testUrl, http.Response('', 204));

        final response = await agentHttpClient.delete(testUrl);

        expect(response.statusCode, equals(204));
        expect(mockHttpClient.requests, hasLength(1));
        
        final request = mockHttpClient.requests.first;
        expect(request.url.toString(), equals(testUrl));
        expect(request.method, equals('DELETE'));
      });

      test('should include authorization headers in DELETE request', () async {
        const testUrl = 'https://test.com/api/1';
        mockHttpClient.setResponse(testUrl, http.Response('', 204));

        await agentHttpClient.delete(testUrl);

        final request = mockHttpClient.requests.first;
        expect(request.headers['Authorization'], equals('Bearer test-token'));
      });

      test('should handle DELETE request errors', () async {
        const testUrl = 'https://test.com/api/1';
        mockHttpClient.setResponse(testUrl, http.Response('Forbidden', 403));

        final response = await agentHttpClient.delete(testUrl);
        expect(response.statusCode, equals(403));
      });

      test('should handle network errors in DELETE', () async {
        final throwingClient = MockHttpClient(shouldThrow: true);
        final client = AgentHttpClient(
          httpClient: throwingClient,
          authService: mockAuthService,
        );

        try {
          expect(
            () => client.delete('https://test.com/1'),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    group('sendMultipartRequest', () {
      test('should send multipart request successfully', () async {
        const testUrl = 'https://test.com/upload';
        final request = http.MultipartRequest('POST', Uri.parse(testUrl));
        request.files.add(http.MultipartFile.fromString('file', 'test content', filename: 'test.txt'));

        mockHttpClient.setResponse(testUrl, http.Response('{"uploaded": true}', 201));

        final response = await agentHttpClient.sendMultipartRequest(request);

        expect(response.statusCode, equals(201));
        expect(response.body, equals('{"uploaded": true}'));
      });

      test('should add authorization header to multipart request', () async {
        const testUrl = 'https://test.com/upload';
        final request = http.MultipartRequest('POST', Uri.parse(testUrl));

        mockHttpClient.setResponse(testUrl, http.Response('{}', 201));

        await agentHttpClient.sendMultipartRequest(request);

        expect(request.headers['Authorization'], equals('Bearer test-token'));
      });

      test('should throw exception when no auth token for multipart', () async {
        final authService = MockAuthService(headers: {'Content-Type': 'application/json'});
        final client = AgentHttpClient(authService: authService);

        final request = http.MultipartRequest('POST', Uri.parse('https://test.com/upload'));

        try {
          expect(
            () => client.sendMultipartRequest(request),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });

      test('should handle multipart request errors', () async {
        const testUrl = 'https://test.com/upload';
        final request = http.MultipartRequest('POST', Uri.parse(testUrl));

        mockHttpClient.setResponse(testUrl, http.Response('Upload failed', 400));

        final response = await agentHttpClient.sendMultipartRequest(request);
        expect(response.statusCode, equals(400));
      });

      test('should handle network errors in multipart request', () async {
        final throwingClient = MockHttpClient(shouldThrow: true);
        final client = AgentHttpClient(
          httpClient: throwingClient,
          authService: mockAuthService,
        );

        final request = http.MultipartRequest('POST', Uri.parse('https://test.com/upload'));

        try {
          expect(
            () => client.sendMultipartRequest(request),
            throwsException,
          );
        } finally {
          client.dispose();
        }
      });
    });

    test('dispose should close http client', () {
      agentHttpClient.dispose();
    });

    test('should handle various URL formats', () async {
      final urls = [
        'https://api.example.com/v1/agents',
        'http://localhost:3000/api/agents',
        'https://sub.domain.com:8080/agents?param=value',
        'https://api.com/agents/123/files',
      ];

      for (final url in urls) {
        mockHttpClient.setResponse(url, http.Response('{}', 200));
        final response = await agentHttpClient.get(url);
        expect(response.statusCode, equals(200));
      }
    });

    test('should handle empty request bodies', () async {
      const testUrl = 'https://test.com/api';
      mockHttpClient.setResponse(testUrl, http.Response('{}', 200));

      final response = await agentHttpClient.post(testUrl, {});
      expect(response.statusCode, equals(200));

      final request = mockHttpClient.requests.last;
      if (request is http.Request) {
        expect(request.body, equals('{}'));
      }
    });

    test('should handle complex JSON data', () async {
      const testUrl = 'https://test.com/api';
      final complexData = {
        'nested': {
          'array': [1, 2, 3],
          'string': 'test',
          'boolean': true,
          'null_value': null,
        },
        'unicode': 'café 🚀',
        'numbers': [1.5, -42, 0],
      };

      mockHttpClient.setResponse(testUrl, http.Response('{}', 200));

      await agentHttpClient.post(testUrl, complexData);

      final request = mockHttpClient.requests.last;
      if (request is http.Request) {
        final decodedBody = json.decode(request.body);
        expect(decodedBody['nested']['array'], equals([1, 2, 3]));
        expect(decodedBody['unicode'], equals('café 🚀'));
      }
    });
  });
}