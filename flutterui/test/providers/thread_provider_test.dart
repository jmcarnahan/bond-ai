@TestOn('browser')
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart'
    show threadServiceProvider;

// ---------------------------------------------------------------------------
// Manual mock for ThreadService
// ---------------------------------------------------------------------------
class MockThreadService implements ThreadService {
  // Stubs – tests set these before exercising the notifier.
  Future<({List<Thread> threads, int total, bool hasMore})> Function({
    int offset,
    int limit,
    bool excludeEmpty,
  })? getThreadsStub;

  Future<Thread> Function(String threadId, String name)? updateThreadStub;
  Future<Thread> Function({String? name})? createThreadStub;
  Future<void> Function(String threadId)? deleteThreadStub;
  Future<int> Function()? cleanupEmptyThreadsStub;

  @override
  Future<({List<Thread> threads, int total, bool hasMore})> getThreads({
    int offset = 0,
    int limit = 20,
    bool excludeEmpty = true,
  }) {
    if (getThreadsStub != null) {
      return getThreadsStub!(
        offset: offset,
        limit: limit,
        excludeEmpty: excludeEmpty,
      );
    }
    return Future.value((threads: <Thread>[], total: 0, hasMore: false));
  }

  @override
  Future<Thread> updateThread(String threadId, String name) {
    if (updateThreadStub != null) return updateThreadStub!(threadId, name);
    throw UnimplementedError('updateThread not stubbed');
  }

  @override
  Future<Thread> createThread({String? name}) {
    if (createThreadStub != null) return createThreadStub!(name: name);
    throw UnimplementedError('createThread not stubbed');
  }

  @override
  Future<void> deleteThread(String threadId) {
    if (deleteThreadStub != null) return deleteThreadStub!(threadId);
    throw UnimplementedError('deleteThread not stubbed');
  }

  @override
  Future<int> cleanupEmptyThreads() {
    if (cleanupEmptyThreadsStub != null) return cleanupEmptyThreadsStub!();
    return Future.value(0);
  }

  // These are not used by ThreadsNotifier but required by the interface.
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
Thread _thread(String id, {String name = 'Thread', DateTime? createdAt}) {
  return Thread(
    id: id,
    name: name,
    createdAt: createdAt ?? DateTime(2025, 1, 1),
    updatedAt: createdAt ?? DateTime(2025, 1, 1),
  );
}

/// Creates a [ProviderContainer] with the given [MockThreadService] wired in,
/// and a [ThreadsNotifier] that does NOT auto-fetch (we control fetch manually).
({ProviderContainer container, ThreadsNotifier notifier, MockThreadService mock})
    _createNotifier({MockThreadService? mock}) {
  final mockService = mock ?? MockThreadService();

  // We need a provider that creates the notifier WITHOUT auto-calling
  // fetchThreads(). We override threadsProvider with a manual notifier.
  final container = ProviderContainer(
    overrides: [
      threadServiceProvider.overrideWithValue(mockService),
    ],
  );

  // Create the notifier via a manual StateNotifierProvider override.
  // But threadsProvider auto-calls fetchThreads(). To avoid that, we build
  // the notifier directly and manage it ourselves.
  final ref = container.read(threadServiceProvider);
  // We need a Ref – use the container to read the notifier from a custom provider.
  // Simplest: create the notifier through the real threadsProvider but stub getThreads.
  // Stubbing getThreads lets fetchThreads complete without hitting the network.
  mockService.getThreadsStub ??= ({
    int offset = 0,
    int limit = 20,
    bool excludeEmpty = true,
  }) async =>
      (threads: <Thread>[], total: 0, hasMore: false);

  // Reading threadsProvider triggers the constructor and fetchThreads().
  final notifier = container.read(threadsProvider.notifier);

  return (container: container, notifier: notifier, mock: mockService);
}

/// Wait for any pending microtasks (e.g. the auto-fetch in the constructor).
Future<void> _pumpEventQueue() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
void main() {
  group('ThreadsNotifier', () {
    // -----------------------------------------------------------------------
    // fetchThreads
    // -----------------------------------------------------------------------
    group('fetchThreads', () {
      test('populates state from service response', () async {
        final t1 = _thread('t1', name: 'First');
        final t2 = _thread('t2', name: 'Second');
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [t1, t2], total: 2, hasMore: false);

        await setup.notifier.fetchThreads();

        final state = setup.container.read(threadsProvider);
        expect(state.asData?.value, hasLength(2));
        expect(state.asData!.value[0].name, 'First');
        expect(state.asData!.value[1].name, 'Second');
        setup.container.dispose();
      });

      test('sets hasMore when more pages exist', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [_thread('t1')], total: 50, hasMore: true);

        await setup.notifier.fetchThreads();

        final hasMore = setup.container.read(hasMoreThreadsProvider);
        expect(hasMore, isTrue);
        setup.container.dispose();
      });

      test('re-adds ensured threads that backend filtered out', () async {
        final setup = _createNotifier();

        // First let the auto-fetch finish with some threads.
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [_thread('t1', name: 'Existing')], total: 1, hasMore: false);

        await setup.notifier.fetchThreads();

        // Now ensureThread adds a thread that the backend won't return.
        setup.notifier.ensureThread('intro-thread', name: 'New Conversation');

        // Simulate a refresh – backend still doesn't return intro-thread.
        await setup.notifier.fetchThreads();

        final state = setup.container.read(threadsProvider);
        final threads = state.asData!.value;
        expect(threads.any((t) => t.id == 'intro-thread'), isTrue,
            reason: 'Ensured thread should survive a fetchThreads refresh');
        expect(threads.firstWhere((t) => t.id == 'intro-thread').name,
            'New Conversation');
        setup.container.dispose();
      });

      test('does not duplicate ensured thread if backend returns it', () async {
        final setup = _createNotifier();
        setup.notifier.ensureThread('t1', name: 'Placeholder');

        // Backend now returns the same thread (user sent a message so it's no
        // longer empty).
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [_thread('t1', name: 'Real Name')], total: 1, hasMore: false);

        await setup.notifier.fetchThreads();

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.where((t) => t.id == 't1').length, 1,
            reason: 'Should not have duplicate entries for the same thread ID');
        // The backend version wins since it is in the fetched list.
        expect(threads.first.name, 'Real Name');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // loadMore
    // -----------------------------------------------------------------------
    group('loadMore', () {
      test('appends next page to existing threads', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async {
          if (offset == 0) {
            return (threads: [_thread('t1')], total: 2, hasMore: true);
          }
          return (threads: [_thread('t2')], total: 2, hasMore: false);
        };

        await setup.notifier.fetchThreads();
        await setup.notifier.loadMore();

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(2));
        expect(threads[0].id, 't1');
        expect(threads[1].id, 't2');
        setup.container.dispose();
      });

      test('does nothing when hasMore is false', () async {
        var callCount = 0;
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async {
          callCount++;
          return (threads: [_thread('t1')], total: 1, hasMore: false);
        };

        await setup.notifier.fetchThreads();
        callCount = 0; // reset after initial fetch
        await setup.notifier.loadMore();

        expect(callCount, 0, reason: 'Should not call getThreads when no more pages');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // renameThread
    // -----------------------------------------------------------------------
    group('renameThread', () {
      test('updates existing thread in local state', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Old Name')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();

        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );

        await setup.notifier.renameThread('t1', 'New Name');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.first.name, 'New Name');
        expect(threads.first.updatedAt, DateTime(2025, 6, 1));
        setup.container.dispose();
      });

      test('adds thread to list when not found (introduction flow race)',
          () async {
        final setup = _createNotifier();
        // Start with a list that does NOT contain the thread being renamed.
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('other', name: 'Other Thread')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();

        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );

        // Rename a thread that's NOT in the local list.
        await setup.notifier.renameThread('intro-thread', 'My Chat');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(2),
            reason: 'Should add the missing thread to the list');
        expect(threads.first.id, 'intro-thread',
            reason: 'New thread should be prepended');
        expect(threads.first.name, 'My Chat');
        setup.container.dispose();
      });

      test('propagates API errors', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [_thread('t1')], total: 1, hasMore: false);

        await setup.notifier.fetchThreads();

        setup.mock.updateThreadStub = (_, __) async =>
            throw Exception('Network error');

        expect(
          () => setup.notifier.renameThread('t1', 'New'),
          throwsA(isA<Exception>()),
        );
        setup.container.dispose();
      });

      test('does not modify state when API fails', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Original')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();

        setup.mock.updateThreadStub = (_, __) async =>
            throw Exception('fail');

        try {
          await setup.notifier.renameThread('t1', 'New');
        } catch (_) {}

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.first.name, 'Original',
            reason: 'State should be unchanged after API error');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // ensureThread
    // -----------------------------------------------------------------------
    group('ensureThread', () {
      test('adds placeholder when thread is missing from list', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();

        setup.notifier.ensureThread('new-id', name: 'My Thread');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(1));
        expect(threads.first.id, 'new-id');
        expect(threads.first.name, 'My Thread');
        setup.container.dispose();
      });

      test('uses "New Conversation" as default name', () async {
        final setup = _createNotifier();
        await _pumpEventQueue(); // let auto-fetch finish
        setup.notifier.ensureThread('new-id');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.first.name, 'New Conversation');
        setup.container.dispose();
      });

      test('does not duplicate if thread already exists', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Existing')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();
        setup.notifier.ensureThread('t1', name: 'Different');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(1));
        expect(threads.first.name, 'Existing',
            reason: 'Should not overwrite existing thread');
        setup.container.dispose();
      });

      test('deferred: added after fetchThreads when state was loading',
          () async {
        // Simulate the race condition: ensureThread is called while
        // fetchThreads is still in progress (state is loading).
        final fetchCompleter =
            Completer<({List<Thread> threads, int total, bool hasMore})>();

        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) =>
            fetchCompleter.future;

        // Start a fetch that won't complete yet.
        final fetchFuture = setup.notifier.fetchThreads();

        // While loading, ensureThread is called (simulating the introduction
        // stream completing before threads loaded).
        setup.notifier.ensureThread('intro-thread', name: 'New Conversation');

        // State is still loading, so ensureThread defers.
        expect(
          setup.container.read(threadsProvider) is AsyncLoading,
          isTrue,
        );

        // Now fetchThreads completes — backend doesn't return intro-thread.
        fetchCompleter.complete(
          (threads: [_thread('t1', name: 'Backend Thread')], total: 1, hasMore: false),
        );
        await fetchFuture;

        // The ensured thread should have been re-added after the fetch.
        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'intro-thread'), isTrue,
            reason:
                'Deferred ensureThread should be replayed after fetchThreads');
        expect(threads.any((t) => t.id == 't1'), isTrue);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // addThread
    // -----------------------------------------------------------------------
    group('addThread', () {
      test('appends new thread and selects it', () async {
        final setup = _createNotifier();
        await _pumpEventQueue();

        final newThread = _thread('new-1', name: 'Created');
        setup.mock.createThreadStub = ({String? name}) async => newThread;

        final result = await setup.notifier.addThread(name: 'Created');

        expect(result, isNotNull);
        expect(result!.id, 'new-1');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'new-1'), isTrue);

        final selectedId = setup.container.read(selectedThreadIdProvider);
        expect(selectedId, 'new-1');
        setup.container.dispose();
      });

      test('returns null and restores state on error', () async {
        final setup = _createNotifier();
        await _pumpEventQueue();

        setup.mock.createThreadStub = ({String? name}) async =>
            throw Exception('Create failed');

        final result = await setup.notifier.addThread(name: 'Will Fail');

        expect(result, isNull);
        final error = setup.container.read(threadErrorProvider);
        expect(error, isNotNull);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // removeThread
    // -----------------------------------------------------------------------
    group('removeThread', () {
      test('removes thread from state and deselects if selected', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1'), _thread('t2')],
              total: 2,
              hasMore: false
            );

        await setup.notifier.fetchThreads();
        setup.notifier.selectThread('t1');
        setup.mock.deleteThreadStub = (_) async {};

        await setup.notifier.removeThread('t1');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(1));
        expect(threads.first.id, 't2');

        final selectedId = setup.container.read(selectedThreadIdProvider);
        expect(selectedId, isNull);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // selectThread / deselectThread
    // -----------------------------------------------------------------------
    group('selectThread / deselectThread', () {
      test('selectThread sets selectedThreadIdProvider', () async {
        final setup = _createNotifier();
        await _pumpEventQueue();

        setup.notifier.selectThread('t1');
        expect(setup.container.read(selectedThreadIdProvider), 't1');
        setup.container.dispose();
      });

      test('deselectThread clears selectedThreadIdProvider', () async {
        final setup = _createNotifier();
        await _pumpEventQueue();

        setup.notifier.selectThread('t1');
        setup.notifier.deselectThread();
        expect(setup.container.read(selectedThreadIdProvider), isNull);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // selectedThreadProvider (derived)
    // -----------------------------------------------------------------------
    group('selectedThreadProvider', () {
      test('returns null when no thread is selected', () async {
        final setup = _createNotifier();
        await _pumpEventQueue();

        final selected = setup.container.read(selectedThreadProvider);
        expect(selected, isNull);
        setup.container.dispose();
      });

      test('returns the matching thread when selected', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Found')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();
        setup.notifier.selectThread('t1');

        final selected = setup.container.read(selectedThreadProvider);
        expect(selected, isNotNull);
        expect(selected!.name, 'Found');
        setup.container.dispose();
      });

      test('returns null when selected ID is not in the list', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: [_thread('t1')], total: 1, hasMore: false);

        await setup.notifier.fetchThreads();
        setup.notifier.selectThread('nonexistent');

        final selected = setup.container.read(selectedThreadProvider);
        expect(selected, isNull);
        setup.container.dispose();
      });

      test('updates when thread is renamed', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Before')],
              total: 1,
              hasMore: false
            );

        await setup.notifier.fetchThreads();
        setup.notifier.selectThread('t1');

        setup.mock.updateThreadStub = (id, name) async =>
            _thread(id, name: name);

        await setup.notifier.renameThread('t1', 'After');

        final selected = setup.container.read(selectedThreadProvider);
        expect(selected!.name, 'After');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // Integration: full introduction → rename flow
    // -----------------------------------------------------------------------
    group('introduction flow integration', () {
      test(
          'ensureThread + rename works even when thread was not in initial fetch',
          () async {
        final setup = _createNotifier();
        // Backend returns no threads (or the intro thread is excluded).
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();

        // Simulate the introduction flow: stream handler discovers a thread.
        setup.notifier.ensureThread('intro-1', name: 'New Conversation');
        setup.notifier.selectThread('intro-1');

        // User renames the thread.
        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );

        await setup.notifier.renameThread('intro-1', 'My Topic');

        // The selected thread should reflect the rename.
        final selected = setup.container.read(selectedThreadProvider);
        expect(selected, isNotNull);
        expect(selected!.name, 'My Topic');
        setup.container.dispose();
      });

      test(
          'rename works when ensureThread was deferred (race condition)',
          () async {
        // This is the exact scenario that was broken:
        // 1. fetchThreads starts (loading)
        // 2. Introduction stream completes → ensureThread called (deferred)
        // 3. fetchThreads completes → ensured thread added
        // 4. User renames → should update the ensured thread.

        final fetchCompleter =
            Completer<({List<Thread> threads, int total, bool hasMore})>();

        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) =>
            fetchCompleter.future;

        final fetchFuture = setup.notifier.fetchThreads();

        // Step 2: Introduction completes while still loading.
        setup.notifier.ensureThread('intro-1', name: 'New Conversation');

        // Step 3: fetchThreads completes with empty list.
        fetchCompleter.complete(
          (threads: <Thread>[], total: 0, hasMore: false),
        );
        await fetchFuture;

        // Verify intro thread was added.
        var threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'intro-1'), isTrue);

        // Step 4: User renames.
        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );

        await setup.notifier.renameThread('intro-1', 'Renamed Topic');

        threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.first.name, 'Renamed Topic');

        // Also check via selectedThreadProvider.
        setup.notifier.selectThread('intro-1');
        final selected = setup.container.read(selectedThreadProvider);
        expect(selected!.name, 'Renamed Topic');
        setup.container.dispose();
      });

      test(
          'rename adds thread when ensureThread never ran (neither deferred nor immediate)',
          () async {
        // Edge case: ensureThread was never called at all (e.g. the listener
        // didn't fire), but the user still has a thread ID from the chat
        // session and tries to rename. The rename should still work.

        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();

        // No ensureThread call — thread is completely unknown to the list.
        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );

        await setup.notifier.renameThread('ghost-thread', 'Named It');

        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(1));
        expect(threads.first.id, 'ghost-thread');
        expect(threads.first.name, 'Named It');
        setup.container.dispose();
      });

      test('rename preserves name on pull-to-refresh for ensured thread',
          () async {
        // Scenario: ensureThread → rename → refresh (backend still excludes thread).
        // The refresh should use the renamed name, not the original placeholder.
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();

        // Introduction flow adds the thread.
        setup.notifier.ensureThread('intro-1', name: 'New Conversation');

        // User renames.
        setup.mock.updateThreadStub = (id, name) async => Thread(
              id: id,
              name: name,
              createdAt: DateTime(2025, 1, 1),
              updatedAt: DateTime(2025, 6, 1),
            );
        await setup.notifier.renameThread('intro-1', 'Renamed Chat');

        // Pull-to-refresh — backend still doesn't return the thread.
        await setup.notifier.fetchThreads();

        final threads = setup.container.read(threadsProvider).asData!.value;
        final introThread = threads.firstWhere((t) => t.id == 'intro-1');
        expect(introThread.name, 'Renamed Chat',
            reason:
                'Refresh should use the renamed name, not the original placeholder');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // _ensuredThreads cleanup
    // -----------------------------------------------------------------------
    group('_ensuredThreads lifecycle', () {
      test('removeThread prevents ensured thread from reappearing on refresh',
          () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();

        // ensureThread adds a placeholder.
        setup.notifier.ensureThread('intro-1', name: 'Ghost Thread');
        var threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'intro-1'), isTrue);

        // User deletes the thread.
        setup.mock.deleteThreadStub = (_) async {};
        await setup.notifier.removeThread('intro-1');

        // Thread should be gone.
        threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'intro-1'), isFalse);

        // Refresh — the deleted thread should NOT reappear.
        await setup.notifier.fetchThreads();
        threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads.any((t) => t.id == 'intro-1'), isFalse,
            reason:
                'Deleted ensured thread must not reappear after refresh');
        setup.container.dispose();
      });

      test('fetchThreads cleans _ensuredThreads when backend returns the thread',
          () async {
        final setup = _createNotifier();

        // Start with empty list, ensure a thread.
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();
        setup.notifier.ensureThread('intro-1', name: 'New Conversation');

        // Now backend returns the thread (user sent a message).
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('intro-1', name: 'Backend Name')],
              total: 1,
              hasMore: false,
            );

        await setup.notifier.fetchThreads();

        final threads = setup.container.read(threadsProvider).asData!.value;
        // Should not have duplicates.
        expect(threads.where((t) => t.id == 'intro-1').length, 1);
        // Backend version should win.
        expect(threads.first.name, 'Backend Name');

        // After another refresh with empty backend, the thread should NOT
        // reappear since it was cleaned from _ensuredThreads.
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (threads: <Thread>[], total: 0, hasMore: false);

        await setup.notifier.fetchThreads();
        final threadsAfter = setup.container.read(threadsProvider).asData!.value;
        expect(threadsAfter.any((t) => t.id == 'intro-1'), isFalse,
            reason:
                'Thread should no longer be ensured after backend returned it');
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // Error handling edge cases
    // -----------------------------------------------------------------------
    group('error handling', () {
      test('fetchThreads error sets threadErrorProvider and AsyncValue.error',
          () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            throw Exception('Network failure');

        await setup.notifier.fetchThreads();

        final state = setup.container.read(threadsProvider);
        expect(state is AsyncError, isTrue,
            reason: 'State should be AsyncError after fetch failure');

        final error = setup.container.read(threadErrorProvider);
        expect(error, isNotNull);
        expect(error, contains('Network failure'));
        setup.container.dispose();
      });

      test('removeThread rolls back state on API failure', () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1', name: 'Thread 1'), _thread('t2', name: 'Thread 2')],
              total: 2,
              hasMore: false
            );

        await setup.notifier.fetchThreads();

        // Delete will fail.
        setup.mock.deleteThreadStub =
            (_) async => throw Exception('Delete failed');

        await setup.notifier.removeThread('t1');

        // State should be rolled back to include both threads.
        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(2),
            reason: 'State should roll back on API failure');
        expect(threads.any((t) => t.id == 't1'), isTrue);

        final error = setup.container.read(threadErrorProvider);
        expect(error, isNotNull);
        setup.container.dispose();
      });

      test('removeThread does not deselect when removing a different thread',
          () async {
        final setup = _createNotifier();
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async =>
            (
              threads: [_thread('t1'), _thread('t2')],
              total: 2,
              hasMore: false
            );

        await setup.notifier.fetchThreads();
        setup.notifier.selectThread('t1');
        setup.mock.deleteThreadStub = (_) async {};

        // Remove t2, NOT the selected thread.
        await setup.notifier.removeThread('t2');

        final selectedId = setup.container.read(selectedThreadIdProvider);
        expect(selectedId, 't1',
            reason:
                'Removing a non-selected thread should not change selection');
        setup.container.dispose();
      });

      test('loadMore error does not corrupt state', () async {
        final setup = _createNotifier();
        var callCount = 0;
        setup.mock.getThreadsStub = ({
          int offset = 0,
          int limit = 20,
          bool excludeEmpty = true,
        }) async {
          callCount++;
          if (callCount == 1) {
            return (threads: [_thread('t1')], total: 50, hasMore: true);
          }
          throw Exception('Page 2 failed');
        };

        await setup.notifier.fetchThreads();
        await setup.notifier.loadMore();

        // State should still have the first page intact.
        final threads = setup.container.read(threadsProvider).asData!.value;
        expect(threads, hasLength(1));
        expect(threads.first.id, 't1');

        // isLoadingMore should be reset.
        final isLoading = setup.container.read(isLoadingMoreThreadsProvider);
        expect(isLoading, isFalse);
        setup.container.dispose();
      });
    });
  });
}
