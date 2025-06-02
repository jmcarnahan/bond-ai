import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/core/constants/api_constants.dart';

class MockHttpClient extends http.BaseClient {
  final Map<String, http.Response> _responses = {};
  final List<http.BaseRequest> _requests = [];

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<http.BaseRequest> get requests => _requests;

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

class MockAuthService implements AuthService {
  final List<Future<Map<String, String>> Function()> _headersProvider;

  MockAuthService() : _headersProvider = [() async => throw Exception('Not authenticated for this request.')];

  void setToken(String token) {
    _headersProvider[0] = () async => {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  void setException(Exception exception) {
    _headersProvider[0] = () async => throw exception;
  }

  @override
  Future<Map<String, String>> get authenticatedHeaders => _headersProvider[0]();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('ThreadService Tests', () {
    late MockHttpClient mockHttpClient;
    late MockAuthService mockAuthService;
    late ThreadService threadService;

    setUp(() {
      mockHttpClient = MockHttpClient();
      mockAuthService = MockAuthService();
      threadService = ThreadService(
        httpClient: mockHttpClient,
        authService: mockAuthService,
      );
    });

    group('getThreads', () {
      test('should return list of threads successfully', () async {
        const token = 'test_token_123';
        final threadsJson = [
          {
            'id': 'thread-1',
            'name': 'Thread 1',
            'description': 'First thread',
          },
          {
            'id': 'thread-2',
            'name': 'Thread 2',
            'description': null,
          },
        ];
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response(jsonEncode(threadsJson), 200),
        );
        
        final threads = await threadService.getThreads();
        
        expect(threads, hasLength(2));
        expect(threads[0].id, equals('thread-1'));
        expect(threads[0].name, equals('Thread 1'));
        expect(threads[0].description, equals('First thread'));
        expect(threads[1].id, equals('thread-2'));
        expect(threads[1].name, equals('Thread 2'));
        expect(threads[1].description, isNull);
        
        expect(mockHttpClient.requests, hasLength(1));
        final request = mockHttpClient.requests[0];
        expect(request.method, equals('GET'));
        expect(request.headers['Authorization'], equals('Bearer $token'));
      });

      test('should return empty list when no threads exist', () async {
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response(jsonEncode([]), 200),
        );
        
        final threads = await threadService.getThreads();
        
        expect(threads, isEmpty);
      });

      test('should throw exception on authentication error', () async {
        mockAuthService.setException(Exception('Not authenticated for this request.'));
        
        expect(
          () => threadService.getThreads(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to fetch threads'),
          )),
        );
      });

      test('should throw exception on HTTP error', () async {
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response('Internal Server Error', 500),
        );
        
        expect(
          () => threadService.getThreads(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to load threads: 500'),
          )),
        );
      });

      test('should handle malformed JSON response', () async {
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response('invalid json', 200),
        );
        
        expect(
          () => threadService.getThreads(),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('createThread', () {
      test('should create thread with name successfully', () async {
        const token = 'test_token_123';
        const threadName = 'New Thread';
        final threadJson = {
          'id': 'thread-123',
          'name': threadName,
          'description': null,
        };
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response(jsonEncode(threadJson), 201),
        );
        
        final thread = await threadService.createThread(name: threadName);
        
        expect(thread.id, equals('thread-123'));
        expect(thread.name, equals(threadName));
        expect(thread.description, isNull);
        
        expect(mockHttpClient.requests, hasLength(1));
        final request = mockHttpClient.requests[0] as http.Request;
        expect(request.method, equals('POST'));
        expect(request.headers['Authorization'], equals('Bearer $token'));
        
        final requestBody = jsonDecode(request.body);
        expect(requestBody['name'], equals(threadName));
      });

      test('should create thread without name successfully', () async {
        const token = 'test_token_123';
        final threadJson = {
          'id': 'thread-123',
          'name': 'Generated Thread Name',
          'description': null,
        };
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response(jsonEncode(threadJson), 201),
        );
        
        final thread = await threadService.createThread();
        
        expect(thread.id, equals('thread-123'));
        expect(thread.name, equals('Generated Thread Name'));
        
        final request = mockHttpClient.requests[0] as http.Request;
        final requestBody = jsonDecode(request.body);
        expect(requestBody['name'], isNull);
      });

      test('should throw exception on HTTP error', () async {
        const token = 'test_token_123';
        const threadName = 'New Thread';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}',
          http.Response('Bad Request', 400),
        );
        
        expect(
          () => threadService.createThread(name: threadName),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to create thread: 400'),
          )),
        );
      });
    });

    group('getMessagesForThread', () {
      test('should return list of messages successfully', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        final messagesJson = [
          {
            'id': 'msg-1',
            'type': 'text',
            'role': 'user',
            'content': 'Hello',
            'is_error': false,
          },
          {
            'id': 'msg-2',
            'type': 'text',
            'role': 'assistant',
            'content': 'Hi there!',
            'is_error': false,
          },
        ];
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=100',
          http.Response(jsonEncode(messagesJson), 200),
        );
        
        final messages = await threadService.getMessagesForThread(threadId);
        
        expect(messages, hasLength(2));
        expect(messages[0].id, equals('msg-1'));
        expect(messages[0].role, equals('user'));
        expect(messages[0].content, equals('Hello'));
        expect(messages[1].id, equals('msg-2'));
        expect(messages[1].role, equals('assistant'));
        expect(messages[1].content, equals('Hi there!'));
        
        final request = mockHttpClient.requests[0];
        expect(request.method, equals('GET'));
        expect(request.headers['Authorization'], equals('Bearer $token'));
      });

      test('should use custom limit parameter', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        const customLimit = 50;
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=$customLimit',
          http.Response(jsonEncode([]), 200),
        );
        
        await threadService.getMessagesForThread(threadId, limit: customLimit);
        
        final request = mockHttpClient.requests[0];
        expect(request.url.toString(), contains('limit=$customLimit'));
      });

      test('should return empty list when no messages exist', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=100',
          http.Response(jsonEncode([]), 200),
        );
        
        final messages = await threadService.getMessagesForThread(threadId);
        
        expect(messages, isEmpty);
      });

      test('should throw exception on HTTP error', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=100',
          http.Response('Not Found', 404),
        );
        
        expect(
          () => threadService.getMessagesForThread(threadId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to load messages for thread $threadId: 404'),
          )),
        );
      });
    });

    group('deleteThread', () {
      test('should delete thread successfully', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId',
          http.Response('', 204),
        );
        
        await threadService.deleteThread(threadId);
        
        expect(mockHttpClient.requests, hasLength(1));
        final request = mockHttpClient.requests[0];
        expect(request.method, equals('DELETE'));
        expect(request.headers['Authorization'], equals('Bearer $token'));
        expect(request.url.toString(), contains(threadId));
      });

      test('should throw exception when thread not found', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId',
          http.Response('Not Found', 404),
        );
        
        expect(
          () => threadService.deleteThread(threadId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Thread not found: 404'),
          )),
        );
      });

      test('should throw exception on other HTTP errors', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId',
          http.Response('Internal Server Error', 500),
        );
        
        expect(
          () => threadService.deleteThread(threadId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete thread: 500'),
          )),
        );
      });

      test('should handle authentication error', () async {
        const threadId = 'thread-123';
        
        mockAuthService.setException(Exception('Not authenticated for this request.'));
        
        expect(
          () => threadService.deleteThread(threadId),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to delete thread $threadId'),
          )),
        );
      });
    });

    group('Constructor', () {
      test('should use provided httpClient', () {
        final customClient = MockHttpClient();
        final service = ThreadService(
          httpClient: customClient,
          authService: mockAuthService,
        );
        
        expect(service, isA<ThreadService>());
      });

      test('should use default httpClient when not provided', () {
        final service = ThreadService(authService: mockAuthService);
        
        expect(service, isA<ThreadService>());
      });
    });

    group('Edge Cases', () {
      test('should handle messages with image data', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        final messagesJson = [
          {
            'id': 'msg-1',
            'type': 'image_file',
            'role': 'user',
            'content': '[Image]',
            'image_data': 'base64data',
            'is_error': false,
          },
        ];
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=100',
          http.Response(jsonEncode(messagesJson), 200),
        );
        
        final messages = await threadService.getMessagesForThread(threadId);
        
        expect(messages, hasLength(1));
        expect(messages[0].type, equals('image_file'));
        expect(messages[0].content, equals('[Image]'));
        expect(messages[0].imageData, equals('base64data'));
      });

      test('should handle error messages', () async {
        const token = 'test_token_123';
        const threadId = 'thread-123';
        final messagesJson = [
          {
            'id': 'msg-1',
            'type': 'text',
            'role': 'assistant',
            'content': 'Error occurred',
            'is_error': true,
          },
        ];
        
        mockAuthService.setToken(token);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=100',
          http.Response(jsonEncode(messagesJson), 200),
        );
        
        final messages = await threadService.getMessagesForThread(threadId);
        
        expect(messages, hasLength(1));
        expect(messages[0].isError, isTrue);
        expect(messages[0].content, equals('Error occurred'));
      });
    });
  });
}
