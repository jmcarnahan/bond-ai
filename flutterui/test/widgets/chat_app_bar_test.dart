@TestOn('browser')
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_app_bar.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/core/theme/app_theme.dart';

class _TestAppTheme implements AppTheme {
  @override
  ThemeData get themeData => ThemeData.light();
  @override
  String get name => 'Test';
  @override
  String get brandingMessage => 'Test Branding';
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
    String agentName = 'Home',
    String? threadName = 'Test Thread',
    String? threadId = 'thread_1',
    VoidCallback? onCreateNewThread,
    VoidCallback? onAttachFile,
    bool isSendingMessage = false,
  }) {
    return ProviderScope(
      overrides: [
        appThemeProvider.overrideWithValue(_TestAppTheme()),
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: MaterialApp(
        home: Scaffold(
          appBar: ChatAppBar(
            agentName: agentName,
            threadName: threadName,
            threadId: threadId,
            onCreateNewThread: onCreateNewThread,
            onAttachFile: onAttachFile,
            isSendingMessage: isSendingMessage,
          ),
          body: const SizedBox.expand(),
        ),
      ),
    );
  }

  group('ChatAppBar', () {
    testWidgets('renders thread name', (tester) async {
      await tester.pumpWidget(buildTestWidget(threadName: 'My Conversation'));
      await tester.pumpAndSettle();

      expect(find.text('My Conversation'), findsOneWidget);
    });

    testWidgets('shows attach file button when callback provided', (tester) async {
      await tester.pumpWidget(buildTestWidget(onAttachFile: () {}));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.attach_file_rounded), findsOneWidget);
    });

    testWidgets('shows new conversation button when callback provided', (tester) async {
      await tester.pumpWidget(buildTestWidget(onCreateNewThread: () {}));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.add_comment_outlined), findsOneWidget);
    });

    testWidgets('hides attach file button when callback is null', (tester) async {
      await tester.pumpWidget(buildTestWidget(onAttachFile: null));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.attach_file_rounded), findsNothing);
    });

    testWidgets('hides new conversation button when callback is null', (tester) async {
      await tester.pumpWidget(buildTestWidget(onCreateNewThread: null));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.add_comment_outlined), findsNothing);
    });

    testWidgets('attach file button triggers callback', (tester) async {
      bool called = false;
      await tester.pumpWidget(buildTestWidget(onAttachFile: () => called = true));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.attach_file_rounded));
      expect(called, true);
    });

    testWidgets('new conversation button triggers callback', (tester) async {
      bool called = false;
      await tester.pumpWidget(buildTestWidget(onCreateNewThread: () => called = true));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.add_comment_outlined));
      expect(called, true);
    });

    testWidgets('buttons disabled when isSendingMessage is true', (tester) async {
      bool attachCalled = false;
      bool newThreadCalled = false;
      await tester.pumpWidget(buildTestWidget(
        onAttachFile: () => attachCalled = true,
        onCreateNewThread: () => newThreadCalled = true,
        isSendingMessage: true,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.attach_file_rounded));
      await tester.tap(find.byIcon(Icons.add_comment_outlined));
      expect(attachCalled, false);
      expect(newThreadCalled, false);
    });
  });
}
