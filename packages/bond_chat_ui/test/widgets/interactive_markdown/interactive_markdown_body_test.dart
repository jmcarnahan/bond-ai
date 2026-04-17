import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('sanitizeBondLinks', () {
    test('encodes spaces in bond:// URLs', () {
      const input = '[Help](bond://prompt/Help with something else)';
      expect(
        sanitizeBondLinks(input),
        equals('[Help](bond://prompt/Help%20with%20something%20else)'),
      );
    });

    test('leaves already-encoded URLs unchanged', () {
      const input = '[Help](bond://prompt/Help%20with%20something)';
      expect(sanitizeBondLinks(input), equals(input));
    });

    test('leaves simple bond://prompt URLs unchanged', () {
      const input = '[Click me](bond://prompt)';
      expect(sanitizeBondLinks(input), equals(input));
    });

    test('does not affect regular URLs', () {
      const input = '[Example](https://example.com/search?q=hello world)';
      expect(sanitizeBondLinks(input), equals(input));
    });
  });

  group('InteractiveMarkdownBody', () {
    testWidgets('renders markdown text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data: '**bold text**',
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      expect(find.text('bold text'), findsOneWidget);
    });

    testWidgets('renders bond://prompt as PromptButton', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data: '[Click me](bond://prompt)',
              onTapLink: (_, __, ___) {},
              onPromptButtonTap: (_) {},
            ),
          ),
        ),
      );
      expect(find.byType(PromptButton), findsOneWidget);
    });
  });
}
