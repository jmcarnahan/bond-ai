import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:collection/collection.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/providers/services/service_providers.dart'
    show threadServiceProvider;
import '../core/utils/logger.dart';

final threadErrorProvider = StateProvider<String?>((ref) => null);
final selectedThreadIdProvider = StateProvider<String?>((ref) => null);

class ThreadsNotifier extends StateNotifier<AsyncValue<List<Thread>>> {
  final Ref _ref;
  late final ThreadService _threadService;

  ThreadsNotifier(this._ref) : super(const AsyncValue.loading()) {
    _threadService = _ref.read(threadServiceProvider);
  }

  Future<void> fetchThreads() async {
    state = const AsyncValue.loading();
    try {
      final threads = await _threadService.getThreads();
      if (mounted) {
        // logger.d("[ThreadsNotifier] Fetched ${threads.length} threads");
        // if (threads.isNotEmpty) {
        //   logger.d("[ThreadsNotifier] First thread: ${threads[0].name} - Updated: ${threads[0].updatedAt}");
        //   logger.d("[ThreadsNotifier] Last thread: ${threads[threads.length - 1].name} - Updated: ${threads[threads.length - 1].updatedAt}");
        // }
        state = AsyncValue.data(threads);
      }
    } catch (e, stackTrace) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = AsyncValue.error(e, stackTrace);
      }
    }
  }

  Future<Thread?> addThread({String? name}) async {
    final previousState = state;

    try {
      final newThread = await _threadService.createThread(name: name);
      if (mounted) {
        final currentThreads = List<Thread>.from(
          previousState.asData?.value ?? [],
        );
        currentThreads.add(newThread);
        state = AsyncValue.data(currentThreads);
        
        // Automatically select the newly created thread
        selectThread(newThread.id);
      }
      return newThread;
    } catch (e) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = previousState;
      }

      logger.i('Error adding thread: $e');
      return null;
    }
  }

  Future<void> removeThread(String threadId) async {
    final previousState = state;

    final currentlySelectedId = _ref.read(selectedThreadIdProvider);
    if (currentlySelectedId == threadId) {
      deselectThread();
    }

    if (mounted && previousState.hasValue) {
      final currentThreads = List<Thread>.from(previousState.asData!.value);
      currentThreads.removeWhere((thread) => thread.id == threadId);
      state = AsyncValue.data(currentThreads);
    }

    try {
      await _threadService.deleteThread(threadId);
    } catch (e) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = previousState;
      }
      logger.i('Error removing thread: $e');
    }
  }

  void selectThread(String threadId) {
    _ref.read(selectedThreadIdProvider.notifier).state = threadId;
  }

  void deselectThread() {
    _ref.read(selectedThreadIdProvider.notifier).state = null;
  }
}

final threadsProvider =
    StateNotifierProvider<ThreadsNotifier, AsyncValue<List<Thread>>>((ref) {
  final notifier = ThreadsNotifier(ref);
  
  notifier.fetchThreads();
  
  return notifier;
});

final selectedThreadProvider = Provider<Thread?>((ref) {
  final selectedId = ref.watch(selectedThreadIdProvider);
  if (selectedId == null) {
    return null;
  }
  final threadsAsyncValue = ref.watch(threadsProvider);
  return threadsAsyncValue.whenOrNull(
    data: (threads) => threads.firstWhereOrNull((t) => t.id == selectedId),
    loading: () => null, 
    error: (_, __) => null,
  );
});
