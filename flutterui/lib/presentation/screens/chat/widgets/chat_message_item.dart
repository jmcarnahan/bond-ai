import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/providers/cached_agent_details_provider.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';
import 'package:flutterui/presentation/screens/chat/widgets/file_card.dart';

class ChatMessageItem extends ConsumerWidget {
  final Message message;
  final bool isSendingMessage;
  final bool isLastMessage;
  final Map<String, Uint8List> imageCache;

  const ChatMessageItem({
    super.key,
    required this.message,
    required this.isSendingMessage,
    required this.isLastMessage,
    required this.imageCache,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Skip rendering messages with empty content (except when showing typing indicator)
    if (message.content.isEmpty &&
        !(message.role == 'assistant' &&
            isSendingMessage &&
            isLastMessage)) {
      return const SizedBox.shrink();
    }

    final isUserMessage = message.role == 'user';
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return RepaintBoundary(
      child: Padding(
        key: ValueKey(message.id),
        padding: const EdgeInsets.symmetric(
          vertical: 6.0,
          horizontal: 16.0,
        ),
        child: Row(
          mainAxisAlignment:
              isUserMessage
                  ? MainAxisAlignment.end
                  : MainAxisAlignment.start,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!isUserMessage) ...[
              _AssistantAvatar(
                message: message,
                colorScheme: colorScheme,
                ref: ref,
              ),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: Container(
                constraints: BoxConstraints(
                  maxWidth: MediaQuery.of(context).size.width * 0.75,
                ),
                padding: const EdgeInsets.symmetric(
                  vertical: 10.0,
                  horizontal: 14.0,
                ),
                decoration: BoxDecoration(
                  color: isUserMessage
                      ? colorScheme.primary
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(16.0),
                ),
                child: DefaultTextStyle(
                  style: TextStyle(
                    color: isUserMessage
                        ? colorScheme.onPrimary
                        : colorScheme.onSurfaceVariant,
                    fontSize: 14,
                  ),
                  child: _buildMessageContent(context),
                ),
              ),
            ),
            if (isUserMessage) ...[
              const SizedBox(width: 8),
              CircleAvatar(
                backgroundColor: colorScheme.primary.withValues(
                  alpha: 0.8,
                ),
                radius: 16,
                child: Icon(
                  Icons.person_outline,
                  color: colorScheme.onPrimary,
                  size: 20,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMessageContent(BuildContext context) {
    if ((message.type == 'image_file' || message.type == 'image') &&
        message.imageData != null) {
      return _buildImageContent(context);
    }

    // Handle file downloads
    if (message.type == 'file_link' && message.content.isNotEmpty) {
      return FileCard(fileDataJson: message.content);
    }

    // Show typing indicator for empty assistant messages while streaming
    if (message.role == 'assistant' &&
        isSendingMessage &&
        isLastMessage &&
        message.content.isEmpty) {
      return const Text('...', style: TextStyle(fontSize: 14));
    }

    if (message.role == 'assistant' && message.type == 'text') {
      return _buildMarkdownContent(context);
    }

    return SelectableText(
      message.content,
      style: const TextStyle(fontSize: 14),
    );
  }

  Widget _buildImageContent(BuildContext context) {
    try {
      final cacheKey = message.id;
      Uint8List imageBytes;

      if (imageCache.containsKey(cacheKey)) {
        imageBytes = imageCache[cacheKey]!;
      } else {
        imageBytes = base64Decode(message.imageData!);
        imageCache[cacheKey] = imageBytes;
      }

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.6,
              maxHeight: 300,
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.memory(
                imageBytes,
                fit: BoxFit.contain,
                gaplessPlayback: true,
              ),
            ),
          ),
          if (message.content.isNotEmpty && message.content != '[Image]')
            Padding(
              padding: const EdgeInsets.only(top: 8.0),
              child: Text(
                message.content,
                style: const TextStyle(fontSize: 14),
              ),
            ),
        ],
      );
    } catch (e) {
      return const Text(
        'Error loading image',
        style: TextStyle(fontSize: 14, color: Colors.red),
      );
    }
  }

  Widget _buildMarkdownContent(BuildContext context) {
    return Builder(
      builder: (context) {
        final defaultStyle = DefaultTextStyle.of(context).style;
        return SelectionArea(
          child: MarkdownBody(
            data: message.content,
            styleSheet: MarkdownStyleSheet.fromTheme(
              Theme.of(context),
            ).copyWith(
              p: defaultStyle,
              h1: defaultStyle.copyWith(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
              h2: defaultStyle.copyWith(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
              h3: defaultStyle.copyWith(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
              code: defaultStyle.copyWith(
                fontFamily: 'monospace',
                backgroundColor: defaultStyle.color?.withValues(
                  alpha: 0.08,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _AssistantAvatar extends StatelessWidget {
  final Message message;
  final ColorScheme colorScheme;
  final WidgetRef ref;

  const _AssistantAvatar({
    required this.message,
    required this.colorScheme,
    required this.ref,
  });

  @override
  Widget build(BuildContext context) {
    if (message.agentId == null) {
      // Fallback for messages without agentId
      return CircleAvatar(
        backgroundColor: colorScheme.surfaceContainerHighest,
        radius: 16,
        child: Icon(
          Icons.smart_toy_outlined,
          color: colorScheme.primary,
          size: 20,
        ),
      );
    }
    
    return ref.watch(getCachedAgentDetailsProvider(message.agentId!)).when(
      data: (agent) {
        if (agent == null) {
          // Fallback if agent not found
          return CircleAvatar(
            backgroundColor: colorScheme.surfaceContainerHighest,
            radius: 16,
            child: Icon(
              Icons.smart_toy_outlined,
              color: colorScheme.primary,
              size: 20,
            ),
          );
        }
        
        return Column(
          children: [
            // Smaller icon for chat messages
            AgentIcon(
              agentName: agent.name,
              metadata: agent.metadata,
              size: 32,
              showBackground: true,
              isSelected: false,
            ),
            Container(
              width: 32,
              margin: const EdgeInsets.only(top: 2),
              child: Text(
                agent.name,
                style: TextStyle(
                  fontSize: 9,
                  color: colorScheme.onSurface.withAlpha(179),
                ),
                textAlign: TextAlign.center,
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
              ),
            ),
          ],
        );
      },
      loading: () => CircleAvatar(
        backgroundColor: colorScheme.surfaceContainerHighest,
        radius: 16,
        child: const SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      error: (_, __) => CircleAvatar(
        backgroundColor: colorScheme.surfaceContainerHighest,
        radius: 16,
        child: Icon(
          Icons.smart_toy_outlined,
          color: colorScheme.primary,
          size: 20,
        ),
      ),
    );
  }
}