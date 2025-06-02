import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart';
import 'package:flutterui/data/models/message_model.dart';

void main() {
  group('ChatSessionState Tests', () {
    test('constructor should create state with default values', () {
      final state = ChatSessionState();
      
      expect(state.currentThreadId, isNull);
      expect(state.messages, isEmpty);
      expect(state.isLoadingMessages, isFalse);
      expect(state.isSendingMessage, isFalse);
      expect(state.errorMessage, isNull);
    });

    test('constructor should create state with provided values', () {
      const messages = [
        Message(
          id: 'msg-1',
          type: 'text',
          role: 'user',
          content: 'Hello',
        ),
        Message(
          id: 'msg-2',
          type: 'text',
          role: 'assistant',
          content: 'Hi there!',
        ),
      ];
      
      final state = ChatSessionState(
        currentThreadId: 'thread-123',
        messages: messages,
        isLoadingMessages: true,
        isSendingMessage: true,
        errorMessage: 'Test error',
      );
      
      expect(state.currentThreadId, equals('thread-123'));
      expect(state.messages, equals(messages));
      expect(state.isLoadingMessages, isTrue);
      expect(state.isSendingMessage, isTrue);
      expect(state.errorMessage, equals('Test error'));
    });

    group('copyWith Tests', () {
      test('should update currentThreadId', () {
        final originalState = ChatSessionState(currentThreadId: 'thread-123');
        
        final newState = originalState.copyWith(currentThreadId: 'thread-456');
        
        expect(newState.currentThreadId, equals('thread-456'));
        expect(newState.messages, equals(originalState.messages));
        expect(newState.isLoadingMessages, equals(originalState.isLoadingMessages));
        expect(newState.isSendingMessage, equals(originalState.isSendingMessage));
        expect(newState.errorMessage, equals(originalState.errorMessage));
      });

      test('should clear currentThreadId when clearCurrentThreadId is true', () {
        final originalState = ChatSessionState(currentThreadId: 'thread-123');
        
        final newState = originalState.copyWith(clearCurrentThreadId: true);
        
        expect(newState.currentThreadId, isNull);
      });

      test('should update messages', () {
        final originalState = ChatSessionState();
        const newMessages = [
          Message(
            id: 'msg-1',
            type: 'text',
            role: 'user',
            content: 'Hello',
          ),
        ];
        
        final newState = originalState.copyWith(messages: newMessages);
        
        expect(newState.messages, equals(newMessages));
        expect(newState.currentThreadId, equals(originalState.currentThreadId));
      });

      test('should update loading states', () {
        final originalState = ChatSessionState();
        
        final newState = originalState.copyWith(
          isLoadingMessages: true,
          isSendingMessage: true,
        );
        
        expect(newState.isLoadingMessages, isTrue);
        expect(newState.isSendingMessage, isTrue);
        expect(newState.messages, equals(originalState.messages));
      });

      test('should update errorMessage', () {
        final originalState = ChatSessionState();
        
        final newState = originalState.copyWith(errorMessage: 'New error');
        
        expect(newState.errorMessage, equals('New error'));
        expect(newState.currentThreadId, equals(originalState.currentThreadId));
      });

      test('should clear errorMessage when clearErrorMessage is true', () {
        final originalState = ChatSessionState(errorMessage: 'Old error');
        
        final newState = originalState.copyWith(clearErrorMessage: true);
        
        expect(newState.errorMessage, isNull);
      });

      test('should preserve original values when no updates provided', () {
        const messages = [
          Message(
            id: 'msg-1',
            type: 'text',
            role: 'user',
            content: 'Hello',
          ),
        ];
        
        final originalState = ChatSessionState(
          currentThreadId: 'thread-123',
          messages: messages,
          isLoadingMessages: true,
          isSendingMessage: true,
          errorMessage: 'Test error',
        );
        
        final newState = originalState.copyWith();
        
        expect(newState.currentThreadId, equals('thread-123'));
        expect(newState.messages, equals(messages));
        expect(newState.isLoadingMessages, isTrue);
        expect(newState.isSendingMessage, isTrue);
        expect(newState.errorMessage, equals('Test error'));
      });

      test('should handle multiple updates at once', () {
        final originalState = ChatSessionState(
          currentThreadId: 'thread-123',
          isLoadingMessages: true,
          errorMessage: 'Old error',
        );
        
        const newMessages = [
          Message(
            id: 'msg-1',
            type: 'text',
            role: 'user',
            content: 'Hello',
          ),
        ];
        
        final newState = originalState.copyWith(
          currentThreadId: 'thread-456',
          messages: newMessages,
          isLoadingMessages: false,
          isSendingMessage: true,
          clearErrorMessage: true,
        );
        
        expect(newState.currentThreadId, equals('thread-456'));
        expect(newState.messages, equals(newMessages));
        expect(newState.isLoadingMessages, isFalse);
        expect(newState.isSendingMessage, isTrue);
        expect(newState.errorMessage, isNull);
      });

      test('should handle null values correctly', () {
        final originalState = ChatSessionState(
          currentThreadId: 'thread-123',
          errorMessage: 'Test error',
        );
        
        final newState = originalState.copyWith(
          currentThreadId: null,
          errorMessage: null,
        );
        
        expect(newState.currentThreadId, equals('thread-123'));
        expect(newState.errorMessage, equals('Test error'));
      });
    });

    group('Edge Cases', () {
      test('should handle empty messages list', () {
        final state = ChatSessionState(messages: []);
        expect(state.messages, isEmpty);
        
        final newState = state.copyWith(messages: []);
        expect(newState.messages, isEmpty);
      });

      test('should handle large messages list', () {
        final manyMessages = List.generate(1000, (index) => Message(
          id: 'msg-$index',
          type: 'text',
          role: index % 2 == 0 ? 'user' : 'assistant',
          content: 'Message $index',
        ));
        
        final state = ChatSessionState(messages: manyMessages);
        expect(state.messages.length, equals(1000));
        
        final newState = state.copyWith();
        expect(newState.messages.length, equals(1000));
        expect(newState.messages, equals(manyMessages));
      });

      test('should handle messages with different types', () {
        const messages = [
          Message(
            id: 'msg-1',
            type: 'text',
            role: 'user',
            content: 'Text message',
          ),
          Message(
            id: 'msg-2',
            type: 'image_file',
            role: 'user',
            content: '[Image]',
            imageData: 'base64data',
          ),
          Message(
            id: 'msg-3',
            type: 'text',
            role: 'assistant',
            content: 'Error occurred',
            isError: true,
          ),
        ];
        
        final state = ChatSessionState(messages: messages);
        expect(state.messages.length, equals(3));
        expect(state.messages[0].type, equals('text'));
        expect(state.messages[1].type, equals('image_file'));
        expect(state.messages[1].imageData, equals('base64data'));
        expect(state.messages[2].isError, isTrue);
      });

      test('should handle very long thread IDs', () {
        final longThreadId = 'thread-${'a' * 1000}';
        final state = ChatSessionState(currentThreadId: longThreadId);
        expect(state.currentThreadId, equals(longThreadId));
      });

      test('should handle very long error messages', () {
        final longError = 'Error: ${'x' * 1000}';
        final state = ChatSessionState(errorMessage: longError);
        expect(state.errorMessage, equals(longError));
      });

      test('should handle special characters in thread ID', () {
        const specialThreadId = 'thread-with-special-chars-@#\$%^&*()_+{}[]|;:,.<>?';
        final state = ChatSessionState(currentThreadId: specialThreadId);
        expect(state.currentThreadId, equals(specialThreadId));
      });

      test('should handle empty string values', () {
        final state = ChatSessionState(
          currentThreadId: '',
          errorMessage: '',
        );
        
        expect(state.currentThreadId, equals(''));
        expect(state.errorMessage, equals(''));
      });

      test('should handle mixed state combinations', () {
        const messages = [
          Message(
            id: 'msg-1',
            type: 'text',
            role: 'user',
            content: 'Hello',
          ),
        ];
        
        final state = ChatSessionState(
          currentThreadId: 'thread-123',
          messages: messages,
          isLoadingMessages: true,
          isSendingMessage: false,
          errorMessage: null,
        );
        
        expect(state.currentThreadId, isNotNull);
        expect(state.messages, isNotEmpty);
        expect(state.isLoadingMessages, isTrue);
        expect(state.isSendingMessage, isFalse);
        expect(state.errorMessage, isNull);
      });
    });

    group('Complex Scenarios', () {
      test('should handle complete conversation flow simulation', () {
        var state = ChatSessionState();
        
        state = state.copyWith(
          currentThreadId: 'thread-123',
          isLoadingMessages: true,
        );
        expect(state.currentThreadId, equals('thread-123'));
        expect(state.isLoadingMessages, isTrue);
        
        state = state.copyWith(
          messages: [
            const Message(
              id: 'msg-1',
              type: 'text',
              role: 'user',
              content: 'Hello',
            ),
          ],
          isLoadingMessages: false,
        );
        expect(state.messages.length, equals(1));
        expect(state.isLoadingMessages, isFalse);
        
        state = state.copyWith(isSendingMessage: true);
        expect(state.isSendingMessage, isTrue);
        
        state = state.copyWith(
          messages: [
            ...state.messages,
            const Message(
              id: 'msg-2',
              type: 'text',
              role: 'assistant',
              content: 'Hi there!',
            ),
          ],
          isSendingMessage: false,
        );
        expect(state.messages.length, equals(2));
        expect(state.isSendingMessage, isFalse);
      });
    });
  });
}