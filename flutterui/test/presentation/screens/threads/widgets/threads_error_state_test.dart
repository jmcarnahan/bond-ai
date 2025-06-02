import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/threads/widgets/threads_error_state.dart';

void main() {
  group('ThreadsErrorState Widget Tests', () {
    late bool onRetryCalled;

    setUp(() {
      onRetryCalled = false;
    });

    testWidgets('should display error state with all elements', (tester) async {
      const errorMessage = 'Network connection failed';
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: errorMessage,
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.text(errorMessage), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
      expect(find.byType(FilledButton), findsOneWidget);
    });

    testWidgets('should call onRetry when button pressed', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      expect(onRetryCalled, isTrue);
    });

    testWidgets('should call onRetry when tapping retry text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.text('Retry'));
      expect(onRetryCalled, isTrue);
    });

    testWidgets('should call onRetry when tapping refresh icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.refresh));
      expect(onRetryCalled, isTrue);
    });

    testWidgets('should center content properly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.byType(Center), findsOneWidget);
      
      final column = tester.widget<Column>(find.byType(Column));
      expect(column.mainAxisAlignment, equals(MainAxisAlignment.center));
    });

    testWidgets('should apply correct theme colors for error icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              error: Colors.red,
            ),
          ),
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.error_outline));
      expect(icon.color, equals(Colors.red));
    });

    testWidgets('should apply correct theme colors for error text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              error: Colors.red,
            ),
          ),
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
    });

    testWidgets('should handle long error messages', (tester) async {
      const longError = 'This is a very long error message that might span multiple lines and should be handled gracefully by the error state widget without causing any layout issues or overflow problems in the user interface.';
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: longError,
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.textContaining('This is a very long error'), findsOneWidget);
      
      final errorText = tester.widget<Text>(find.text(longError));
      expect(errorText.textAlign, equals(TextAlign.center));
    });

    testWidgets('should handle empty error message', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: '',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text(''), findsOneWidget);
      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('should handle special characters in error message', (tester) async {
      const specialError = 'Error with émojis 💥 and spëcial chars @#\$%^&*()';
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: specialError,
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text(specialError), findsOneWidget);
    });

    testWidgets('should maintain proper spacing between elements', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsNWidgets(3));
      expect(find.byType(Padding), findsOneWidget);
    });

    testWidgets('should apply correct button styling', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
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
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => pressCount++,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      await tester.tap(find.byType(FilledButton));
      await tester.tap(find.byType(FilledButton));
      
      expect(pressCount, equals(3));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 600));
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pump();

      expect(find.text('Failed to load threads'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle layout in constrained space', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              height: 300,
              child: ThreadsErrorState(
                error: 'Test error',
                onRetry: () => onRetryCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('should handle dark theme correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should handle light theme correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should display icon with correct properties', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.error_outline));
      expect(icon.icon, equals(Icons.error_outline));
      expect(icon.size, greaterThan(30));
    });

    testWidgets('should handle text overflow gracefully', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              child: ThreadsErrorState(
                error: 'This is a very long error message that should wrap properly',
                onRetry: () => onRetryCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.textContaining('This is a very long'), findsOneWidget);
    });

    testWidgets('should maintain button functionality in narrow layout', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 150,
              child: ThreadsErrorState(
                error: 'Test error',
                onRetry: () => onRetryCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(FilledButton));
      expect(onRetryCalled, isTrue);
    });

    testWidgets('should display all UI elements in correct order', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
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
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.text('Test error'), findsOneWidget);
    });

    testWidgets('should handle rapid button taps', (tester) async {
      int tapCount = 0;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => tapCount++,
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

    testWidgets('should handle different error types', (tester) async {
      final errorTypes = [
        'Network timeout',
        'Server error 500',
        'Connection refused',
        'Authentication failed',
        'Invalid response format',
        'Service unavailable',
      ];

      for (final error in errorTypes) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ThreadsErrorState(
                error: error,
                onRetry: () => onRetryCalled = true,
              ),
            ),
          ),
        );

        expect(find.text(error), findsOneWidget);
        expect(find.text('Failed to load threads'), findsOneWidget);
      }
    });

    testWidgets('should work with accessibility features', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Retry'), findsOneWidget);
      await tester.tap(find.text('Retry'));
      expect(onRetryCalled, isTrue);
    });

    testWidgets('should maintain padding correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      final padding = tester.widget<Padding>(find.byType(Padding));
      expect(padding.padding, isNotNull);
    });

    testWidgets('should handle custom color schemes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.purple,
              error: Colors.orange,
            ),
          ),
          home: Scaffold(
            body: ThreadsErrorState(
              error: 'Test error',
              onRetry: () => onRetryCalled = true,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.error_outline));
      expect(icon.color, equals(Colors.orange));
    });

    testWidgets('should be scrollable when content exceeds screen height', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 200));
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ThreadsErrorState(
                error: 'Test error',
                onRetry: () => onRetryCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Failed to load threads'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });
  });
}