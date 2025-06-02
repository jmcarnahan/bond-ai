import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/utils/bond_message_parser.dart';

void main() {
  group('ParsedBondMessage Tests', () {
    test('constructor should create object with default values', () {
      final message = ParsedBondMessage(content: 'test content');
      
      expect(message.id, equals(''));
      expect(message.type, equals(''));
      expect(message.role, equals(''));
      expect(message.content, equals('test content'));
      expect(message.imageData, isNull);
      expect(message.isErrorAttribute, isFalse);
      expect(message.parsingHadError, isFalse);
    });

    test('constructor should create object with all provided values', () {
      final message = ParsedBondMessage(
        id: 'test-id',
        type: 'text',
        role: 'assistant',
        content: 'test content',
        imageData: 'base64data',
        isErrorAttribute: true,
        parsingHadError: true,
      );
      
      expect(message.id, equals('test-id'));
      expect(message.type, equals('text'));
      expect(message.role, equals('assistant'));
      expect(message.content, equals('test content'));
      expect(message.imageData, equals('base64data'));
      expect(message.isErrorAttribute, isTrue);
      expect(message.parsingHadError, isTrue);
    });
  });

  group('BondMessageParser.parseFirstFoundBondMessage Tests', () {
    test('should return error for empty string', () {
      final result = BondMessageParser.parseFirstFoundBondMessage('');
      
      expect(result.content, equals('Error: Empty response.'));
      expect(result.parsingHadError, isTrue);
      expect(result.isErrorAttribute, isTrue);
    });

    test('should return error for whitespace only string', () {
      final result = BondMessageParser.parseFirstFoundBondMessage('   ');
      
      expect(result.content, equals('Error: Empty response.'));
      expect(result.parsingHadError, isTrue);
      expect(result.isErrorAttribute, isTrue);
    });

    test('should parse basic bondmessage successfully', () {
      const xmlString = '<_bondmessage id="1" type="text" role="assistant">Hello World</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.id, equals('1'));
      expect(result.type, equals('text'));
      expect(result.role, equals('assistant'));
      expect(result.content, equals('Hello World'));
      expect(result.isErrorAttribute, isFalse);
      expect(result.parsingHadError, isFalse);
    });

    test('should handle missing attributes gracefully', () {
      const xmlString = '<_bondmessage>Hello World</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.id, equals(''));
      expect(result.type, equals(''));
      expect(result.role, equals(''));
      expect(result.content, equals('Hello World'));
      expect(result.isErrorAttribute, isFalse);
      expect(result.parsingHadError, isFalse);
    });

    test('should parse error attribute correctly', () {
      const xmlString = '<_bondmessage is_error="true">Error message</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.content, equals('Error message'));
      expect(result.isErrorAttribute, isTrue);
      expect(result.parsingHadError, isFalse);
    });

    test('should handle PNG image file type', () {
      const xmlString = '<_bondmessage type="image_file">data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.type, equals('image_file'));
      expect(result.content, equals('[Image]'));
      expect(result.imageData, equals('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='));
      expect(result.parsingHadError, isFalse);
    });

    test('should handle JPEG image file type', () {
      const xmlString = '<_bondmessage type="image_file">data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.type, equals('image_file'));
      expect(result.content, equals('[Image]'));
      expect(result.imageData, equals('/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k='));
      expect(result.parsingHadError, isFalse);
    });

    test('should handle generic data:image format', () {
      const xmlString = '<_bondmessage type="image_file">data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7</_bondmessage>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.type, equals('image_file'));
      expect(result.content, equals('[Image]'));
      expect(result.imageData, equals('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'));
      expect(result.parsingHadError, isFalse);
    });

    test('should return error for no bondmessage element found', () {
      const xmlString = '<othertag>Some content</othertag>';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.content, equals('Error: No <_bondmessage> element found in the provided XML string.'));
      expect(result.parsingHadError, isTrue);
      expect(result.isErrorAttribute, isTrue);
    });

    test('should return error for invalid XML', () {
      const xmlString = '<_bondmessage>Unclosed tag';
      final result = BondMessageParser.parseFirstFoundBondMessage(xmlString);
      
      expect(result.content, startsWith('Error parsing XML:'));
      expect(result.parsingHadError, isTrue);
      expect(result.isErrorAttribute, isTrue);
    });
  });

  group('BondMessageParser.extractStreamingBodyContent Tests', () {
    test('should return default placeholder for empty string', () {
      final result = BondMessageParser.extractStreamingBodyContent('');
      expect(result, equals('...'));
    });

    test('should extract assistant message content', () {
      const xmlString = '<_bondmessage role="assistant">Hello World</_bondmessage>';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('Hello World'));
    });

    test('should extract incomplete assistant message content', () {
      const xmlString = '<_bondmessage role="assistant">Hello World';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('Hello World'));
    });

    test('should skip system messages', () {
      const xmlString = '<_bondmessage role="system">System message</_bondmessage>';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('...'));
    });

    test('should strip HTML tags from content', () {
      const xmlString = '<_bondmessage role="assistant">Hello <b>World</b></_bondmessage>';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('Hello World'));
    });

    test('should fallback to any message if no assistant message found', () {
      const xmlString = '<_bondmessage role="user">User message</_bondmessage>';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('User message'));
    });

    test('should handle empty content gracefully', () {
      const xmlString = '<_bondmessage role="assistant"></_bondmessage>';
      final result = BondMessageParser.extractStreamingBodyContent(xmlString);
      expect(result, equals('...'));
    });
  });

  group('BondMessageParser.parseAllBondMessages Tests', () {
    test('should return empty list for empty string', () {
      final result = BondMessageParser.parseAllBondMessages('');
      expect(result, isEmpty);
    });

    test('should parse single message', () {
      const xmlString = '<_bondmessage id="1" role="assistant">Hello</_bondmessage>';
      final result = BondMessageParser.parseAllBondMessages(xmlString);
      
      expect(result, hasLength(1));
      expect(result[0].id, equals('1'));
      expect(result[0].role, equals('assistant'));
      expect(result[0].content, equals('Hello'));
    });

    test('should parse multiple messages', () {
      const xmlString = '''
        <_bondmessage id="1" role="user">User message</_bondmessage>
        <_bondmessage id="2" role="assistant">Assistant message</_bondmessage>
      ''';
      final result = BondMessageParser.parseAllBondMessages(xmlString);
      
      expect(result, hasLength(2));
      expect(result[0].id, equals('1'));
      expect(result[0].role, equals('user'));
      expect(result[0].content, equals('User message'));
      expect(result[1].id, equals('2'));
      expect(result[1].role, equals('assistant'));
      expect(result[1].content, equals('Assistant message'));
    });

    test('should handle image messages in multiple parsing', () {
      const xmlString = '''
        <_bondmessage id="1" type="text" role="user">Hello</_bondmessage>
        <_bondmessage id="2" type="image_file" role="assistant">data:image/png;base64,iVBORw0KGgo</_bondmessage>
      ''';
      final result = BondMessageParser.parseAllBondMessages(xmlString);
      
      expect(result, hasLength(2));
      expect(result[0].type, equals('text'));
      expect(result[0].content, equals('Hello'));
      expect(result[1].type, equals('image_file'));
      expect(result[1].content, equals('[Image]'));
      expect(result[1].imageData, equals('iVBORw0KGgo'));
    });

    test('should return error message for invalid XML', () {
      const xmlString = '<_bondmessage>Unclosed';
      final result = BondMessageParser.parseAllBondMessages(xmlString);
      
      expect(result, hasLength(1));
      expect(result[0].content, startsWith('Error parsing XML:'));
      expect(result[0].parsingHadError, isTrue);
      expect(result[0].isErrorAttribute, isTrue);
    });
  });

  group('BondMessageParser.stripAllTags Tests', () {
    test('should strip HTML tags', () {
      final result = BondMessageParser.stripAllTags('Hello <b>World</b>');
      expect(result, equals('Hello World'));
    });

    test('should strip XML tags', () {
      final result = BondMessageParser.stripAllTags('<message>Hello <strong>World</strong></message>');
      expect(result, equals('Hello World'));
    });

    test('should handle self-closing tags', () {
      final result = BondMessageParser.stripAllTags('Hello <br/> World');
      expect(result, equals('Hello  World'));
    });

    test('should return trimmed result', () {
      final result = BondMessageParser.stripAllTags('  <div>Hello</div>  ');
      expect(result, equals('Hello'));
    });

    test('should handle string with no tags', () {
      final result = BondMessageParser.stripAllTags('Hello World');
      expect(result, equals('Hello World'));
    });

    test('should handle empty string', () {
      final result = BondMessageParser.stripAllTags('');
      expect(result, equals(''));
    });

    test('should handle complex nested tags', () {
      final result = BondMessageParser.stripAllTags('<div><p>Hello <span><strong>World</strong></span></p></div>');
      expect(result, equals('Hello World'));
    });
  });
}