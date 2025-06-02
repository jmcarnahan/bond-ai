import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/presentation/widgets/selected_thread_banner.dart';
import 'package:flutterui/providers/thread_provider.dart';

class MockThreadsNotifier extends Mock implements ThreadsNotifier {}

void main() {
  group('SelectedThreadBanner Widget Tests', () {
    late ProviderContainer container;
    late MockThreadsNotifier mockThreadsNotifier;

    setUp(() {
      mockThreadsNotifier = MockThreadsNotifier();
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should not display when no thread is selected', (tester) async {
      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => null),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.byType(SelectedThreadBanner), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.text('Active Thread:'), findsNothing);
    });

    testWidgets('should display thread name when thread is selected', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.text('Active Thread: Test Thread'), findsOneWidget);
      expect(find.byIcon(Icons.close), findsOneWidget);
      expect(find.byType(Material), findsOneWidget);
    });

    testWidgets('should display thread ID when thread name is empty', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: '',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.text('Active Thread: Thread ID: thread-123'), findsOneWidget);
      expect(find.byIcon(Icons.close), findsOneWidget);
    });

    testWidgets('should call deselectThread when close icon is tapped', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.close));
      await tester.pump();

      verify(mockThreadsNotifier.deselectThread()).called(1);
    });

    testWidgets('should have correct styling and layout', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      final material = tester.widget<Material>(find.byType(Material));
      expect(material.elevation, equals(4.0));

      final containerWidget = tester.widget<Container>(find.byType(Container).first);
      expect(containerWidget.padding, equals(const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0)));
      expect(containerWidget.constraints?.minHeight, equals(50));

      final color = containerWidget.color!;
      expect(color.r, equals(Colors.green.r));
      expect(color.g, equals(Colors.green.g));
      expect(color.b, equals(Colors.green.b));
    });

    testWidgets('should handle long thread names with ellipsis', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'This is a very long thread name that should be truncated with ellipsis when displayed in the banner',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 300,
                child: SelectedThreadBanner(),
              ),
            ),
          ),
        ),
      );

      final textWidget = tester.widget<Text>(find.textContaining('Active Thread:'));
      expect(textWidget.overflow, equals(TextOverflow.ellipsis));
      expect(textWidget.maxLines, equals(1));
    });

    testWidgets('should have correct text styling', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      final textWidget = tester.widget<Text>(find.text('Active Thread: Test Thread'));
      expect(textWidget.style?.color, equals(Colors.white));
      expect(textWidget.style?.fontWeight, equals(FontWeight.bold));
    });

    testWidgets('should center content properly', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      final centerWidget = tester.widget<Center>(find.byType(Center));
      expect(centerWidget.child, isA<Row>());

      final rowWidget = tester.widget<Row>(find.byType(Row));
      expect(rowWidget.mainAxisAlignment, equals(MainAxisAlignment.spaceBetween));
      expect(rowWidget.crossAxisAlignment, equals(CrossAxisAlignment.center));
    });

    testWidgets('should have correct mouse cursor on close icon', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      final mouseRegion = tester.widget<MouseRegion>(find.byType(MouseRegion));
      expect(mouseRegion.cursor, equals(SystemMouseCursors.click));
    });

    testWidgets('should handle empty thread ID gracefully', (tester) async {
      const selectedThread = Thread(
        id: '',
        name: '',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.text('Active Thread: Thread ID: '), findsOneWidget);
    });

    testWidgets('should handle special characters in thread name', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Thread with émojis 🧵 and spëcial chars @#\$%',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.text('Active Thread: Thread with émojis 🧵 and spëcial chars @#\$%'), findsOneWidget);
    });

    testWidgets('should handle very long thread IDs', (tester) async {
      final longId = 'thread-${'a' * 100}';
      final selectedThread = Thread(
        id: longId,
        name: '',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.textContaining('Active Thread: Thread ID:'), findsOneWidget);
    });

    testWidgets('should work with different screen sizes', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.text('Active Thread: Test Thread'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(200, 400));
      await tester.pump();

      expect(find.textContaining('Active Thread:'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle rapid provider state changes', (tester) async {
      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => null),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);

      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container.updateOverrides([
        selectedThreadProvider.overrideWith((ref) => selectedThread),
        threadsProvider.overrideWith((ref) => mockThreadsNotifier),
      ]);

      await tester.pump();

      expect(find.text('Active Thread: Test Thread'), findsOneWidget);

      container.updateOverrides([
        selectedThreadProvider.overrideWith((ref) => null),
        threadsProvider.overrideWith((ref) => mockThreadsNotifier),
      ]);

      await tester.pump();

      expect(find.byType(SizedBox), findsOneWidget);
    });

    testWidgets('should maintain consistent height', (tester) async {
      const selectedThread = Thread(
        id: 'thread-123',
        name: 'Test Thread',
      );

      container = ProviderContainer(
        overrides: [
          selectedThreadProvider.overrideWith((ref) => selectedThread),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: SelectedThreadBanner(),
            ),
          ),
        ),
      );

      final containerWidget = tester.widget<Container>(find.byType(Container).first);
      expect(containerWidget.constraints?.minHeight, equals(50));
    });
  });
}