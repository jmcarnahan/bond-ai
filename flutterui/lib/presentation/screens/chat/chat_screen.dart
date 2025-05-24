import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/providers/thread_chat_provider.dart';
import 'package:flutterui/providers/thread_provider.dart'; // Added import for threadsProvider

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

  @override
  void initState() {
    super.initState();
    // Use WidgetsBinding.instance.addPostFrameCallback to ensure providers are ready
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // If an initialThreadId is provided, load its messages.
      // Otherwise, ChatSessionNotifier starts with no currentThreadId.
      // A new thread will be created on the first message send if no thread is active.
      if (widget.initialThreadId != null) {
        print(
          "[ChatScreen] Initializing with threadId: ${widget.initialThreadId}",
        );
        ref
            .read(chatSessionNotifierProvider.notifier)
            .setCurrentThread(widget.initialThreadId!);
      } else {
        // If no initial thread, ensure any previous session for this notifier instance is cleared.
        // This is important if .autoDispose is not used or if navigating back to a chat for a new agent.
        ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
        print(
          "[ChatScreen] Initializing new chat session for agentId: ${widget.agentId}",
        );
      }
    });
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final currentSessionState = ref.read(chatSessionNotifierProvider);

    if (currentSessionState.currentThreadId == null) {
      // If no current thread, create a new one and send the first message.
      print(
        "[ChatScreen] No current thread. Creating new thread for agent ${widget.agentId} and sending message.",
      );
      chatNotifier.createAndSetNewThread(
        // name: "Chat with ${widget.agentName}", // Optional: name for the new thread
        agentIdForFirstMessage: widget.agentId,
        firstMessagePrompt: text,
      );
    } else {
      // If a thread is already active, just send the message.
      print(
        "[ChatScreen] Sending message to existing thread ${currentSessionState.currentThreadId}.",
      );
      chatNotifier.sendMessage(agentId: widget.agentId, prompt: text);
    }
    _textController.clear();
    _scrollToBottom();
  }

  void _scrollToBottom() {
    // Scroll to the bottom after a short delay to allow the UI to update.
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
    // If the agentId changes (e.g., navigating from one agent chat to another directly),
    // reset the chat session.
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

    // Listen for new messages and scroll to bottom
    ref.listen(
      chatSessionNotifierProvider.select((state) => state.messages.length),
      (_, __) {
        _scrollToBottom();
      },
    );

    return Scaffold(
      appBar: AppBar(
        title: Text("Chat with ${widget.agentName}"),
        actions: [
          IconButton(
            icon: const Icon(Icons.forum_outlined),
            tooltip: 'View/Change Threads',
            onPressed: () {
              Navigator.pushNamed(context, '/threads');
            },
          ),
          IconButton(
            icon: const Icon(Icons.add_comment_outlined),
            tooltip: 'Start New Thread',
            onPressed: () async {
              // Optional: Show confirmation dialog
              final confirm = await showDialog<bool>(
                context: context,
                builder:
                    (context) => AlertDialog(
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
                // Create a default name for the new thread, perhaps with a timestamp
                // final newThreadName = "Chat with ${widget.agentName} - ${DateTime.now().toIso8601String()}";
                await ref
                    .read(chatSessionNotifierProvider.notifier)
                    .startNewEmptyThread(
                      name: "New chat with ${widget.agentName}",
                    );
                // Refresh the main threads list so the new thread appears there
                ref.read(threadsProvider.notifier).fetchThreads();
              }
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child:
                chatState.isLoadingMessages && chatState.messages.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.all(8.0),
                      itemCount: chatState.messages.length,
                      itemBuilder: (context, index) {
                        final message = chatState.messages[index];
                        final isUserMessage = message.role == 'user';
                        return Align(
                          alignment:
                              isUserMessage
                                  ? Alignment.centerRight
                                  : Alignment.centerLeft,
                          child: Card(
                            color:
                                message.isError
                                    ? Colors
                                        .red
                                        .shade100 // Error message background
                                    : (isUserMessage
                                        ? Theme.of(
                                          context,
                                        ).colorScheme.primaryContainer
                                        : Theme.of(
                                          context,
                                        ).colorScheme.secondaryContainer),
                            elevation: 1.0,
                            margin: const EdgeInsets.symmetric(
                              vertical: 4.0,
                              horizontal: 8.0,
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(10.0),
                              child: SelectableText(
                                message.content,
                                style: TextStyle(
                                  color:
                                      message.isError
                                          ? Colors.red.shade900
                                          : null,
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
          ),
          if (chatState.errorMessage != null)
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: Text(
                "Error: ${chatState.errorMessage}",
                style: const TextStyle(color: Colors.red),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    decoration: const InputDecoration(
                      hintText: 'Type a message...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8.0),
                chatState.isSendingMessage
                    ? const CircularProgressIndicator()
                    : IconButton(
                      icon: const Icon(Icons.send),
                      onPressed: _sendMessage,
                      tooltip: 'Send message',
                    ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
