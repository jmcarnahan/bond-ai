import 'dart:convert';
import 'package:flutter/foundation.dart' show immutable;
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/web_http_client.dart' as web_client;
import '../../core/utils/logger.dart';

@immutable
class ThreadService {
  final http.Client _httpClient;
  final AuthService _authService;

  ThreadService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? web_client.createHttpClient(),
      _authService = authService;

  Future<({List<Thread> threads, int total, bool hasMore})> getThreads({
    int offset = 0,
    int limit = 20,
    bool excludeEmpty = true,
  }) async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final uri = Uri.parse(
        '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}?offset=$offset&limit=$limit&exclude_empty=$excludeEmpty',
      );
      final response = await _httpClient.get(uri, headers: headers);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final List<dynamic> threadsList = data['threads'];
        final List<Thread> threads =
            threadsList
                .map((item) => Thread.fromJson(item as Map<String, dynamic>))
                .toList();
        return (
          threads: threads,
          total: data['total'] as int,
          hasMore: data['has_more'] as bool,
        );
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

  Future<Thread> updateThread(String threadId, String name) async {
    logger.i("[ThreadService] updateThread called for threadId: $threadId, name: $name");
    try {
      final headers = await _authService.authenticatedHeaders;
      final body = json.encode({'name': name});
      final response = await _httpClient.put(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId',
        ),
        headers: headers,
        body: body,
      );

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final Thread updated = Thread.fromJson(data);
        logger.i("[ThreadService] Updated thread: ${updated.id} - ${updated.name}");
        return updated;
      } else {
        logger.i(
          "[ThreadService] Failed to update thread. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to update thread: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[ThreadService] Error in updateThread: ${e.toString()}");
      throw Exception('Failed to update thread: ${e.toString()}');
    }
  }

  Future<int> cleanupEmptyThreads() async {
    logger.i("[ThreadService] cleanupEmptyThreads called");
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.post(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/cleanup',
        ),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final deleted = data['deleted'] as int;
        logger.i("[ThreadService] Cleaned up $deleted empty threads");
        return deleted;
      } else {
        logger.i(
          "[ThreadService] Failed to cleanup threads. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to cleanup threads: ${response.statusCode}');
      }
    } catch (e) {
      logger.i("[ThreadService] Error in cleanupEmptyThreads: ${e.toString()}");
      throw Exception('Failed to cleanup threads: ${e.toString()}');
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

  Future<void> submitFeedback(
    String threadId,
    String messageId,
    String feedbackType,
    String? feedbackMessage,
  ) async {
    logger.i(
      "[ThreadService] submitFeedback called for message $messageId: $feedbackType",
    );
    try {
      final headers = await _authService.authenticatedHeaders;
      final body = json.encode({
        'feedback_type': feedbackType,
        'feedback_message': feedbackMessage,
      });

      final response = await _httpClient.put(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages/$messageId/feedback',
        ),
        headers: headers,
        body: body,
      );

      if (response.statusCode == 200) {
        logger.i(
          "[ThreadService] Submitted feedback for message $messageId: $feedbackType",
        );
        return;
      } else {
        logger.e(
          "[ThreadService] Failed to submit feedback. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to submit feedback: ${response.statusCode}');
      }
    } catch (e) {
      logger.e(
        "[ThreadService] Error in submitFeedback for message $messageId: ${e.toString()}",
      );
      throw Exception('Failed to submit feedback: ${e.toString()}');
    }
  }

  Future<void> deleteFeedback(String threadId, String messageId) async {
    logger.i(
      "[ThreadService] deleteFeedback called for message $messageId",
    );
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.delete(
        Uri.parse(
          '${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}/$threadId/messages/$messageId/feedback',
        ),
        headers: headers,
      );

      if (response.statusCode == 204) {
        logger.i("[ThreadService] Deleted feedback for message $messageId");
        return;
      } else {
        logger.e(
          "[ThreadService] Failed to delete feedback. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to delete feedback: ${response.statusCode}');
      }
    } catch (e) {
      logger.e(
        "[ThreadService] Error in deleteFeedback for message $messageId: ${e.toString()}",
      );
      throw Exception('Failed to delete feedback: ${e.toString()}');
    }
  }
}
