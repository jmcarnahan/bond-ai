@TestOn('browser')
library;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_input_bar.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/core/theme/app_theme.dart';

class _TestAppTheme implements AppTheme {
  @override
  ThemeData get themeData => ThemeData.light();
  @override
  String get name => 'Test';
  @override
  String get brandingMessage => '';
  @override
  String get logo => '';
  @override
  String get logoIcon => '';
}

void main() {
  late SharedPreferences prefs;

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
  });

  Widget buildTestWidget({
    TextEditingController? textController,
    FocusNode? focusNode,
    bool isTextFieldFocused = false,
    bool isSendingMessage = false,
    VoidCallback? onSendMessage,
    void Function(List<PlatformFile>)? onFileAttachmentsChanged,
    List<PlatformFile>? attachments,
  }) {
    return ProviderScope(
      overrides: [
        appThemeProvider.overrideWithValue(_TestAppTheme()),
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: MessageInputBar(
            textController: textController ?? TextEditingController(),
            focusNode: focusNode ?? FocusNode(),
            isTextFieldFocused: isTextFieldFocused,
            isSendingMessage: isSendingMessage,
            onSendMessage: onSendMessage ?? () {},
            onFileAttachmentsChanged: onFileAttachmentsChanged ?? (_) {},
            attachments: attachments ?? [],
          ),
        ),
      ),
    );
  }

  group('MessageInputBar', () {
    testWidgets('renders text input field', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Type your message here...'), findsOneWidget);
    });

    testWidgets('renders send button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.send_rounded), findsOneWidget);
    });

    testWidgets('does NOT render attach file button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.attach_file_rounded), findsNothing);
    });

    testWidgets('does NOT render new thread button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.add_rounded), findsNothing);
      expect(find.byIcon(Icons.add_comment_outlined), findsNothing);
    });

    testWidgets('shows loading spinner when sending', (tester) async {
      await tester.pumpWidget(buildTestWidget(isSendingMessage: true));
      // Use pump instead of pumpAndSettle to avoid timer issues
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.byIcon(Icons.send_rounded), findsNothing);
    });
  });
}
