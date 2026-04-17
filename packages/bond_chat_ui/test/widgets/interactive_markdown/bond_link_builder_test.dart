import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('BondLinkBuilder', () {
    testWidgets('bond://prompt link renders PromptButton', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Click me](bond://prompt)',
              builders: {'a': BondLinkBuilder(onPromptButtonTap: (_) {})},
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      expect(find.byType(PromptButton), findsOneWidget);
      expect(find.text('Click me'), findsOneWidget);
    });

    testWidgets('bond://prompt tap fires callback with link text', (tester) async {
      String? capturedPrompt;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Click me](bond://prompt)',
              builders: {'a': BondLinkBuilder(onPromptButtonTap: (p) => capturedPrompt = p)},
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      await tester.tap(find.byType(PromptButton));
      expect(capturedPrompt, equals('Click me'));
    });

    testWidgets('unknown bond:// scheme renders plain text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Foo](bond://unknown)',
              builders: {'a': BondLinkBuilder(onPromptButtonTap: (_) {})},
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      expect(find.byType(PromptButton), findsNothing);
      expect(find.text('Foo'), findsOneWidget);
    });

    testWidgets('regular link does not render PromptButton', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Example](https://example.com)',
              builders: {'a': BondLinkBuilder(onPromptButtonTap: (_) {})},
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      expect(find.byType(PromptButton), findsNothing);
    });

    testWidgets('multi-word link text does not leak trailing words', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Tell me more](bond://prompt) | [Help with something else](bond://prompt)',
              builders: {'a': BondLinkBuilder(onPromptButtonTap: (_) {})},
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );
      expect(find.byType(PromptButton), findsNWidgets(2));
      expect(find.text('with something else'), findsNothing);
    });
  });
}
