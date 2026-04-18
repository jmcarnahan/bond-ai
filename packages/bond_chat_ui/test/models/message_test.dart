import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('Message', () {
    test('constructs with required fields and defaults', () {
      const msg = Message(id: '1', type: 'text', role: 'user', content: 'hi');
      expect(msg.id, '1');
      expect(msg.type, 'text');
      expect(msg.role, 'user');
      expect(msg.content, 'hi');
      expect(msg.imageData, isNull);
      expect(msg.agentId, isNull);
      expect(msg.isError, false);
      expect(msg.feedbackType, isNull);
      expect(msg.feedbackMessage, isNull);
    });

    test('hasFeedback returns true when feedbackType is set', () {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'hello', feedbackType: 'up');
      expect(msg.hasFeedback, true);
    });

    test('hasFeedback returns false when feedbackType is null', () {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'hello');
      expect(msg.hasFeedback, false);
    });

    group('fromJson', () {
      test('parses all fields', () {
        final json = {
          'id': 'msg-1',
          'type': 'image',
          'role': 'assistant',
          'content': '[Image]',
          'image_data': 'base64data',
          'agent_id': 'agent-1',
          'is_error': true,
          'feedback_type': 'down',
          'feedback_message': 'not helpful',
        };
        final msg = Message.fromJson(json);
        expect(msg.id, 'msg-1');
        expect(msg.type, 'image');
        expect(msg.role, 'assistant');
        expect(msg.content, '[Image]');
        expect(msg.imageData, 'base64data');
        expect(msg.agentId, 'agent-1');
        expect(msg.isError, true);
        expect(msg.feedbackType, 'down');
        expect(msg.feedbackMessage, 'not helpful');
      });

      test('handles missing optional fields', () {
        final json = {
          'id': '1',
          'type': 'text',
          'role': 'user',
          'content': 'hello',
        };
        final msg = Message.fromJson(json);
        expect(msg.imageData, isNull);
        expect(msg.agentId, isNull);
        expect(msg.isError, false);
        expect(msg.feedbackType, isNull);
        expect(msg.feedbackMessage, isNull);
      });
    });

    group('toJson', () {
      test('serializes all fields', () {
        const msg = Message(
          id: 'msg-1',
          type: 'text',
          role: 'assistant',
          content: 'hi',
          imageData: 'img',
          agentId: 'a1',
          isError: true,
          feedbackType: 'up',
          feedbackMessage: 'great',
        );
        final json = msg.toJson();
        expect(json['id'], 'msg-1');
        expect(json['type'], 'text');
        expect(json['role'], 'assistant');
        expect(json['content'], 'hi');
        expect(json['image_data'], 'img');
        expect(json['agent_id'], 'a1');
        expect(json['is_error'], true);
        expect(json['feedback_type'], 'up');
        expect(json['feedback_message'], 'great');
      });
    });

    test('fromJson/toJson round-trip preserves data', () {
      const original = Message(
        id: 'rt-1',
        type: 'file_link',
        role: 'assistant',
        content: '{"file_id": "f1"}',
        agentId: 'agent-x',
        feedbackType: 'down',
        feedbackMessage: 'wrong answer',
      );
      final restored = Message.fromJson(original.toJson());
      expect(restored.id, original.id);
      expect(restored.type, original.type);
      expect(restored.role, original.role);
      expect(restored.content, original.content);
      expect(restored.agentId, original.agentId);
      expect(restored.feedbackType, original.feedbackType);
      expect(restored.feedbackMessage, original.feedbackMessage);
    });

    group('copyWith', () {
      const base = Message(
        id: '1',
        type: 'text',
        role: 'user',
        content: 'original',
        feedbackType: 'up',
        feedbackMessage: 'good',
      );

      test('preserves untouched fields', () {
        final copy = base.copyWith(content: 'modified');
        expect(copy.id, '1');
        expect(copy.type, 'text');
        expect(copy.role, 'user');
        expect(copy.content, 'modified');
        expect(copy.feedbackType, 'up');
        expect(copy.feedbackMessage, 'good');
      });

      test('clearFeedback nulls feedback fields', () {
        final copy = base.copyWith(clearFeedback: true);
        expect(copy.feedbackType, isNull);
        expect(copy.feedbackMessage, isNull);
        expect(copy.content, 'original');
      });

      test('can override multiple fields at once', () {
        final copy = base.copyWith(
          id: '2',
          role: 'assistant',
          isError: true,
        );
        expect(copy.id, '2');
        expect(copy.role, 'assistant');
        expect(copy.isError, true);
        expect(copy.content, 'original');
      });
    });
  });
}
