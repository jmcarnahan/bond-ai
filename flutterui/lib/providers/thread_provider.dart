import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:collection/collection.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/providers/services/service_providers.dart'
    show threadServiceProvider;
import '../core/utils/logger.dart';

final threadErrorProvider = StateProvider<String?>((ref) => null);
final selectedThreadIdProvider = StateProvider<String?>((ref) => null);
final hasMoreThreadsProvider = StateProvider<bool>((ref) => false);
final isLoadingMoreThreadsProvider = StateProvider<bool>((ref) => false);

class ThreadsNotifier extends StateNotifier<AsyncValue<List<Thread>>> {
  final Ref _ref;
  late final ThreadService _threadService;

  int _currentOffset = 0;
  bool _hasMore = false;
  bool _isLoadingMore = false;
  final int _pageSize = 20;
  // Thread IDs that must be present in the list even if the backend
  // filters them out (e.g., newly created threads with no user messages).
  final Map<String, String> _ensuredThreads = {};

  ThreadsNotifier(this._ref) : super(const AsyncValue.loading()) {
    _threadService = _ref.read(threadServiceProvider);
  }

  Future<void> fetchThreads() async {
    state = const AsyncValue.loading();
    _currentOffset = 0;
    try {
      // Fire-and-forget cleanup of empty threads
      _threadService.cleanupEmptyThreads().catchError((e) {
        logger.d("[ThreadsNotifier] Background cleanup error (non-critical): $e");
        return 0;
      });

      final result = await _threadService.getThreads(
        offset: 0,
        limit: _pageSize,
      );
      _hasMore = result.hasMore;
      _currentOffset = result.threads.length;
      if (mounted) {
        // After loading, reconcile _ensuredThreads with the backend response.
        final threads = List<Thread>.from(result.threads);
        final idsToRemove = <String>[];
        for (final entry in _ensuredThreads.entries) {
          if (threads.any((t) => t.id == entry.key)) {
            // Backend now returns this thread — no longer needs special treatment.
            idsToRemove.add(entry.key);
          } else {
            threads.insert(0, Thread(
              id: entry.key,
              name: entry.value,
              createdAt: DateTime.now(),
              updatedAt: DateTime.now(),
            ));
          }
        }
        for (final id in idsToRemove) {
          _ensuredThreads.remove(id);
        }
        state = AsyncValue.data(threads);
        _ref.read(hasMoreThreadsProvider.notifier).state = _hasMore;
      }
    } catch (e, stackTrace) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = AsyncValue.error(e, stackTrace);
      }
    }
  }

  Future<void> loadMore() async {
    if (_isLoadingMore || !_hasMore) return;
    _isLoadingMore = true;
    if (mounted) {
      _ref.read(isLoadingMoreThreadsProvider.notifier).state = true;
    }

    try {
      final result = await _threadService.getThreads(
        offset: _currentOffset,
        limit: _pageSize,
      );
      _hasMore = result.hasMore;
      _currentOffset += result.threads.length;
      if (mounted) {
        final currentThreads = List<Thread>.from(
          state.asData?.value ?? [],
        );
        currentThreads.addAll(result.threads);
        state = AsyncValue.data(currentThreads);
        _ref.read(hasMoreThreadsProvider.notifier).state = _hasMore;
      }
    } catch (e) {
      logger.i('[ThreadsNotifier] Error loading more threads: $e');
    } finally {
      _isLoadingMore = false;
      if (mounted) {
        _ref.read(isLoadingMoreThreadsProvider.notifier).state = false;
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

    // Remove from ensured threads so it doesn't reappear on refresh.
    _ensuredThreads.remove(threadId);

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

  Future<void> renameThread(String threadId, String newName) async {
    try {
      final updated = await _threadService.updateThread(threadId, newName);
      if (mounted && state.hasValue) {
        // Keep _ensuredThreads name in sync so pull-to-refresh preserves rename.
        if (_ensuredThreads.containsKey(threadId)) {
          _ensuredThreads[threadId] = updated.name;
        }
        final currentThreads = state.asData!.value;
        final found = currentThreads.any((t) => t.id == threadId);
        if (found) {
          // Update existing thread in list
          final updatedList = currentThreads.map((t) {
            return t.id == threadId
                ? t.copyWith(name: updated.name, updatedAt: updated.updatedAt)
                : t;
          }).toList();
          state = AsyncValue.data(updatedList);
        } else {
          // Thread not in local list (e.g., created during introduction flow
          // before fetchThreads completed). Add it from the API response.
          state = AsyncValue.data([updated, ...currentThreads]);
        }
      }
    } catch (e) {
      logger.i('Error renaming thread: $e');
      rethrow;
    }
  }

  /// Ensure a thread exists in the local state. If it doesn't, add a
  /// placeholder so that providers like [selectedThreadProvider] can find it.
  /// This is needed when the backend creates a thread during the introduction
  /// flow — the chat session discovers the thread ID from the stream but the
  /// thread never gets added to [threadsProvider].
  ///
  /// The thread ID is also recorded so that [fetchThreads] can re-add it
  /// after a refresh (the backend's exclude_empty filter may omit it).
  void ensureThread(String threadId, {String? name}) {
    if (!mounted) return;
    final threadName = name ?? 'New Conversation';
    _ensuredThreads[threadId] = threadName;
    if (!state.hasValue) return; // Will be added when fetchThreads completes
    final exists = state.asData!.value.any((t) => t.id == threadId);
    if (!exists) {
      final placeholder = Thread(
        id: threadId,
        name: threadName,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
      state = AsyncValue.data([placeholder, ...state.asData!.value]);
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
