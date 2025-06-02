import 'dart:convert';

import 'package:flutter/foundation.dart' show immutable;
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:http/http.dart' as http;

import '../../core/utils/logger.dart';

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
    logger.i(
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

      logger.i(
        "[ChatService] streamChatResponse status code: ${response.statusCode}",
      );

      if (response.statusCode == 200) {
        await for (List<int> chunkBytes in response.stream) {
          final String decodedChunk = utf8.decode(chunkBytes);
          yield decodedChunk;
        }
        logger.i("[ChatService] Stream finished for threadId: $threadId");
      } else {
        final errorBody = await response.stream.bytesToString();
        logger.i(
          "[ChatService] Failed to stream chat response. Status: ${response.statusCode}, Body: $errorBody",
        );
        throw Exception(
          'Failed to stream chat response: ${response.statusCode} - $errorBody',
        );
      }
    } catch (e) {
      logger.i("[ChatService] Error in streamChatResponse: ${e.toString()}");
      throw Exception('Error streaming chat: ${e.toString()}');
    }
  }
}
