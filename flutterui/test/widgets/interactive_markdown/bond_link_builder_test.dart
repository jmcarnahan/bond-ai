import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutterui/presentation/screens/chat/widgets/interactive_markdown/bond_link_builder.dart';
import 'package:flutterui/presentation/screens/chat/widgets/interactive_markdown/prompt_button.dart';

void main() {
  group('BondLinkBuilder', () {
    testWidgets('bond://prompt link renders PromptButton', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Click me](bond://prompt)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      expect(find.byType(PromptButton), findsOneWidget);
      expect(find.text('Click me'), findsOneWidget);
    });

    testWidgets('bond://prompt tap fires callback with link text',
        (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Click me](bond://prompt)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (prompt) => capturedPrompt = prompt,
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      await tester.tap(find.byType(PromptButton));
      expect(capturedPrompt, equals('Click me'));
    });

    testWidgets('bond://prompt/Custom text still uses label as prompt',
        (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Short label](bond://prompt/Custom%20text)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (prompt) => capturedPrompt = prompt,
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      await tester.tap(find.byType(PromptButton));
      // Label text is always used as the prompt, regardless of URL path
      expect(capturedPrompt, equals('Short label'));
    });

    testWidgets('unknown bond:// scheme renders plain text', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Foo](bond://unknown)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      expect(find.byType(PromptButton), findsNothing);
      expect(find.text('Foo'), findsOneWidget);
    });

    testWidgets('bond://prompt/ trailing slash uses label as prompt',
        (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Ask me](bond://prompt/)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (prompt) => capturedPrompt = prompt,
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      await tester.tap(find.byType(PromptButton));
      expect(capturedPrompt, equals('Ask me'));
    });

    testWidgets('bond://prompt with URL path always uses label as prompt',
        (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data:
                  '[Details](bond://prompt/What%20is%20%22hello%20world%22%3F)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (prompt) => capturedPrompt = prompt,
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      await tester.tap(find.byType(PromptButton));
      // Label is always used as the prompt, URL path is ignored
      expect(capturedPrompt, equals('Details'));
    });

    testWidgets('null onPromptButtonTap does not throw on tap',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Click me](bond://prompt)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: null,
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      // Should render button but tapping should not throw
      expect(find.byType(PromptButton), findsOneWidget);
      await tester.tap(find.byType(PromptButton));
      // No exception = pass
    });

    testWidgets('regular link does not render PromptButton', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Example](https://example.com)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      expect(find.byType(PromptButton), findsNothing);
    });

    testWidgets(
        'multi-word link text does not leak trailing words '
        '(flutter_markdown #137688 regression)',
        (tester) async {
      // This reproduces the bug where "Help with something else" renders as
      // a PromptButton + orphaned teal "with something else" text.
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data:
                  '[Tell me more](bond://prompt) | [Help with something else](bond://prompt)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      expect(find.byType(PromptButton), findsNWidgets(2));
      expect(find.text('Tell me more'), findsOneWidget);
      expect(find.text('Help with something else'), findsOneWidget);
      // The bug would cause "with something else" to appear as separate text
      expect(find.text('with something else'), findsNothing);
    });

    testWidgets('bond://prompter does not match bond://prompt',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[Foo](bond://prompter)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      // bond://prompter is NOT bond://prompt — should render as plain text
      expect(find.byType(PromptButton), findsNothing);
      expect(find.text('Foo'), findsOneWidget);
    });

    testWidgets('empty label link is not rendered by markdown parser',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MarkdownBody(
              data: '[](bond://prompt)',
              builders: {
                'a': BondLinkBuilder(
                  onPromptButtonTap: (_) {},
                ),
              },
              onTapLink: (_, __, ___) {},
            ),
          ),
        ),
      );

      // The markdown parser skips empty-label links entirely — no element
      // is created, so no PromptButton is rendered. This is correct behavior.
      expect(find.byType(PromptButton), findsNothing);
    });
  });
}
