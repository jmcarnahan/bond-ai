import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart' as bond;

import 'package:flutterui/providers/cached_agent_details_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';

/// Riverpod wrapper that bridges bond_chat_ui's callback-based ChatMessageItem
/// to the app's provider-based services.
class BondChatMessageItem extends ConsumerWidget {
  final bond.Message message;
  final bool isSendingMessage;
  final bool isLastMessage;
  final Map<String, Uint8List> imageCache;
  final String? threadId;
  final void Function(String messageId, String? feedbackType, String? feedbackMessage)? onFeedbackChanged;
  final void Function(String prompt)? onSendPrompt;

  const BondChatMessageItem({
    super.key,
    required this.message,
    required this.isSendingMessage,
    required this.isLastMessage,
    required this.imageCache,
    this.threadId,
    this.onFeedbackChanged,
    this.onSendPrompt,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return bond.ChatMessageItem(
      message: message,
      isSendingMessage: isSendingMessage,
      isLastMessage: isLastMessage,
      imageCache: imageCache,
      onSendPrompt: onSendPrompt,
      onFeedbackChanged: onFeedbackChanged,
      onFeedbackSubmit: (messageId, feedbackType, feedbackMessage) async {
        if (threadId == null) {
          throw StateError('Cannot submit feedback: no active thread');
        }
        final threadService = ref.read(threadServiceProvider);
        await threadService.submitFeedback(
          threadId!,
          messageId,
          feedbackType,
          feedbackMessage,
        );
      },
      onFeedbackDelete: (messageId) async {
        if (threadId == null) {
          throw StateError('Cannot delete feedback: no active thread');
        }
        final threadService = ref.read(threadServiceProvider);
        await threadService.deleteFeedback(threadId!, messageId);
      },
      assistantAvatarBuilder: (context, message) {
        return _AssistantAvatar(
          message: message,
          ref: ref,
        );
      },
      fileCardBuilder: (context, fileDataJson) {
        return bond.FileCard(
          fileDataJson: fileDataJson,
          onDownload: (fileId, fileName) async {
            final fileService = ref.read(fileServiceProvider);
            await fileService.downloadFile(fileId, fileName);
          },
        );
      },
    );
  }
}

class _AssistantAvatar extends StatelessWidget {
  final bond.Message message;
  final WidgetRef ref;

  const _AssistantAvatar({
    required this.message,
    required this.ref,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    if (message.agentId == null) {
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
