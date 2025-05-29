import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart'; // Added this import
import 'package:flutterui/presentation/widgets/typing_indicator.dart';
import 'package:flutterui/presentation/screens/chat/widgets/image_message_widget.dart';

class MessageListView extends ConsumerWidget {
  final ChatSessionState chatState;
  final ScrollController scrollController;
  final String agentName; // For empty placeholder

  const MessageListView({
    super.key,
    required this.chatState,
    required this.scrollController,
    required this.agentName,
  });

  Widget _buildEmptyChatPlaceholder(BuildContext context, String agentName) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircleAvatar(
            radius: 40,
            backgroundColor: Colors.grey.shade200,
            child: Icon(
              Icons.smart_toy_outlined,
              size: 48,
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Start a conversation',
            style: textTheme.headlineSmall?.copyWith(
              color: Colors.grey.shade700,
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40.0),
            child: Text(
              'Send a message to begin your chat with $agentName.',
              textAlign: TextAlign.center,
              style: textTheme.bodyLarge?.copyWith(
                color: Colors.grey.shade500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    if (chatState.isLoadingMessages && chatState.messages.isEmpty) {
      return const Center(child: TypingIndicator());
    }

    if (chatState.messages.isEmpty) {
      return _buildEmptyChatPlaceholder(context, agentName);
    }

    return ListView.builder(
      controller: scrollController,
      // Greatly reduce horizontal padding on the ListView itself
      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 72.0), 
      itemCount: chatState.messages.length,
      itemBuilder: (context, index) {
        final message = chatState.messages[index];
        final isUserMessage = message.role == 'user';
        final isError = message.isError;

        Widget coreMessageWidget;
        Color messageTextColor;

        if (isError) {
          messageTextColor = colorScheme.onErrorContainer;
        } else if (isUserMessage) {
          messageTextColor = colorScheme.onPrimary;
        } else {
          messageTextColor = colorScheme.onSurfaceVariant;
        }

        if (message.role == 'assistant' &&
            chatState.isSendingMessage &&
            index == chatState.messages.length - 1 &&
            message.content.isEmpty) {
          coreMessageWidget = TypingIndicator(
            dotColor: messageTextColor.withOpacity(0.7),
          );
        } else if (message.type == 'image_file' && message.imageData != null) {
          // Handle image messages
          coreMessageWidget = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ImageMessageWidget(
                base64ImageData: message.imageData!,
                maxWidth: MediaQuery.of(context).size.width * 0.6,
                maxHeight: 300,
              ),
              if (message.content.isNotEmpty && message.content != '[Image]')
                Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: SelectableText(
                    message.content,
                    style: textTheme.bodyMedium?.copyWith(color: messageTextColor),
                  ),
                ),
            ],
          );
        } else {
          // Handle text messages
          coreMessageWidget = SelectableText(
            message.content,
            style: textTheme.bodyMedium?.copyWith(color: messageTextColor),
          );
        }

        Widget finalMessageContent;
        if (isError) {
          final bubbleColor = colorScheme.errorContainer;
          final borderRadius = BorderRadius.circular(16.0);
          finalMessageContent = Card(
            color: bubbleColor,
            elevation: 0.5,
            shape: RoundedRectangleBorder(borderRadius: borderRadius),
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10.0, horizontal: 14.0),
              child: coreMessageWidget,
            ),
          );
        } else if (isUserMessage) {
          final bubbleColor = colorScheme.primary;
          final borderRadius = BorderRadius.circular(16.0);
          finalMessageContent = Card(
            color: bubbleColor,
            elevation: 0.5,
            shape: RoundedRectangleBorder(borderRadius: borderRadius),
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10.0, horizontal: 14.0),
              child: coreMessageWidget,
            ),
          );
        } else {
          finalMessageContent = Padding(
            padding: const EdgeInsets.only(top: 2.0),
            child: coreMessageWidget,
          );
        }

        if (isUserMessage) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Flexible(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                    child: finalMessageContent,
                  ),
                ),
                const SizedBox(width: 8),
                CircleAvatar(
                  backgroundColor: colorScheme.primary.withOpacity(0.8),
                  child: Icon(Icons.person_outline, color: colorScheme.onPrimary, size: 20),
                  radius: 16,
                ),
              ],
            ),
          );
        } else {
          if (isError) {
            Widget avatar = CircleAvatar(
              backgroundColor: colorScheme.errorContainer,
              radius: 16,
              child: Icon(
                Icons.error_outline,
                color: colorScheme.onErrorContainer,
                size: 20,
              ),
            );
            Widget displayContent = Flexible(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                child: finalMessageContent,
              ),
            );
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 6.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.start,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  avatar,
                  const SizedBox(width: 8),
                  displayContent,
                ],
              ),
            );
          } else {
            bool isAgentTyping = message.role == 'assistant' &&
                chatState.isSendingMessage &&
                index == chatState.messages.length - 1 &&
                message.content.isEmpty;

            Widget displayContent;
            if (isAgentTyping) {
              displayContent = finalMessageContent;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.start,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    displayContent,
                  ],
                ),
              );
            } else { // Regular assistant message
              displayContent = Flexible(
                child: ConstrainedBox( // Add ConstrainedBox here as well for consistency
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                  child: finalMessageContent,
                ),
              );
              return Padding(
                // Reduce horizontal padding here if ListView padding is already handling spacing
                padding: const EdgeInsets.symmetric(vertical: 6.0), // Removed horizontal: 32.0
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.start,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Consider adding an avatar for assistant messages if desired, or ensure spacing
                    // For now, just the content, assuming ListView padding gives enough edge spacing.
                    displayContent,
                  ],
                ),
              );
            }
          }
        }
      },
    );
  }
}
