import 'dart:convert';
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;
// ignore: avoid_web_libraries_in_flutter
import 'dart:js_util' as js_util;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:markdown/markdown.dart' as md;
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/providers/cached_agent_details_provider.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';
import 'package:flutterui/presentation/screens/chat/widgets/file_card.dart';
import 'package:flutterui/presentation/screens/chat/widgets/feedback_dialog.dart';
import 'package:flutterui/providers/services/service_providers.dart';

class ChatMessageItem extends ConsumerStatefulWidget {
  final Message message;
  final bool isSendingMessage;
  final bool isLastMessage;
  final Map<String, Uint8List> imageCache;
  final String? threadId;
  final Function(String messageId, String? feedbackType, String? feedbackMessage)? onFeedbackChanged;

  const ChatMessageItem({
    super.key,
    required this.message,
    required this.isSendingMessage,
    required this.isLastMessage,
    required this.imageCache,
    this.threadId,
    this.onFeedbackChanged,
  });

  @override
  ConsumerState<ChatMessageItem> createState() => _ChatMessageItemState();
}

class _ChatMessageItemState extends ConsumerState<ChatMessageItem> {
  bool _showFeedbackDialog = false;
  String? _selectedFeedbackType;
  bool _isSubmitting = false;

  Message get message => widget.message;
  bool get isSendingMessage => widget.isSendingMessage;
  bool get isLastMessage => widget.isLastMessage;
  Map<String, Uint8List> get imageCache => widget.imageCache;

  @override
  Widget build(BuildContext context) {
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
    final showFeedbackThumbs = !isUserMessage && !isSendingMessage && message.content.isNotEmpty;

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
              child: Column(
                crossAxisAlignment: isUserMessage
                    ? CrossAxisAlignment.end
                    : CrossAxisAlignment.start,
                children: [
                  Container(
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
                    child: Theme(
                      data: isUserMessage
                          ? Theme.of(context).copyWith(
                              textSelectionTheme: TextSelectionThemeData(
                                selectionColor:
                                    Colors.white.withValues(alpha: 0.3),
                              ),
                            )
                          : Theme.of(context),
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
                  if (showFeedbackThumbs)
                    _buildFeedbackThumbs(colorScheme),
                  if (_showFeedbackDialog && _selectedFeedbackType != null)
                    Container(
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(context).size.width * 0.75,
                      ),
                      child: FeedbackDialog(
                        feedbackType: _selectedFeedbackType!,
                        existingMessage: message.feedbackMessage,
                        isEditing: message.hasFeedback,
                        onCancel: () {
                          setState(() {
                            _showFeedbackDialog = false;
                            _selectedFeedbackType = null;
                          });
                        },
                        onSubmit: _handleFeedbackSubmit,
                        onDelete: message.hasFeedback ? _handleFeedbackDelete : null,
                      ),
                    ),
                ],
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

  Widget _buildFeedbackThumbs(ColorScheme colorScheme) {
    final hasUpFeedback = message.feedbackType == 'up';
    final hasDownFeedback = message.feedbackType == 'down';
    final hasImage = message.imageData != null;

    return Padding(
      padding: const EdgeInsets.only(top: 4, left: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _FeedbackThumb(
            isUp: true,
            isFilled: hasUpFeedback,
            isSubmitting: _isSubmitting,
            colorScheme: colorScheme,
            onTap: () => _handleThumbTap('up'),
          ),
          const SizedBox(width: 4),
          _FeedbackThumb(
            isUp: false,
            isFilled: hasDownFeedback,
            isSubmitting: _isSubmitting,
            colorScheme: colorScheme,
            onTap: () => _handleThumbTap('down'),
          ),
          if (!hasImage) ...[
            const SizedBox(width: 8),
            _ImageActionButton(
              icon: Icons.content_copy_rounded,
              tooltip: 'Copy text',
              colorScheme: colorScheme,
              onTap: () => _copyTextToClipboard(context),
            ),
          ],
          if (hasImage) ...[
            const SizedBox(width: 8),
            _ImageActionButton(
              icon: Icons.copy_rounded,
              tooltip: 'Copy image',
              colorScheme: colorScheme,
              onTap: () => _copyImageToClipboard(context),
            ),
            const SizedBox(width: 4),
            _ImageActionButton(
              icon: Icons.download_rounded,
              tooltip: 'Download image',
              colorScheme: colorScheme,
              onTap: () => _downloadImage(),
            ),
          ],
        ],
      ),
    );
  }

  void _handleThumbTap(String feedbackType) {
    setState(() {
      _selectedFeedbackType = feedbackType;
      _showFeedbackDialog = true;
    });
  }

  void _copyTextToClipboard(BuildContext context) {
    final plainText = _MarkdownTextExtractor().extract(message.content);
    Clipboard.setData(ClipboardData(text: plainText));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Text copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  Future<void> _copyImageToClipboard(BuildContext context) async {
    final bytes = imageCache[message.id];
    if (bytes == null) return;

    try {
      final blob = html.Blob([bytes], 'image/png');
      final clipboardItem = js_util.callConstructor(
        js_util.getProperty(html.window, 'ClipboardItem'),
        [js_util.jsify({'image/png': blob})],
      );
      final clipboard = html.window.navigator.clipboard;
      if (clipboard == null) throw Exception('Clipboard API not available');
      await js_util.promiseToFuture(
        js_util.callMethod(
          clipboard,
          'write',
          [js_util.jsify([clipboardItem])],
        ),
      );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Image copied to clipboard'),
            duration: Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Failed to copy image to clipboard'),
            duration: Duration(seconds: 2),
          ),
        );
      }
    }
  }

  void _downloadImage() {
    final bytes = imageCache[message.id];
    if (bytes == null) return;

    final blob = html.Blob([bytes], 'image/png');
    final url = html.Url.createObjectUrlFromBlob(blob);
    final anchor = html.AnchorElement()
      ..href = url
      ..download = 'chart_${message.id}.png'
      ..style.display = 'none';
    html.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
    html.Url.revokeObjectUrl(url);
  }

  Future<void> _handleFeedbackSubmit(String feedbackType, String? feedbackMessage) async {
    if (widget.threadId == null) return;

    setState(() => _isSubmitting = true);

    try {
      final threadService = ref.read(threadServiceProvider);
      await threadService.submitFeedback(
        widget.threadId!,
        message.id,
        feedbackType,
        feedbackMessage,
      );

      widget.onFeedbackChanged?.call(message.id, feedbackType, feedbackMessage);

      if (mounted) {
        setState(() {
          _showFeedbackDialog = false;
          _selectedFeedbackType = null;
          _isSubmitting = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSubmitting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to submit feedback: $e')),
        );
      }
    }
  }

  Future<void> _handleFeedbackDelete() async {
    if (widget.threadId == null) return;

    setState(() => _isSubmitting = true);

    try {
      final threadService = ref.read(threadServiceProvider);
      await threadService.deleteFeedback(widget.threadId!, message.id);

      widget.onFeedbackChanged?.call(message.id, null, null);

      if (mounted) {
        setState(() {
          _showFeedbackDialog = false;
          _selectedFeedbackType = null;
          _isSubmitting = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isSubmitting = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete feedback: $e')),
        );
      }
    }
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

class _FeedbackThumb extends StatelessWidget {
  final bool isUp;
  final bool isFilled;
  final bool isSubmitting;
  final ColorScheme colorScheme;
  final VoidCallback onTap;

  const _FeedbackThumb({
    required this.isUp,
    required this.isFilled,
    required this.isSubmitting,
    required this.colorScheme,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: isSubmitting ? null : onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: Icon(
          isUp
              ? (isFilled ? Icons.thumb_up : Icons.thumb_up_outlined)
              : (isFilled ? Icons.thumb_down : Icons.thumb_down_outlined),
          size: 16,
          color: isFilled
              ? colorScheme.primary
              : colorScheme.onSurfaceVariant.withAlpha(153),
        ),
      ),
    );
  }
}

class _ImageActionButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final ColorScheme colorScheme;
  final VoidCallback onTap;

  const _ImageActionButton({
    required this.icon,
    required this.tooltip,
    required this.colorScheme,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Icon(
            icon,
            size: 16,
            color: colorScheme.onSurfaceVariant.withAlpha(153),
          ),
        ),
      ),
    );
  }
}

class _MarkdownTextExtractor implements md.NodeVisitor {
  final StringBuffer _buffer = StringBuffer();

  String extract(String markdownText) {
    _buffer.clear();
    final lines = markdownText.split('\n');
    final document = md.Document().parseLines(lines);
    for (final node in document) {
      node.accept(this);
    }
    return _buffer.toString().trim();
  }

  @override
  bool visitElementBefore(md.Element element) {
    if (_buffer.isNotEmpty &&
        !_buffer.toString().endsWith('\n') &&
        const ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre']
            .contains(element.tag)) {
      _buffer.write('\n');
    }
    return true;
  }

  @override
  void visitElementAfter(md.Element element) {
    if (const ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote']
        .contains(element.tag)) {
      if (!_buffer.toString().endsWith('\n')) {
        _buffer.write('\n');
      }
    }
  }

  @override
  void visitText(md.Text text) {
    _buffer.write(text.text);
  }
}
