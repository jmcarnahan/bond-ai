import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart' as bond;
import 'package:flutterui/presentation/screens/chat/widgets/bond_chat_message_item.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/cached_agent_details_provider.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ---------------------------------------------------------------------------
// Minimal mock for ThreadService — only feedback methods needed
// ---------------------------------------------------------------------------
class MockThreadService implements ThreadService {
  String? lastSubmitThreadId;
  String? lastSubmitMessageId;
  String? lastSubmitFeedbackType;
  String? lastSubmitFeedbackMessage;
  bool submitFeedbackCalled = false;

  String? lastDeleteThreadId;
  String? lastDeleteMessageId;
  bool deleteFeedbackCalled = false;

  @override
  Future<void> submitFeedback(
    String threadId,
    String messageId,
    String feedbackType,
    String? feedbackMessage,
  ) async {
    submitFeedbackCalled = true;
    lastSubmitThreadId = threadId;
    lastSubmitMessageId = messageId;
    lastSubmitFeedbackType = feedbackType;
    lastSubmitFeedbackMessage = feedbackMessage;
  }

  @override
  Future<void> deleteFeedback(String threadId, String messageId) async {
    deleteFeedbackCalled = true;
    lastDeleteThreadId = threadId;
    lastDeleteMessageId = messageId;
  }

  // Unused methods — satisfy interface
  @override
  Future<({List<Thread> threads, int total, bool hasMore})> getThreads({
    int offset = 0, int limit = 20, bool excludeEmpty = true,
  }) async => (threads: <Thread>[], total: 0, hasMore: false);
  @override
  Future<Thread> updateThread(String threadId, String name) => throw UnimplementedError();
  @override
  Future<Thread> createThread({String? name}) => throw UnimplementedError();
  @override
  Future<void> deleteThread(String threadId) => throw UnimplementedError();
  @override
  Future<int> cleanupEmptyThreads() => throw UnimplementedError();
  @override
  Future<List<Message>> getMessagesForThread(String threadId, {int? limit}) => throw UnimplementedError();
}

// ---------------------------------------------------------------------------
// Minimal mock for FileService
// ---------------------------------------------------------------------------
class MockFileService implements FileService {
  String? lastDownloadFileId;
  String? lastDownloadFileName;
  bool downloadFileCalled = false;

  @override
  Future<void> downloadFile(String fileId, String fileName) async {
    downloadFileCalled = true;
    lastDownloadFileId = fileId;
    lastDownloadFileName = fileName;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => throw UnimplementedError();
}

// ---------------------------------------------------------------------------
// Minimal mock for AuthService
// ---------------------------------------------------------------------------
class MockAuthService implements AuthService {
  @override
  dynamic noSuchMethod(Invocation invocation) => throw UnimplementedError();
}

void main() {
  late SharedPreferences prefs;
  late MockThreadService mockThreadService;
  late MockFileService mockFileService;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    mockThreadService = MockThreadService();
    mockFileService = MockFileService();
  });

  Widget buildTestWidget({
    required bond.Message message,
    bool isSendingMessage = false,
    bool isLastMessage = false,
    String? threadId = 'thread-1',
    void Function(String, String?, String?)? onFeedbackChanged,
  }) {
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        threadServiceProvider.overrideWithValue(mockThreadService),
        fileServiceProvider.overrideWithValue(mockFileService),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: BondChatMessageItem(
              message: message,
              isSendingMessage: isSendingMessage,
              isLastMessage: isLastMessage,
              imageCache: <String, Uint8List>{},
              threadId: threadId,
              onFeedbackChanged: onFeedbackChanged,
            ),
          ),
        ),
      ),
    );
  }

  group('BondChatMessageItem', () {
    testWidgets('renders assistant message with default avatar', (tester) async {
      const msg = bond.Message(
        id: '1', type: 'text', role: 'assistant', content: 'Hello!',
      );
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();

      expect(find.text('Hello!'), findsOneWidget);
      // Default avatar (no agentId) shows robot icon
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });

    testWidgets('renders user message', (tester) async {
      const msg = bond.Message(
        id: '1', type: 'text', role: 'user', content: 'Hi there',
      );
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();

      expect(find.text('Hi there'), findsOneWidget);
      expect(find.byIcon(Icons.person_outline), findsOneWidget);
    });

    testWidgets('feedback submit calls threadService with correct args', (tester) async {
      String? changedId;
      String? changedType;

      const msg = bond.Message(
        id: 'msg-42', type: 'text', role: 'assistant', content: 'Answer',
      );
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        threadId: 'thread-7',
        onFeedbackChanged: (id, type, message) {
          changedId = id;
          changedType = type;
        },
      ));
      await tester.pumpAndSettle();

      // Tap thumb up
      await tester.tap(find.byIcon(Icons.thumb_up_outlined));
      await tester.pumpAndSettle();

      // Enter feedback text and submit
      await tester.enterText(find.byType(TextField), 'great answer');
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();

      // Verify threadService was called with correct args
      expect(mockThreadService.submitFeedbackCalled, true);
      expect(mockThreadService.lastSubmitThreadId, 'thread-7');
      expect(mockThreadService.lastSubmitMessageId, 'msg-42');
      expect(mockThreadService.lastSubmitFeedbackType, 'up');
      expect(mockThreadService.lastSubmitFeedbackMessage, 'great answer');

      // Verify onFeedbackChanged was called
      expect(changedId, 'msg-42');
      expect(changedType, 'up');
    });

    testWidgets('feedback submit shows error SnackBar when threadId is null', (tester) async {
      const msg = bond.Message(
        id: 'msg-1', type: 'text', role: 'assistant', content: 'Answer',
      );
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        threadId: null,
      ));
      await tester.pumpAndSettle();

      // Tap thumb up and submit
      await tester.tap(find.byIcon(Icons.thumb_up_outlined));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Submit'));
      await tester.pumpAndSettle();

      // ThreadService should NOT have been called
      expect(mockThreadService.submitFeedbackCalled, false);
      // Error SnackBar should appear (the package catches the StateError)
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('Failed to submit feedback'), findsOneWidget);
    });

    testWidgets('feedback delete calls threadService.deleteFeedback', (tester) async {
      String? changedId;
      String? changedType;

      const msg = bond.Message(
        id: 'msg-10', type: 'text', role: 'assistant', content: 'Old answer',
        feedbackType: 'down', feedbackMessage: 'was wrong',
      );
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        threadId: 'thread-5',
        onFeedbackChanged: (id, type, message) {
          changedId = id;
          changedType = type;
        },
      ));
      await tester.pumpAndSettle();

      // Tap filled thumb_down to open edit dialog
      await tester.tap(find.byIcon(Icons.thumb_down));
      await tester.pumpAndSettle();

      // Dialog should show "Edit feedback" with Delete button
      expect(find.text('Edit feedback'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);

      // Tap Delete
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      // Verify threadService.deleteFeedback was called
      expect(mockThreadService.deleteFeedbackCalled, true);
      expect(mockThreadService.lastDeleteThreadId, 'thread-5');
      expect(mockThreadService.lastDeleteMessageId, 'msg-10');

      // Verify onFeedbackChanged was called with nulls (cleared)
      expect(changedId, 'msg-10');
      expect(changedType, isNull);
    });

    testWidgets('feedback delete shows error SnackBar when threadId is null', (tester) async {
      const msg = bond.Message(
        id: 'msg-10', type: 'text', role: 'assistant', content: 'Old answer',
        feedbackType: 'up',
      );
      await tester.pumpWidget(buildTestWidget(
        message: msg,
        threadId: null,
      ));
      await tester.pumpAndSettle();

      // Tap filled thumb to open edit dialog
      await tester.tap(find.byIcon(Icons.thumb_up));
      await tester.pumpAndSettle();

      // Tap Delete
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      // ThreadService should NOT have been called
      expect(mockThreadService.deleteFeedbackCalled, false);
      // Error SnackBar should appear
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('Failed to delete feedback'), findsOneWidget);
    });

    testWidgets('file card uses fileService for download', (tester) async {
      final msg = bond.Message(
        id: '1',
        type: 'file_link',
        role: 'assistant',
        content: '{"file_id":"f-99","file_name":"report.pdf","file_size":1024,"mime_type":"application/pdf"}',
      );
      await tester.pumpWidget(buildTestWidget(message: msg));
      await tester.pumpAndSettle();

      expect(find.text('report.pdf'), findsOneWidget);

      // Tap the file card to trigger download
      await tester.tap(find.text('report.pdf'));
      await tester.pumpAndSettle();

      expect(mockFileService.downloadFileCalled, true);
      expect(mockFileService.lastDownloadFileId, 'f-99');
      expect(mockFileService.lastDownloadFileName, 'report.pdf');
    });

    testWidgets('assistant avatar shows fallback for agent with id when provider errors', (tester) async {
      const msg = bond.Message(
        id: '1', type: 'text', role: 'assistant', content: 'Hi',
        agentId: 'agent-123',
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            threadServiceProvider.overrideWithValue(mockThreadService),
            fileServiceProvider.overrideWithValue(mockFileService),
            // Override agent details to return null (agent not found)
            getCachedAgentDetailsProvider('agent-123').overrideWith(
              (ref) async => null,
            ),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(
                child: BondChatMessageItem(
                  message: msg,
                  isSendingMessage: false,
                  isLastMessage: false,
                  imageCache: <String, Uint8List>{},
                  threadId: 'thread-1',
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Agent not found → fallback robot icon
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });
  });
}
