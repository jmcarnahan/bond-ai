import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/widgets/typing_indicator.dart';

void main() {
  group('TypingIndicator Widget Tests', () {
    testWidgets('should render with default properties', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);
      expect(find.byType(Row), findsOneWidget);
      expect(find.byType(Container), findsNWidgets(3));
    });

    testWidgets('should render with custom dot size', (tester) async {
      const customDotSize = 12.0;
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(dotSize: customDotSize),
          ),
        ),
      );

      final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
      expect(typingIndicator.dotSize, equals(customDotSize));

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.height, equals(customDotSize * 2.5));
    });

    testWidgets('should render with custom dot color', (tester) async {
      const customColor = Colors.red;
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(dotColor: customColor),
          ),
        ),
      );

      final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
      expect(typingIndicator.dotColor, equals(customColor));
    });

    testWidgets('should use theme color when no custom color provided', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light().copyWith(
              onSurfaceVariant: Colors.blue,
            ),
          ),
          home: const Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should animate dots over time', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      await tester.pump();
      
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump();
      
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump();
      
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump();
      
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump();

      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should handle different dot sizes correctly', (tester) async {
      final dotSizes = [4.0, 8.0, 12.0, 16.0, 20.0];

      for (final dotSize in dotSizes) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TypingIndicator(dotSize: dotSize),
            ),
          ),
        );

        final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
        expect(typingIndicator.dotSize, equals(dotSize));

        final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
        expect(sizedBox.height, equals(dotSize * 2.5));

        final containers = tester.widgetList<Container>(find.byType(Container));
        for (final container in containers) {
          expect(container.constraints?.minWidth, isNull);
        }
      }
    });

    testWidgets('should handle different color values', (tester) async {
      final colors = [
        Colors.red,
        Colors.blue,
        Colors.green,
        Colors.transparent,
        const Color(0xFF123456),
        Colors.white,
        Colors.black,
      ];

      for (final color in colors) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TypingIndicator(dotColor: color),
            ),
          ),
        );

        final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
        expect(typingIndicator.dotColor, equals(color));
      }
    });

    testWidgets('should create three dot containers', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      final containers = tester.widgetList<Container>(find.byType(Container));
      expect(containers.length, equals(3));

      for (final container in containers) {
        final decoration = container.decoration as BoxDecoration?;
        expect(decoration?.shape, equals(BoxShape.circle));
        expect(container.margin, equals(const EdgeInsets.symmetric(horizontal: 2.0)));
      }
    });

    testWidgets('should center dots horizontally', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      final row = tester.widget<Row>(find.byType(Row));
      expect(row.mainAxisAlignment, equals(MainAxisAlignment.center));
      expect(row.children.length, equals(3));
    });

    testWidgets('should dispose properly when widget is removed', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: Text('No indicator'),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsNothing);
      expect(find.text('No indicator'), findsOneWidget);
    });

    testWidgets('should handle rapid rebuilds without errors', (tester) async {
      for (int i = 0; i < 10; i++) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TypingIndicator(
                dotSize: 8.0 + i,
                dotColor: i % 2 == 0 ? Colors.red : Colors.blue,
              ),
            ),
          ),
        );
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should work with extreme dot sizes', (tester) async {
      const extremeSizes = [0.1, 0.5, 1.0, 50.0, 100.0];

      for (final size in extremeSizes) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: TypingIndicator(dotSize: size),
            ),
          ),
        );

        final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
        expect(typingIndicator.dotSize, equals(size));

        final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
        expect(sizedBox.height, equals(size * 2.5));
      }
    });

    testWidgets('should maintain consistent height regardless of animation state', (tester) async {
      const dotSize = 10.0;
      const expectedHeight = dotSize * 2.5;

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(dotSize: dotSize),
          ),
        ),
      );

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.height, equals(expectedHeight));

      await tester.pump(const Duration(milliseconds: 200));
      
      final sizedBoxAfterAnimation = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBoxAfterAnimation.height, equals(expectedHeight));

      await tester.pump(const Duration(milliseconds: 600));
      
      final sizedBoxAfterMoreAnimation = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBoxAfterMoreAnimation.height, equals(expectedHeight));
    });

    testWidgets('should handle null dotColor parameter', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(dotColor: null),
          ),
        ),
      );

      final typingIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
      expect(typingIndicator.dotColor, isNull);
      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should work in different theme modes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          home: const Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: const Scaffold(
            body: TypingIndicator(),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should create dot containers with correct properties', (tester) async {
      const dotSize = 10.0;
      
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(
              dotSize: dotSize,
              dotColor: Colors.red,
            ),
          ),
        ),
      );

      final containers = tester.widgetList<Container>(find.byType(Container));
      
      for (final container in containers) {
        expect(container.constraints?.minWidth, isNull);
        expect(container.constraints?.minHeight, isNull);
        expect(container.margin, equals(const EdgeInsets.symmetric(horizontal: 2.0)));
        
        final decoration = container.decoration as BoxDecoration?;
        expect(decoration?.shape, equals(BoxShape.circle));
      }
    });

    testWidgets('should handle widget updates correctly', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(
              dotSize: 8.0,
              dotColor: Colors.red,
            ),
          ),
        ),
      );

      expect(find.byType(TypingIndicator), findsOneWidget);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: TypingIndicator(
              dotSize: 12.0,
              dotColor: Colors.blue,
            ),
          ),
        ),
      );

      final updatedIndicator = tester.widget<TypingIndicator>(find.byType(TypingIndicator));
      expect(updatedIndicator.dotSize, equals(12.0));
      expect(updatedIndicator.dotColor, equals(Colors.blue));
    });
  });
}