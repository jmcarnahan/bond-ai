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
      _initializeChatSession();
    });

  }

  void _initializeChatSession() {
    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final globalSelectedThreadId = ref.read(selectedThreadIdProvider); // Read it once for this initialization

    if (widget.initialThreadId != null) {
      logger.i("[ChatScreen] Initializing with explicit threadId: ${widget.initialThreadId}");
      chatNotifier.setCurrentThread(widget.initialThreadId!);
      // If an explicit threadId is given, it should become the global one.
      if (globalSelectedThreadId != widget.initialThreadId) {
        ref.read(threadsProvider.notifier).selectThread(widget.initialThreadId!);
      }
    } else if (globalSelectedThreadId != null) {
      logger.i("[ChatScreen] Initializing with global selectedThreadId: $globalSelectedThreadId");
      // We need to check if this global thread is associated with the current agent.
      // For now, we'll assume it is, or that setCurrentThread can handle it.
      // This might need more sophisticated logic if threads are strictly agent-bound
      // and the global thread might not be for widget.agentId.
      // Also, ensure the chat session's current thread matches the global one.
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != globalSelectedThreadId) {
        chatNotifier.setCurrentThread(globalSelectedThreadId);
      }
    } else {
      logger.i("[ChatScreen] No initial or global thread, clearing session.");
      // Only clear if the session isn't already cleared or for a different (now null) thread
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != null) {
        chatNotifier.clearChatSession();
      }
    }
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
      // If agentId changes, or if initialThreadId changes, re-initialize.
      // The selectedThreadProvider might also change, but this screen primarily reacts to explicit props.
      // If global selection changes *while on this screen*, the banner handles deselection.
      // If we want this screen to *react* to global changes without prop changes, we'd need to watch selectedThreadProvider.
      // For now, this covers explicit navigation changes.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        logger.i("[ChatScreen] didUpdateWidget: agentId or initialThreadId changed. Re-initializing.");
        _initializeChatSession();
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

    // Listen to changes in the global selected thread ID
    // If this chat screen was NOT launched for a specific initialThreadId,
    // then it should react to global changes.
    ref.listen<String?>(selectedThreadIdProvider, (previousId, newId) {
      if (widget.initialThreadId == null && previousId != newId) {
        // Schedule _initializeChatSession to run after the current build cycle
        WidgetsBinding.instance.addPostFrameCallback((_) {
          // Check if the widget is still mounted before calling
          if (mounted) {
            logger.i(
                "[ChatScreen] Global selected thread changed from $previousId to $newId. Re-initializing session (post-frame).");
            _initializeChatSession();
          }
        });
      }
    });

    return Scaffold(
      backgroundColor: colorScheme.background,
      appBar: ChatAppBar(
        agentName: widget.agentName,
        onViewThreads: () {
          Navigator.pushNamed(context, '/threads', arguments: {'isFromAgentChat': true});
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
