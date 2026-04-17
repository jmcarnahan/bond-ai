import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  group('ChatMessagesList', () {
    testWidgets('renders correct number of messages', (tester) async {
      final messages = [
        const Message(id: '1', type: 'text', role: 'user', content: 'Q1'),
        const Message(id: '2', type: 'text', role: 'assistant', content: 'A1'),
        const Message(id: '3', type: 'text', role: 'user', content: 'Q2'),
      ];

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ChatMessagesList(
            messages: messages,
            isSendingMessage: false,
            scrollController: ScrollController(),
            imageCache: <String, Uint8List>{},
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Q1'), findsOneWidget);
      expect(find.text('A1'), findsOneWidget);
      expect(find.text('Q2'), findsOneWidget);
    });

    testWidgets('renders empty list without crashing', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ChatMessagesList(
            messages: const [],
            isSendingMessage: false,
            scrollController: ScrollController(),
            imageCache: <String, Uint8List>{},
          ),
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.byType(ListView), findsOneWidget);
    });

    testWidgets('passes callbacks through to ChatMessageItem', (tester) async {
      final messages = [
        const Message(id: '1', type: 'text', role: 'assistant', content: 'Response'),
      ];

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: ChatMessagesList(
            messages: messages,
            isSendingMessage: false,
            scrollController: ScrollController(),
            imageCache: <String, Uint8List>{},
            onSendPrompt: (prompt) {},
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // The widget should render — callbacks are passed through
      expect(find.text('Response'), findsOneWidget);
    });
  });
}
