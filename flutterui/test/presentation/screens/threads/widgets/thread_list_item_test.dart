import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/presentation/screens/threads/widgets/thread_list_item.dart';
import 'package:flutterui/providers/thread_provider.dart';

class MockThreadsNotifier extends Mock implements ThreadsNotifier {}

void main() {
  group('ThreadListItem Widget Tests', () {
    late ProviderContainer container;
    late MockThreadsNotifier mockThreadsNotifier;
    late VoidCallback mockOnTap;

    const testThread = Thread(
      id: 'thread-123',
      name: 'Test Thread',
      description: 'Test Description',
    );

    setUp(() {
      mockThreadsNotifier = MockThreadsNotifier();
      mockOnTap = () {};
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should display thread with all information', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Thread'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
      expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    });

    testWidgets('should display unnamed thread when name is empty', (tester) async {
      const unnamedThread = Thread(
        id: 'thread-123',
        name: '',
        description: 'Test Description',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: unnamedThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Unnamed Thread'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
    });

    testWidgets('should not display subtitle when description is null', (tester) async {
      const threadNoDescription = Thread(
        id: 'thread-123',
        name: 'Test Thread',
        description: null,
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: threadNoDescription,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Thread'), findsOneWidget);
      expect(find.text('Test Description'), findsNothing);
    });

    testWidgets('should not display subtitle when description is empty', (tester) async {
      const threadEmptyDescription = Thread(
        id: 'thread-123',
        name: 'Test Thread',
        description: '',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: threadEmptyDescription,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Thread'), findsOneWidget);
      expect(find.text('Test Description'), findsNothing);
    });

    testWidgets('should show selected state styling', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: true,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.chat_bubble), findsOneWidget);
      expect(find.byIcon(Icons.chat_bubble_outline), findsNothing);

      final card = tester.widget<Card>(find.byType(Card));
      final shape = card.shape as RoundedRectangleBorder;
      expect(shape.side.width, equals(1.5));
    });

    testWidgets('should show unselected state styling', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
      expect(find.byIcon(Icons.chat_bubble), findsNothing);

      final card = tester.widget<Card>(find.byType(Card));
      final shape = card.shape as RoundedRectangleBorder;
      expect(shape.side.width, equals(0.5));
    });

    testWidgets('should not show delete button when from agent chat', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: true,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.delete_outline), findsNothing);
      expect(find.byType(IconButton), findsNothing);
    });

    testWidgets('should call onTap when tapped', (tester) async {
      bool tapped = false;
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: () => tapped = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(ListTile));
      expect(tapped, isTrue);
    });

    testWidgets('should show delete confirmation dialog', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      expect(find.text('Delete Thread?'), findsOneWidget);
      expect(find.text('Are you sure you want to delete "Test Thread"? This action cannot be undone.'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);
    });

    testWidgets('should cancel delete when cancel pressed', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Delete Thread?'), findsNothing);
      verifyZeroInteractions(mockThreadsNotifier);
    });

    testWidgets('should delete thread when confirmed', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.removeThread('thread-123')).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      verify(mockThreadsNotifier.removeThread('thread-123')).called(1);
    });

    testWidgets('should show error snackbar when delete fails', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.removeThread('thread-123')).thenThrow(Exception('Delete failed'));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('Failed to delete thread:'), findsOneWidget);
    });

    testWidgets('should handle unnamed thread in delete dialog', (tester) async {
      const unnamedThread = Thread(
        id: 'thread-123',
        name: '',
        description: 'Test Description',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: unnamedThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      expect(find.text('Are you sure you want to delete "this unnamed thread"? This action cannot be undone.'), findsOneWidget);
    });

    testWidgets('should handle long thread names with ellipsis', (tester) async {
      const longNameThread = Thread(
        id: 'thread-123',
        name: 'This is a very long thread name that should be truncated with ellipsis',
        description: 'Test Description',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 200,
                child: ThreadListItem(
                  thread: longNameThread,
                  isSelected: false,
                  isFromAgentChat: false,
                  onTap: mockOnTap,
                ),
              ),
            ),
          ),
        ),
      );

      final titleText = tester.widget<Text>(find.textContaining('This is a very long'));
      expect(titleText.maxLines, equals(1));
      expect(titleText.overflow, equals(TextOverflow.ellipsis));
    });

    testWidgets('should handle long descriptions with ellipsis', (tester) async {
      const longDescThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
        description: 'This is a very long description that should be truncated with ellipsis when displayed',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 200,
                child: ThreadListItem(
                  thread: longDescThread,
                  isSelected: false,
                  isFromAgentChat: false,
                  onTap: mockOnTap,
                ),
              ),
            ),
          ),
        ),
      );

      final subtitleText = tester.widget<Text>(find.textContaining('This is a very long description'));
      expect(subtitleText.maxLines, equals(1));
      expect(subtitleText.overflow, equals(TextOverflow.ellipsis));
    });

    testWidgets('should apply correct theme colors', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                primary: Colors.blue,
                onSurface: Colors.black,
                error: Colors.red,
              ),
            ),
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: true,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.chat_bubble));
      expect(icon.color, equals(Colors.blue));
    });

    testWidgets('should handle special characters in thread name', (tester) async {
      const specialThread = Thread(
        id: 'thread-123',
        name: 'Thread with émojis 🧵 and spëcial chars @#\$%',
        description: 'Description with unicode: café ☕',
      );

      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: specialThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Thread with émojis 🧵 and spëcial chars @#\$%'), findsOneWidget);
      expect(find.text('Description with unicode: café ☕'), findsOneWidget);
    });

    testWidgets('should maintain card structure and layout', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: ThreadListItem(
                thread: testThread,
                isSelected: false,
                isFromAgentChat: false,
                onTap: mockOnTap,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(Card), findsOneWidget);
      expect(find.byType(ListTile), findsOneWidget);
      
      final card = tester.widget<Card>(find.byType(Card));
      expect(card.shape, isA<RoundedRectangleBorder>());
      expect(card.elevation, greaterThan(0));
    });
  });
}