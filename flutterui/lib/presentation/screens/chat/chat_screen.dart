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
import 'package:flutterui/presentation/widgets/app_drawer.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import 'package:flutterui/providers/notification_provider.dart';

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
    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    final globalSelectedThreadId = ref.read(selectedThreadIdProvider);

    // Check for pending system message from notification
    final pendingSystemMessage = ref.read(pendingSystemMessageProvider);
    
    if (pendingSystemMessage != null) {
      // Clear the chat session to start fresh
      chatNotifier.clearChatSession();
      
      // Clear the pending message provider
      ref.read(pendingSystemMessageProvider.notifier).state = null;
      
      // Send the system message (this will create a new thread)
      _sendPendingSystemMessage(
        pendingSystemMessage.message, 
        pendingSystemMessage.agentId,
        threadName: pendingSystemMessage.threadName,
      );
      return;
    }

    if (widget.initialThreadId != null) {
      chatNotifier.setCurrentThread(widget.initialThreadId!);
      if (globalSelectedThreadId != widget.initialThreadId) {
        ref.read(threadsProvider.notifier).selectThread(widget.initialThreadId!);
      }
    } else if (globalSelectedThreadId != null) {
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != globalSelectedThreadId) {
        chatNotifier.setCurrentThread(globalSelectedThreadId);
      }
    } else {
      final chatSessionCurrentThread = ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != null) {
        chatNotifier.clearChatSession();
      }
      _checkAndSendIntroductionIfNeeded();
    }
  }

  void _checkAndSendIntroductionIfNeeded() async {
    // logger.d("[ChatScreen] Checking if agent has introduction for auto-send");
    
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
          // logger.d("[ChatScreen] Agent has no introduction, waiting for user to start conversation");
        }
      },
      ref: ref,
      errorMessage: 'Failed to load agent information.',
      isCritical: false,  // This is a service error, not critical
    );
  }

  void _sendPendingSystemMessage(String message, String agentId, {String? threadName}) async {
    logger.i("[ChatScreen] Starting _sendPendingSystemMessage");
    
    // Check if widget is still mounted before using ref
    if (!mounted) {
      logger.w("[ChatScreen] Widget disposed, skipping _sendPendingSystemMessage");
      return;
    }
    
    // Set sending state immediately to show loading
    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    chatNotifier.state = chatNotifier.state.copyWith(isSendingMessage: true);
    
    // Only proceed with error handling if still mounted
    if (!mounted) {
      logger.w("[ChatScreen] Widget disposed, cannot proceed with error handling");
      return;
    }
    
    await withErrorHandling(
      operation: () async {
        logger.i("[ChatScreen] Creating thread with name: $threadName");
        
        // Check mounted before using ref
        if (!mounted) {
          logger.w("[ChatScreen] Widget disposed during operation");
          return;
        }
        
        // First, create a thread with the proper name from the notification
        final newThread = await ref.read(threadsProvider.notifier).addThread(
          name: threadName ?? 'New Conversation',
        );
        
        if (newThread == null) {
          throw Exception('Failed to create thread');
        }
        logger.i("[ChatScreen] Thread created: ${newThread.id}");
        
        // Check mounted again after async operation
        if (!mounted) {
          logger.w("[ChatScreen] Widget disposed after thread creation");
          return;
        }
        
        // Set the current thread ID in the chat session (without loading messages)
        chatNotifier.setThreadIdOnly(newThread.id);
        
        logger.i("[ChatScreen] Sending system message");
        // Now send the system message to the created thread
        await chatNotifier.sendMessage(
          agentId: agentId,
          prompt: message,
          overrideRole: "system",
        );
        logger.i("[ChatScreen] System message sent");
      },
      ref: ref,
      errorMessage: 'Failed to send system message.',
      isCritical: false,
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
    
    // Only re-initialize if we're actually changing to a different thread
    if (widget.agentId != oldWidget.agentId ||
        (widget.initialThreadId != oldWidget.initialThreadId && 
         widget.initialThreadId != ref.read(chatSessionNotifierProvider).currentThreadId)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _initializeChatSession();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatSessionNotifierProvider);

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

    // Listen for pending system message changes
    ref.listen<PendingSystemMessage?>(pendingSystemMessageProvider, (previous, next) {
      if (next != null) {
        // Clear current chat session
        final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
        chatNotifier.clearChatSession();
        
        // Clear the pending message provider
        ref.read(pendingSystemMessageProvider.notifier).state = null;
        
        // Send the system message
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _sendPendingSystemMessage(next.message, next.agentId, threadName: next.threadName);
          }
        });
      }
    });

    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      drawer: const AppDrawer(),
      appBar: ChatAppBar(
        agentName: widget.agentName,
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
