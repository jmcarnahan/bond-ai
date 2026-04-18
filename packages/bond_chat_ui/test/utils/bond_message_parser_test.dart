import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

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

    test('returns "..." for empty content', () {
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false" is_done="false">'
          '</_bondmessage>';

      final result = BondMessageParser.extractStreamingBodyContent(xml);
      expect(result, '...');
    });

    test('returns "..." for no bondmessage tags', () {
      expect(BondMessageParser.extractStreamingBodyContent('random text'), '...');
    });

    test('returns "..." for system messages', () {
      final xml = '<_bondmessage role="system">system content</_bondmessage>';
      expect(BondMessageParser.extractStreamingBodyContent(xml), '...');
    });
  });

  group('parseAllBondMessages', () {
    test('parses single message', () {
      final xml = '<_bondmessage id="1" thread_id="t" agent_id="a" '
          'type="text" role="assistant" is_error="false">'
          'Compare: x &lt; y and a &gt; b'
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].content, 'Compare: x < y and a > b');
      expect(messages[0].id, '1');
      expect(messages[0].threadId, 't');
      expect(messages[0].agentId, 'a');
      expect(messages[0].role, 'assistant');
      expect(messages[0].parsingHadError, false);
    });

    test('parses multiple messages', () {
      final xml = '<_bondmessage id="1" thread_id="t" type="text" role="user">hello</_bondmessage>'
          '<_bondmessage id="2" thread_id="t" type="text" role="assistant">hi</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 2);
      expect(messages[0].role, 'user');
      expect(messages[1].role, 'assistant');
    });

    test('extracts image data from PNG', () {
      final xml = '<_bondmessage id="1" thread_id="t" type="image" role="assistant">'
          'data:image/png;base64,iVBORw0KGgo='
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].imageData, 'iVBORw0KGgo=');
      expect(messages[0].content, '[Image]');
    });

    test('extracts image data from JPEG', () {
      final xml = '<_bondmessage id="1" thread_id="t" type="image_file" role="assistant">'
          'data:image/jpeg;base64,/9j/4AAQ='
          '</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].imageData, '/9j/4AAQ=');
      expect(messages[0].content, '[Image]');
    });

    test('handles XML parse error with parsingHadError', () {
      final xml = '<_bondmessage id="1" role="assistant">content with < unescaped';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages.length, 1);
      expect(messages[0].parsingHadError, true);
    });

    test('returns empty list for empty input', () {
      expect(BondMessageParser.parseAllBondMessages(''), isEmpty);
      expect(BondMessageParser.parseAllBondMessages('  '), isEmpty);
    });

    test('parses is_error attribute', () {
      final xml = '<_bondmessage id="1" thread_id="t" type="text" role="assistant" is_error="true">'
          'Error occurred</_bondmessage>';

      final messages = BondMessageParser.parseAllBondMessages(xml);
      expect(messages[0].isErrorAttribute, true);
    });
  });

  group('stripAllTags', () {
    test('strips HTML/XML tags', () {
      expect(BondMessageParser.stripAllTags('<p>hello</p>'), 'hello');
    });

    test('strips nested tags', () {
      expect(BondMessageParser.stripAllTags('<div><span>text</span></div>'), 'text');
    });

    test('returns plain text unchanged', () {
      expect(BondMessageParser.stripAllTags('no tags here'), 'no tags here');
    });
  });
}
