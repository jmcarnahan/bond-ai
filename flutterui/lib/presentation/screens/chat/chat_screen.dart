import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';
import '../../../core/utils/logger.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_app_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_input_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_list_view.dart';

class ChatScreen extends ConsumerStatefulWidget {
  final String agentId;
  final String agentName;
  final String? initialThreadId;

  const ChatScreen({
    super.key,
    required this.agentId,
    required this.agentName,
    this.initialThreadId,
  });

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _textFieldFocusNode = FocusNode();
  bool _isTextFieldFocused = false;

  @override
  void initState() {
    super.initState();
    _textFieldFocusNode.addListener(_onFocusChange);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.initialThreadId != null) {
        ref
          .read(chatSessionNotifierProvider.notifier)
          .setCurrentThread(widget.initialThreadId!);
      } else {
        ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
      }
    });
  }

  @override
  void dispose() {
    _textFieldFocusNode.removeListener(_onFocusChange);
    _textFieldFocusNode.dispose();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onFocusChange() {
    setState(() {
      _isTextFieldFocused = _textFieldFocusNode.hasFocus;
    });
  }

  String _generateThreadNameFromPrompt(String prompt) {
    const maxLength = 30;
    if (prompt.length <= maxLength) {
      return prompt;
    }
    return '${prompt.substring(0, maxLength - 3)}...';
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    final chatState = ref.read(chatSessionNotifierProvider);
    if (chatState.isSendingMessage) return;

    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final currentSessionState = ref.read(chatSessionNotifierProvider);

    if (currentSessionState.currentThreadId == null) {
      chatNotifier.createAndSetNewThread(
        name: _generateThreadNameFromPrompt(text), // Pass generated name
        agentIdForFirstMessage: widget.agentId,
        firstMessagePrompt: text,
      );
    } else {
      chatNotifier.sendMessage(agentId: widget.agentId, prompt: text);
    }
    _textController.clear();
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void didUpdateWidget(covariant ChatScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.agentId != oldWidget.agentId ||
        widget.initialThreadId != oldWidget.initialThreadId) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (widget.initialThreadId != null) {
          logger.i(
            "[ChatScreen] Updating with new threadId: ${widget.initialThreadId}",
          );
          ref
              .read(chatSessionNotifierProvider.notifier)
              .setCurrentThread(widget.initialThreadId!);
        } else {
          ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
          logger.i(
            "[ChatScreen] Agent/Thread changed, cleared chat session for agentId: ${widget.agentId}",
          );
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatSessionNotifierProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;
    // final customColors = theme.extension<CustomColors>(); // Moved to ChatAppBar
    // final appBarBackgroundColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface; // Moved to ChatAppBar
    // final appTheme = ref.watch(appThemeProvider); // Moved to ChatAppBar

    ref.listen(
      chatSessionNotifierProvider.select((state) => state.messages.length),
      (_, __) {
        _scrollToBottom();
      },
    );

    return Scaffold(
      backgroundColor: colorScheme.background,
      appBar: ChatAppBar(
        agentName: widget.agentName,
        onViewThreads: () {
          Navigator.pushNamed(context, '/threads');
        },
        onStartNewThread: () async {
          final confirm = await showDialog<bool>(
            context: context,
            builder: (context) => AlertDialog(
              title: const Text('Start New Conversation?'),
              content: Text(
                'This will start a new, empty conversation with ${widget.agentName}. The current chat view will be cleared.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Cancel'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Start New'),
                ),
              ],
            ),
          );

          if (confirm == true) {
            await ref
                .read(chatSessionNotifierProvider.notifier)
                .startNewEmptyThread(
                  name: "New chat with ${widget.agentName}",
                );
            ref.read(threadsProvider.notifier).fetchThreads();
          }
        },
      ),
      body: Column(
        children: [
          Expanded(
            child: MessageListView(
              chatState: chatState,
              scrollController: _scrollController,
              agentName: widget.agentName,
            ),
          ),
          MessageInputBar(
            textController: _textController,
            focusNode: _textFieldFocusNode,
            isTextFieldFocused: _isTextFieldFocused,
            isSendingMessage: chatState.isSendingMessage,
            onSendMessage: _sendMessage,
          ),
        ],
      ),
    );
  }
}
