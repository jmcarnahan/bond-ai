import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

// A 1x1 red PNG pixel for image tests
final _tinyPng = base64Encode([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
  0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41,
  0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
  0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
  0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
]);

Widget buildTestWidget({
  required Message message,
  bool isSendingMessage = false,
  bool isLastMessage = false,
  Map<String, Uint8List>? imageCache,
  Future<void> Function(String, String, String?)? onFeedbackSubmit,
  Future<void> Function(String)? onFeedbackDelete,
  void Function(String, String?, String?)? onFeedbackChanged,
  void Function(String)? onSendPrompt,
  Widget Function(BuildContext, Message)? assistantAvatarBuilder,
  Widget Function(BuildContext, String)? fileCardBuilder,
}) {
  return MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: ChatMessageItem(
          message: message,
          isSendingMessage: isSendingMessage,
          isLastMessage: isLastMessage,
          imageCache: imageCache ?? {},
          onFeedbackSubmit: onFeedbackSubmit,
          onFeedbackDelete: onFeedbackDelete,
          onFeedbackChanged: onFeedbackChanged,
          onSendPrompt: onSendPrompt,
          assistantAvatarBuilder: assistantAvatarBuilder,
          fileCardBuilder: fileCardBuilder,
        ),
      ),
    ),
  );
}

void main() {
  group('ChatMessageItem (decoupled)', () {
    testWidgets('renders user message text', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'user', content: 'Hello there');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.text('Hello there'), findsOneWidget);
    });

    testWidgets('user message shows person icon avatar', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'user', content: 'Hi');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.person_outline), findsOneWidget);
    });

    testWidgets('default assistant avatar shows robot icon', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'Hello!');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });

    testWidgets('custom assistantAvatarBuilder is used', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'Hello!');
      Message? receivedMessage;
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        assistantAvatarBuilder: (context, message) {
          receivedMessage = message;
          return const CircleAvatar(child: Icon(Icons.star));
        },
      ));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.star), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsNothing);
      expect(receivedMessage?.id, '1');
    });

    testWidgets('empty content renders SizedBox.shrink', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'user', content: '');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      // Nothing visible
      expect(find.byType(SelectableText), findsNothing);
    });

    testWidgets('streaming typing indicator shows "..."', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: '');
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        isSendingMessage: true,
        isLastMessage: true,
      ));
      await tester.pumpAndSettle();
      expect(find.text('...'), findsOneWidget);
    });

    testWidgets('renders assistant text as markdown', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: '**bold text**');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.text('bold text'), findsOneWidget);
    });

    testWidgets('renders file_link with default FileCard', (tester) async {
      final fileJson = json.encode({
        'file_id': 'f1',
        'file_name': 'report.pdf',
        'file_size': 1024,
        'mime_type': 'application/pdf',
      });
      final msg = Message(id: '1', type: 'file_link', role: 'assistant', content: fileJson);
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.text('report.pdf'), findsOneWidget);
    });

    testWidgets('uses fileCardBuilder when provided', (tester) async {
      final fileJson = json.encode({'file_id': 'f1', 'file_name': 'test.txt'});
      final msg = Message(id: '1', type: 'file_link', role: 'assistant', content: fileJson);
      String? receivedJson;
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        fileCardBuilder: (context, json) {
          receivedJson = json;
          return const Text('Custom File Card');
        },
      ));
      await tester.pumpAndSettle();
      expect(find.text('Custom File Card'), findsOneWidget);
      expect(receivedJson, fileJson);
    });

    testWidgets('renders image from base64', (tester) async {
      final msg = Message(id: 'img-1', type: 'image', role: 'assistant', content: '[Image]', imageData: _tinyPng);
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      expect(find.byType(Image), findsOneWidget);
    });

    group('feedback', () {
      testWidgets('thumbs appear for non-streaming assistant messages', (tester) async {
        const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'Response');
        await tester.pumpWidget(buildTestWidget(message: msg));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.thumb_up_outlined), findsOneWidget);
        expect(find.byIcon(Icons.thumb_down_outlined), findsOneWidget);
      });

      testWidgets('thumbs hidden during streaming', (tester) async {
        const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'Streaming...');
        await tester.pumpWidget(buildTestWidget(message: msg, isSendingMessage: true));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.thumb_up_outlined), findsNothing);
      });

      testWidgets('filled thumb when feedback exists', (tester) async {
        const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'x', feedbackType: 'up');
        await tester.pumpWidget(buildTestWidget(message: msg));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.thumb_up), findsOneWidget);
      });

      testWidgets('onFeedbackSubmit callback receives correct args', (tester) async {
        String? submittedId;
        String? submittedType;
        String? submittedMessage;

        const msg = Message(id: 'msg-1', type: 'text', role: 'assistant', content: 'Answer');
        await tester.pumpWidget(buildTestWidget(
          message: msg,
          onFeedbackSubmit: (id, type, message) async {
            submittedId = id;
            submittedType = type;
            submittedMessage = message;
          },
          onFeedbackChanged: (_, __, ___) {},
        ));
        await tester.pumpAndSettle();

        // Tap thumb up to open dialog
        await tester.tap(find.byIcon(Icons.thumb_up_outlined));
        await tester.pumpAndSettle();

        // Enter feedback text
        await tester.enterText(find.byType(TextField), 'great response');

        // Submit
        await tester.tap(find.text('Submit'));
        await tester.pumpAndSettle();

        expect(submittedId, 'msg-1');
        expect(submittedType, 'up');
        expect(submittedMessage, 'great response');
      });
    });

    testWidgets('works with all optional callbacks null', (tester) async {
      const msg = Message(id: '1', type: 'text', role: 'assistant', content: 'Safe');
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();
      // Should render without crashing
      expect(find.text('Safe'), findsOneWidget);
    });
  });
}
