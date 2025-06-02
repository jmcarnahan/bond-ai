import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/message_model.dart';

void main() {
  group('Message Model Tests', () {
    test('constructor should create message with required fields', () {
      const message = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
      );

      expect(message.id, equals('test-id'));
      expect(message.type, equals('text'));
      expect(message.role, equals('user'));
      expect(message.content, equals('Hello World'));
      expect(message.imageData, isNull);
      expect(message.isError, isFalse);
    });

    test('constructor should create message with all fields', () {
      const message = Message(
        id: 'test-id',
        type: 'image_file',
        role: 'assistant',
        content: '[Image]',
        imageData: 'base64data',
        isError: true,
      );

      expect(message.id, equals('test-id'));
      expect(message.type, equals('image_file'));
      expect(message.role, equals('assistant'));
      expect(message.content, equals('[Image]'));
      expect(message.imageData, equals('base64data'));
      expect(message.isError, isTrue);
    });

    test('fromJson should create message from valid JSON', () {
      final json = {
        'id': 'test-id',
        'type': 'text',
        'role': 'user',
        'content': 'Hello World',
        'image_data': null,
        'is_error': false,
      };

      final message = Message.fromJson(json);

      expect(message.id, equals('test-id'));
      expect(message.type, equals('text'));
      expect(message.role, equals('user'));
      expect(message.content, equals('Hello World'));
      expect(message.imageData, isNull);
      expect(message.isError, isFalse);
    });

    test('fromJson should handle missing optional fields', () {
      final json = {
        'id': 'test-id',
        'type': 'text',
        'role': 'user',
        'content': 'Hello World',
      };

      final message = Message.fromJson(json);

      expect(message.id, equals('test-id'));
      expect(message.type, equals('text'));
      expect(message.role, equals('user'));
      expect(message.content, equals('Hello World'));
      expect(message.imageData, isNull);
      expect(message.isError, isFalse);
    });

    test('fromJson should handle image data', () {
      final json = {
        'id': 'test-id',
        'type': 'image_file',
        'role': 'assistant',
        'content': '[Image]',
        'image_data': 'base64data',
        'is_error': false,
      };

      final message = Message.fromJson(json);

      expect(message.id, equals('test-id'));
      expect(message.type, equals('image_file'));
      expect(message.role, equals('assistant'));
      expect(message.content, equals('[Image]'));
      expect(message.imageData, equals('base64data'));
      expect(message.isError, isFalse);
    });

    test('fromJson should handle error messages', () {
      final json = {
        'id': 'test-id',
        'type': 'text',
        'role': 'assistant',
        'content': 'Error occurred',
        'is_error': true,
      };

      final message = Message.fromJson(json);

      expect(message.id, equals('test-id'));
      expect(message.type, equals('text'));
      expect(message.role, equals('assistant'));
      expect(message.content, equals('Error occurred'));
      expect(message.isError, isTrue);
    });

    test('toJson should convert message to JSON correctly', () {
      const message = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
        imageData: null,
        isError: false,
      );

      final json = message.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['type'], equals('text'));
      expect(json['role'], equals('user'));
      expect(json['content'], equals('Hello World'));
      expect(json['image_data'], isNull);
      expect(json['is_error'], isFalse);
    });

    test('toJson should handle image data', () {
      const message = Message(
        id: 'test-id',
        type: 'image_file',
        role: 'assistant',
        content: '[Image]',
        imageData: 'base64data',
        isError: false,
      );

      final json = message.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['type'], equals('image_file'));
      expect(json['role'], equals('assistant'));
      expect(json['content'], equals('[Image]'));
      expect(json['image_data'], equals('base64data'));
      expect(json['is_error'], isFalse);
    });

    test('toJson should handle error messages', () {
      const message = Message(
        id: 'test-id',
        type: 'text',
        role: 'assistant',
        content: 'Error occurred',
        isError: true,
      );

      final json = message.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['type'], equals('text'));
      expect(json['role'], equals('assistant'));
      expect(json['content'], equals('Error occurred'));
      expect(json['is_error'], isTrue);
    });

    test('copyWith should create new message with updated fields', () {
      const originalMessage = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
      );

      final copiedMessage = originalMessage.copyWith(
        content: 'Updated content',
        isError: true,
      );

      expect(copiedMessage.id, equals('test-id'));
      expect(copiedMessage.type, equals('text'));
      expect(copiedMessage.role, equals('user'));
      expect(copiedMessage.content, equals('Updated content'));
      expect(copiedMessage.imageData, isNull);
      expect(copiedMessage.isError, isTrue);
      
      expect(originalMessage.content, equals('Hello World'));
      expect(originalMessage.isError, isFalse);
    });

    test('copyWith should preserve original fields when not specified', () {
      const originalMessage = Message(
        id: 'test-id',
        type: 'image_file',
        role: 'assistant',
        content: '[Image]',
        imageData: 'base64data',
        isError: false,
      );

      final copiedMessage = originalMessage.copyWith(role: 'user');

      expect(copiedMessage.id, equals('test-id'));
      expect(copiedMessage.type, equals('image_file'));
      expect(copiedMessage.role, equals('user'));
      expect(copiedMessage.content, equals('[Image]'));
      expect(copiedMessage.imageData, equals('base64data'));
      expect(copiedMessage.isError, isFalse);
    });

    test('copyWith should handle null values correctly', () {
      const originalMessage = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
        imageData: 'some-data',
        isError: true,
      );

      final copiedMessage = originalMessage.copyWith();

      expect(copiedMessage.id, equals(originalMessage.id));
      expect(copiedMessage.type, equals(originalMessage.type));
      expect(copiedMessage.role, equals(originalMessage.role));
      expect(copiedMessage.content, equals(originalMessage.content));
      expect(copiedMessage.imageData, equals(originalMessage.imageData));
      expect(copiedMessage.isError, equals(originalMessage.isError));
    });

    test('equality should work for identical messages', () {
      const message1 = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
      );

      const message2 = Message(
        id: 'test-id',
        type: 'text',
        role: 'user',
        content: 'Hello World',
      );

      expect(message1.id, equals(message2.id));
      expect(message1.type, equals(message2.type));
      expect(message1.role, equals(message2.role));
      expect(message1.content, equals(message2.content));
      expect(message1.imageData, equals(message2.imageData));
      expect(message1.isError, equals(message2.isError));
    });
  });
}