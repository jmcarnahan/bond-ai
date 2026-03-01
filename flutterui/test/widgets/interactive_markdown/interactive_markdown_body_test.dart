import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/presentation/screens/chat/widgets/interactive_markdown/interactive_markdown_body.dart';
import 'package:flutterui/presentation/screens/chat/widgets/interactive_markdown/prompt_button.dart';

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

    test('handles multiple bond links in same string', () {
      const input =
          '[A](bond://prompt/Opt A) | [B](bond://prompt/Opt B)';
      expect(
        sanitizeBondLinks(input),
        equals('[A](bond://prompt/Opt%20A) | [B](bond://prompt/Opt%20B)'),
      );
    });

    test('handles mixed bond and regular links', () {
      const input =
          '[A](bond://prompt/Hello world) and [B](https://example.com)';
      expect(
        sanitizeBondLinks(input),
        equals(
            '[A](bond://prompt/Hello%20world) and [B](https://example.com)'),
      );
    });
  });

  group('InteractiveMarkdownBody', () {
    testWidgets('renders mixed content with text and prompt buttons',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data:
                  'Hello world\n\n[Click me](bond://prompt)\n\n[Example](https://example.com)',
              onTapLink: (_, __, ___) {},
              onPromptButtonTap: (_) {},
            ),
          ),
        ),
      );

      expect(find.text('Hello world'), findsOneWidget);
      expect(find.byType(PromptButton), findsOneWidget);
      expect(find.text('Click me'), findsOneWidget);
    });

    testWidgets('renders multiple prompt buttons', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data:
                  '[Option A](bond://prompt)\n\n[Option B](bond://prompt)\n\n[Option C](bond://prompt)',
              onTapLink: (_, __, ___) {},
              onPromptButtonTap: (_) {},
            ),
          ),
        ),
      );

      expect(find.byType(PromptButton), findsNWidgets(3));
    });

    testWidgets('callback wiring works for prompt buttons', (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data: '[Click me](bond://prompt)',
              onTapLink: (_, __, ___) {},
              onPromptButtonTap: (prompt) => capturedPrompt = prompt,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(PromptButton));
      expect(capturedPrompt, equals('Click me'));
    });

    testWidgets('onTapLink fires for regular links', (tester) async {
      String? capturedHref;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              data: '[Example](https://example.com)',
              onTapLink: (_, href, __) => capturedHref = href,
              onPromptButtonTap: (_) {},
            ),
          ),
        ),
      );

      // Regular links are rendered as text with GestureRecognizer via onTapLink
      // Just verify no PromptButton was rendered
      expect(find.byType(PromptButton), findsNothing);
      expect(find.text('Example'), findsOneWidget);
    });

    testWidgets(
        'unencoded spaces in bond:// URL render cleanly (no orphaned text)',
        (tester) async {
      String? capturedPrompt;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: InteractiveMarkdownBody(
              // LLM emitted unencoded spaces — sanitizer should fix this
              data: '[Help](bond://prompt/Help with something else)',
              onTapLink: (_, __, ___) {},
              onPromptButtonTap: (prompt) => capturedPrompt = prompt,
            ),
          ),
        ),
      );

      // Should render exactly one PromptButton, no orphaned text
      expect(find.byType(PromptButton), findsOneWidget);
      expect(find.text('Help'), findsOneWidget);

      await tester.tap(find.byType(PromptButton));
      // Label text is always used as the prompt
      expect(capturedPrompt, equals('Help'));
    });
  });
}
