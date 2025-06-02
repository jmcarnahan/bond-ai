import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_error_banner.dart';

void main() {
  group('AgentErrorBanner Widget Tests', () {
    testWidgets('should not display when errorMessage is null', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: null),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);
      expect(find.byIcon(Icons.error_outline), findsNothing);
      expect(find.byType(Text), findsNothing);
    });

    testWidgets('should display error banner when errorMessage is provided', (tester) async {
      const errorMessage = 'Test error message';
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: errorMessage),
          ),
        ),
      );

      expect(find.text(errorMessage), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);
      expect(find.byType(Padding), findsOneWidget);
    });

    testWidgets('should apply correct theme colors for error container', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.light(
              error: Colors.red,
              errorContainer: Colors.red.withValues(alpha: 0.1),
            ),
          ),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.color, equals(Colors.red.withValues(alpha: 0.1)));
      expect((decoration.border as Border).top.color, equals(Colors.red.withValues(alpha: 0.3)));
    });

    testWidgets('should apply correct theme colors for error icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.light(
              error: Colors.red,
              errorContainer: Colors.red.withValues(alpha: 0.1),
            ),
          ),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
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
            colorScheme: ColorScheme.light(
              error: Colors.red,
              errorContainer: Colors.red.withValues(alpha: 0.1),
            ),
          ),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Test error'));
      final style = text.style!;
      expect(style.color, equals(Colors.red));
      expect(style.fontWeight, equals(FontWeight.w500));
    });

    testWidgets('should handle long error messages', (tester) async {
      const longError = 'This is a very long error message that should wrap properly and not cause any overflow issues in the user interface display';
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: longError),
          ),
        ),
      );

      expect(find.textContaining('This is a very long error'), findsOneWidget);
      expect(find.byType(Expanded), findsOneWidget);
    });

    testWidgets('should handle empty error message', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: ''),
          ),
        ),
      );

      expect(find.text(''), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);
    });

    testWidgets('should handle special characters in error message', (tester) async {
      const specialError = 'Error with émojis 💥 and spëcial chars @#\$%^&*()';
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: specialError),
          ),
        ),
      );

      expect(find.text(specialError), findsOneWidget);
    });

    testWidgets('should maintain proper layout structure', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      expect(find.byType(Padding), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);
      expect(find.byType(Row), findsOneWidget);
      expect(find.byType(Icon), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Expanded), findsOneWidget);

      final row = tester.widget<Row>(find.byType(Row));
      expect(row.children, hasLength(3));
    });

    testWidgets('should apply correct padding and spacing', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final outerPadding = tester.widget<Padding>(find.byType(Padding));
      expect(outerPadding.padding, isA<EdgeInsets>());

      final container = tester.widget<Container>(find.byType(Container));
      expect(container.padding, isA<EdgeInsets>());

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, greaterThan(0));
    });

    testWidgets('should apply border radius correctly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.borderRadius, isA<BorderRadius>());
      expect(decoration.border, isA<Border>());
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      expect(find.text('Test error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should work with custom color scheme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.purple,
              error: Colors.orange,
              errorContainer: Colors.orange.withValues(alpha: 0.1),
            ),
          ),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.error_outline));
      expect(icon.color, equals(Colors.orange));
    });

    testWidgets('should handle different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error message'),
          ),
        ),
      );

      expect(find.text('Test error message'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Test error message'), findsOneWidget);

      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should handle constrained width properly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              child: AgentErrorBanner(errorMessage: 'This is a longer error message that should wrap'),
            ),
          ),
        ),
      );

      expect(find.textContaining('This is a longer error'), findsOneWidget);
      expect(find.byType(Expanded), findsOneWidget);
    });

    testWidgets('should maintain icon size correctly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.error_outline));
      expect(icon.size, greaterThan(0));
      expect(icon.icon, equals(Icons.error_outline));
    });

    testWidgets('should apply text theme correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              bodyMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.normal),
            ),
          ),
          home: const Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error'),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Test error'));
      expect(text.style?.fontWeight, equals(FontWeight.w500));
    });

    testWidgets('should handle multiple state changes', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: null),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'First error'),
          ),
        ),
      );

      expect(find.text('First error'), findsOneWidget);
      expect(find.byType(Container), findsOneWidget);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Second error'),
          ),
        ),
      );

      expect(find.text('Second error'), findsOneWidget);
      expect(find.text('First error'), findsNothing);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: null),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Container), findsNothing);
    });

    testWidgets('should handle edge case error messages', (tester) async {
      final edgeCases = [
        'Single',
        '123',
        'Error\nwith\nnewlines',
        'Error\twith\ttabs',
        'Error with    multiple    spaces',
        'Error-with-dashes_and_underscores',
      ];

      for (final errorMessage in edgeCases) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: AgentErrorBanner(errorMessage: errorMessage),
            ),
          ),
        );

        expect(find.text(errorMessage), findsOneWidget);
        expect(find.byIcon(Icons.error_outline), findsOneWidget);
      }
    });

    testWidgets('should work in different container layouts', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                Container(height: 100),
                AgentErrorBanner(errorMessage: 'Test error'),
                Container(height: 100),
              ],
            ),
          ),
        ),
      );

      expect(find.text('Test error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Accessibility test error'),
          ),
        ),
      );

      expect(find.text('Accessibility test error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should maintain consistent visual appearance', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Visual consistency test'),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      
      expect(decoration.color, isNotNull);
      expect(decoration.borderRadius, isNotNull);
      expect(decoration.border, isNotNull);
      expect(container.padding, isNotNull);
    });

    testWidgets('should handle very short error messages', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'X'),
          ),
        ),
      );

      expect(find.text('X'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should properly expand text area', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentErrorBanner(errorMessage: 'Test error message for expansion'),
          ),
        ),
      );

      final expanded = tester.widget<Expanded>(find.byType(Expanded));
      expect(expanded.flex, equals(1));
    });
  });
}