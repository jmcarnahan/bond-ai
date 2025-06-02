import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/thread_chat/chat_session_notifier.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:mockito/mockito.dart';

class MockRef extends Mock implements Ref<Object?> {}

// ignore: must_be_immutable
class MockThreadService implements ThreadService {
  List<Thread> mockThreads = [];
  List<Message> mockMessages = [];
  bool shouldThrowError = false;
  String? errorMessage;
  bool getMessagesForThreadCalled = false;
  bool createThreadCalled = false;
  bool deleteThreadCalled = false;
  String? lastThreadIdForMessages;
  String? lastCreatedThreadName;
  String? lastDeletedThreadId;
  Thread? mockNewThread;

  @override
  Future<List<Thread>> getThreads() async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get threads error');
    }
    return mockThreads;
  }

  @override
  Future<List<Message>> getMessagesForThread(String threadId, {int limit = 100}) async {
    getMessagesForThreadCalled = true;
    lastThreadIdForMessages = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get messages error');
    }
    return mockMessages;
  }

  @override
  Future<Thread> createThread({String? name}) async {
    createThreadCalled = true;
    lastCreatedThreadName = name;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock create thread error');
    }
    final newThread = mockNewThread ?? Thread(
            id: 'new-thread-${mockThreads.length}',
            name: name ?? 'New Thread',
          );
    mockThreads.add(newThread);
    return newThread;
  }

  @override
  Future<void> deleteThread(String threadId) async {
    deleteThreadCalled = true;
    lastDeletedThreadId = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete thread error');
    }
    mockThreads.removeWhere((thread) => thread.id == threadId);
  }
}

// ignore: must_be_immutable
class MockChatService implements ChatService {
  bool shouldThrowError = false;
  String? errorMessage;
  bool streamChatResponseCalled = false;
  String? lastThreadId;
  String? lastAgentId;
  String? lastPrompt;
  List<String> mockStreamChunks = [];
  bool shouldErrorInStream = false;
  String? streamErrorMessage;
  StreamController<String>? _streamController;

  @override
  Stream<String> streamChatResponse({
    required String threadId,
    required String agentId,
    required String prompt,
  }) {
    streamChatResponseCalled = true;
    lastThreadId = threadId;
    lastAgentId = agentId;
    lastPrompt = prompt;

    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock stream chat error');
    }

    _streamController = StreamController<String>();

    Future.delayed(Duration(milliseconds: 10), () async {
      try {
        for (final chunk in mockStreamChunks) {
          if (_streamController!.isClosed) break;
          _streamController!.add(chunk);
          await Future.delayed(Duration(milliseconds: 5));
        }

        if (shouldErrorInStream) {
          _streamController!.addError(Exception(streamErrorMessage ?? 'Stream error'));
        } else {
          _streamController!.close();
        }
      } catch (e) {
        _streamController!.addError(e);
      }
    });

    return _streamController!.stream;
  }

  void closeStream() {
    _streamController?.close();
  }
}

class MockThreadsNotifier extends ThreadsNotifier {
  bool selectThreadCalled = false;
  bool fetchThreadsCalled = false;
  String? lastSelectedThreadId;

  MockThreadsNotifier(super.ref);

  @override
  void selectThread(String threadId) {
    selectThreadCalled = true;
    lastSelectedThreadId = threadId;
  }

  @override
  Future<void> fetchThreads() async {
    fetchThreadsCalled = true;
  }
}

void main() {
  group('Chat Session Notifier Tests', () {
    late MockThreadService mockThreadService;
    late MockChatService mockChatService;
    late MockThreadsNotifier mockThreadsNotifier;
    late ProviderContainer container;
    late ChatSessionNotifier notifier;

    setUp(() {
      mockThreadService = MockThreadService();
      mockChatService = MockChatService();
      final mockRef = MockRef();
      mockThreadsNotifier = MockThreadsNotifier(mockRef);

      container = ProviderContainer(
        overrides: [
          threadServiceProvider.overrideWithValue(mockThreadService),
          chatServiceProvider.overrideWithValue(mockChatService),
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      notifier = ChatSessionNotifier(
        mockThreadService,
        mockChatService,
        mockRef,
      );
    });

    tearDown(() {
      notifier.dispose();
      mockChatService.closeStream();
      container.dispose();
    });

    group('ChatSessionState', () {
      test('should create default state', () {
        final state = ChatSessionState();

        expect(state.currentThreadId, isNull);
        expect(state.messages, isEmpty);
        expect(state.isLoadingMessages, isFalse);
        expect(state.isSendingMessage, isFalse);
        expect(state.errorMessage, isNull);
      });

      test('should create state with custom values', () {
        final messages = [
          Message(
            id: '1',
            type: 'text',
            role: 'user',
            content: 'Test message',
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

      test('should copy with new values', () {
        final originalState = ChatSessionState(
          currentThreadId: 'original-thread',
          messages: [],
          isLoadingMessages: false,
          errorMessage: 'Original error',
        );

        final newState = originalState.copyWith(
          currentThreadId: 'new-thread',
          isLoadingMessages: true,
        );

        expect(newState.currentThreadId, equals('new-thread'));
        expect(newState.isLoadingMessages, isTrue);
        expect(newState.errorMessage, equals('Original error'));
      });

      test('should clear thread ID when specified', () {
        final state = ChatSessionState(currentThreadId: 'thread-123');
        final newState = state.copyWith(clearCurrentThreadId: true);

        expect(state.currentThreadId, equals('thread-123'));
        expect(newState.currentThreadId, isNull);
      });

      test('should clear error message when specified', () {
        final state = ChatSessionState(errorMessage: 'Error');
        final newState = state.copyWith(clearErrorMessage: true);

        expect(state.errorMessage, equals('Error'));
        expect(newState.errorMessage, isNull);
      });
    });

    group('Initialization', () {
      test('should start with default state', () {
        expect(notifier.state.currentThreadId, isNull);
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, isNull);
      });

      test('should initialize with mixin properties', () {
        expect(notifier.currentAssistantXmlBuffer, isNotNull);
        expect(notifier.chatStreamSubscription, isNull);
      });
    });

    group('setCurrentThread', () {
      test('should set thread and load messages successfully', () async {
        final testMessages = [
          Message(
            id: '1',
            type: 'text',
            role: 'user',
            content: 'Hello',
          ),
          Message(
            id: '2',
            type: 'text',
            role: 'assistant',
            content: 'Hi there!',
          ),
        ];
        mockThreadService.mockMessages = testMessages;

        await notifier.setCurrentThread('test-thread-id');

        expect(notifier.state.currentThreadId, equals('test-thread-id'));
        expect(notifier.state.messages, equals(testMessages));
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.errorMessage, isNull);
        expect(mockThreadService.getMessagesForThreadCalled, isTrue);
        expect(mockThreadService.lastThreadIdForMessages, equals('test-thread-id'));
      });

      test('should handle loading state correctly', () async {
        mockThreadService.mockMessages = [];
        final future = notifier.setCurrentThread('test-thread-id');

        expect(notifier.state.currentThreadId, equals('test-thread-id'));
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.isLoadingMessages, isTrue);
        expect(notifier.state.errorMessage, isNull);

        await future;

        expect(notifier.state.isLoadingMessages, isFalse);
      });

      test('should handle get messages error', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Failed to load messages';

        await notifier.setCurrentThread('error-thread-id');

        expect(notifier.state.currentThreadId, equals('error-thread-id'));
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.errorMessage, contains('Failed to load messages'));
      });

      test('should clear previous messages and errors', () async {
        notifier.state = notifier.state.copyWith(
          messages: [Message(id: '1', type: 'text', role: 'user', content: 'Old')],
          errorMessage: 'Old error',
        );

        await notifier.setCurrentThread('new-thread');

        expect(notifier.state.currentThreadId, equals('new-thread'));
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.errorMessage, isNull);
      });
    });

    group('createAndSetNewThread', () {
      test('should create thread and send first message successfully', () async {
        final newThread = Thread(
            id: 'new-thread-123',
            name: 'New Conversation',
          );
        mockThreadService.mockNewThread = newThread;
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Hello!</bond:message>',
        ];

        final future = notifier.createAndSetNewThread(
          name: 'New Conversation',
          agentIdForFirstMessage: 'agent-1',
          firstMessagePrompt: 'Hello, how are you?',
        );

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.currentThreadId, equals('new-thread-123'));
        expect(mockThreadService.createThreadCalled, isTrue);
        expect(mockThreadService.lastCreatedThreadName, equals('New Conversation'));
        expect(mockThreadsNotifier.selectThreadCalled, isTrue);
        expect(mockThreadsNotifier.lastSelectedThreadId, equals('new-thread-123'));
        expect(mockThreadsNotifier.fetchThreadsCalled, isTrue);

        await future;
      });

      test('should handle thread creation error', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Failed to create thread';

        await notifier.createAndSetNewThread(
          agentIdForFirstMessage: 'agent-1',
          firstMessagePrompt: 'Hello',
        );

        expect(notifier.state.currentThreadId, isNull);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, contains('Failed to create thread'));
      });

      test('should set loading states correctly', () async {
        mockThreadService.mockNewThread = Thread(
            id: 'new-thread',
            name: 'Test',
          );

        final future = notifier.createAndSetNewThread(
          agentIdForFirstMessage: 'agent-1',
          firstMessagePrompt: 'Hello',
        );

        expect(notifier.state.isLoadingMessages, isTrue);
        expect(notifier.state.isSendingMessage, isTrue);
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.errorMessage, isNull);

        await future;
      });
    });

    group('startNewEmptyThread', () {
      test('should create empty thread successfully', () async {
        final newThread = Thread(
            id: 'empty-thread-123',
            name: 'Empty Thread',
          );
        mockThreadService.mockNewThread = newThread;

        await notifier.startNewEmptyThread(name: 'Empty Thread');

        expect(notifier.state.currentThreadId, equals('empty-thread-123'));
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, isNull);
        expect(mockThreadService.createThreadCalled, isTrue);
        expect(mockThreadService.lastCreatedThreadName, equals('Empty Thread'));
        expect(mockThreadsNotifier.selectThreadCalled, isTrue);
        expect(mockThreadsNotifier.fetchThreadsCalled, isTrue);
      });

      test('should create empty thread without name', () async {
        final newThread = Thread(
            id: 'unnamed-thread',
            name: 'New Thread',
          );
        mockThreadService.mockNewThread = newThread;

        await notifier.startNewEmptyThread();

        expect(notifier.state.currentThreadId, equals('unnamed-thread'));
        expect(mockThreadService.lastCreatedThreadName, isNull);
      });

      test('should handle empty thread creation error', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Network error';

        await notifier.startNewEmptyThread(name: 'Failed Thread');

        expect(notifier.state.currentThreadId, isNull);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, contains('Network error'));
      });

      test('should clear previous state', () async {
        notifier.state = notifier.state.copyWith(
          currentThreadId: 'old-thread',
          messages: [Message(id: '1', type: 'text', role: 'user', content: 'Old')],
          errorMessage: 'Old error',
        );

        final newThread = Thread(
            id: 'new-empty-thread',
            name: 'New',
          );
        mockThreadService.mockNewThread = newThread;

        await notifier.startNewEmptyThread();

        expect(notifier.state.currentThreadId, equals('new-empty-thread'));
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.errorMessage, isNull);
      });
    });

    group('sendMessage', () {
      setUp(() {
        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
      });

      test('should fail when no thread is selected', () async {
        notifier.state = notifier.state.copyWith(clearCurrentThreadId: true);

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hello',
        );

        expect(notifier.state.errorMessage, equals('No active thread selected.'));
        expect(mockChatService.streamChatResponseCalled, isFalse);
      });

      test('should not send empty message', () async {
        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: '',
        );

        expect(mockChatService.streamChatResponseCalled, isFalse);
        expect(notifier.state.messages, isEmpty);
      });

      test('should add user message and start streaming', () async {
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Response chunk 1</bond:message>',
        ];

        final future = notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hello, how are you?',
        );

        expect(notifier.state.isSendingMessage, isTrue);
        expect(notifier.state.messages, hasLength(2));
        expect(notifier.state.messages[0].role, equals('user'));
        expect(notifier.state.messages[0].content, equals('Hello, how are you?'));
        expect(notifier.state.messages[1].role, equals('assistant'));
        expect(notifier.state.messages[1].content, isEmpty);
        expect(notifier.state.errorMessage, isNull);

        expect(mockChatService.streamChatResponseCalled, isTrue);
        expect(mockChatService.lastThreadId, equals('test-thread'));
        expect(mockChatService.lastAgentId, equals('agent-1'));
        expect(mockChatService.lastPrompt, equals('Hello, how are you?'));

        await future;
      });

      test('should handle streaming response correctly', () async {
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Hello</bond:message>',
          '<bond:message role="assistant">Hello there!</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hi',
        );

        await Future.delayed(Duration(milliseconds: 100));

        expect(notifier.state.messages, hasLength(2));
        expect(notifier.state.messages[1].content, equals('Hello there!'));
        expect(notifier.state.isSendingMessage, isFalse);
      });

      test('should handle chat service error', () async {
        mockChatService.shouldThrowError = true;
        mockChatService.errorMessage = 'Chat service error';

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hello',
        );

        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, contains('Chat service error'));
      });

      test('should handle stream error', () async {
        mockChatService.shouldErrorInStream = true;
        mockChatService.streamErrorMessage = 'Stream interrupted';
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Partial response</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hello',
        );

        await Future.delayed(Duration(milliseconds: 100));

        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, contains('Stream interrupted'));
        expect(notifier.state.messages[1].isError, isTrue);
      });

      test('should cancel previous stream when sending new message', () async {
        mockChatService.mockStreamChunks = ['<bond:message role="assistant">First</bond:message>'];

        await notifier.sendMessage(agentId: 'agent-1', prompt: 'First message');
        await notifier.sendMessage(agentId: 'agent-1', prompt: 'Second message');

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.messages, hasLength(4));
      });

      test('should clear XML buffer for new message', () async {
        notifier.currentAssistantXmlBuffer.write('Previous content');
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">New response</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'New message',
        );

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.currentAssistantXmlBuffer.toString(), isEmpty);
      });

      test('should handle multiple messages in conversation', () async {
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">First response</bond:message>',
        ];

        await notifier.sendMessage(agentId: 'agent-1', prompt: 'First');
        await Future.delayed(Duration(milliseconds: 50));

        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Second response</bond:message>',
        ];

        await notifier.sendMessage(agentId: 'agent-1', prompt: 'Second');
        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.messages, hasLength(4));
        expect(notifier.state.messages[0].content, equals('First'));
        expect(notifier.state.messages[1].content, equals('First response'));
        expect(notifier.state.messages[2].content, equals('Second'));
        expect(notifier.state.messages[3].content, equals('Second response'));
      });
    });

    group('clearChatSession', () {
      test('should reset to default state', () {
        notifier.state = notifier.state.copyWith(
          currentThreadId: 'test-thread',
          messages: [Message(id: '1', type: 'text', role: 'user', content: 'Test')],
          isLoadingMessages: true,
          isSendingMessage: true,
          errorMessage: 'Test error',
        );

        notifier.clearChatSession();

        expect(notifier.state.currentThreadId, isNull);
        expect(notifier.state.messages, isEmpty);
        expect(notifier.state.isLoadingMessages, isFalse);
        expect(notifier.state.isSendingMessage, isFalse);
        expect(notifier.state.errorMessage, isNull);
      });

      test('should cancel active stream subscription', () async {
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Response</bond:message>',
        ];

        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
        await notifier.sendMessage(agentId: 'agent-1', prompt: 'Hello');

        expect(notifier.chatStreamSubscription, isNotNull);

        notifier.clearChatSession();

        expect(notifier.chatStreamSubscription, isNull);
      });
    });

    group('dispose', () {
      test('should cancel stream subscription on dispose', () async {
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Response</bond:message>',
        ];

        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
        await notifier.sendMessage(agentId: 'agent-1', prompt: 'Hello');

        expect(notifier.chatStreamSubscription, isNotNull);

        notifier.dispose();

        expect(notifier.chatStreamSubscription, isNull);
      });

      test('should handle dispose with no active subscription', () {
        expect(() => notifier.dispose(), returnsNormally);
      });
    });

    group('Integration Scenarios', () {
      test('should handle complete workflow', () async {
        await notifier.startNewEmptyThread(name: 'Test Conversation');
        
        expect(notifier.state.currentThreadId, isNotNull);
        expect(notifier.state.messages, isEmpty);

        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Hello! How can I help you today?</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: 'Hello, I need help with something.',
        );

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.messages, hasLength(2));
        expect(notifier.state.messages[0].role, equals('user'));
        expect(notifier.state.messages[1].role, equals('assistant'));
        expect(notifier.state.isSendingMessage, isFalse);
      });

      test('should handle thread switching', () async {
        final messagesThread1 = [
          Message(id: '1', type: 'text', role: 'user', content: 'Message in thread 1'),
        ];
        final messagesThread2 = [
          Message(id: '2', type: 'text', role: 'user', content: 'Message in thread 2'),
        ];

        mockThreadService.mockMessages = messagesThread1;
        await notifier.setCurrentThread('thread-1');
        expect(notifier.state.messages, equals(messagesThread1));

        mockThreadService.mockMessages = messagesThread2;
        await notifier.setCurrentThread('thread-2');
        expect(notifier.state.messages, equals(messagesThread2));
      });

      test('should handle error recovery', () async {
        mockThreadService.shouldThrowError = true;
        mockThreadService.errorMessage = 'Network failure';

        await notifier.setCurrentThread('failing-thread');
        expect(notifier.state.errorMessage, contains('Network failure'));

        mockThreadService.shouldThrowError = false;
        mockThreadService.mockMessages = [
          Message(id: '1', type: 'text', role: 'user', content: 'Recovery test'),
        ];

        await notifier.setCurrentThread('working-thread');
        expect(notifier.state.errorMessage, isNull);
        expect(notifier.state.messages, hasLength(1));
      });
    });

    group('Edge Cases', () {
      test('should handle rapid thread changes', () async {
        final futures = <Future>[];
        for (int i = 0; i < 5; i++) {
          mockThreadService.mockMessages = [
            Message(id: '$i', type: 'text', role: 'user', content: 'Message $i'),
          ];
          futures.add(notifier.setCurrentThread('thread-$i'));
        }

        await Future.wait(futures);

        expect(notifier.state.currentThreadId, equals('thread-4'));
      });

      test('should handle concurrent message sending', () async {
        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">Response</bond:message>',
        ];

        final futures = <Future>[];
        for (int i = 0; i < 3; i++) {
          futures.add(notifier.sendMessage(
            agentId: 'agent-$i',
            prompt: 'Message $i',
          ));
        }

        await Future.wait(futures);
        await Future.delayed(Duration(milliseconds: 100));

        expect(notifier.state.messages.length, greaterThanOrEqualTo(2));
      });

      test('should handle very long messages', () async {
        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
        final longMessage = 'Very long message ' * 1000;
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">$longMessage</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: longMessage,
        );

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.messages[0].content, equals(longMessage));
        expect(notifier.state.messages[1].content, equals(longMessage));
      });

      test('should handle special characters in messages', () async {
        notifier.state = notifier.state.copyWith(currentThreadId: 'test-thread');
        const specialMessage = 'Message with émojis 🚀 and spëcial chars @#\$%';
        mockChatService.mockStreamChunks = [
          '<bond:message role="assistant">$specialMessage</bond:message>',
        ];

        await notifier.sendMessage(
          agentId: 'agent-1',
          prompt: specialMessage,
        );

        await Future.delayed(Duration(milliseconds: 50));

        expect(notifier.state.messages[0].content, equals(specialMessage));
        expect(notifier.state.messages[1].content, equals(specialMessage));
      });

      test('should maintain state consistency during errors', () async {
        notifier.state = notifier.state.copyWith(
          currentThreadId: 'test-thread',
          messages: [Message(id: '1', type: 'text', role: 'user', content: 'Existing')],
        );

        mockChatService.shouldThrowError = true;
        mockChatService.errorMessage = 'Service error';

        await notifier.sendMessage(agentId: 'agent-1', prompt: 'New message');

        expect(notifier.state.currentThreadId, equals('test-thread'));
        expect(notifier.state.messages, hasLength(1));
        expect(notifier.state.messages[0].content, equals('Existing'));
        expect(notifier.state.isSendingMessage, isFalse);
      });
    });
  });
}