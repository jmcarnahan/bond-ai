import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import '../../core/utils/logger.dart';

@immutable
class ThreadService {
  final http.Client _httpClient;
  final AuthService _authService;

  ThreadService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? http.Client(),
      _authService = authService;

  Future<List<Thread>> getThreads() async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse(ApiConstants.baseUrl + ApiConstants.threadsEndpoint),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<Thread> threads =
            data
                .map((item) => Thread.fromJson(item as Map<String, dynamic>))
                .toList();
        // logger.i("[ThreadService] Parsed ${threads.length} threads.");
        return threads;
      } else {
        logger.i(
          "[ThreadService] Failed to load threads. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to load threads: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[ThreadService] Error in getThreads: ${e.toString()}");
      throw Exception('Failed to fetch threads: ${e.toString()}');
    }
  }

  Future<Thread> createThread({String? name}) async {
    logger.i("[ThreadService] createThread called with name: $name");
    try {
      final headers = await _authService.authenticatedHeaders;
      final body = json.encode({'name': name});

      final response = await _httpClient.post(
        Uri.parse(ApiConstants.baseUrl + ApiConstants.threadsEndpoint),
        headers: headers,
        body: body,
      );

      if (response.statusCode == 201) {
        final Map<String, dynamic> data = json.decode(response.body);
        final Thread newThread = Thread.fromJson(data);
        logger.i(
          "[ThreadService] Created new thread: ${newThread.id} - ${newThread.name}",
        );
        return newThread;
      } else {
        logger.i(
          "[ThreadService] Failed to create thread. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to create thread: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[ThreadService] Error in createThread: ${e.toString()}");
      throw Exception('Failed to create thread: ${e.toString()}');
    }
  }

  Future<List<Message>> getMessagesForThread(
    String threadId, {
    int limit = 100,
  }) async {
    logger.i(
      "[ThreadService] getMessagesForThread called for threadId: $threadId, limit: $limit",
    );
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages?limit=$limit',
        ),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final List<Message> messages =
            data
                .map((item) => Message.fromJson(item as Map<String, dynamic>))
                .toList();
        logger.i(
          "[ThreadService] Parsed ${messages.length} messages for thread $threadId.",
        );
        for (final msg in messages) {
          logger.d(
            "[ThreadService] Message from API - ID: ${msg.id}, Agent: ${msg.agentId ?? 'none'}, Type: ${msg.type}, Role: ${msg.role}",
          );
        }
        return messages;
      } else {
        logger.i(
          "[ThreadService] Failed to load messages for thread $threadId. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to load messages for thread $threadId: ${response.statusCode}',
        );
      }
    } catch (e) {
      logger.i(
        "[ThreadService] Error in getMessagesForThread for thread $threadId: ${e.toString()}",
      );
      throw Exception(
        'Failed to fetch messages for thread $threadId: ${e.toString()}',
      );
    }
  }

  Future<void> deleteThread(String threadId) async {
    logger.i("[ThreadService] deleteThread called for threadId: $threadId");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.delete(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId',
        ),
        headers: headers,
      );

      if (response.statusCode == 204) {
        logger.i("[ThreadService] Deleted thread: $threadId");
        return;
      } else if (response.statusCode == 404) {
        logger.i(
          "[ThreadService] Failed to delete thread. Not Found. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Thread not found: ${response.statusCode}');
      } else {
        logger.i(
          "[ThreadService] Failed to delete thread. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception(
          'Failed to delete thread: ${response.statusCode}, Body: ${response.body}',
        );
      }
    } catch (e) {
      logger.i(
        "[ThreadService] Error in deleteThread for thread $threadId: ${e.toString()}",
      );
      throw Exception('Failed to delete thread $threadId: ${e.toString()}');
    }
  }
}
