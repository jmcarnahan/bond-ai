import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/threads/widgets/threads_empty_state.dart';

void main() {
  group('ThreadsEmptyState Widget Tests', () {
    late bool onCreateThreadCalled;

    setUp(() {
      onCreateThreadCalled = false;
    });

    testWidgets('should display empty state with all elements', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);
      expect(find.text('Create your first thread to start chatting with agents'), findsOneWidget);
      expect(find.text('Create Thread'), findsOneWidget);
      expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
      expect(find.byIcon(Icons.add), findsOneWidget);
      expect(find.byType(FilledButton), findsOneWidget);
    });

    testWidgets('should call onCreateThread when button pressed', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      expect(onCreateThreadCalled, isTrue);
    });

    testWidgets('should call onCreateThread when tapping button text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create Thread'));
      expect(onCreateThreadCalled, isTrue);
    });

    testWidgets('should call onCreateThread when tapping button icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.add));
      expect(onCreateThreadCalled, isTrue);
    });

    testWidgets('should center content properly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.byType(Center), findsOneWidget);
      
      final column = tester.widget<Column>(find.byType(Column));
      expect(column.mainAxisAlignment, equals(MainAxisAlignment.center));
    });

    testWidgets('should apply correct theme styling', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              onSurface: Colors.black,
            ),
          ),
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.forum_outlined));
      expect(icon.color, equals(Colors.black.withValues(alpha: 0.3)));
    });

    testWidgets('should handle different theme colors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.dark(
              onSurface: Colors.white,
            ),
          ),
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);
      expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
    });

    testWidgets('should have correct text alignment', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final bodyText = tester.widget<Text>(find.text('Create your first thread to start chatting with agents'));
      expect(bodyText.textAlign, equals(TextAlign.center));
    });

    testWidgets('should maintain proper spacing between elements', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsNWidgets(3));
      expect(find.byType(Padding), findsOneWidget);
    });

    testWidgets('should display icon with correct properties', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.forum_outlined));
      expect(icon.icon, equals(Icons.forum_outlined));
      expect(icon.size, greaterThan(50));
    });

    testWidgets('should apply correct button styling', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<FilledButton>(find.byType(FilledButton));
      expect(button.onPressed, isNotNull);
      expect(button.style, isNotNull);
    });

    testWidgets('should handle multiple button presses', (tester) async {
      int pressCount = 0;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => pressCount++,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      await tester.tap(find.byType(FilledButton));
      await tester.tap(find.byType(FilledButton));
      
      expect(pressCount, equals(3));
    });

    testWidgets('should handle layout in constrained space', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              height: 300,
              child: ThreadsEmptyState(
                onCreateThread: () => onCreateThreadCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);
      expect(find.text('Create Thread'), findsOneWidget);
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 600));
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pump();

      expect(find.text('No threads yet'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle text overflow gracefully', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              child: ThreadsEmptyState(
                onCreateThread: () => onCreateThreadCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.textContaining('Create your first thread'), findsOneWidget);
    });

    testWidgets('should maintain button functionality in narrow layout', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 150,
              child: ThreadsEmptyState(
                onCreateThread: () => onCreateThreadCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      expect(onCreateThreadCalled, isTrue);
    });

    testWidgets('should display all UI elements in correct order', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.children, hasLength(7));
    });

    testWidgets('should handle theme text styles correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              headlineSmall: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              bodyLarge: TextStyle(fontSize: 16),
            ),
          ),
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);
      expect(find.text('Create your first thread to start chatting with agents'), findsOneWidget);
    });

    testWidgets('should be scrollable when content exceeds screen height', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 200));
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ThreadsEmptyState(
                onCreateThread: () => onCreateThreadCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('No threads yet'), findsOneWidget);
      expect(find.text('Create Thread'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle rapid button taps', (tester) async {
      int tapCount = 0;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => tapCount++,
            ),
          ),
        ),
      );

      for (int i = 0; i < 10; i++) {
        await tester.tap(find.byType(FilledButton));
        await tester.pump(const Duration(milliseconds: 10));
      }
      
      expect(tapCount, equals(10));
    });

    testWidgets('should maintain padding correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      final padding = tester.widget<Padding>(find.byType(Padding));
      expect(padding.padding, isNotNull);
    });

    testWidgets('should work with accessibility features', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsEmptyState(
              onCreateThread: () => onCreateThreadCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Create Thread'), findsOneWidget);
      await tester.tap(find.text('Create Thread'));
      expect(onCreateThreadCalled, isTrue);
    });
  });
}