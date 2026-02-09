import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/presentation/screens/chat/widgets/clipboard_helper.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_attachment_bar.dart';
import 'package:flutterui/providers/core_providers.dart' show appThemeProvider;

class MessageInputBar extends ConsumerStatefulWidget {
  final TextEditingController textController;
  final FocusNode focusNode;
  final bool isTextFieldFocused;
  final bool isSendingMessage;
  final VoidCallback onSendMessage;
  final void Function(List<PlatformFile>) onFileAttachmentsChanged;
  final List<PlatformFile> attachments;
  final VoidCallback? onCreateNewThread;

  const MessageInputBar({
    super.key,
    required this.textController,
    required this.focusNode,
    required this.isTextFieldFocused,
    required this.isSendingMessage,
    required this.onSendMessage,
    required this.onFileAttachmentsChanged,
    required this.attachments,
    this.onCreateNewThread,
  });

  @override
  ConsumerState<MessageInputBar> createState() => _MessageInputBarState();
}

class _MessageInputBarState extends ConsumerState<MessageInputBar> {
  late final FocusNode _keyboardFocusNode;
  late final ScrollController _inputScrollController;

  /// Replace non-ASCII characters in filenames with spaces.
  String _sanitizeFilename(String name) {
    return name.replaceAll(RegExp(r'[^\x20-\x7E]'), ' ').replaceAll(RegExp(r' {2,}'), ' ').trim();
  }

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: true);

    if (result != null && result.files.isNotEmpty) {
      final sanitized = result.files.map((f) => PlatformFile(
        name: _sanitizeFilename(f.name),
        size: f.size,
        bytes: f.bytes,
      )).toList();
      final updated = List<PlatformFile>.from(widget.attachments)
        ..addAll(sanitized);
      widget.onFileAttachmentsChanged(List.unmodifiable(updated));
    }
  }

  void _onAttachmentRemoved(PlatformFile file) {
    final updated = List<PlatformFile>.from(widget.attachments)..remove(file);
    widget.onFileAttachmentsChanged(updated);
  }

  Future<void> _handlePaste() async {
    final files = await ClipboardHelper.readFilesFromClipboard();
    if (files.isEmpty) return;

    final platformFiles = files
        .map((f) => PlatformFile(
              name: f.name,
              size: f.bytes.length,
              bytes: f.bytes,
            ))
        .toList();

    final updated = List<PlatformFile>.from(widget.attachments)
      ..addAll(platformFiles);
    widget.onFileAttachmentsChanged(updated);
  }

  @override
  void initState() {
    super.initState();
    _keyboardFocusNode = FocusNode();
    _inputScrollController = ScrollController();
  }

  @override
  void dispose() {
    _keyboardFocusNode.dispose();
    _inputScrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final appTheme = ref.watch(appThemeProvider);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 16.0),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        boxShadow: [
          BoxShadow(
            offset: const Offset(0, -2),
            blurRadius: 8.0,
            spreadRadius: 0,
            color: colorScheme.shadow.withValues(alpha: 0.1),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        spacing: 12.0,
        children: [
          MessageAttachmentBar(
            attachments: widget.attachments,
            onAttachmentRemoved: _onAttachmentRemoved,
          ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              if (widget.onCreateNewThread != null) ...[
                _buildActionButton(
                  icon: Icons.add_rounded,
                  onPressed:
                      widget.isSendingMessage ? null : widget.onCreateNewThread,
                  tooltip: 'New thread',
                ),
                const SizedBox(width: 12.0),
              ],
              Expanded(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  constraints: BoxConstraints(
                    minHeight: 48,
                    maxHeight: MediaQuery.of(context).size.height * 0.4,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(28.0),
                    color: colorScheme.surfaceContainerHighest,
                    border: Border.all(
                      color:
                          widget.isTextFieldFocused
                              ? colorScheme.primary
                              : colorScheme.outline,
                      width: widget.isTextFieldFocused ? 2.0 : 1.0,
                    ),
                    boxShadow:
                        widget.isTextFieldFocused
                            ? [
                              BoxShadow(
                                color: colorScheme.primary.withValues(
                                  alpha: 0.1,
                                ),
                                blurRadius: 8,
                                spreadRadius: 1,
                              ),
                            ]
                            : null,
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20.0,
                        vertical: 2.0,
                      ),
                      child: KeyboardListener(
                        focusNode: _keyboardFocusNode,
                        onKeyEvent: (KeyEvent event) {
                          if (event is KeyDownEvent &&
                              event.logicalKey == LogicalKeyboardKey.enter &&
                              !HardwareKeyboard.instance.isShiftPressed &&
                              !widget.isSendingMessage &&
                              widget.textController.text.trim().isNotEmpty) {
                            widget.onSendMessage();
                          }
                          // Ctrl+V / Cmd+V: check clipboard for files
                          if (event is KeyDownEvent &&
                              event.logicalKey == LogicalKeyboardKey.keyV &&
                              (HardwareKeyboard.instance.isControlPressed ||
                                  HardwareKeyboard.instance.isMetaPressed)) {
                            _handlePaste();
                          }
                        },
                        child: Scrollbar(
                          controller: _inputScrollController,
                          child: TextField(
                          controller: widget.textController,
                          focusNode: widget.focusNode,
                          scrollController: _inputScrollController,
                          maxLines: null,
                          keyboardType: TextInputType.multiline,
                          textCapitalization: TextCapitalization.sentences,
                          style: TextStyle(
                            color: colorScheme.onSurface,
                            fontSize: 16,
                          ),
                          decoration: InputDecoration(
                            hintText:
                                widget.isSendingMessage
                                    ? '${appTheme.name} is typing...'
                                    : 'Type your message here...',
                            hintStyle: TextStyle(
                              color: colorScheme.onSurfaceVariant,
                              fontSize: 16,
                            ),
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            filled: false,
                            contentPadding: const EdgeInsets.symmetric(
                              vertical: 12.0,
                            ),
                          ),
                            onSubmitted: (value) {
                              if (!widget.isSendingMessage &&
                                  value.trim().isNotEmpty) {
                                widget.onSendMessage();
                              }
                            },
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12.0),
              _buildActionButton(
                icon: Icons.attach_file_rounded,
                onPressed: widget.isSendingMessage ? null : _pickFiles,
                tooltip: 'Attach file',
              ),
              const SizedBox(width: 8.0),
              widget.isSendingMessage
                  ? Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: colorScheme.primary.withValues(alpha: 0.1),
                    ),
                    child: Center(
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: colorScheme.primary,
                        ),
                      ),
                    ),
                  )
                  : _buildActionButton(
                    icon: Icons.send_rounded,
                    onPressed:
                        widget.textController.text.trim().isEmpty
                            ? null
                            : widget.onSendMessage,
                    tooltip: 'Send message',
                    isPrimary: true,
                  ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required VoidCallback? onPressed,
    required String tooltip,
    bool isPrimary = false,
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isEnabled = onPressed != null;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color:
            isPrimary && isEnabled
                ? colorScheme.primary
                : isEnabled
                ? colorScheme.surfaceContainerHighest
                : colorScheme.surfaceContainerHigh,
        boxShadow:
            isPrimary && isEnabled
                ? [
                  BoxShadow(
                    color: colorScheme.primary.withValues(alpha: 0.3),
                    blurRadius: 8,
                    spreadRadius: 0,
                  ),
                ]
                : null,
      ),
      child: IconButton(
        icon: Icon(
          icon,
          color:
              isPrimary && isEnabled
                  ? colorScheme.onPrimary
                  : isEnabled
                  ? colorScheme.onSurface
                  : colorScheme.onSurfaceVariant,
          size: 24,
        ),
        tooltip: tooltip,
        onPressed: onPressed,
        constraints: const BoxConstraints(
          minWidth: 48,
          minHeight: 48,
        ),
      ),
    );
  }
}
