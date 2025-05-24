import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable, kIsWeb;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/services/auth_service.dart'; // To get authenticated headers

@immutable
class ChatService {
  final http.Client _httpClient;
  final AuthService _authService;

  ChatService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? http.Client(),
      _authService = authService;

  Stream<String> streamChatResponse({
    required String threadId,
    required String agentId,
    required String prompt,
  }) async* {
    print(
      "[ChatService] streamChatResponse called for threadId: $threadId, agentId: $agentId",
    );
    try {
      final headers = await _authService.authenticatedHeaders;
      final body = jsonEncode({
        'thread_id': threadId,
        'agent_id': agentId,
        'prompt': prompt,
      });

      final request =
          http.Request(
              'POST',
              Uri.parse(ApiConstants.baseUrl + ApiConstants.chatEndpoint),
            )
            ..headers.addAll(headers)
            ..body = body;

      final http.StreamedResponse response = await _httpClient.send(request);

      print(
        "[ChatService] streamChatResponse status code: ${response.statusCode}",
      );

      if (response.statusCode == 200) {
        // Handle different decoding based on platform due to potential browser issues with chunked responses.
        // On web, browsers might automatically handle SSE and provide full lines or decoded chunks.
        // For non-web, you might get raw bytes.
        // The backend is expected to send plain text chunks for simplicity here.
        // If it's text/event-stream with "data: " prefixes, parsing would be needed.

        await for (List<int> chunkBytes in response.stream) {
          final String decodedChunk = utf8.decode(chunkBytes);
          print("[ChatService] Decoded chunk: $decodedChunk");
          yield decodedChunk;
        }
        print("[ChatService] Stream finished for threadId: $threadId");
      } else {
        final errorBody = await response.stream.bytesToString();
        print(
          "[ChatService] Failed to stream chat response. Status: ${response.statusCode}, Body: $errorBody",
        );
        throw Exception(
          'Failed to stream chat response: ${response.statusCode} - $errorBody',
        );
      }
    } catch (e) {
      print("[ChatService] Error in streamChatResponse: ${e.toString()}");
      throw Exception('Error streaming chat: ${e.toString()}');
    }
  }
}
