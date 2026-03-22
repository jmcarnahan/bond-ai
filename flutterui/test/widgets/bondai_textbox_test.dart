@TestOn('browser')
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

Widget _wrap(Widget child) {
  return MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));
}

bool _richTextContains(Widget widget, String text) {
  if (widget is! Text) return false;
  final span = widget.textSpan;
  if (span == null) return false;
  return span.toPlainText().contains(text);
}

void main() {
  group('BondAITextBox isRequired', () {
    testWidgets('does not show asterisk by default', (tester) async {
      await tester.pumpWidget(_wrap(
        BondAITextBox(
          controller: TextEditingController(),
          labelText: 'Name',
        ),
      ));

      expect(find.text('Name'), findsOneWidget);
      expect(
        find.byWidgetPredicate((w) => _richTextContains(w, '*')),
        findsNothing,
      );
    });

    testWidgets('shows red asterisk when isRequired is true (no helpTooltip)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        BondAITextBox(
          controller: TextEditingController(),
          labelText: 'Agent Name',
          isRequired: true,
        ),
      ));

      expect(
        find.byWidgetPredicate((w) => _richTextContains(w, 'Agent Name *')),
        findsOneWidget,
      );
    });

    testWidgets(
        'shows red asterisk when isRequired is true (with helpTooltip)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        BondAITextBox(
          controller: TextEditingController(),
          labelText: 'Agent Name',
          isRequired: true,
          helpTooltip: 'Enter the agent name',
        ),
      ));

      expect(
        find.byWidgetPredicate((w) => _richTextContains(w, 'Agent Name *')),
        findsOneWidget,
      );
    });

    testWidgets('backwards compatibility - no isRequired param works',
        (tester) async {
      await tester.pumpWidget(_wrap(
        BondAITextBox(
          controller: TextEditingController(),
          labelText: 'Description',
        ),
      ));

      expect(find.text('Description'), findsOneWidget);
    });
  });

  group('ResizableTextBox isRequired', () {
    testWidgets('does not show asterisk by default', (tester) async {
      await tester.pumpWidget(_wrap(
        ResizableTextBox(
          controller: TextEditingController(),
          labelText: 'Notes',
        ),
      ));

      expect(
        find.byWidgetPredicate((w) => _richTextContains(w, '*')),
        findsNothing,
      );
    });

    testWidgets('shows red asterisk when isRequired is true (no helpTooltip)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        ResizableTextBox(
          controller: TextEditingController(),
          labelText: 'Instructions',
          isRequired: true,
        ),
      ));

      expect(
        find.byWidgetPredicate(
            (w) => _richTextContains(w, 'Instructions *')),
        findsOneWidget,
      );
    });

    testWidgets(
        'shows red asterisk when isRequired is true (with helpTooltip)',
        (tester) async {
      await tester.pumpWidget(_wrap(
        ResizableTextBox(
          controller: TextEditingController(),
          labelText: 'Instructions',
          isRequired: true,
          helpTooltip: 'Enter instructions',
        ),
      ));

      expect(
        find.byWidgetPredicate(
            (w) => _richTextContains(w, 'Instructions *')),
        findsOneWidget,
      );
    });
  });
}
