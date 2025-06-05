import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'chat_session_state.dart';
import 'chat_session_notifier.dart';
import '../../core/utils/logger.dart';

final allThreadsProvider = FutureProvider<List<Thread>>((ref) async {
  logger.i("[allThreadsProvider] Fetching all threads...");
  final threadService = ref.watch(threadServiceProvider);
  try {
    final threads = await threadService.getThreads();
    logger.i(
      "[allThreadsProvider] Successfully fetched ${threads.length} threads.",
    );
    return threads;
  } catch (e) {
    logger.i("[allThreadsProvider] Error fetching all threads: ${e.toString()}");
    rethrow;
  }
});

final chatSessionNotifierProvider =
    StateNotifierProvider.autoDispose<ChatSessionNotifier, ChatSessionState>((
      ref,
    ) {
      final threadService = ref.watch(threadServiceProvider);
      final chatService = ref.watch(chatServiceProvider);
      final agentService = ref.watch(agentServiceProvider);
      return ChatSessionNotifier(threadService, chatService, agentService, ref);
    });
