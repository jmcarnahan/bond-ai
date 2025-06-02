import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/thread_model.dart';

void main() {
  group('Thread Model Tests', () {
    test('constructor should create thread with required fields', () {
      const thread = Thread(
            id: 'test-id',
            name: 'Test Thread',
          );

      expect(thread.id, equals('test-id'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, isNull);
    });

    test('constructor should create thread with all fields', () {
      const thread = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      expect(thread.id, equals('test-id'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, equals('Test description'));
    });

    test('fromJson should create thread from valid JSON', () {
      final json = {
        'id': 'test-id',
        'name': 'Test Thread',
        'description': 'Test description',
      };

      final thread = Thread.fromJson(json);

      expect(thread.id, equals('test-id'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, equals('Test description'));
    });

    test('fromJson should handle missing optional fields', () {
      final json = {
        'id': 'test-id',
        'name': 'Test Thread',
      };

      final thread = Thread.fromJson(json);

      expect(thread.id, equals('test-id'));
      expect(thread.name, equals('Test Thread'));
      expect(thread.description, isNull);
    });

    test('toJson should convert thread to JSON correctly', () {
      const thread = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      final json = thread.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['name'], equals('Test Thread'));
      expect(json['description'], equals('Test description'));
    });

    test('toJson should handle null description', () {
      const thread = Thread(
            id: 'test-id',
            name: 'Test Thread',
          );

      final json = thread.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['name'], equals('Test Thread'));
      expect(json['description'], isNull);
    });

    test('equality should work correctly for identical threads', () {
      const thread1 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      const thread2 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      expect(thread1, equals(thread2));
    });

    test('equality should work correctly for different threads', () {
      const thread1 = Thread(
            id: 'test-id-1',
            name: 'Test Thread',
          );

      const thread2 = Thread(
            id: 'test-id-2',
            name: 'Test Thread',
          );

      expect(thread1, isNot(equals(thread2)));
    });

    test('equality should handle null descriptions correctly', () {
      const thread1 = Thread(
            id: 'test-id',
            name: 'Test Thread',
          );

      const thread2 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: null,
      );

      expect(thread1, equals(thread2));
    });

    test('equality should differentiate threads with different descriptions', () {
      const thread1 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Description 1',
      );

      const thread2 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Description 2',
      );

      expect(thread1, isNot(equals(thread2)));
    });

    test('hashCode should be consistent for identical threads', () {
      const thread1 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      const thread2 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      expect(thread1.hashCode, equals(thread2.hashCode));
    });

    test('hashCode should be different for different threads', () {
      const thread1 = Thread(
            id: 'test-id-1',
            name: 'Test Thread',
          );

      const thread2 = Thread(
            id: 'test-id-2',
            name: 'Test Thread',
          );

      expect(thread1.hashCode, isNot(equals(thread2.hashCode)));
    });

    test('hashCode should handle null descriptions', () {
      const thread1 = Thread(
            id: 'test-id',
            name: 'Test Thread',
          );

      const thread2 = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: null,
      );

      expect(thread1.hashCode, equals(thread2.hashCode));
    });

    test('should handle JSON roundtrip correctly', () {
      const originalThread = Thread(
        id: 'test-id',
        name: 'Test Thread',
        description: 'Test description',
      );

      final json = originalThread.toJson();
      final reconstructedThread = Thread.fromJson(json);

      expect(reconstructedThread, equals(originalThread));
      expect(reconstructedThread.id, equals(originalThread.id));
      expect(reconstructedThread.name, equals(originalThread.name));
      expect(reconstructedThread.description, equals(originalThread.description));
    });

    test('should handle JSON roundtrip with null description', () {
      const originalThread = Thread(
            id: 'test-id',
            name: 'Test Thread',
          );

      final json = originalThread.toJson();
      final reconstructedThread = Thread.fromJson(json);

      expect(reconstructedThread, equals(originalThread));
      expect(reconstructedThread.id, equals(originalThread.id));
      expect(reconstructedThread.name, equals(originalThread.name));
      expect(reconstructedThread.description, isNull);
    });
  });
}