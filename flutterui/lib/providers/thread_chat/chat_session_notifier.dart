import 'dart:async';

import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/providers/thread_provider.dart'; // Import for threadsProvider
import 'chat_session_state.dart';
import 'chat_stream_handler_mixin.dart';
import '../../core/utils/logger.dart';

class ChatSessionNotifier extends StateNotifier<ChatSessionState> with ChatStreamHandlerMixin {
  final ThreadService _threadService;
  final ChatService _chatService;
  final AgentService _agentService;
  final Ref _ref; // Add Ref
  
  @override
  final StringBuffer currentAssistantXmlBuffer = StringBuffer();
  @override
  StreamSubscription<String>? chatStreamSubscription;

  ChatSessionNotifier(this._threadService, 
                      this._chatService, 
                      this._agentService,
                      this._ref) // Modify constructor
      : super(ChatSessionState());

  Future<void> setCurrentThread(String threadId) async {
    state = state.copyWith(
      currentThreadId: threadId,
      messages: [],
      isLoadingMessages: true,
      clearErrorMessage: true,
    );
    try {
      final messages = await _threadService.getMessagesForThread(threadId);
      state = state.copyWith(messages: messages, isLoadingMessages: false);
    } catch (e) {
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
      );
    }
  }

  Future<void> createAndSetNewThread({
    String? name,
    required String agentIdForFirstMessage,
    required String firstMessagePrompt,
    List<PlatformFile>? attachedFiles,
  }) async {
    state = state.copyWith(
      isLoadingMessages: true,
      isSendingMessage: true,
      clearErrorMessage: true,
      messages: [],
    );
    try {
      final newThread = await _threadService.createThread(name: name);
      logger.i("[ChatSessionNotifier] Created new thread: ${newThread.id}");
      state = state.copyWith(
        currentThreadId: newThread.id,
        isLoadingMessages: false,
      );
      // Also set this new thread as the globally selected one
      _ref.read(threadsProvider.notifier).selectThread(newThread.id);
      // Refresh the threads list in threadsProvider as a new one was created
      // This might be redundant if selectThread or other mechanisms already trigger a refresh.
      // However, explicitly fetching ensures the list is up-to-date.
      await _ref.read(threadsProvider.notifier).fetchThreads();


      await sendMessage(
        agentId: agentIdForFirstMessage,
        prompt: firstMessagePrompt,
        attachedFiles: attachedFiles,
      );
    } catch (e) {
      logger.i("[ChatSessionNotifier] Error creating new thread: ${e.toString()}");
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
        isSendingMessage: false,
      );
    }
  }

  Future<void> startNewEmptyThread({String? name}) async {
    state = state.copyWith(
      isLoadingMessages: true,
      isSendingMessage: false,
      clearErrorMessage: true,
      messages: [],
    );
    try {
      final newThread = await _threadService.createThread(name: name);
      logger.i("[ChatSessionNotifier] Created new empty thread: ${newThread.id}");
      state = state.copyWith(
        currentThreadId: newThread.id,
        messages: [],
        isLoadingMessages: false,
        isSendingMessage: false,
      );
      // Also set this new thread as the globally selected one
      _ref.read(threadsProvider.notifier).selectThread(newThread.id);
      // Refresh the threads list
      await _ref.read(threadsProvider.notifier).fetchThreads();
    } catch (e) {
      logger.i(
        "[ChatSessionNotifier] Error creating new empty thread: ${e.toString()}",
      );
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
        isSendingMessage: false,
      );
    }
  }

  Future<void> sendMessage({
    required String agentId,
    required String prompt,
    List<PlatformFile>? attachedFiles
  }) async {
    if (state.currentThreadId == null) {
      state = state.copyWith(errorMessage: "No active thread selected.");
      return;
    }
    if (prompt.isEmpty) return;
    state = state.copyWith(isSendingMessage: true, clearErrorMessage: true);

    List<String>? provideFileIds;
    if (attachedFiles != null && attachedFiles.isNotEmpty) {
      // Handle file attachments
      try {
        final uploadResponses = await Future.wait(
          attachedFiles.map((file) => _agentService.uploadFile(file.name, file.bytes!)),
        );
        provideFileIds = uploadResponses.map((response) => response.providerFileId).toList(growable: false);
      }
      catch (e) {
        logger.i("[ChatSessionNotifier] Error uploading files: ${e.toString()}");
        state = state.copyWith(
          isSendingMessage: false,
          errorMessage: "Failed to upload files: ${e.toString()}",
        );
        return;
      }
    }

    final userMessage = Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      type: 'text',
      role: 'user',
      content: prompt,
    );
    state = state.copyWith(messages: [...state.messages, userMessage]);

    final assistantMessageId =
        (DateTime.now().millisecondsSinceEpoch + 1).toString();
    Message assistantMessage = Message(
      id: assistantMessageId,
      type: 'text',
      role: 'assistant',
      content: '',
      isError: false,
    );
    int assistantMessageIndex = state.messages.length;
    state = state.copyWith(messages: [...state.messages, assistantMessage]);
    currentAssistantXmlBuffer.clear();

    try {
      chatStreamSubscription?.cancel();
      chatStreamSubscription = _chatService
          .streamChatResponse(
            threadId: state.currentThreadId!,
            agentId: agentId,
            prompt: prompt,
          )
          .listen(
            (chunk) => handleStreamData(chunk, assistantMessageIndex),
            onDone: () => handleStreamDone(assistantMessageIndex),
            onError: (error) => handleStreamError(error, assistantMessageIndex),
          );
    } catch (e) {
      logger.i("[ChatSessionNotifier] Error sending message: ${e.toString()}");
      state = state.copyWith(
        isSendingMessage: false,
        errorMessage: e.toString(),
      );
    }
  }

  void clearChatSession() {
    logger.i("[ChatSessionNotifier] Clearing chat session.");
    chatStreamSubscription?.cancel(); // Use mixin's field name
    chatStreamSubscription = null; // Use mixin's field name
    state = ChatSessionState(); // Reset to initial empty state
  }

  @override
  void dispose() {
    chatStreamSubscription?.cancel(); // Use mixin's field name
    super.dispose();
  }

  // _handleStreamData, _handleStreamDone, _handleStreamError are now in ChatStreamHandlerMixin
}
