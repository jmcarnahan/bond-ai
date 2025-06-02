import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/models/message_model.dart';

// ignore: must_be_immutable
class MockThreadService implements ThreadService {
  List<Thread> mockThreads = [];
  bool shouldThrowError = false;
  String? errorMessage;
  bool getThreadsCalled = false;
  bool createThreadCalled = false;
  bool deleteThreadCalled = false;
  String? lastCreatedThreadName;
  String? lastDeletedThreadId;

  @override
  Future<List<Thread>> getThreads() async {
    getThreadsCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get threads error');
    }
    return mockThreads;
  }

  @override
  Future<Thread> createThread({String? name}) async {
    createThreadCalled = true;
    lastCreatedThreadName = name;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock create thread error');
    }
    final newThread = Thread(
            id: 'new-thread-${mockThreads.length}',
            name: name ?? 'New Thread',
          );
    mockThreads.add(newThread);
    return newThread;
  }

  @override
  Future<void> deleteThread(String threadId) async {
    deleteThreadCalled = true;
    lastDeletedThreadId = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete thread error');
    }
    mockThreads.removeWhere((thread) => thread.id == threadId);
  }

  @override
  Future<List<Message>> getMessagesForThread(String threadId, {int limit = 50}) async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get messages error');
    }
    return [];
  }
}

void main() {
  group('Thread Provider Tests', () {
    late MockThreadService mockThreadService;
    late ProviderContainer container;

    setUp(() {
      mockThreadService = MockThreadService();
      container = ProviderContainer(
        overrides: [
          threadServiceProvider.overrideWithValue(mockThreadService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('threadErrorProvider', () {
      test('should start with null error', () {
        final error = container.read(threadErrorProvider);
        expect(error, isNull);
      });

      test('should update error state', () {
        const testError = 'Test error message';
        container.read(threadErrorProvider.notifier).state = testError;
        
        final error = container.read(threadErrorProvider);
        expect(error, equals(testError));
      });

      test('should clear error state', () {
        container.read(threadErrorProvider.notifier).state = 'Error';
        container.read(threadErrorProvider.notifier).state = null;
        
        final error = container.read(threadErrorProvider);
        expect(error, isNull);
      });
    });

    group('selectedThreadIdProvider', () {
      test('should start with null selected thread ID', () {
        final selectedId = container.read(selectedThreadIdProvider);
        expect(selectedId, isNull);
      });

      test('should update selected thread ID', () {
        const testId = 'test-thread-id';
        container.read(selectedThreadIdProvider.notifier).state = testId;
        
        final selectedId = container.read(selectedThreadIdProvider);
        expect(selectedId, equals(testId));
      });

      test('should clear selected thread ID', () {
        container.read(selectedThreadIdProvider.notifier).state = 'thread-id';
        container.read(selectedThreadIdProvider.notifier).state = null;
        
        final selectedId = container.read(selectedThreadIdProvider);
        expect(selectedId, isNull);
      });
    });

    group('ThreadsNotifier', () {
      test('should start with loading state', () {
        final state = container.read(threadsProvider);
        expect(state, isA<AsyncLoading>());
      });

      test('should fetch threads successfully', () async {
        final testThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, equals(testThreads));
        expect(data.value, hasLength(2));
        expect(mockThreadService.getThreadsCalled, isTrue);
      });

      test('should handle fetch threads error', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Network error';

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncError>());
        final error = state as AsyncError;
        expect(error.error.toString(), contains('Network error'));
        
        final errorState = container.read(threadErrorProvider);
        expect(errorState, contains('Network error'));
      });

      test('should add thread successfully', () async {
        final initialThreads = [
          Thread(
            id: 'existing-thread',
            name: 'Existing Thread',
          ),
        ];
        mockThreadService.mockThreads = initialThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        await notifier.addThread(name: 'New Thread');

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, hasLength(2));
        expect(data.value.last.name, equals('New Thread'));
        expect(mockThreadService.createThreadCalled, isTrue);
        expect(mockThreadService.lastCreatedThreadName, equals('New Thread'));
      });

      test('should add thread with null name', () async {
        mockThreadService.mockThreads = [];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        await notifier.addThread();

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, hasLength(1));
        expect(mockThreadService.createThreadCalled, isTrue);
        expect(mockThreadService.lastCreatedThreadName, isNull);
      });

      test('should handle add thread error', () async {
        mockThreadService.mockThreads = [];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Create failed';

        await notifier.addThread(name: 'Failed Thread');

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, isEmpty);
        
        final errorState = container.read(threadErrorProvider);
        expect(errorState, contains('Create failed'));
      });

      test('should remove thread successfully', () async {
        final initialThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
        ];
        mockThreadService.mockThreads = List.from(initialThreads);

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        await notifier.removeThread('thread-1');

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, hasLength(1));
        expect(data.value.first.id, equals('thread-2'));
        expect(mockThreadService.deleteThreadCalled, isTrue);
        expect(mockThreadService.lastDeletedThreadId, equals('thread-1'));
      });

      test('should deselect thread when removing selected thread', () async {
        final initialThreads = [
          Thread(
            id: 'selected-thread',
            name: 'Selected Thread',
          ),
        ];
        mockThreadService.mockThreads = List.from(initialThreads);

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        notifier.selectThread('selected-thread');
        expect(container.read(selectedThreadIdProvider), equals('selected-thread'));

        await notifier.removeThread('selected-thread');

        expect(container.read(selectedThreadIdProvider), isNull);
      });

      test('should handle remove thread error', () async {
        final initialThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
        ];
        mockThreadService.mockThreads = List.from(initialThreads);

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Delete failed';

        await notifier.removeThread('thread-1');

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, hasLength(1));
        
        final errorState = container.read(threadErrorProvider);
        expect(errorState, contains('Delete failed'));
      });

      test('should select thread correctly', () {
        final notifier = container.read(threadsProvider.notifier);

        notifier.selectThread('test-thread-id');

        final selectedId = container.read(selectedThreadIdProvider);
        expect(selectedId, equals('test-thread-id'));
      });

      test('should deselect thread correctly', () {
        final notifier = container.read(threadsProvider.notifier);

        notifier.selectThread('test-thread-id');
        notifier.deselectThread();

        final selectedId = container.read(selectedThreadIdProvider);
        expect(selectedId, isNull);
      });

      test('should handle multiple selections', () {
        final notifier = container.read(threadsProvider.notifier);

        notifier.selectThread('thread-1');
        expect(container.read(selectedThreadIdProvider), equals('thread-1'));

        notifier.selectThread('thread-2');
        expect(container.read(selectedThreadIdProvider), equals('thread-2'));
      });

      test('should handle empty thread list operations', () async {
        mockThreadService.mockThreads = [];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, isEmpty);

        await notifier.removeThread('non-existent-thread');
        expect(data.value, isEmpty);
      });

      test('should handle special characters in thread operations', () async {
        const specialName = 'Thread with émojis 🚀 and spëcial chars';
        mockThreadService.mockThreads = [];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        await notifier.addThread(name: specialName);

        expect(mockThreadService.lastCreatedThreadName, equals(specialName));
      });
    });

    group('threadsProvider', () {
      test('should create ThreadsNotifier and fetch threads automatically', () async {
        final testThreads = [
          Thread(
            id: 'auto-thread',
            name: 'Auto Thread',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        await Future.delayed(const Duration(milliseconds: 100));

        final notifier = container.read(threadsProvider.notifier);
        expect(notifier, isA<ThreadsNotifier>());
        expect(mockThreadService.getThreadsCalled, isTrue);
      });

      test('should provide access to threads state', () async {
        final testThreads = [
          Thread(
            id: 'provider-thread',
            name: 'Provider Thread',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final state = container.read(threadsProvider);
        expect(state, isA<AsyncData>());
        final data = state as AsyncData<List<Thread>>;
        expect(data.value, equals(testThreads));
      });

      test('should handle provider refresh', () async {
        final initialThreads = [
          Thread(
            id: 'initial-thread',
            name: 'Initial Thread',
          ),
        ];
        mockThreadService.mockThreads = initialThreads;

        final initialNotifier = container.read(threadsProvider.notifier);
        await initialNotifier.fetchThreads();

        container.invalidate(threadsProvider);

        final newNotifier = container.read(threadsProvider.notifier);
        expect(newNotifier, isNot(same(initialNotifier)));
      });
    });

    group('selectedThreadProvider', () {
      test('should return null when no thread is selected', () {
        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread, isNull);
      });

      test('should return null when threads are loading', () {
        container.read(selectedThreadIdProvider.notifier).state = 'thread-1';

        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread, isNull);
      });

      test('should return correct thread when selected', () async {
        final testThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        container.read(selectedThreadIdProvider.notifier).state = 'thread-2';

        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread, isNotNull);
        expect(selectedThread?.id, equals('thread-2'));
        expect(selectedThread?.name, equals('Thread 2'));
      });

      test('should return null for non-existent thread ID', () async {
        final testThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        container.read(selectedThreadIdProvider.notifier).state = 'non-existent-thread';

        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread, isNull);
      });

      test('should return null when threads are in error state', () async {
        mockThreadService.shouldThrowError = true;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        container.read(selectedThreadIdProvider.notifier).state = 'thread-1';

        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread, isNull);
      });

      test('should update when selected thread ID changes', () async {
        final testThreads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        container.read(selectedThreadIdProvider.notifier).state = 'thread-1';
        final firstSelection = container.read(selectedThreadProvider);
        expect(firstSelection?.id, equals('thread-1'));

        container.read(selectedThreadIdProvider.notifier).state = 'thread-2';
        final secondSelection = container.read(selectedThreadProvider);
        expect(secondSelection?.id, equals('thread-2'));
      });
    });

    group('Provider Integration', () {
      test('should work together for complete thread workflow', () async {
        final initialThreads = [
          Thread(
            id: 'workflow-thread',
            name: 'Workflow Thread',
          ),
        ];
        mockThreadService.mockThreads = initialThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final threads = container.read(threadsProvider);
        expect(threads, isA<AsyncData>());

        notifier.selectThread('workflow-thread');
        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread?.id, equals('workflow-thread'));

        await notifier.addThread(name: 'New Workflow Thread');
        final updatedThreads = container.read(threadsProvider);
        final data = updatedThreads as AsyncData<List<Thread>>;
        expect(data.value, hasLength(2));

        await notifier.removeThread('workflow-thread');
        final finalThreads = container.read(threadsProvider);
        final finalData = finalThreads as AsyncData<List<Thread>>;
        expect(finalData.value, hasLength(1));

        final finalSelectedThread = container.read(selectedThreadProvider);
        expect(finalSelectedThread, isNull);
      });

      test('should handle error propagation correctly', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Service unavailable';

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final threadsState = container.read(threadsProvider);
        expect(threadsState, isA<AsyncError>());

        final errorState = container.read(threadErrorProvider);
        expect(errorState, contains('Service unavailable'));
      });

      test('should maintain consistency across provider operations', () async {
        final testThreads = [
          Thread(
            id: 'consistency-thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'consistency-thread-2',
            name: 'Thread 2',
          ),
        ];
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        notifier.selectThread('consistency-thread-1');
        
        final threadsCount = (container.read(threadsProvider) as AsyncData<List<Thread>>).value.length;
        final selectedThread = container.read(selectedThreadProvider);
        final selectedId = container.read(selectedThreadIdProvider);

        expect(threadsCount, equals(2));
        expect(selectedThread?.id, equals('consistency-thread-1'));
        expect(selectedId, equals('consistency-thread-1'));
      });
    });

    group('Edge Cases', () {
      test('should handle concurrent operations gracefully', () async {
        mockThreadService.mockThreads = [];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final futures = <Future>[];
        for (int i = 0; i < 5; i++) {
          futures.add(notifier.addThread(name: 'Concurrent Thread $i'));
        }

        await Future.wait(futures);

        final threads = container.read(threadsProvider);
        final data = threads as AsyncData<List<Thread>>;
        expect(data.value.length, greaterThanOrEqualTo(1));
      });

      test('should handle rapid selection changes', () async {
        final testThreads = List.generate(10, (index) => Thread(
            id: 'rapid-thread-$index',
            name: 'Thread $index',
          ));
        mockThreadService.mockThreads = testThreads;

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        for (int i = 0; i < 10; i++) {
          notifier.selectThread('rapid-thread-$i');
        }

        final selectedThread = container.read(selectedThreadProvider);
        expect(selectedThread?.id, equals('rapid-thread-9'));
      });

      test('should handle thread with special properties', () async {
        final specialThread = Thread(
            id: '',
            name: '',
          );
        mockThreadService.mockThreads = [specialThread];

        final notifier = container.read(threadsProvider.notifier);
        await notifier.fetchThreads();

        final threads = container.read(threadsProvider);
        final data = threads as AsyncData<List<Thread>>;
        expect(data.value, hasLength(1));
        expect(data.value.first.id, equals(''));
      });
    });
  });
}