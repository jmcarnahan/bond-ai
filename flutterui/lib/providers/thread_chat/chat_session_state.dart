import 'package:flutterui/data/models/message_model.dart';

class ChatSessionState {
  final String? currentThreadId;
  final List<Message> messages;
  final bool isLoadingMessages;
  final bool isSendingMessage;
  final bool isSendingIntroduction;
  final String? errorMessage;

  ChatSessionState({
    this.currentThreadId,
    this.messages = const [],
    this.isLoadingMessages = false,
    this.isSendingMessage = false,
    this.isSendingIntroduction = false,
    this.errorMessage,
  });

  ChatSessionState copyWith({
    String? currentThreadId,
    bool? clearCurrentThreadId,
    List<Message>? messages,
    bool? isLoadingMessages,
    bool? isSendingMessage,
    bool? isSendingIntroduction,
    String? errorMessage,
    bool? clearErrorMessage,
  }) {
    return ChatSessionState(
      currentThreadId:
          clearCurrentThreadId == true
              ? null
              : currentThreadId ?? this.currentThreadId,
      messages: messages ?? this.messages,
      isLoadingMessages: isLoadingMessages ?? this.isLoadingMessages,
      isSendingMessage: isSendingMessage ?? this.isSendingMessage,
      isSendingIntroduction: isSendingIntroduction ?? this.isSendingIntroduction,
      errorMessage:
          clearErrorMessage == true ? null : errorMessage ?? this.errorMessage,
    );
  }
}
