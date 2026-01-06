import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_message_item.dart';

class ChatMessagesList extends ConsumerStatefulWidget {
  final ScrollController scrollController;
  final Map<String, Uint8List> imageCache;

  const ChatMessagesList({
    super.key,
    required this.scrollController,
    required this.imageCache,
  });

  @override
  ConsumerState<ChatMessagesList> createState() => _ChatMessagesListState();
}

class _ChatMessagesListState extends ConsumerState<ChatMessagesList> {
  @override
  void initState() {
    super.initState();
    _setupListeners();
  }

  void _setupListeners() {
    // Listen for new messages
    ref.listenManual(
      chatSessionNotifierProvider.select((state) => state.messages.length),
      (previous, current) {
        if (current > (previous ?? 0)) {
          _scrollToBottom();
        }
      },
    );

    // Listen for content changes during streaming
    ref.listenManual(
      chatSessionNotifierProvider.select(
        (state) => state.messages.isNotEmpty && state.isSendingMessage
            ? state.messages.last.content
            : null,
      ),
      (_, current) {
        if (current != null) {
          _scrollToBottom();
        }
      },
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.scrollController.hasClients && mounted) {
        widget.scrollController.jumpTo(
          widget.scrollController.position.maxScrollExtent,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatSessionNotifierProvider);

    return ListView.builder(
      controller: widget.scrollController,
      padding: const EdgeInsets.symmetric(
        vertical: 8.0,
        horizontal: 72.0,
      ),
      itemCount: chatState.messages.length,
      itemBuilder: (context, index) {
        final message = chatState.messages[index];
        final isLastMessage = index == chatState.messages.length - 1;

        return ChatMessageItem(
          message: message,
          isSendingMessage: chatState.isSendingMessage,
          isLastMessage: isLastMessage,
          imageCache: widget.imageCache,
        );
      },
    );
  }
}
