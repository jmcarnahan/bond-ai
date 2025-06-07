import 'dart:async';

import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/chat_models.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/data/services/agent_service.dart';
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


  Future<void> sendMessage({
    required String agentId,
    required String prompt,
    List<PlatformFile>? attachedFiles,
    String overrideRole = "user"
  }) async {
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
            threadId: state.currentThreadId,  // Can be null
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

  Future<void> _sendIntroductionMessageAndWait({
    required String agentId,
    required String introduction,
  }) async {
    final completer = Completer<void>();
    
    logger.i("[ChatSessionNotifier] _sendIntroductionMessageAndWait called - agentId: $agentId");
    logger.i("[ChatSessionNotifier] Introduction length: ${introduction.length} chars");
    
    if (state.currentThreadId == null) {
      logger.i("[ChatSessionNotifier] ERROR: No active thread selected for introduction");
      state = state.copyWith(errorMessage: "No active thread selected.");
      completer.completeError("No active thread selected.");
      return completer.future;
    }
    if (introduction.isEmpty) {
      logger.i("[ChatSessionNotifier] ERROR: Introduction is empty");
      completer.complete();
      return completer.future;
    }
    
    logger.i("[ChatSessionNotifier] Sending introduction message for agent: $agentId on thread: ${state.currentThreadId}");
    state = state.copyWith(isSendingMessage: true, clearErrorMessage: true);

    final assistantMessageId = DateTime.now().millisecondsSinceEpoch.toString();
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
      logger.i("[ChatSessionNotifier] Creating stream subscription for introduction...");
      chatStreamSubscription?.cancel();
      chatStreamSubscription = _chatService
          .streamChatResponse(
            threadId: state.currentThreadId,  // Can be null
            agentId: agentId,
            prompt: introduction,
            overrideRole: "system",
          )
          .listen(
            (chunk) {
              // logger.i("[ChatSessionNotifier] Introduction stream received chunk");
              handleStreamData(chunk, assistantMessageIndex);
            },
            onDone: () {
              logger.i("[ChatSessionNotifier] Introduction stream completed");
              handleStreamDone(assistantMessageIndex);
              completer.complete();
            },
            onError: (error) {
              logger.i("[ChatSessionNotifier] Introduction stream error: $error");
              handleStreamError(error, assistantMessageIndex);
              completer.completeError(error);
            },
          );
      logger.i("[ChatSessionNotifier] Stream subscription created successfully");
      
      return completer.future;
    } catch (e) {
      logger.i("[ChatSessionNotifier] Error sending introduction message: ${e.toString()}");
      state = state.copyWith(
        isSendingMessage: false,
        errorMessage: e.toString(),
      );
      completer.completeError(e);
      return completer.future;
    }
  }

  Future<void> sendIntroductionMessage({
    required String agentId,
    required String introduction,
  }) async {
    logger.i("[ChatSessionNotifier] sendIntroductionMessage called - agentId: $agentId");
    logger.i("[ChatSessionNotifier] Introduction length: ${introduction.length} chars");
    
    if (introduction.isEmpty) {
      logger.i("[ChatSessionNotifier] ERROR: Introduction is empty");
      return;
    }
    
    // Send with current thread_id (can be null - backend will create thread)
    logger.i("[ChatSessionNotifier] Sending introduction message for agent: $agentId on thread: ${state.currentThreadId ?? 'null (will create new)'}");
    state = state.copyWith(isSendingMessage: true, clearErrorMessage: true);

    final assistantMessageId = DateTime.now().millisecondsSinceEpoch.toString();
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
      logger.i("[ChatSessionNotifier] Creating stream subscription for introduction...");
      chatStreamSubscription?.cancel();
      chatStreamSubscription = _chatService
          .streamChatResponse(
            threadId: state.currentThreadId!,
            agentId: agentId,
            prompt: introduction,
            overrideRole: "system",
          )
          .listen(
            (chunk) {
              logger.i("[ChatSessionNotifier] Introduction stream received chunk");
              handleStreamData(chunk, assistantMessageIndex);
            },
            onDone: () {
              logger.i("[ChatSessionNotifier] Introduction stream completed");
              handleStreamDone(assistantMessageIndex);
            },
            onError: (error) {
              logger.i("[ChatSessionNotifier] Introduction stream error: $error");
              handleStreamError(error, assistantMessageIndex);
            },
          );
      logger.i("[ChatSessionNotifier] Stream subscription created successfully");
    } catch (e) {
      logger.i("[ChatSessionNotifier] Error sending introduction message: ${e.toString()}");
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
