import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/core/constants/api_constants.dart';

class MockHttpClient extends http.BaseClient {
  final Map<String, StreamedResponseData> _streamedResponses = {};
  final List<http.BaseRequest> _requests = [];

  void setStreamedResponse(String url, StreamedResponseData response) {
    _streamedResponses[url] = response;
  }

  List<http.BaseRequest> get requests => _requests;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    _requests.add(request);
    final response = _streamedResponses[request.url.toString()];
    
    if (response != null) {
      return http.StreamedResponse(
        response.stream,
        response.statusCode,
        headers: response.headers ?? {},
      );
    }
    
    return http.StreamedResponse(
      Stream.value([]),
      404,
    );
  }
}

class StreamedResponseData {
  final Stream<List<int>> stream;
  final int statusCode;
  final Map<String, String>? headers;

  StreamedResponseData(this.stream, this.statusCode, {this.headers});
}

class MockAuthService implements AuthService {
  final Map<String, dynamic> _state = {};

  void setToken(String token) {
    _state['token'] = token;
    _state.remove('exception');
  }

  void setException(Exception exception) {
    _state['exception'] = exception;
    _state.remove('token');
  }

  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    final exception = _state['exception'] as Exception?;
    if (exception != null) {
      throw exception;
    }
    final token = _state['token'] as String?;
    if (token == null) {
      throw Exception('Not authenticated for this request.');
    }
    return {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('ChatService Tests', () {
    late MockHttpClient mockHttpClient;
    late MockAuthService mockAuthService;
    late ChatService chatService;

    setUp(() {
      mockHttpClient = MockHttpClient();
      mockAuthService = MockAuthService();
      chatService = ChatService(
        httpClient: mockHttpClient,
        authService: mockAuthService,
      );
    });

    group('streamChatResponse', () {
      test('should stream chat response successfully', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        
        final chunks = [
          'Hello',
          ' there!',
          ' How can',
          ' I help you',
          ' today?'
        ];
        
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            200,
          ),
        );
        
        final responseStream = chatService.streamChatResponse(
          threadId: threadId,
          agentId: agentId,
          prompt: prompt,
        );
        
        final receivedChunks = <String>[];
        final subscription = responseStream.listen(receivedChunks.add);
        
        for (final chunk in chunks) {
          streamController.add(utf8.encode(chunk));
          await Future.delayed(const Duration(milliseconds: 10));
        }
        await streamController.close();
        
        await subscription.asFuture();
        
        expect(receivedChunks, equals(chunks));
        expect(mockHttpClient.requests, hasLength(1));
        
        final request = mockHttpClient.requests[0];
        expect(request.method, equals('POST'));
        expect(request.url.toString(), equals('${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}'));
        expect(request.headers['Authorization'], equals('Bearer $token'));
        expect(request.headers['Content-Type'], equals('application/json'));
        
        final requestBody = jsonDecode((request as http.Request).body);
        expect(requestBody['thread_id'], equals(threadId));
        expect(requestBody['agent_id'], equals(agentId));
        expect(requestBody['prompt'], equals(prompt));
      });

      test('should handle authentication error', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        
        mockAuthService.setException(Exception('Not authenticated for this request.'));
        
        expect(
          () => chatService.streamChatResponse(
            threadId: threadId,
            agentId: agentId,
            prompt: prompt,
          ).toList(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Error streaming chat'),
          )),
        );
      });

      test('should handle HTTP error response', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        
        const errorMessage = 'Internal Server Error';
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            500,
          ),
        );
        
        streamController.add(utf8.encode(errorMessage));
        await streamController.close();
        
        expect(
          () => chatService.streamChatResponse(
            threadId: threadId,
            agentId: agentId,
            prompt: prompt,
          ).toList(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to stream chat response: 500'),
          )),
        );
      });

      test('should handle empty stream', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            200,
          ),
        );
        
        final responseStream = chatService.streamChatResponse(
          threadId: threadId,
          agentId: agentId,
          prompt: prompt,
        );
        
        await streamController.close();
        
        final chunks = await responseStream.toList();
        expect(chunks, isEmpty);
      });

      test('should handle single chunk response', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        const responseText = 'Complete response in one chunk';
        
        mockAuthService.setToken(token);
        
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            200,
          ),
        );
        
        final responseStream = chatService.streamChatResponse(
          threadId: threadId,
          agentId: agentId,
          prompt: prompt,
        );
        
        streamController.add(utf8.encode(responseText));
        await streamController.close();
        
        final chunks = await responseStream.toList();
        expect(chunks, equals([responseText]));
      });

      test('should handle stream error', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        
        mockAuthService.setToken(token);
        
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            200,
          ),
        );
        
        final responseStream = chatService.streamChatResponse(
          threadId: threadId,
          agentId: agentId,
          prompt: prompt,
        );
        
        streamController.addError(Exception('Stream error'));
        
        expect(
          () => responseStream.toList(),
          throwsA(isA<Exception>()),
        );
      });

      test('should handle UTF-8 decoding of special characters', () async {
        const threadId = 'thread-123';
        const agentId = 'agent-456';
        const prompt = 'Hello, how are you?';
        const token = 'test_token_123';
        const responseText = 'Response with émojis 🚀 and spëcial chars: café, naïve, résumé';
        
        mockAuthService.setToken(token);
        
        final streamController = StreamController<List<int>>();
        
        mockHttpClient.setStreamedResponse(
          '${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}',
          StreamedResponseData(
            streamController.stream,
            200,
          ),
        );
        
        final responseStream = chatService.streamChatResponse(
          threadId: threadId,
          agentId: agentId,
          prompt: prompt,
        );
        
        streamController.add(utf8.encode(responseText));
        await streamController.close();
        
        final chunks = await responseStream.toList();
        expect(chunks, equals([responseText]));
      });
    });

    group('Constructor', () {
      test('should use provided httpClient', () {
        final customClient = MockHttpClient();
        final service = ChatService(
          httpClient: customClient,
          authService: mockAuthService,
        );
        
        expect(service, isA<ChatService>());
      });

      test('should use default httpClient when not provided', () {
        final service = ChatService(authService: mockAuthService);
        
        expect(service, isA<ChatService>());
      });
    });
  });
}
