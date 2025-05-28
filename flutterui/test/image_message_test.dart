import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/utils/bond_message_parser.dart';
import 'package:flutterui/data/models/message_model.dart';

void main() {
  group('Image Message Support Tests', () {
    test('BondMessageParser should parse image_file messages correctly', () {
      // Sample XML with base64 image data (shortened for test)
      const xmlString = '''
        <_bondmessage id="msg_123" type="image_file" role="assistant" is_done="true">
          data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
        </_bondmessage>
      ''';

      final parsed = BondMessageParser.parseFirstFoundBondMessage(xmlString);

      expect(parsed.id, equals('msg_123'));
      expect(parsed.type, equals('image_file'));
      expect(parsed.role, equals('assistant'));
      expect(parsed.content, equals('[Image]'));
      expect(parsed.imageData, isNotNull);
      expect(parsed.imageData, equals('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='));
      expect(parsed.parsingHadError, isFalse);
    });

    test('BondMessageParser should handle JPEG image format', () {
      const xmlString = '''
        <_bondmessage id="msg_456" type="image_file" role="assistant">
          data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gNzUK/9sAQwAIBgYHBgUIBwcHCQkICgwUDQwLCwwZEhMPFB0aHx4dGhwcICQuJyAiLCMcHCg3KSwwMTQ0NB8nOT04MjwuMzQy/9sAQwEJCQkMCwwYDQ0YMiEcITIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBkQgUQqGxwdHwFSNCkeHxMzJiYnLRQwp0
        </_bondmessage>
      ''';

      final parsed = BondMessageParser.parseFirstFoundBondMessage(xmlString);

      expect(parsed.type, equals('image_file'));
      expect(parsed.content, equals('[Image]'));
      expect(parsed.imageData, isNotNull);
      expect(parsed.imageData, startsWith('/9j/4AAQSkZJRgABAQEAYABgAAD'));
    });

    test('BondMessageParser should handle text messages normally', () {
      const xmlString = '''
        <_bondmessage id="msg_789" type="text" role="assistant">
          Hello, this is a normal text message.
        </_bondmessage>
      ''';

      final parsed = BondMessageParser.parseFirstFoundBondMessage(xmlString);

      expect(parsed.type, equals('text'));
      expect(parsed.content, equals('Hello, this is a normal text message.'));
      expect(parsed.imageData, isNull);
    });

    test('Message model should handle image data correctly', () {
      const message = Message(
        id: 'test_msg',
        type: 'image_file',
        role: 'assistant',
        content: '[Image]',
        imageData: 'base64ImageDataHere',
      );

      expect(message.type, equals('image_file'));
      expect(message.imageData, equals('base64ImageDataHere'));
      
      // Test JSON serialization
      final json = message.toJson();
      expect(json['image_data'], equals('base64ImageDataHere'));
      
      // Test JSON deserialization
      final fromJson = Message.fromJson(json);
      expect(fromJson.imageData, equals('base64ImageDataHere'));
      expect(fromJson.type, equals('image_file'));
    });

    test('Message copyWith should handle imageData', () {
      const original = Message(
        id: 'test',
        type: 'text',
        role: 'user',
        content: 'Hello',
      );

      final withImage = original.copyWith(
        type: 'image_file',
        imageData: 'base64Data',
        content: '[Image]',
      );

      expect(withImage.type, equals('image_file'));
      expect(withImage.imageData, equals('base64Data'));
      expect(withImage.content, equals('[Image]'));
      expect(withImage.id, equals('test')); // Original id preserved
    });

    test('BondMessageParser should handle malformed image data gracefully', () {
      const xmlString = '''
        <_bondmessage id="msg_error" type="image_file" role="assistant">
          This is not valid base64 image data
        </_bondmessage>
      ''';

      final parsed = BondMessageParser.parseFirstFoundBondMessage(xmlString);

      expect(parsed.type, equals('image_file'));
      expect(parsed.content, equals('This is not valid base64 image data'));
      expect(parsed.imageData, isNull);
    });

    test('BondMessageParser should parse multiple messages correctly', () {
      const xmlString = '''
        <_bondmessage id="msg_system" type="text" role="system" is_error="true">
          An error occurred: Server error
        </_bondmessage>
        <_bondmessage id="msg_assistant1" type="text" role="assistant">
          Here is some text content.
        </_bondmessage>
        <_bondmessage id="msg_assistant2" type="image_file" role="assistant">
          data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
        </_bondmessage>
        <_bondmessage id="msg_system2" type="text" role="system">
          Done.
        </_bondmessage>
      ''';

      final allMessages = BondMessageParser.parseAllBondMessages(xmlString);

      expect(allMessages.length, equals(4));
      
      // System error message
      expect(allMessages[0].id, equals('msg_system'));
      expect(allMessages[0].role, equals('system'));
      expect(allMessages[0].isErrorAttribute, isTrue);
      expect(allMessages[0].content, equals('An error occurred: Server error'));
      
      // Assistant text message
      expect(allMessages[1].id, equals('msg_assistant1'));
      expect(allMessages[1].role, equals('assistant'));
      expect(allMessages[1].type, equals('text'));
      expect(allMessages[1].content, equals('Here is some text content.'));
      
      // Assistant image message
      expect(allMessages[2].id, equals('msg_assistant2'));
      expect(allMessages[2].role, equals('assistant'));
      expect(allMessages[2].type, equals('image_file'));
      expect(allMessages[2].content, equals('[Image]'));
      expect(allMessages[2].imageData, isNotNull);
      
      // System done message
      expect(allMessages[3].id, equals('msg_system2'));
      expect(allMessages[3].role, equals('system'));
      expect(allMessages[3].content, equals('Done.'));
    });

    test('extractStreamingBodyContent should prioritize assistant messages', () {
      const xmlString = '''
        <_bondmessage id="msg_system" type="text" role="system" is_error="true">
          An error occurred: Server error
        </_bondmessage>
        <_bondmessage id="msg_assistant" type="text" role="assistant">
          This is the assistant response.
        </_bondmessage>
      ''';

      final extracted = BondMessageParser.extractStreamingBodyContent(xmlString);
      
      // Should extract the assistant message, not the system error
      expect(extracted, equals('This is the assistant response.'));
    });

    test('extractStreamingBodyContent should handle system-only messages', () {
      const xmlString = '''
        <_bondmessage id="msg_system" type="text" role="system" is_error="true">
          An error occurred: Server error
        </_bondmessage>
      ''';

      final extracted = BondMessageParser.extractStreamingBodyContent(xmlString);
      
      // Should return placeholder when only system messages are present
      expect(extracted, equals('...'));
    });

    test('Multiple assistant messages (text + image) should be parsed correctly', () {
      const xmlString = '''
        <_bondmessage id="msg_text" type="text" role="assistant">
          Here's the analysis of your data:
        </_bondmessage>
        <_bondmessage id="msg_image" type="image_file" role="assistant">
          data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
        </_bondmessage>
      ''';

      final allMessages = BondMessageParser.parseAllBondMessages(xmlString);
      
      // Should have exactly 2 assistant messages
      final assistantMessages = allMessages.where((msg) => msg.role == 'assistant').toList();
      expect(assistantMessages.length, equals(2));
      
      // First message should be text
      expect(assistantMessages[0].type, equals('text'));
      expect(assistantMessages[0].content, equals('Here\'s the analysis of your data:'));
      expect(assistantMessages[0].imageData, isNull);
      
      // Second message should be image
      expect(assistantMessages[1].type, equals('image_file'));
      expect(assistantMessages[1].content, equals('[Image]'));
      expect(assistantMessages[1].imageData, isNotNull);
      expect(assistantMessages[1].imageData, equals('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='));
    });

    test('StreamingBodyContent should extract first assistant message from multi-message stream', () {
      const xmlString = '''
        <_bondmessage id="msg_text" type="text" role="assistant">
          Here's the analysis:
        </_bondmessage>
        <_bondmessage id="msg_image" type="image_file" role="assistant">
          data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
        </_bondmessage>
      ''';

      final extracted = BondMessageParser.extractStreamingBodyContent(xmlString);
      
      // Should extract the first assistant message for streaming display
      expect(extracted, equals('Here\'s the analysis:'));
    });
  });
}