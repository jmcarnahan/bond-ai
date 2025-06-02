import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_loading_overlay.dart';

void main() {
  group('AgentLoadingOverlay Widget Tests', () {
    testWidgets('should not display when isVisible is false', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: false),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('Saving agent...'), findsNothing);
    });

    testWidgets('should display loading overlay when isVisible is true', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(Container), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.byType(Center), findsOneWidget);
      expect(find.byType(Column), findsOneWidget);
    });

    testWidgets('should apply correct overlay background color', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container));
      expect(container.color, equals(Colors.black.withValues(alpha: 0.3)));
    });

    testWidgets('should center content properly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(Center), findsOneWidget);
      
      final column = tester.widget<Column>(find.byType(Column));
      expect(column.mainAxisSize, equals(MainAxisSize.min));
    });

    testWidgets('should display progress indicator with default styling', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      
      final progressIndicator = tester.widget<CircularProgressIndicator>(find.byType(CircularProgressIndicator));
      expect(progressIndicator.value, isNull);
    });

    testWidgets('should apply correct text styling', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Saving agent...'));
      final style = text.style!;
      expect(style.color, equals(Colors.white));
      expect(style.fontSize, equals(16));
      expect(style.fontWeight, equals(FontWeight.bold));
    });

    testWidgets('should maintain proper spacing between elements', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      
      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.height, greaterThan(0));
    });

    testWidgets('should work in different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Saving agent...'), findsOneWidget);

      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should handle state changes correctly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: false),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(Container), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: false),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);
    });

    testWidgets('should cover entire screen when visible', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Stack(
              children: [
                Center(child: Text('Background content')),
                AgentLoadingOverlay(isVisible: true),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Background content'), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should work with different theme colors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
            ),
          ),
          home: const Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: const Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
      
      final text = tester.widget<Text>(find.text('Saving agent...'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should maintain layout structure consistently', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.children, hasLength(3));
      expect(column.children[0], isA<CircularProgressIndicator>());
      expect(column.children[1], isA<SizedBox>());
      expect(column.children[2], isA<Text>());
    });

    testWidgets('should be positioned correctly in stack layouts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Stack(
              children: [
                Positioned.fill(
                  child: Container(color: Colors.grey),
                ),
                AgentLoadingOverlay(isVisible: true),
              ],
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
    });

    testWidgets('should handle rapid visibility changes', (tester) async {
      for (int i = 0; i < 5; i++) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: AgentLoadingOverlay(isVisible: i % 2 == 0),
            ),
          ),
        );

        if (i % 2 == 0) {
          expect(find.byType(Container), findsOneWidget);
          expect(find.text('Saving agent...'), findsOneWidget);
        } else {
          expect(find.byType(SizedBox), findsOneWidget);
          expect(find.byType(Container), findsNothing);
        }
      }
    });

    testWidgets('should work in different container layouts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 300,
              height: 200,
              child: AgentLoadingOverlay(isVisible: true),
            ),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should handle overlays in complex layouts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Container(height: 100, color: Colors.red),
                Expanded(
                  child: Stack(
                    children: [
                      Container(color: Colors.blue),
                      AgentLoadingOverlay(isVisible: true),
                    ],
                  ),
                ),
                Container(height: 100, color: Colors.green),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should maintain accessibility requirements', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should work with custom app themes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.purple,
              primary: Colors.purple,
            ),
          ),
          home: const Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
    });

    testWidgets('should handle animation properly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should work in portrait and landscape orientations', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Saving agent...'), findsOneWidget);
      
      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should maintain consistent text content', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      expect(find.text('Saving agent...'), findsOneWidget);
      expect(find.text('Loading...'), findsNothing);
      expect(find.text('Please wait...'), findsNothing);
    });

    testWidgets('should work with scaffold backgrounds', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            backgroundColor: Colors.yellow,
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container));
      expect(container.color, equals(Colors.black.withValues(alpha: 0.3)));
      expect(find.text('Saving agent...'), findsOneWidget);
    });

    testWidgets('should handle edge case visibility values', (tester) async {
      const testCases = [true, false, true, false, true];
      
      for (final isVisible in testCases) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: AgentLoadingOverlay(isVisible: isVisible),
            ),
          ),
        );

        if (isVisible) {
          expect(find.byType(Container), findsOneWidget);
          expect(find.text('Saving agent...'), findsOneWidget);
        } else {
          expect(find.byType(SizedBox), findsOneWidget);
          expect(find.byType(Container), findsNothing);
        }
      }
    });

    testWidgets('should work as overlay in navigation contexts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Navigator(
            onGenerateRoute: (settings) => MaterialPageRoute(
              builder: (context) => Scaffold(
                body: Stack(
                  children: [
                    Center(child: Text('Page content')),
                    AgentLoadingOverlay(isVisible: true),
                  ],
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.text('Page content'), findsOneWidget);
      expect(find.text('Saving agent...'), findsOneWidget);
    });

    testWidgets('should handle theme text style inheritance', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              bodyMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.normal),
            ),
          ),
          home: const Scaffold(
            body: AgentLoadingOverlay(isVisible: true),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Saving agent...'));
      expect(text.style?.fontSize, equals(16));
      expect(text.style?.fontWeight, equals(FontWeight.bold));
      expect(text.style?.color, equals(Colors.white));
    });
  });
}