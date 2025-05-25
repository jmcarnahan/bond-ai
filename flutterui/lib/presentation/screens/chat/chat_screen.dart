import 'package:flutter/material.dart';
import 'package:flutter/services.dart'; // Added for keyboard event handling
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/providers/thread_chat_provider.dart';
import 'package:flutterui/providers/thread_provider.dart'; // Added import for threadsProvider
import 'package:flutterui/core/theme/mcafee_theme.dart'; // Import McAfeeTheme for CustomColors
import 'package:flutterui/main.dart'; // Import for appThemeProvider
import 'package:flutterui/presentation/widgets/typing_indicator.dart'; // Import TypingIndicator

class ChatScreen extends ConsumerStatefulWidget {
  final String agentId;
  final String agentName; // To display in AppBar
  final String?
  initialThreadId; // Optional, if navigating to an existing thread

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
        print(
          "[ChatScreen] Initializing with threadId: ${widget.initialThreadId}",
        );
        ref
            .read(chatSessionNotifierProvider.notifier)
            .setCurrentThread(widget.initialThreadId!);
      } else {
        ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
        print(
          "[ChatScreen] Initializing new chat session for agentId: ${widget.agentId}",
        );
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

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    // Prevent sending if already sending
    final chatState = ref.read(chatSessionNotifierProvider);
    if (chatState.isSendingMessage) return;

    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final currentSessionState = ref.read(chatSessionNotifierProvider);

    if (currentSessionState.currentThreadId == null) {
      print(
        "[ChatScreen] No current thread. Creating new thread for agent ${widget.agentId} and sending message.",
      );
      chatNotifier.createAndSetNewThread(
        agentIdForFirstMessage: widget.agentId,
        firstMessagePrompt: text,
      );
    } else {
      print(
        "[ChatScreen] Sending message to existing thread ${currentSessionState.currentThreadId}.",
      );
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
          print(
            "[ChatScreen] Updating with new threadId: ${widget.initialThreadId}",
          );
          ref
              .read(chatSessionNotifierProvider.notifier)
              .setCurrentThread(widget.initialThreadId!);
        } else {
          ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
          print(
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
    final customColors = theme.extension<CustomColors>();
    final appBarBackgroundColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface;
    final appTheme = ref.watch(appThemeProvider);

    ref.listen(
      chatSessionNotifierProvider.select((state) => state.messages.length),
      (_, __) {
        _scrollToBottom();
      },
    );

    return Scaffold(
      backgroundColor: colorScheme.background,
      appBar: AppBar(
        backgroundColor: appBarBackgroundColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              appTheme.logoIcon,
              height: 24,
              width: 24,
            ),
            const SizedBox(width: 8),
            Text(
              "Chat with ${widget.agentName}",
              style: textTheme.titleLarge?.copyWith(color: Colors.white),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.forum_outlined, color: Colors.white),
            tooltip: 'View/Change Threads',
            onPressed: () {
              Navigator.pushNamed(context, '/threads');
            },
          ),
          IconButton(
            icon: const Icon(Icons.add_comment_outlined, color: Colors.white),
            tooltip: 'Start New Thread',
            onPressed: () async {
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
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: chatState.isLoadingMessages && chatState.messages.isEmpty
                ? const Center(child: TypingIndicator())
                : chatState.messages.isEmpty
                    ? _buildEmptyChatPlaceholder(context)
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 12.0),
                        itemCount: chatState.messages.length,
                    itemBuilder: (context, index) {
                      final message = chatState.messages[index];
                      final isUserMessage = message.role == 'user';
                      final isError = message.isError;

                      Color bubbleColor;
                      Color textColor;
                      BorderRadius borderRadius;

                      if (isError) {
                        bubbleColor = colorScheme.errorContainer;
                        textColor = colorScheme.onErrorContainer;
                        borderRadius = BorderRadius.circular(16.0);
                      } else if (isUserMessage) {
                        bubbleColor = colorScheme.primary; // McAfee Red
                        textColor = colorScheme.onPrimary; // White
                        borderRadius = BorderRadius.circular(16.0);
                      } else { // Agent message
                        bubbleColor = colorScheme.surfaceVariant; // Light grey
                        textColor = colorScheme.onSurfaceVariant;
                        borderRadius = BorderRadius.circular(16.0);
                      }

                      Widget messageContent = Card(
                        color: bubbleColor,
                        elevation: 0.5,
                        shape: RoundedRectangleBorder(borderRadius: borderRadius),
                        margin: EdgeInsets.zero,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 10.0, horizontal: 14.0),
                          child: (message.role == 'assistant' &&
                                  chatState.isSendingMessage && // Agent is "typing"
                                  index == chatState.messages.length - 1 && // It's the last message
                                  message.content.isEmpty) // And content hasn't arrived yet
                              ? TypingIndicator(
                                  dotColor: textColor.withOpacity(0.7), // Use themed color for dots
                                )
                              : SelectableText(
                                  message.content,
                                  style: textTheme.bodyMedium?.copyWith(color: textColor),
                                ),
                        ),
                      );

                      if (isUserMessage) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6.0),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Flexible(
                                child: ConstrainedBox( // Ensure user bubble doesn't take full width if short
                                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                                  child: messageContent,
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
                      } else { // Agent or Error message
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6.0),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.start,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              CircleAvatar(
                                backgroundColor: isError 
                                    ? colorScheme.errorContainer 
                                    : (customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface),
                                radius: 16,
                                child: Icon(
                                  isError ? Icons.error_outline : Icons.smart_toy_outlined,
                                  color: isError ? colorScheme.onErrorContainer : Colors.white, // White icon on dark grey
                                  size: 20,
                                ),
                              ),
                              const SizedBox(width: 8),
                              // If it's the typing indicator, let the Card determine its own width.
                              // Otherwise, constrain the width for actual messages.
                              (message.role == 'assistant' &&
                                      chatState.isSendingMessage &&
                                      index == chatState.messages.length - 1 &&
                                      message.content.isEmpty)
                                  ? messageContent // This is the Card containing TypingIndicator
                                  : Flexible(
                                      child: ConstrainedBox(
                                        constraints: BoxConstraints(
                                            maxWidth: MediaQuery.of(context)
                                                    .size
                                                    .width *
                                                0.75),
                                        child: messageContent,
                                      ),
                                    ),
                            ],
                          ),
                        );
                      }
                    },
                  ),
          ),
          // Removed standalone error message text as errors are now in bubbles
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12.0, vertical: 8.0),
            decoration: BoxDecoration(
              color: theme.scaffoldBackgroundColor, // Use scaffold background for consistency
              boxShadow: [
                BoxShadow(
                  offset: const Offset(0, -1),
                  blurRadius: 2.0,
                  spreadRadius: 0.5,
                  color: Colors.black.withOpacity(0.08),
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
                        border: _isTextFieldFocused
                            ? Border.all(color: Colors.red, width: 2.0)
                            : null, // No border when not focused
                      ),
                      child: Material(
                        borderRadius: BorderRadius.circular(25.0),
                        clipBehavior: Clip.antiAlias,
                        color: colorScheme.surfaceVariant.withOpacity(0.6), // Moved fill color here
                        child: Padding( // Added padding here for TextField
                          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 0), // Adjusted vertical padding
                          child: TextField(
                            controller: _textController,
                            focusNode: _textFieldFocusNode, // Assign the FocusNode
                            maxLines: null, // Allows for multiline input with Shift+Enter
                            keyboardType: TextInputType.multiline,
                            textCapitalization: TextCapitalization.sentences,
                            decoration: InputDecoration(
                              hintText: chatState.isSendingMessage ? 'Waiting for response...' : 'Type a message...',
                              border: InputBorder.none,
                              enabledBorder: InputBorder.none,
                              focusedBorder: InputBorder.none, // Border is now handled by DecoratedBox
                              filled: false,
                              contentPadding: const EdgeInsets.symmetric(vertical: 12.0),
                            ),
                            // onSubmitted is still useful for specific actions like 'done' on mobile keyboards
                          // but our RawKeyboardListener handles desktop Enter.
                          onSubmitted: (_) { // Removed extra comma here
                            if (!chatState.isSendingMessage) {
                              _sendMessage();
                            }
                          },
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8.0),
                chatState.isSendingMessage
                    ? Padding(
                        padding: const EdgeInsets.only(bottom: 4.0, right: 4.0), // Align with IconButton
                        child: SizedBox(
                          width: 28,
                          height: 28,
                          child: CircularProgressIndicator(strokeWidth: 2.5, color: colorScheme.primary),
                        ),
                      )
                    : IconButton(
                        icon: Icon(Icons.send, color: chatState.isSendingMessage ? Colors.grey : colorScheme.primary, size: 28), // Grey out icon when disabled
                        tooltip: chatState.isSendingMessage ? 'Waiting for response' : 'Send message',
                        padding: const EdgeInsets.only(bottom: 4.0), // Align with TextField baseline
                        onPressed: chatState.isSendingMessage ? null : _sendMessage, // Disable button when sending
                      ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyChatPlaceholder(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircleAvatar(
            radius: 40,
            backgroundColor: Colors.grey.shade200, // Light grey circle
            child: Icon(
              Icons.smart_toy_outlined,
              size: 48,
              color: Colors.grey.shade600, // Slightly darker grey icon
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Start a conversation',
            style: textTheme.headlineSmall?.copyWith(
              color: Colors.grey.shade700, // Lighter grey text
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40.0),
            child: Text(
              'Send a message to begin your chat with ${widget.agentName}.',
              textAlign: TextAlign.center,
              style: textTheme.bodyLarge?.copyWith(
                color: Colors.grey.shade500, // Even lighter grey text
              ),
            ),
          ),
        ],
      ),
    );
  }
}
