import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('PromptButton', () {
    testWidgets('renders label text', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: PromptButton(label: 'Hello'))),
      );
      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('tap calls onPressed', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: PromptButton(label: 'Click me', onPressed: () => tapped = true),
          ),
        ),
      );
      await tester.tap(find.byType(PromptButton));
      expect(tapped, isTrue);
    });

    testWidgets('disabled when onPressed is null', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(home: Scaffold(body: PromptButton(label: 'Disabled'))),
      );
      final buttonFinder = find.ancestor(
        of: find.text('Disabled'),
        matching: find.byWidgetPredicate(
          (widget) => widget is ButtonStyleButton && widget.onPressed == null,
        ),
      );
      expect(buttonFinder, findsOneWidget);
    });

    testWidgets('renders with chat icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: PromptButton(label: 'Test', onPressed: () {})),
        ),
      );
      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
    });
  });
}
