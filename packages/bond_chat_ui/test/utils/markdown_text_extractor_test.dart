import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  late MarkdownTextExtractor extractor;

  setUp(() {
    extractor = MarkdownTextExtractor();
  });

  group('MarkdownTextExtractor', () {
    test('extracts plain text from simple paragraph', () {
      expect(extractor.extract('Hello world'), 'Hello world');
    });

    test('strips bold markers', () {
      expect(extractor.extract('**bold text**'), 'bold text');
    });

    test('strips italic markers', () {
      expect(extractor.extract('*italic text*'), 'italic text');
    });

    test('extracts text from headings', () {
      final result = extractor.extract('# Heading 1\n## Heading 2');
      expect(result, contains('Heading 1'));
      expect(result, contains('Heading 2'));
    });

    test('extracts text from lists', () {
      final result = extractor.extract('- item 1\n- item 2\n- item 3');
      expect(result, contains('item 1'));
      expect(result, contains('item 2'));
      expect(result, contains('item 3'));
    });

    test('extracts text from code blocks', () {
      final result = extractor.extract('```\ncode here\n```');
      expect(result, contains('code here'));
    });

    test('extracts link text without URL', () {
      final result = extractor.extract('[click me](https://example.com)');
      expect(result, contains('click me'));
    });

    test('handles empty input', () {
      expect(extractor.extract(''), '');
    });

    test('handles multiple paragraphs', () {
      final result = extractor.extract('First paragraph.\n\nSecond paragraph.');
      expect(result, contains('First paragraph.'));
      expect(result, contains('Second paragraph.'));
    });

    test('can be reused for multiple extractions', () {
      final first = extractor.extract('first');
      final second = extractor.extract('second');
      expect(first, 'first');
      expect(second, 'second');
    });
  });
}
