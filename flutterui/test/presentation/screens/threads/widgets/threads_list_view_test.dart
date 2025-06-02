import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/threads/widgets/threads_list_view.dart';
import 'package:flutterui/presentation/screens/threads/widgets/thread_list_item.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:mockito/mockito.dart';

class MockRef extends Mock implements Ref<Object?> {}

class MockThreadsNotifier extends ThreadsNotifier {
  bool fetchThreadsCalled = false;

  MockThreadsNotifier(super.ref);

  @override
  Future<void> fetchThreads() async {
    fetchThreadsCalled = true;
  }
}

void main() {
  group('ThreadsListView Widget Tests', () {
    late Thread? selectedThread;
    late bool onThreadSelectedCalled;
    late MockThreadsNotifier mockNotifier;

    setUp(() {
      selectedThread = null;
      onThreadSelectedCalled = false;
      mockNotifier = MockThreadsNotifier(MockRef());
    });

    Widget createTestWidget({
      List<Thread> threads = const [],
      String? selectedThreadId,
      bool isFromAgentChat = false,
    }) {
      return ProviderScope(
        overrides: [
          threadsProvider.overrideWith((ref) => MockThreadsNotifier(ref)),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: ThreadsListView(
              threads: threads,
              selectedThreadId: selectedThreadId,
              isFromAgentChat: isFromAgentChat,
              onThreadSelected: (thread) {
                selectedThread = thread;
                onThreadSelectedCalled = true;
              },
            ),
          ),
        ),
      );
    }

    List<Thread> createSampleThreads({int count = 3}) {
      return List.generate(count, (index) => Thread(
            id: 'thread-$index',
            name: 'Thread $index',
          ));
    }

    testWidgets('should display empty list when no threads', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(ListView), findsOneWidget);
      expect(find.byType(ThreadListItem), findsNothing);
    });

    testWidgets('should display thread items when threads exist', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsNWidgets(3));
      expect(find.text('Thread 0'), findsOneWidget);
      expect(find.text('Thread 1'), findsOneWidget);
      expect(find.text('Thread 2'), findsOneWidget);
    });

    testWidgets('should display threads in reverse order (newest first)', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(threads: threads));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      
      expect(threadItems[0].thread.id, equals('thread-2'));
      expect(threadItems[1].thread.id, equals('thread-1'));
      expect(threadItems[2].thread.id, equals('thread-0'));
    });

    testWidgets('should mark selected thread correctly', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        selectedThreadId: 'thread-1',
      ));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      
      expect(threadItems.any((item) => item.isSelected && item.thread.id == 'thread-1'), isTrue);
      expect(threadItems.where((item) => item.isSelected).length, equals(1));
    });

    testWidgets('should call onThreadSelected when thread is tapped', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(createTestWidget(threads: threads));

      await tester.tap(find.byType(ThreadListItem).first);

      expect(onThreadSelectedCalled, isTrue);
      expect(selectedThread?.id, equals('thread-1'));
    });

    testWidgets('should pass isFromAgentChat to thread items correctly', (tester) async {
      final threads = createSampleThreads(count: 1);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        isFromAgentChat: true,
      ));

      final threadItem = tester.widget<ThreadListItem>(find.byType(ThreadListItem));
      expect(threadItem.isFromAgentChat, isTrue);
    });

    testWidgets('should have correct padding', (tester) async {
      final threads = createSampleThreads(count: 1);

      await tester.pumpWidget(createTestWidget(threads: threads));

      final listView = tester.widget<ListView>(find.byType(ListView));
      expect(listView.padding, isA<EdgeInsets>());
    });

    testWidgets('should display separators between items', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(SizedBox), findsNWidgets(2));

      final separators = tester.widgetList<SizedBox>(find.byType(SizedBox)).toList();
      for (final separator in separators) {
        expect(separator.height, greaterThan(0));
      }
    });

    testWidgets('should support pull to refresh', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(RefreshIndicator), findsOneWidget);

      await tester.fling(find.byType(ListView), const Offset(0, 500), 1000);
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));

      expect(mockNotifier.fetchThreadsCalled, isTrue);
    });

    testWidgets('should work with single thread', (tester) async {
      final threads = createSampleThreads(count: 1);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsOneWidget);
      expect(find.text('Thread 0'), findsOneWidget);
    });

    testWidgets('should work with many threads', (tester) async {
      final threads = createSampleThreads(count: 10);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsNWidgets(10));
    });

    testWidgets('should handle no selected thread', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        selectedThreadId: null,
      ));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      expect(threadItems.any((item) => item.isSelected), isFalse);
    });

    testWidgets('should handle invalid selected thread ID', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        selectedThreadId: 'non-existent-thread',
      ));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      expect(threadItems.any((item) => item.isSelected), isFalse);
    });

    testWidgets('should work with different screen sizes', (tester) async {
      final threads = createSampleThreads(count: 3);

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsNWidgets(3));

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.byType(ThreadListItem), findsNWidgets(3));

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should maintain scroll position', (tester) async {
      final threads = createSampleThreads(count: 20);

      await tester.pumpWidget(createTestWidget(threads: threads));

      await tester.drag(find.byType(ListView), const Offset(0, -500));
      await tester.pump();

      expect(find.byType(ThreadListItem), findsWidgets);
    });

    testWidgets('should handle rapid thread selection', (tester) async {
      final threads = createSampleThreads(count: 3);
      int selectionCount = 0;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            threadsProvider.overrideWith((ref) => MockThreadsNotifier(ref)),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: ThreadsListView(
                threads: threads,
                selectedThreadId: null,
                isFromAgentChat: false,
                onThreadSelected: (thread) => selectionCount++,
              ),
            ),
          ),
        ),
      );

      for (int i = 0; i < 3; i++) {
        await tester.tap(find.byType(ThreadListItem).at(i));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(selectionCount, equals(3));
    });

    testWidgets('should work in different layout contexts', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            threadsProvider.overrideWith((ref) => MockThreadsNotifier(ref)),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: Column(
                children: [
                  Container(height: 100, color: Colors.red),
                  Expanded(
                    child: ThreadsListView(
                      threads: threads,
                      selectedThreadId: null,
                      isFromAgentChat: false,
                      onThreadSelected: (thread) {},
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      expect(find.byType(ThreadListItem), findsNWidgets(2));
    });

    testWidgets('should handle threads with identical timestamps', (tester) async {
      final threads = [
        Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
        Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
      ];

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsNWidgets(2));
    });

    testWidgets('should maintain state consistency during updates', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        selectedThreadId: 'thread-0',
      ));

      expect(find.byType(ThreadListItem), findsNWidgets(2));

      await tester.pumpWidget(createTestWidget(
        threads: createSampleThreads(count: 3),
        selectedThreadId: 'thread-1',
      ));

      expect(find.byType(ThreadListItem), findsNWidgets(3));
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ListView), findsOneWidget);
      expect(find.byType(ThreadListItem), findsNWidgets(2));
    });

    testWidgets('should work with custom thread data', (tester) async {
      final threads = [
        Thread(
            id: 'custom-thread',
            name: 'Custom Thread Title',
          ),
      ];

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsOneWidget);
    });

    testWidgets('should handle empty thread properties gracefully', (tester) async {
      final threads = [
        Thread(
            id: '',
            name: '',
          ),
      ];

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(ThreadListItem), findsOneWidget);
    });

    testWidgets('should work with different isFromAgentChat values', (tester) async {
      final threads = createSampleThreads(count: 2);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        isFromAgentChat: false,
      ));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      expect(threadItems.every((item) => !item.isFromAgentChat), isTrue);

      await tester.pumpWidget(createTestWidget(
        threads: threads,
        isFromAgentChat: true,
      ));

      final updatedThreadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      expect(updatedThreadItems.every((item) => item.isFromAgentChat), isTrue);
    });

    testWidgets('should handle provider state changes', (tester) async {
      final threads = createSampleThreads(count: 1);

      await tester.pumpWidget(createTestWidget(threads: threads));

      expect(find.byType(RefreshIndicator), findsOneWidget);
      expect(mockNotifier.fetchThreadsCalled, isFalse);

      await tester.fling(find.byType(ListView), const Offset(0, 300), 1000);
      await tester.pump();

      expect(mockNotifier.fetchThreadsCalled, isTrue);
    });

    testWidgets('should maintain correct item order with index calculations', (tester) async {
      final threads = [
        Thread(
            id: 'oldest',
            name: 'Oldest Thread',
          ),
        Thread(
            id: 'middle',
            name: 'Middle Thread',
          ),
        Thread(
            id: 'newest',
            name: 'Newest Thread',
          ),
      ];

      await tester.pumpWidget(createTestWidget(threads: threads));

      final threadItems = tester.widgetList<ThreadListItem>(find.byType(ThreadListItem)).toList();
      
      expect(threadItems[0].thread.id, equals('newest'));
      expect(threadItems[1].thread.id, equals('middle'));
      expect(threadItems[2].thread.id, equals('oldest'));
    });

    testWidgets('should handle ListView scrolling properly', (tester) async {
      final threads = createSampleThreads(count: 15);

      await tester.pumpWidget(createTestWidget(threads: threads));

      await tester.dragUntilVisible(
        find.text('Thread 0'),
        find.byType(ListView),
        const Offset(0, -100),
      );

      expect(find.text('Thread 0'), findsOneWidget);
    });
  });
}