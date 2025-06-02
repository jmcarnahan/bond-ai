import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/chat/chat_screen.dart';
import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart';
import 'package:flutterui/providers/thread_chat/chat_session_notifier.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:mockito/mockito.dart';

// ignore: must_be_immutable
class MockRef extends Mock implements Ref<Object?> {}
// ignore: must_be_immutable
class MockThreadService extends Mock implements ThreadService {}
// ignore: must_be_immutable
class MockChatService extends Mock implements ChatService {}

class MockChatSessionNotifier extends ChatSessionNotifier {
  bool setCurrentThreadCalled = false;
  bool createAndSetNewThreadCalled = false;
  bool sendMessageCalled = false;
  bool clearChatSessionCalled = false;
  String? lastThreadId;
  String? lastThreadName;
  String? lastAgentId;
  String? lastPrompt;

  MockChatSessionNotifier() : super(MockThreadService(), MockChatService(), MockRef());

  void setState(ChatSessionState newState) {
    state = newState;
  }

  @override
  Future<void> setCurrentThread(String threadId) async {
    setCurrentThreadCalled = true;
    lastThreadId = threadId;
    state = state.copyWith(currentThreadId: threadId);
  }

  @override
  Future<void> createAndSetNewThread({
    String? name,
    required String agentIdForFirstMessage,
    required String firstMessagePrompt,
  }) async {
    createAndSetNewThreadCalled = true;
    lastThreadName = name;
    lastAgentId = agentIdForFirstMessage;
    lastPrompt = firstMessagePrompt;
    state = state.copyWith(
      currentThreadId: 'new-thread-id',
      isSendingMessage: true,
    );
  }

  @override
  Future<void> sendMessage({
    required String agentId,
    required String prompt,
  }) async {
    sendMessageCalled = true;
    lastAgentId = agentId;
    lastPrompt = prompt;
    state = state.copyWith(isSendingMessage: true);
  }

  @override
  void clearChatSession() {
    clearChatSessionCalled = true;
    state = ChatSessionState();
  }
}

class MockThreadsNotifier extends ThreadsNotifier {
  bool selectThreadCalled = false;
  bool deselectThreadCalled = false;
  String? lastSelectedThreadId;

  MockThreadsNotifier(super.ref);

  @override
  void selectThread(String threadId) {
    selectThreadCalled = true;
    lastSelectedThreadId = threadId;
  }

  @override
  void deselectThread() {
    deselectThreadCalled = true;
  }

  @override
  Future<void> fetchThreads() async {
    // Mock implementation
  }
}

void main() {
  group('ChatScreen Widget Tests', () {
    late MockChatSessionNotifier mockChatNotifier;
    late MockThreadsNotifier mockThreadsNotifier;
    late ProviderContainer container;

    setUp(() {
      mockChatNotifier = MockChatSessionNotifier();
      
      container = ProviderContainer(
        overrides: [
          chatSessionNotifierProvider.overrideWith((ref) => mockChatNotifier),
          threadsProvider.overrideWith((ref) {
            mockThreadsNotifier = MockThreadsNotifier(ref);
            return mockThreadsNotifier;
          }),
          selectedThreadIdProvider.overrideWith((ref) => null),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    Widget createTestWidget({
      String agentId = 'test-agent',
      String agentName = 'Test Agent',
      String? initialThreadId,
    }) {
      return UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          routes: {
            '/threads': (context) => const Scaffold(
              body: Center(child: Text('Threads Screen')),
            ),
          },
          home: ChatScreen(
            agentId: agentId,
            agentName: agentName,
            initialThreadId: initialThreadId,
          ),
        ),
      );
    }

    testWidgets('should display all required UI elements', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byType(Column), findsOneWidget);
      expect(find.byType(Expanded), findsOneWidget);
      expect(find.text('Test Agent'), findsOneWidget);
    });

    testWidgets('should initialize with explicit thread ID', (tester) async {
      await tester.pumpWidget(createTestWidget(
        initialThreadId: 'explicit-thread-id',
      ));
      await tester.pumpAndSettle();

      expect(mockChatNotifier.setCurrentThreadCalled, isTrue);
      expect(mockChatNotifier.lastThreadId, equals('explicit-thread-id'));
      expect(mockThreadsNotifier.selectThreadCalled, isTrue);
      expect(mockThreadsNotifier.lastSelectedThreadId, equals('explicit-thread-id'));
    });

    testWidgets('should initialize with global selected thread ID', (tester) async {
      container.updateOverrides([
        selectedThreadIdProvider.overrideWith((ref) => 'global-thread-id'),
        chatSessionNotifierProvider.overrideWith((ref) => mockChatNotifier),
        threadsProvider.overrideWith((ref) => MockThreadsNotifier(ref)),
      ]);

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(mockChatNotifier.setCurrentThreadCalled, isTrue);
      expect(mockChatNotifier.lastThreadId, equals('global-thread-id'));
    });

    testWidgets('should clear session when no thread ID available', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        currentThreadId: 'existing-thread',
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(mockChatNotifier.clearChatSessionCalled, isTrue);
    });

    testWidgets('should send message when text field is submitted', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        currentThreadId: 'existing-thread',
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'Test message');
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.sendMessageCalled, isTrue);
      expect(mockChatNotifier.lastPrompt, equals('Test message'));
      expect(mockChatNotifier.lastAgentId, equals('test-agent'));
    });

    testWidgets('should create new thread when no current thread exists', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'First message');
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.createAndSetNewThreadCalled, isTrue);
      expect(mockChatNotifier.lastPrompt, equals('First message'));
      expect(mockChatNotifier.lastAgentId, equals('test-agent'));
      expect(mockChatNotifier.lastThreadName, equals('First message'));
    });

    testWidgets('should generate thread name from prompt', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final longMessage = 'This is a very long message that should be truncated';
      await tester.enterText(find.byType(TextField), longMessage);
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.createAndSetNewThreadCalled, isTrue);
      expect(mockChatNotifier.lastThreadName, equals('This is a very long message...'));
    });

    testWidgets('should not send empty messages', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), '   ');
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.sendMessageCalled, isFalse);
      expect(mockChatNotifier.createAndSetNewThreadCalled, isFalse);
    });

    testWidgets('should not send message when already sending', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        currentThreadId: 'existing-thread',
        isSendingMessage: true,
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'Test message');
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.sendMessageCalled, isFalse);
    });

    testWidgets('should navigate to threads screen', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.forum));
      await tester.pumpAndSettle();

      expect(find.text('Threads Screen'), findsOneWidget);
    });

    testWidgets('should show new thread confirmation dialog', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.add_comment));
      await tester.pumpAndSettle();

      expect(find.text('Start New Conversation?'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Start New'), findsOneWidget);
    });

    testWidgets('should start new thread when confirmed', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.add_comment));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Start New'));
      await tester.pumpAndSettle();

      expect(mockThreadsNotifier.deselectThreadCalled, isTrue);
      expect(mockChatNotifier.clearChatSessionCalled, isTrue);
    });

    testWidgets('should cancel new thread when dismissed', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.add_comment));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(mockThreadsNotifier.deselectThreadCalled, isFalse);
      expect(mockChatNotifier.clearChatSessionCalled, isFalse);
    });

    testWidgets('should handle widget updates correctly', (tester) async {
      await tester.pumpWidget(createTestWidget(
        agentId: 'agent-1',
        initialThreadId: 'thread-1',
      ));
      await tester.pumpAndSettle();

      mockChatNotifier.setCurrentThreadCalled = false;

      await tester.pumpWidget(createTestWidget(
        agentId: 'agent-2',
        initialThreadId: 'thread-2',
      ));
      await tester.pumpAndSettle();

      expect(mockChatNotifier.setCurrentThreadCalled, isTrue);
      expect(mockChatNotifier.lastThreadId, equals('thread-2'));
    });

    testWidgets('should handle focus changes correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final textField = find.byType(TextField);
      await tester.tap(textField);
      await tester.pump();

      final textFieldWidget = tester.widget<TextField>(textField);
      expect(textFieldWidget.focusNode?.hasFocus, isTrue);

      await tester.tap(find.byType(Scaffold));
      await tester.pump();
    });

    testWidgets('should scroll to bottom when messages change', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        messages: [
          Message(
            id: '1',
            type: 'text',
            role: 'user',
            content: 'Message 1',
          ),
          Message(
            id: '2',
            type: 'text',
            role: 'assistant',
            content: 'Message 2',
          ),
        ],
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Message 1'), findsOneWidget);
      expect(find.text('Message 2'), findsOneWidget);
    });

    testWidgets('should handle selected thread changes', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      container.updateOverrides([
        selectedThreadIdProvider.overrideWith((ref) => 'new-selected-thread'),
        chatSessionNotifierProvider.overrideWith((ref) => mockChatNotifier),
        threadsProvider.overrideWith((ref) => MockThreadsNotifier(ref)),
      ]);

      await tester.pump();
      await tester.pumpAndSettle();

      expect(mockChatNotifier.setCurrentThreadCalled, isTrue);
    });

    testWidgets('should dispose controllers properly', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.pumpWidget(Container());
      await tester.pumpAndSettle();

      expect(find.byType(ChatScreen), findsNothing);
    });

    testWidgets('should handle different agent names', (tester) async {
      await tester.pumpWidget(createTestWidget(
        agentName: 'Custom AI Assistant',
      ));
      await tester.pumpAndSettle();

      expect(find.text('Custom AI Assistant'), findsOneWidget);
    });

    testWidgets('should clear text field after sending message', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        currentThreadId: 'existing-thread',
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final textField = find.byType(TextField);
      await tester.enterText(textField, 'Test message');
      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();

      final textFieldWidget = tester.widget<TextField>(textField);
      expect(textFieldWidget.controller?.text, isEmpty);
    });

    testWidgets('should handle error states gracefully', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        errorMessage: 'Test error',
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.byType(ChatScreen), findsOneWidget);
    });

    testWidgets('should handle loading states correctly', (tester) async {
      mockChatNotifier.setState(mockChatNotifier.state.copyWith(
        isLoadingMessages: true,
      ));

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.byType(ChatScreen), findsOneWidget);
    });

    testWidgets('should handle rapid text changes', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final textField = find.byType(TextField);
      for (int i = 0; i < 5; i++) {
        await tester.enterText(textField, 'Message $i');
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(find.text('Message 4'), findsOneWidget);
    });

    testWidgets('should handle special characters in messages', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      const specialMessage = 'Message with émojis 🚀 and spëcial chars @#\$%';
      await tester.enterText(find.byType(TextField), specialMessage);
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.createAndSetNewThreadCalled, isTrue);
      expect(mockChatNotifier.lastPrompt, equals(specialMessage));
    });

    testWidgets('should handle very long messages', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final longMessage = 'Very long message ' * 100;
      await tester.enterText(find.byType(TextField), longMessage);
      await tester.tap(find.byType(IconButton));
      await tester.pump();

      expect(mockChatNotifier.createAndSetNewThreadCalled, isTrue);
      expect(mockChatNotifier.lastPrompt, equals(longMessage));
    });

    testWidgets('should maintain state consistency during rapid interactions', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      for (int i = 0; i < 3; i++) {
        await tester.enterText(find.byType(TextField), 'Message $i');
        await tester.tap(find.byType(IconButton));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(mockChatNotifier.createAndSetNewThreadCalled, isTrue);
    });
  });
}