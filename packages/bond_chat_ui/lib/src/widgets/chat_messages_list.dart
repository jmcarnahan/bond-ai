import 'dart:typed_data';
import 'package:flutter/material.dart';

import '../models/message.dart';
import 'chat_message_item.dart';

class ChatMessagesList extends StatelessWidget {
  final List<Message> messages;
  final bool isSendingMessage;
  final ScrollController scrollController;
  final Map<String, Uint8List> imageCache;
  final void Function(String prompt)? onSendPrompt;
  final Future<void> Function(String messageId, String feedbackType, String? feedbackMessage)? onFeedbackSubmit;
  final Future<void> Function(String messageId)? onFeedbackDelete;
  final void Function(String messageId, String? feedbackType, String? feedbackMessage)? onFeedbackChanged;
  final Widget Function(BuildContext context, Message message)? assistantAvatarBuilder;
  final Widget Function(BuildContext context, String fileDataJson)? fileCardBuilder;

  const ChatMessagesList({
    super.key,
    required this.messages,
    required this.isSendingMessage,
    required this.scrollController,
    required this.imageCache,
    this.onSendPrompt,
    this.onFeedbackSubmit,
    this.onFeedbackDelete,
    this.onFeedbackChanged,
    this.assistantAvatarBuilder,
    this.fileCardBuilder,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: scrollController,
      padding: const EdgeInsets.symmetric(
        vertical: 8.0,
        horizontal: 72.0,
      ),
      itemCount: messages.length,
      itemBuilder: (context, index) {
        final message = messages[index];
        final isLastMessage = index == messages.length - 1;

        return ChatMessageItem(
          message: message,
          isSendingMessage: isSendingMessage,
          isLastMessage: isLastMessage,
          imageCache: imageCache,
          onFeedbackSubmit: onFeedbackSubmit,
          onFeedbackDelete: onFeedbackDelete,
          onFeedbackChanged: onFeedbackChanged,
          onSendPrompt: onSendPrompt,
          assistantAvatarBuilder: assistantAvatarBuilder,
          fileCardBuilder: fileCardBuilder,
        );
      },
    );
  }
}
