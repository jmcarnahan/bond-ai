import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutterui/providers/thread_chat/chat_session_state.dart';
import 'package:flutterui/presentation/widgets/typing_indicator.dart';
import 'package:flutterui/presentation/screens/chat/widgets/image_message_widget.dart';

class MessageListView extends ConsumerWidget {
  final ChatSessionState chatState;
  final ScrollController scrollController;
  final String agentName;

  const MessageListView({
    super.key,
    required this.chatState,
    required this.scrollController,
    required this.agentName,
  });

  /// Creates a markdown stylesheet with consistent theming
  MarkdownStyleSheet _createMarkdownStyleSheet(TextTheme textTheme, Color messageTextColor) {
    return MarkdownStyleSheet(
      p: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      h1: textTheme.headlineLarge?.copyWith(color: messageTextColor),
      h2: textTheme.headlineMedium?.copyWith(color: messageTextColor),
      h3: textTheme.headlineSmall?.copyWith(color: messageTextColor),
      h4: textTheme.titleLarge?.copyWith(color: messageTextColor),
      h5: textTheme.titleMedium?.copyWith(color: messageTextColor),
      h6: textTheme.titleSmall?.copyWith(color: messageTextColor),
      em: textTheme.bodyMedium?.copyWith(color: messageTextColor, fontStyle: FontStyle.italic),
      strong: textTheme.bodyMedium?.copyWith(color: messageTextColor, fontWeight: FontWeight.bold),
      del: textTheme.bodyMedium?.copyWith(color: messageTextColor, decoration: TextDecoration.lineThrough),
      blockquote: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      img: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      checkbox: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      blockSpacing: 8,
      listIndent: 24,
      listBullet: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      tableHead: textTheme.bodyMedium?.copyWith(color: messageTextColor, fontWeight: FontWeight.bold),
      tableBody: textTheme.bodyMedium?.copyWith(color: messageTextColor),
      tableHeadAlign: TextAlign.center,
      tableBorder: TableBorder.all(color: messageTextColor.withValues(alpha: 0.3), width: 1),
      tableColumnWidth: const FlexColumnWidth(),
      blockquotePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      blockquoteDecoration: BoxDecoration(
        color: messageTextColor.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(4),
        border: Border(
          left: BorderSide(color: messageTextColor.withValues(alpha: 0.5), width: 4),
        ),
      ),
      codeblockPadding: const EdgeInsets.all(12),
      codeblockDecoration: BoxDecoration(
        color: messageTextColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(4),
      ),
      code: textTheme.bodyMedium?.copyWith(
        color: messageTextColor,
        fontFamily: 'monospace',
        backgroundColor: messageTextColor.withValues(alpha: 0.08),
      ),
    );
  }

  /// Creates a styled markdown widget
  Widget _buildMarkdownWidget(String content, TextTheme textTheme, Color messageTextColor) {
    return MarkdownBody(
      data: content,
      styleSheet: _createMarkdownStyleSheet(textTheme, messageTextColor),
      selectable: true,
    );
  }

  Widget _buildEmptyChatPlaceholder(BuildContext context, String agentName, bool isSendingIntroduction) {
    final textTheme = Theme.of(context).textTheme;
    
    if (isSendingIntroduction) {
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
              'Starting a conversation with $agentName',
              style: textTheme.headlineSmall?.copyWith(
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 16),
            const TypingIndicator(),
          ],
        ),
      );
    }
    
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
      return _buildEmptyChatPlaceholder(context, agentName, chatState.isSendingIntroduction);
    }

    return ListView.builder(
      controller: scrollController,
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
            dotColor: messageTextColor.withValues(alpha: 0.7),
          );
        } else if ((message.type == 'image_file' || message.type == 'image') && message.imageData != null) {
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
                  child: _buildMarkdownWidget(message.content, textTheme, messageTextColor),
                ),
            ],
          );
        } else if (message.type == 'file') {
          coreMessageWidget = Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.description, // Use Icons.insert_drive_file for a generic file
                color: messageTextColor, // maybe a different color?
                size: 22,
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  message.content,
                  style: textTheme.bodyMedium?.copyWith(
                    color: messageTextColor,
                    fontStyle: FontStyle.italic,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          );
        } else {
          // Use MarkdownBody for text messages to render markdown properly
          if (message.type == 'text' && !isUserMessage) {
            coreMessageWidget = _buildMarkdownWidget(message.content, textTheme, messageTextColor);
          } else {
            coreMessageWidget = SelectableText(
              message.content,
              style: textTheme.bodyMedium?.copyWith(color: messageTextColor),
            );
          }
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
                  backgroundColor: colorScheme.primary.withValues(alpha: 0.8),
                  radius: 16,
                  child: Icon(Icons.person_outline, color: colorScheme.onPrimary, size: 20),
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
            } else {
              displayContent = Flexible(
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
