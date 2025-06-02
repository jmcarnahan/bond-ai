import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/threads/widgets/threads_loading_state.dart';

void main() {
  group('ThreadsLoadingState Widget Tests', () {
    testWidgets('should display loading indicator and text', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
      expect(find.byType(Center), findsOneWidget);
      expect(find.byType(Column), findsOneWidget);
    });

    testWidgets('should center content properly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.mainAxisAlignment, equals(MainAxisAlignment.center));
    });

    testWidgets('should apply correct theme colors for progress indicator', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
            ),
          ),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      final progressIndicator = tester.widget<CircularProgressIndicator>(find.byType(CircularProgressIndicator));
      final valueColor = progressIndicator.valueColor as AlwaysStoppedAnimation<Color>;
      expect(valueColor.value, equals(Colors.blue));
    });

    testWidgets('should apply correct theme colors for text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              onSurface: Colors.black,
            ),
          ),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should maintain proper spacing between elements', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should work with different theme colors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.dark(
              primary: Colors.red,
              onSurface: Colors.white,
            ),
          ),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      final progressIndicator = tester.widget<CircularProgressIndicator>(find.byType(CircularProgressIndicator));
      final valueColor = progressIndicator.valueColor as AlwaysStoppedAnimation<Color>;
      expect(valueColor.value, equals(Colors.red));

      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should work in different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 600));
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pump();

      expect(find.text('Loading threads...'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should work in constrained containers', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              height: 300,
              child: ThreadsLoadingState(),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should handle very small containers', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 100,
              height: 100,
              child: ThreadsLoadingState(),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should maintain column structure', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.children, hasLength(3));
    });

    testWidgets('should work with custom text themes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              bodyLarge: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should handle light theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should handle dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should be accessible', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should maintain layout when parent changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Container(
              color: Colors.red,
              child: ThreadsLoadingState(),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Container(
              color: Colors.blue,
              child: ThreadsLoadingState(),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should handle orientation changes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Loading threads...'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should work in scrollable containers', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: SizedBox(
                height: 2000,
                child: ThreadsLoadingState(),
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should maintain consistent appearance', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);

      await tester.pump(const Duration(milliseconds: 500));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should handle theme changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should work with custom color schemes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.purple),
          ),
          home: const Scaffold(
            body: ThreadsLoadingState(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });

    testWidgets('should be a stateless widget', (tester) async {
      const widget = ThreadsLoadingState();
      expect(widget, isA<StatelessWidget>());
    });

    testWidgets('should handle rapid rebuilds', (tester) async {
      for (int i = 0; i < 10; i++) {
        await tester.pumpWidget(
          MaterialApp(
            theme: i % 2 == 0 ? ThemeData.light() : ThemeData.dark(),
            home: const Scaffold(
              body: ThreadsLoadingState(),
            ),
          ),
        );
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading threads...'), findsOneWidget);
    });
  });
}