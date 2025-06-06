import 'dart:async';

import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/chat_models.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'chat_session_state.dart';
import 'chat_stream_handler_mixin.dart';
import '../../core/utils/logger.dart';

class ChatSessionNotifier extends StateNotifier<ChatSessionState> with ChatStreamHandlerMixin {
  final ThreadService _threadService;
  final ChatService _chatService;
  final FileService _fileService;
  final Ref _ref;
  
  @override
  final StringBuffer currentAssistantXmlBuffer = StringBuffer();
  @override
  StreamSubscription<String>? chatStreamSubscription;

  ChatSessionNotifier(this._threadService, 
                      this._chatService, 
                      this._fileService,
                      this._ref)
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
      state = state.copyWith(
        currentThreadId: newThread.id,
        isLoadingMessages: false,
      );
      _ref.read(threadsProvider.notifier).selectThread(newThread.id);
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
      _ref.read(threadsProvider.notifier).selectThread(newThread.id);
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

    // Handle file attachments
    List<ChatAttachment>? chatAttachments;
    if (attachedFiles != null && attachedFiles.isNotEmpty) {
      try {
        final uploadResponses = await Future.wait(
          attachedFiles.map((file) => _fileService.uploadFile(file.name, file.bytes!)),
        );
        chatAttachments = uploadResponses.map((response) => ChatAttachment(
          fileId: response.providerFileId,
          suggestedTool: response.suggestedTool,
        )).toList(growable: false);

        for(final file in attachedFiles) {
          final message = Message(
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            type: file.extension == 'png' || file.extension == 'jpg' || file.extension == 'jpeg'
                ? 'image_file'
                : 'file',
            role: 'user',
            content: file.name,
          );

          state = state.copyWith(messages: [...state.messages, message]);
        }
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
            attachments: chatAttachments,
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
    chatStreamSubscription?.cancel();
    chatStreamSubscription = null;
    state = ChatSessionState();
  }

  @override
  void dispose() {
    chatStreamSubscription?.cancel();
    super.dispose();
  }
}
