import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class MessageInputBar extends ConsumerWidget {
  final TextEditingController textController;
  final FocusNode focusNode;
  final bool isTextFieldFocused;
  final bool isSendingMessage;
  final VoidCallback onSendMessage;

  const MessageInputBar({
    super.key,
    required this.textController,
    required this.focusNode,
    required this.isTextFieldFocused,
    required this.isSendingMessage,
    required this.onSendMessage,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 24.0),
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        boxShadow: [
          BoxShadow(
            offset: const Offset(0, -1),
            blurRadius: 2.0,
            spreadRadius: 0.5,
            color: Colors.black.withValues(alpha: .08),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(25.0),
                border: isTextFieldFocused
                    ? Border.all(color: Colors.red, width: 2.0)
                    : null,
              ),
              child: Material(
                borderRadius: BorderRadius.circular(25.0),
                clipBehavior: Clip.antiAlias,
                color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.6),
                child: Padding( 
                  padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 0),
                  child: KeyboardListener(
                    focusNode: FocusNode(),
                    onKeyEvent: (KeyEvent event) {
                      if (event is KeyDownEvent && 
                          event.logicalKey == LogicalKeyboardKey.enter &&
                          !HardwareKeyboard.instance.isShiftPressed &&
                          !isSendingMessage &&
                          textController.text.trim().isNotEmpty) {
                        onSendMessage();
                      }
                    },
                    child: TextField(
                      controller: textController,
                      focusNode: focusNode,
                      maxLines: null,
                      keyboardType: TextInputType.multiline,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        hintText: isSendingMessage ? 'Waiting for response...' : 'Type a message...',
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        filled: false,
                        contentPadding: const EdgeInsets.symmetric(vertical: 12.0),
                      ),
                      onSubmitted: (value) {
                        if (!isSendingMessage && value.trim().isNotEmpty) {
                          onSendMessage();
                        }
                      },
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8.0),
          isSendingMessage
              ? Padding(
                  padding: const EdgeInsets.only(bottom: 4.0, right: 4.0),
                  child: SizedBox(
                    width: 28,
                    height: 28,
                    child: CircularProgressIndicator(strokeWidth: 2.5, color: colorScheme.primary),
                  ),
                )
              : IconButton(
                  icon: Icon(Icons.send, color: isSendingMessage ? Colors.grey : colorScheme.primary, size: 28), // Grey out icon when disabled
                  tooltip: isSendingMessage ? 'Waiting for response' : 'Send message',
                  padding: const EdgeInsets.only(bottom: 4.0),
                  onPressed: isSendingMessage ? null : onSendMessage,
                ),
        ],
      ),
    );
  }
}
