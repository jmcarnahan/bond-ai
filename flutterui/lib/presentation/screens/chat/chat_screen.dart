import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../../../core/utils/logger.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_app_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_input_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_list_view.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';

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

class _ChatScreenState extends ConsumerState<ChatScreen> with ErrorHandlingMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _textFieldFocusNode = FocusNode();
  bool _isTextFieldFocused = false;
  List<PlatformFile> _fileAttachments = [];

  @override
  void initState() {
    super.initState();
    _textFieldFocusNode.addListener(_onFocusChange);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initializeChatSession();
    });

  }

  void _initializeChatSession() {
    logger.i("[ChatScreen] _initializeChatSession called - agentId: ${widget.agentId}, agentName: ${widget.agentName}");
    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final globalSelectedThreadId = ref.read(selectedThreadIdProvider);

    if (widget.initialThreadId != null) {
      logger.i("[ChatScreen] Initializing with explicit threadId: ${widget.initialThreadId}, agentId: ${widget.agentId}");
      chatNotifier.setCurrentThread(widget.initialThreadId!);
      if (globalSelectedThreadId != widget.initialThreadId) {
        ref.read(threadsProvider.notifier).selectThread(widget.initialThreadId!);
      }
    } else if (globalSelectedThreadId != null) {
      logger.i("[ChatScreen] Initializing with global selectedThreadId: $globalSelectedThreadId, agentId: ${widget.agentId}");
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != globalSelectedThreadId) {
        chatNotifier.setCurrentThread(globalSelectedThreadId);
      }
    } else {
      logger.i("[ChatScreen] No initial or global thread, checking if should auto-send introduction.");
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != null) {
        chatNotifier.clearChatSession();
      }
      
      // Check if agent has introduction and auto-send it
      _checkAndSendIntroductionIfNeeded();
    }
  }

  void _checkAndSendIntroductionIfNeeded() async {
    logger.i("[ChatScreen] Checking if agent has introduction for auto-send");
    
    await withErrorHandling(
      operation: () async {
        // Get agent service from providers  
        final agentService = ref.read(agentServiceProvider);
        final agentDetails = await agentService.getAgentDetails(widget.agentId);
        
        if (agentDetails.introduction != null && agentDetails.introduction!.trim().isNotEmpty) {
          logger.i("[ChatScreen] Agent has introduction, auto-sending it");
          final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
          
          // Send introduction with null thread_id (backend will create thread)
          await chatNotifier.sendIntroduction(
            agentId: widget.agentId,
            introduction: agentDetails.introduction!.trim(),
          );
        } else {
          logger.i("[ChatScreen] Agent has no introduction, waiting for user to start conversation");
        }
      },
      ref: ref,
      errorMessage: 'Failed to load agent information.',
      isCritical: false,  // This is a service error, not critical
    );
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


  void _onAttachmentsChanged(List<PlatformFile> attachments) {
    setState(() {
      _fileAttachments = attachments; // PlatformFiles are passed by reference FYI
    });
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    final chatState = ref.read(chatSessionNotifierProvider);
    if (chatState.isSendingMessage) return;

    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final hasAttachement = _fileAttachments.isNotEmpty;

    // Just send the message - backend will create thread if needed
    chatNotifier.sendMessage(
      agentId: widget.agentId, 
      prompt: text, 
      attachedFiles: hasAttachement ? _fileAttachments : null,
    );
    
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _textController.clear();
      _onAttachmentsChanged([]);
    });
    
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

    ref.listen(
      chatSessionNotifierProvider.select((state) => state.messages.length),
      (_, __) {
        _scrollToBottom();
      },
    );

    // Also scroll when streaming message content changes
    ref.listen(
      chatSessionNotifierProvider.select((state) => 
        state.messages.isNotEmpty && state.isSendingMessage 
          ? state.messages.last.content 
          : null
      ),
      (_, __) {
        if (chatState.isSendingMessage) {
          _scrollToBottom();
        }
      },
    );

    ref.listen<String?>(selectedThreadIdProvider, (previousId, newId) {
      if (widget.initialThreadId == null && previousId != newId) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            logger.i(
                "[ChatScreen] Global selected thread changed from $previousId to $newId. Re-initializing session (post-frame).");
            _initializeChatSession();
          }
        });
      }
    });

    return Scaffold(
      backgroundColor: colorScheme.surface,
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
                'This will clear the current conversation from view, allowing you to start fresh with ${widget.agentName}.',
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
            ref.read(threadsProvider.notifier).deselectThread();
            ref.read(chatSessionNotifierProvider.notifier).clearChatSession();
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
            onFileAttachmentsChanged: _onAttachmentsChanged,
            attachments: _fileAttachments,
          ),
        ],
      ),
    );
  }
}
