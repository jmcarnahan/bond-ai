import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('ParsedBondMessage', () {
    test('defaults are empty strings and false booleans', () {
      final msg = ParsedBondMessage(content: 'hello');
      expect(msg.id, '');
      expect(msg.threadId, '');
      expect(msg.agentId, isNull);
      expect(msg.type, '');
      expect(msg.role, '');
      expect(msg.content, 'hello');
      expect(msg.imageData, isNull);
      expect(msg.isErrorAttribute, false);
      expect(msg.parsingHadError, false);
    });

    test('all fields can be set', () {
      final msg = ParsedBondMessage(
        id: 'msg-1',
        threadId: 'thread-1',
        agentId: 'agent-1',
        type: 'text',
        role: 'assistant',
        content: 'response',
        imageData: 'base64',
        isErrorAttribute: true,
        parsingHadError: true,
      );
      expect(msg.id, 'msg-1');
      expect(msg.threadId, 'thread-1');
      expect(msg.agentId, 'agent-1');
      expect(msg.type, 'text');
      expect(msg.role, 'assistant');
      expect(msg.content, 'response');
      expect(msg.imageData, 'base64');
      expect(msg.isErrorAttribute, true);
      expect(msg.parsingHadError, true);
    });
  });
}
