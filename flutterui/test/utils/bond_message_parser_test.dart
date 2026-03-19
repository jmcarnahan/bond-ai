import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/utils/bond_message_parser.dart';

void main() {
  group('unescapeXmlEntities', () {
    test('unescapes &lt; to <', () {
      expect(BondMessageParser.unescapeXmlEntities('x &lt; y'), 'x < y');
    });

    test('unescapes &gt; to >', () {
      expect(BondMessageParser.unescapeXmlEntities('x &gt; y'), 'x > y');
    });

    test('unescapes &amp; to &', () {
      expect(BondMessageParser.unescapeXmlEntities('x &amp; y'), 'x & y');
    });

    test('unescapes &quot; and &apos;', () {
      expect(
        BondMessageParser.unescapeXmlEntities('say &quot;hello&quot; &amp; &apos;bye&apos;'),
        'say "hello" & \'bye\'',
      );
    });

    test('&amp;lt; stays &lt; (amp unescaped last)', () {
      // The string "&amp;lt;" should become "&lt;" not "<"
      expect(BondMessageParser.unescapeXmlEntities('&amp;lt;'), '&lt;');
    });

    test('returns plain text unchanged', () {
      expect(BondMessageParser.unescapeXmlEntities('hello world'), 'hello world');
    });
  });

  group('extractStreamingBodyContent', () {
    test('unescapes XML entities in assistant content', () {
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          'if x &lt; y &amp;&amp; z &gt; 0</_bondmessage>';

      final result = BondMessageParser.extractStreamingBodyContent(xml);
      expect(result, 'if x < y && z > 0');
    });

    test('unescapes XML entities in non-assistant fallback path', () {
      // This hits the else branch (no role="assistant" in the tag, but has content)
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="user" is_error="false" is_done="false">'
          '&lt;script&gt;</_bondmessage>';

      final result = BondMessageParser.extractStreamingBodyContent(xml);
      expect(result, '<script>');
    });

    test('returns "..." for empty content', () {
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          '</_bondmessage>';

      final result = BondMessageParser.extractStreamingBodyContent(xml);
      expect(result, '...');
    });
  });

  group('parseAllBondMessages', () {
    test('unescapes XML entities in parsed message content', () {
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          'Compare: x &lt; y and a &gt; b'
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].content, 'Compare: x < y and a > b');
      expect(messages[0].parsingHadError, false);
    });

    test('full roundtrip with escaped content', () {
      final xml = '<_bondmessage id="msg-1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          'x &lt; y &amp;&amp; z &gt; 0'
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      // XML parser handles entity unescaping natively
      expect(messages[0].content, 'x < y && z > 0');
    });

    test('literal entity string preserved (no double-unescape)', () {
      // LLM outputs literal "&lt;" → backend escapes to "&amp;lt;"
      // XML parser unescapes to "&lt;" — should stay as "&lt;", not become "<"
      final xml = '<_bondmessage id="msg-1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          'The entity &amp;lt; means less-than'
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].content, 'The entity &lt; means less-than');
    });

    test('handles XML parse error with parsingHadError', () {
      // Malformed XML - unclosed tag with special chars
      final xml = '<_bondmessage id="1" role="assistant">content with < unescaped';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].parsingHadError, true);
    });
  });
}
