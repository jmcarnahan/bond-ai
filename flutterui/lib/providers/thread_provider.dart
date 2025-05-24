import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
// Import the existing threadServiceProvider from thread_chat_provider.dart
// to ensure we use the same ThreadService instance.
import 'package:flutterui/providers/thread_chat_provider.dart'
    show threadServiceProvider;

// This provider can be used to communicate errors from thread operations to the UI,
// for example, by showing a SnackBar.
final threadErrorProvider = StateProvider<String?>((ref) => null);

class ThreadsNotifier extends StateNotifier<AsyncValue<List<Thread>>> {
  final Ref _ref;
  // Use the ThreadService instance provided by threadServiceProvider
  late final ThreadService _threadService;

  ThreadsNotifier(this._ref) : super(const AsyncValue.loading()) {
    // Get the ThreadService instance from the existing provider
    _threadService = _ref.read(threadServiceProvider);
    fetchThreads();
  }

  Future<void> fetchThreads() async {
    state = const AsyncValue.loading();
    try {
      final threads = await _threadService.getThreads();
      if (mounted) {
        // Check if the notifier is still mounted before updating state
        state = AsyncValue.data(threads);
      }
    } catch (e, stackTrace) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = AsyncValue.error(e, stackTrace);
      }
    }
  }

  Future<void> addThread({String? name}) async {
    final previousState = state;
    // Optionally, show a specific loading state for adding
    // state = const AsyncValue.loading();
    // For simplicity, we'll update after success or revert on error.

    try {
      final newThread = await _threadService.createThread(name: name);
      if (mounted) {
        final currentThreads = List<Thread>.from(
          previousState.asData?.value ?? [],
        );
        currentThreads.add(newThread);
        state = AsyncValue.data(currentThreads);
        // No need to call fetchThreads() if server returns the created object
        // and local state is updated accurately.
      }
    } catch (e, stackTrace) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = previousState; // Revert to previous state on error
      }
      // Optionally re-throw or handle more gracefully, e.g. logging
      print('Error adding thread: $e');
    }
  }

  Future<void> removeThread(String threadId) async {
    final previousState = state;

    // Optimistically update the UI
    if (mounted && previousState.hasValue) {
      final currentThreads = List<Thread>.from(previousState.asData!.value);
      currentThreads.removeWhere((thread) => thread.id == threadId);
      state = AsyncValue.data(currentThreads);
    }

    try {
      await _threadService.deleteThread(threadId);
      // If delete is successful, state is already updated optimistically.
      // Optionally, call fetchThreads() to ensure full consistency if needed,
      // but optimistic update is usually fine.
      // e.g. await fetchThreads();
    } catch (e, stackTrace) {
      if (mounted) {
        _ref.read(threadErrorProvider.notifier).state = e.toString();
        state = previousState; // Revert to previous state on error
      }
      print('Error removing thread: $e');
    }
  }
}

final threadsProvider =
    StateNotifierProvider<ThreadsNotifier, AsyncValue<List<Thread>>>((ref) {
      return ThreadsNotifier(ref);
    });
