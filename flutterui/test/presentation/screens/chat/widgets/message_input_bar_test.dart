import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/presentation/screens/chat/widgets/message_input_bar.dart';

void main() {
  group('MessageInputBar Widget Tests', () {
    late TextEditingController textController;
    late FocusNode focusNode;
    late bool onSendMessageCalled;

    setUp(() {
      textController = TextEditingController();
      focusNode = FocusNode();
      onSendMessageCalled = false;
    });

    tearDown(() {
      textController.dispose();
      focusNode.dispose();
    });

    testWidgets('should display message input bar with text field', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.send), findsOneWidget);
      expect(find.text('Type a message...'), findsOneWidget);
    });

    testWidgets('should show different hint text when sending message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Waiting for response...'), findsOneWidget);
      expect(find.text('Type a message...'), findsNothing);
    });

    testWidgets('should show progress indicator when sending message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.byIcon(Icons.send), findsNothing);
    });

    testWidgets('should show send button when not sending message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.byIcon(Icons.send), findsOneWidget);
      expect(find.byType(IconButton), findsOneWidget);
    });

    testWidgets('should call onSendMessage when send button pressed', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.send));
      expect(onSendMessageCalled, isTrue);
    });

    testWidgets('should not call onSendMessage when sending message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(IconButton), findsNothing);
      expect(onSendMessageCalled, isFalse);
    });

    testWidgets('should call onSendMessage when text submitted with content', (tester) async {
      textController.text = 'Test message';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.testTextInput.receiveAction(TextInputAction.done);
      expect(onSendMessageCalled, isTrue);
    });

    testWidgets('should not call onSendMessage when text submitted with empty content', (tester) async {
      textController.text = '   ';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.testTextInput.receiveAction(TextInputAction.done);
      expect(onSendMessageCalled, isFalse);
    });

    testWidgets('should show focused border when text field is focused', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: true,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final decoratedBox = tester.widget<DecoratedBox>(find.byType(DecoratedBox).first);
      final decoration = decoratedBox.decoration as BoxDecoration;
      expect(decoration.border?.top.color, equals(Colors.red));
      expect(decoration.border?.top.width, equals(2.0));
    });

    testWidgets('should not show focused border when text field is not focused', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final decoratedBox = tester.widget<DecoratedBox>(find.byType(DecoratedBox).first);
      final decoration = decoratedBox.decoration as BoxDecoration;
      expect(decoration.border, isNull);
    });

    testWidgets('should handle keyboard enter key to send message', (tester) async {
      textController.text = 'Test message';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(onSendMessageCalled, isTrue);
    });

    testWidgets('should not send message on enter when text is empty', (tester) async {
      textController.text = '';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(onSendMessageCalled, isFalse);
    });

    testWidgets('should not send message on enter when already sending', (tester) async {
      textController.text = 'Test message';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(onSendMessageCalled, isFalse);
    });

    testWidgets('should handle multiline input correctly', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.maxLines, isNull);
      expect(textField.keyboardType, equals(TextInputType.multiline));
    });

    testWidgets('should apply correct styling and decoration', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final container = tester.widget<Container>(find.byType(Container).first);
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.boxShadow, isNotEmpty);
      expect(decoration.boxShadow?.first.offset, equals(const Offset(0, -1)));

      final material = tester.widget<Material>(find.byType(Material));
      expect(material.borderRadius, equals(BorderRadius.circular(25.0)));
      expect(material.clipBehavior, equals(Clip.antiAlias));
    });

    testWidgets('should handle theme colors correctly', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                primary: Colors.blue,
                surfaceContainerHighest: Colors.grey,
              ),
            ),
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.send));
      expect(icon.color, equals(Colors.blue));
    });

    testWidgets('should show correct tooltip text', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final iconButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconButton.tooltip, equals('Send message'));

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(IconButton), findsNothing);
    });

    testWidgets('should handle text capitalization', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.textCapitalization, equals(TextCapitalization.sentences));
    });

    testWidgets('should maintain proper layout with row and expanded', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(Row), findsOneWidget);
      expect(find.byType(Expanded), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);

      final row = tester.widget<Row>(find.byType(Row));
      expect(row.crossAxisAlignment, equals(CrossAxisAlignment.end));
    });

    testWidgets('should handle empty text trimming', (tester) async {
      textController.text = '   \n\t   ';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.send));
      expect(onSendMessageCalled, isFalse);
    });

    testWidgets('should handle text with whitespace properly', (tester) async {
      textController.text = '  Hello World  ';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.send));
      expect(onSendMessageCalled, isTrue);
    });

    testWidgets('should maintain focus node correctly', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.focusNode, equals(focusNode));
      expect(textField.controller, equals(textController));
    });

    testWidgets('should handle progress indicator sizing', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: true,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      final sizedBox = tester.widget<SizedBox>(find.ancestor(
        of: find.byType(CircularProgressIndicator),
        matching: find.byType(SizedBox),
      ).first);
      expect(sizedBox.width, equals(28));
      expect(sizedBox.height, equals(28));

      final progressIndicator = tester.widget<CircularProgressIndicator>(find.byType(CircularProgressIndicator));
      expect(progressIndicator.strokeWidth, equals(2.5));
    });

    testWidgets('should handle dark theme colors', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              body: MessageInputBar(
                textController: textController,
                focusNode: focusNode,
                isTextFieldFocused: false,
                isSendingMessage: false,
                onSendMessage: () => onSendMessageCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.send), findsOneWidget);
    });
  });
}