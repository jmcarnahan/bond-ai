import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/thread_model.dart';

void main() {
  group('Thread.fromJson', () {
    test('parses all fields including lastAgentId and lastAgentName', () {
      final json = {
        'id': 'thread_1',
        'name': 'Test Thread',
        'description': 'A description',
        'created_at': '2025-01-01T00:00:00.000Z',
        'updated_at': '2025-01-02T00:00:00.000Z',
        'last_agent_id': 'agent_abc',
        'last_agent_name': 'My Agent',
      };

      final thread = Thread.fromJson(json);

      expect(thread.id, 'thread_1');
      expect(thread.name, 'Test Thread');
      expect(thread.description, 'A description');
      expect(thread.lastAgentId, 'agent_abc');
      expect(thread.lastAgentName, 'My Agent');
    });

    test('handles null lastAgentId and lastAgentName', () {
      final json = {
        'id': 'thread_2',
        'name': 'Thread Without Agent',
        'description': null,
        'created_at': null,
        'updated_at': null,
        'last_agent_id': null,
        'last_agent_name': null,
      };

      final thread = Thread.fromJson(json);

      expect(thread.lastAgentId, isNull);
      expect(thread.lastAgentName, isNull);
    });

    test('handles missing lastAgentId and lastAgentName keys', () {
      final json = {
        'id': 'thread_3',
        'name': 'Old Thread',
      };

      final thread = Thread.fromJson(json);

      expect(thread.lastAgentId, isNull);
      expect(thread.lastAgentName, isNull);
    });
  });

  group('Thread.copyWith', () {
    final base = Thread(
      id: 'thread_1',
      name: 'Original',
      lastAgentId: 'agent_old',
      lastAgentName: 'Old Agent',
    );

    test('preserves lastAgentId when not specified', () {
      final copy = base.copyWith(name: 'Renamed');

      expect(copy.name, 'Renamed');
      expect(copy.lastAgentId, 'agent_old');
      expect(copy.lastAgentName, 'Old Agent');
    });

    test('replaces lastAgentId when specified', () {
      final copy = base.copyWith(
        lastAgentId: 'agent_new',
        lastAgentName: 'New Agent',
      );

      expect(copy.lastAgentId, 'agent_new');
      expect(copy.lastAgentName, 'New Agent');
    });

    test('clears lastAgentId with clearLastAgentId flag', () {
      final copy = base.copyWith(clearLastAgentId: true);

      expect(copy.lastAgentId, isNull);
      // lastAgentName preserved unless also cleared
      expect(copy.lastAgentName, 'Old Agent');
    });

    test('clears lastAgentName with clearLastAgentName flag', () {
      final copy = base.copyWith(clearLastAgentName: true);

      expect(copy.lastAgentId, 'agent_old');
      expect(copy.lastAgentName, isNull);
    });

    test('clears both agent fields together', () {
      final copy = base.copyWith(
        clearLastAgentId: true,
        clearLastAgentName: true,
      );

      expect(copy.lastAgentId, isNull);
      expect(copy.lastAgentName, isNull);
    });
  });

  group('Thread.toJson', () {
    test('includes lastAgentId and lastAgentName', () {
      final thread = Thread(
        id: 'thread_1',
        name: 'Test',
        lastAgentId: 'agent_abc',
        lastAgentName: 'My Agent',
      );

      final json = thread.toJson();

      expect(json['last_agent_id'], 'agent_abc');
      expect(json['last_agent_name'], 'My Agent');
    });

    test('includes null values for absent agent fields', () {
      final thread = Thread(
        id: 'thread_1',
        name: 'Test',
      );

      final json = thread.toJson();

      expect(json.containsKey('last_agent_id'), isTrue);
      expect(json['last_agent_id'], isNull);
      expect(json.containsKey('last_agent_name'), isTrue);
      expect(json['last_agent_name'], isNull);
    });
  });

  group('Thread equality', () {
    test('threads with different lastAgentId are not equal', () {
      final a = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_a');
      final b = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_b');

      expect(a, isNot(equals(b)));
    });

    test('threads with same lastAgentId are equal', () {
      final a = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_a');
      final b = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_a');

      expect(a, equals(b));
    });

    test('threads with null vs non-null lastAgentId are not equal', () {
      final a = Thread(id: 'thread_1', name: 'Test');
      final b = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_a');

      expect(a, isNot(equals(b)));
    });

    test('hashCode differs for threads with different lastAgentId', () {
      final a = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_a');
      final b = Thread(id: 'thread_1', name: 'Test', lastAgentId: 'agent_b');

      expect(a.hashCode, isNot(equals(b.hashCode)));
    });
  });

  group('Thread.fromJson roundtrip', () {
    test('toJson then fromJson preserves agent fields', () {
      final original = Thread(
        id: 'thread_1',
        name: 'Test',
        lastAgentId: 'agent_abc',
        lastAgentName: 'My Agent',
      );

      final json = original.toJson();
      final restored = Thread.fromJson(json);

      expect(restored.lastAgentId, original.lastAgentId);
      expect(restored.lastAgentName, original.lastAgentName);
    });
  });
}
