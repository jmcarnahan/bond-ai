import 'dart:async';

import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/chat_models.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'chat_session_state.dart';
import 'chat_stream_handler_mixin.dart';
import '../../core/utils/logger.dart';

class ChatSessionNotifier extends StateNotifier<ChatSessionState>
    with ChatStreamHandlerMixin {
  final ThreadService _threadService;
  final ChatService _chatService;
  final FileService _fileService;

  @override
  final StringBuffer currentAssistantXmlBuffer = StringBuffer();
  @override
  StreamSubscription<String>? chatStreamSubscription;

  ChatSessionNotifier(this._threadService, this._chatService, this._fileService)
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
      logger.i(
        "[ChatSessionNotifier] Loaded ${messages.length} messages for thread $threadId",
      );
      for (final msg in messages) {
        logger.d(
          "[ChatSessionNotifier] Loaded message - ID: ${msg.id}, Agent: ${msg.agentId ?? 'none'}, Type: ${msg.type}, Role: ${msg.role}",
        );
      }
      state = state.copyWith(messages: messages, isLoadingMessages: false);
    } catch (e) {
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
      );
    }
  }

  void setThreadIdOnly(String threadId) {
    state = state.copyWith(currentThreadId: threadId);
  }

  void setSendingState(bool isSending) {
    state = state.copyWith(isSendingMessage: isSending);
  }

  Future<void> sendMessage({
    required String agentId,
    required String prompt,
    List<PlatformFile>? attachedFiles,
    String overrideRole = "user",
  }) async {
    if (prompt.isEmpty) return;
    state = state.copyWith(isSendingMessage: true, clearErrorMessage: true);

    // Handle file attachments
    List<ChatAttachment>? chatAttachments;
    if (attachedFiles != null && attachedFiles.isNotEmpty) {
      try {
        final uploadResponses = await Future.wait(
          attachedFiles.map(
            (file) => _fileService.uploadFile(file.name, file.bytes!),
          ),
        );
        chatAttachments = uploadResponses
            .map(
              (response) => ChatAttachment(
                fileId: response.providerFileId,
                suggestedTool: response.suggestedTool,
              ),
            )
            .toList(growable: false);

        for (final file in attachedFiles) {
          final message = Message(
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            type:
                file.extension == 'png' ||
                        file.extension == 'jpg' ||
                        file.extension == 'jpeg'
                    ? 'image_file'
                    : 'file',
            role: 'user',
            content: file.name,
            agentId: agentId,
          );

          logger.i(
            "[ChatSessionNotifier] Created file message - ID: ${message.id}, Agent: ${message.agentId ?? 'none'}, Type: ${message.type}",
          );
          state = state.copyWith(messages: [...state.messages, message]);
        }
      } catch (e) {
        logger.i(
          "[ChatSessionNotifier] Error uploading files: ${e.toString()}",
        );
        state = state.copyWith(
          isSendingMessage: false,
          errorMessage: "Failed to upload files: ${e.toString()}",
        );
        return;
      }
    }

    // Add user message to UI (unless it's a system message)
    if (overrideRole != "system") {
      final userMessage = Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        type: 'text',
        role: 'user',
        content: prompt,
        agentId: agentId,
      );
      logger.i(
        "[ChatSessionNotifier] Created user message - ID: ${userMessage.id}, Agent: ${userMessage.agentId ?? 'none'}, Type: ${userMessage.type}",
      );
      state = state.copyWith(messages: [...state.messages, userMessage]);
    }

    final assistantMessageId =
        (DateTime.now().millisecondsSinceEpoch + 1).toString();
    Message assistantMessage = Message(
      id: assistantMessageId,
      type: 'text',
      role: 'assistant',
      content: '',
      agentId: agentId,
      isError: false,
    );
    logger.i(
      "[ChatSessionNotifier] Created assistant placeholder - ID: ${assistantMessage.id}, Agent: ${assistantMessage.agentId ?? 'none'}, Type: ${assistantMessage.type}",
    );
    int assistantMessageIndex = state.messages.length;
    state = state.copyWith(messages: [...state.messages, assistantMessage]);
    currentAssistantXmlBuffer.clear();

    try {
      chatStreamSubscription?.cancel();
      logger.i("[ChatSessionNotifier] Calling streamChatResponse with:");
      logger.i("[ChatSessionNotifier]   - agentId: $agentId");
      logger.i("[ChatSessionNotifier]   - threadId: ${state.currentThreadId}");
      logger.i("[ChatSessionNotifier]   - prompt: $prompt");
      logger.i("[ChatSessionNotifier]   - overrideRole: $overrideRole");

      chatStreamSubscription = _chatService
          .streamChatResponse(
            threadId:
                state
                    .currentThreadId, // Can be null - backend will create thread
            agentId: agentId,
            prompt: prompt,
            attachments: chatAttachments,
            overrideRole: overrideRole,
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

  // Simple helper for sending introductions
  Future<void> sendIntroduction({
    required String agentId,
    required String introduction,
  }) async {
    state = state.copyWith(isSendingIntroduction: true);
    await sendMessage(
      agentId: agentId,
      prompt: introduction,
      overrideRole: "system",
    );
    state = state.copyWith(isSendingIntroduction: false);
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
