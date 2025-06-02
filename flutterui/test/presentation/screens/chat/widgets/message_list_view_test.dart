import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/chat/widgets/message_list_view.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/presentation/widgets/typing_indicator.dart';
import 'package:flutterui/presentation/screens/chat/widgets/image_message_widget.dart';

void main() {
  group('MessageListView Widget Tests', () {
    late ScrollController scrollController;

    setUp(() {
      scrollController = ScrollController();
    });

    tearDown(() {
      scrollController.dispose();
    });

    Widget createTestWidget({
      required ChatSessionState chatState,
      String agentName = 'Test Agent',
    }) {
      return ProviderScope(
        child: MaterialApp(
          home: Scaffold(
            body: MessageListView(
              chatState: chatState,
              scrollController: scrollController,
              agentName: agentName,
            ),
          ),
        ),
      );
    }

    ChatSessionState createChatState({
      List<Message> messages = const [],
      bool isLoadingMessages = false,
      bool isSendingMessage = false,
    }) {
      return ChatSessionState(
        messages: messages,
        isLoadingMessages: isLoadingMessages,
        isSendingMessage: isSendingMessage,
        currentThreadId: 'test-thread',
      );
    }

    testWidgets('should display typing indicator when loading messages and no messages', (tester) async {
      final chatState = createChatState(isLoadingMessages: true);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(TypingIndicator), findsOneWidget);
      expect(find.byType(Center), findsOneWidget);
    });

    testWidgets('should display empty chat placeholder when no messages', (tester) async {
      final chatState = createChatState();

      await tester.pumpWidget(createTestWidget(chatState: chatState, agentName: 'Test Agent'));

      expect(find.text('Start a conversation'), findsOneWidget);
      expect(find.text('Send a message to begin your chat with Test Agent.'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
      expect(find.byType(CircleAvatar), findsOneWidget);
    });

    testWidgets('should display message list when messages exist', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Hello!',
        ),
        Message(
          id: '2',
          type: 'text',
          role: 'assistant',
          content: 'Hi there!',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(ListView), findsOneWidget);
      expect(find.text('Hello!'), findsOneWidget);
      expect(find.text('Hi there!'), findsOneWidget);
    });

    testWidgets('should display user messages on the right with correct styling', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'User message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('User message'), findsOneWidget);
      expect(find.byIcon(Icons.person_outline), findsOneWidget);

      final row = tester.widget<Row>(find.byType(Row).first);
      expect(row.mainAxisAlignment, equals(MainAxisAlignment.end));
    });

    testWidgets('should display assistant messages on the left', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'assistant',
          content: 'Assistant message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('Assistant message'), findsOneWidget);

      final row = tester.widget<Row>(find.byType(Row).first);
      expect(row.mainAxisAlignment, equals(MainAxisAlignment.start));
    });

    testWidgets('should display error messages with correct styling', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'assistant',
          content: 'Error occurred',
          isError: true,
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('Error occurred'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should display typing indicator for assistant when sending message', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'assistant',
          content: '',
        ),
      ];
      final chatState = createChatState(messages: messages, isSendingMessage: true);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('should display image messages correctly', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'image_file',
          role: 'user',
          content: 'Image message',
          imageData: 'base64imagedata',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(ImageMessageWidget), findsOneWidget);
      expect(find.text('Image message'), findsOneWidget);
    });

    testWidgets('should display image without text when content is [Image]', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'image_file',
          role: 'user',
          content: '[Image]',
          imageData: 'base64imagedata',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(ImageMessageWidget), findsOneWidget);
      expect(find.text('[Image]'), findsNothing);
    });

    testWidgets('should apply correct padding to ListView', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Test message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final listView = tester.widget<ListView>(find.byType(ListView));
      expect(listView.padding, equals(const EdgeInsets.symmetric(vertical: 8.0, horizontal: 72.0)));
    });

    testWidgets('should use provided scroll controller', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Test message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final listView = tester.widget<ListView>(find.byType(ListView));
      expect(listView.controller, equals(scrollController));
    });

    testWidgets('should apply correct constraints to message content', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Very long message that should be constrained to 75% of screen width',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final constrainedBox = tester.widget<ConstrainedBox>(find.byType(ConstrainedBox));
      final screenWidth = tester.getSize(find.byType(Scaffold)).width;
      expect(constrainedBox.constraints.maxWidth, equals(screenWidth * 0.75));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Test message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('Test message'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Test message'), findsOneWidget);

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should apply correct theme colors to user messages', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'User message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onPrimary: Colors.white,
            ),
          ),
          home: Scaffold(
            body: ProviderScope(
              child: MessageListView(
                chatState: chatState,
                scrollController: scrollController,
                agentName: 'Test Agent',
              ),
            ),
          ),
        ),
      );

      final card = tester.widget<Card>(find.byType(Card));
      expect(card.color, equals(Colors.blue));
    });

    testWidgets('should handle empty content gracefully', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: '',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(SelectableText), findsOneWidget);
    });

    testWidgets('should handle multiple messages correctly', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'First message',
        ),
        Message(
          id: '2',
          type: 'text',
          role: 'assistant',
          content: 'Second message',
        ),
        Message(
          id: '3',
          type: 'text',
          role: 'user',
          content: 'Third message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('First message'), findsOneWidget);
      expect(find.text('Second message'), findsOneWidget);
      expect(find.text('Third message'), findsOneWidget);
      expect(find.byType(SelectableText), findsNWidgets(3));
    });

    testWidgets('should work with dark theme', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Test message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: ProviderScope(
              child: MessageListView(
                chatState: chatState,
                scrollController: scrollController,
                agentName: 'Test Agent',
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test message'), findsOneWidget);
    });

    testWidgets('should apply correct border radius to message cards', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Test message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final card = tester.widget<Card>(find.byType(Card));
      final shape = card.shape as RoundedRectangleBorder;
      expect(shape.borderRadius, equals(BorderRadius.circular(16.0)));
    });

    testWidgets('should handle special characters in messages', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Message with émojis 🚀 and spëcial chars @#\$%',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.textContaining('Message with émojis 🚀'), findsOneWidget);
    });

    testWidgets('should handle very long messages', (tester) async {
      final longMessage = 'This is a very long message that should wrap properly and not cause any overflow issues in the chat interface. ' * 5;
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: longMessage,
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.textContaining('This is a very long message'), findsOneWidget);
    });

    testWidgets('should maintain correct spacing between messages', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'First',
        ),
        Message(
          id: '2',
          type: 'text',
          role: 'assistant',
          content: 'Second',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final paddings = tester.widgetList<Padding>(find.byType(Padding));
      expect(paddings.length, greaterThan(0));
    });

    testWidgets('should handle messages without explicit type', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Regular text message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('Regular text message'), findsOneWidget);
      expect(find.byType(SelectableText), findsOneWidget);
    });

    testWidgets('should use SelectableText for message content', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Selectable message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(SelectableText), findsOneWidget);
      
      final selectableText = tester.widget<SelectableText>(find.byType(SelectableText));
      expect(selectableText.data, equals('Selectable message'));
    });

    testWidgets('should handle image messages with empty content', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'image_file',
          role: 'user',
          content: '',
          imageData: 'base64imagedata',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(ImageMessageWidget), findsOneWidget);
      expect(find.byType(SelectableText), findsNothing);
    });

    testWidgets('should apply correct width constraints to image messages', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'image_file',
          role: 'user',
          content: 'Image with text',
          imageData: 'base64imagedata',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final imageWidget = tester.widget<ImageMessageWidget>(find.byType(ImageMessageWidget));
      final screenWidth = tester.getSize(find.byType(Scaffold)).width;
      expect(imageWidget.maxWidth, equals(screenWidth * 0.6));
      expect(imageWidget.maxHeight, equals(300));
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'Accessible message',
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.byType(SelectableText), findsOneWidget);
    });

    testWidgets('should handle different agent names in placeholder', (tester) async {
      final chatState = createChatState();

      await tester.pumpWidget(createTestWidget(chatState: chatState, agentName: 'Custom Agent'));

      expect(find.text('Send a message to begin your chat with Custom Agent.'), findsOneWidget);
    });

    testWidgets('should maintain consistent card styling across message types', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'user',
          content: 'User message',
        ),
        Message(
          id: '2',
          type: 'text',
          role: 'assistant',
          content: 'Error message',
          isError: true,
        ),
      ];
      final chatState = createChatState(messages: messages);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      final cards = tester.widgetList<Card>(find.byType(Card));
      for (final card in cards) {
        expect(card.elevation, equals(0.5));
        expect(card.margin, equals(EdgeInsets.zero));
      }
    });

    testWidgets('should handle edge case of typing indicator with content', (tester) async {
      final messages = [
        Message(
          id: '1',
          type: 'text',
          role: 'assistant',
          content: 'Some content',
        ),
      ];
      final chatState = createChatState(messages: messages, isSendingMessage: true);

      await tester.pumpWidget(createTestWidget(chatState: chatState));

      expect(find.text('Some content'), findsOneWidget);
      expect(find.byType(TypingIndicator), findsNothing);
    });
  });
}