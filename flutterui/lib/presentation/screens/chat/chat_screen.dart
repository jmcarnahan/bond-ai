import 'dart:typed_data';
import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_picker/file_picker.dart' show PlatformFile;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/agent_model.dart';
import '../../../core/utils/logger.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_app_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/message_input_bar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/agent_sidebar.dart';
import 'package:flutterui/presentation/screens/chat/widgets/chat_messages_list.dart';
import 'package:flutterui/presentation/screens/chat/widgets/web_drop_helper.dart';
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

class _ChatScreenState extends ConsumerState<ChatScreen>
    with ErrorHandlingMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _textFieldFocusNode = FocusNode();
  bool _isTextFieldFocused = false;
  bool _isDragging = false;
  List<PlatformFile> _fileAttachments = [];
  // Cache for decoded images to prevent repeated base64 decoding
  final Map<String, Uint8List> _imageCache = {};

  // Track current agent locally to allow switching without navigation
  late String _currentAgentId;
  late String _currentAgentName;

  @override
  void initState() {
    super.initState();
    _currentAgentId = widget.agentId;
    _currentAgentName = widget.agentName;
    _textFieldFocusNode.addListener(_onFocusChange);
    if (kIsWeb && WebDropHelper.isSupported) {
      WebDropHelper.init(
        onFileDrop: _handleWebFileDrop,
        onDragEnter: () { if (mounted) setState(() => _isDragging = true); },
        onDragLeave: () { if (mounted) setState(() => _isDragging = false); },
      );
    }
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
        ref
            .read(threadsProvider.notifier)
            .selectThread(widget.initialThreadId!);
      }
    } else if (globalSelectedThreadId != null) {
      final chatSessionCurrentThread =
          ref.read(chatSessionNotifierProvider).currentThreadId;
      if (chatSessionCurrentThread != globalSelectedThreadId) {
        chatNotifier.setCurrentThread(globalSelectedThreadId);
      }
    } else {
      final chatSessionCurrentThread =
          ref.read(chatSessionNotifierProvider).currentThreadId;
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
        final agentDetails = await agentService.getAgentDetails(
          _currentAgentId,
        );

        if (agentDetails.introduction != null &&
            agentDetails.introduction!.trim().isNotEmpty) {
          logger.i("[ChatScreen] Agent has introduction, auto-sending it");
          final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);

          // Send introduction with null thread_id (backend will create thread)
          await chatNotifier.sendIntroduction(
            agentId: _currentAgentId,
            introduction: agentDetails.introduction!.trim(),
          );
        } else {
          // logger.d("[ChatScreen] Agent has no introduction, waiting for user to start conversation");
        }
      },
      ref: ref,
      errorMessage: 'Failed to load agent information.',
      isCritical: false, // This is a service error, not critical
    );
  }

  void _sendPendingSystemMessage(
    String message,
    String agentId, {
    String? threadName,
  }) async {
    logger.i("[ChatScreen] Starting _sendPendingSystemMessage");

    // Check if widget is still mounted before using ref
    if (!mounted) {
      logger.w(
        "[ChatScreen] Widget disposed, skipping _sendPendingSystemMessage",
      );
      return;
    }

    // Set sending state immediately to show loading
    final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
    chatNotifier.setSendingState(true);

    // Only proceed with error handling if still mounted
    if (!mounted) {
      logger.w(
        "[ChatScreen] Widget disposed, cannot proceed with error handling",
      );
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
        final newThread = await ref
            .read(threadsProvider.notifier)
            .addThread(name: threadName ?? 'New Conversation');

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
    if (kIsWeb && WebDropHelper.isSupported) {
      WebDropHelper.dispose();
    }
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
      _fileAttachments =
          attachments; // PlatformFiles are passed by reference FYI
    });
  }

  void _handleAgentSwitch(AgentListItemModel agent) {
    // Only update local state when switching from sidebar
    // This prevents screen reconstruction and thread changes
    setState(() {
      _currentAgentId = agent.id;
      _currentAgentName = agent.name;
    });
  }

  /// Replace non-ASCII characters in filenames with spaces.
  /// macOS uses \u202f (narrow no-break space) in screenshot names which
  /// breaks S3 metadata uploads.
  String _sanitizeFilename(String name) {
    return name.replaceAll(RegExp(r'[^\x20-\x7E]'), ' ').replaceAll(RegExp(r' {2,}'), ' ').trim();
  }

  void _handleFileDrop(DropDoneDetails details) async {
    setState(() => _isDragging = false);

    final droppedFiles = <PlatformFile>[];
    for (final xfile in details.files) {
      final bytes = await xfile.readAsBytes();
      droppedFiles.add(PlatformFile(
        name: _sanitizeFilename(xfile.name),
        size: bytes.length,
        bytes: Uint8List.fromList(bytes),
      ));
    }

    final updated = List<PlatformFile>.from(_fileAttachments)
      ..addAll(droppedFiles);
    _onAttachmentsChanged(updated);
  }

  /// Handle files dropped via our custom JavaScript bridge (web only).
  /// This bypasses desktop_drop which gets tree-shaken in release builds.
  void _handleWebFileDrop(List<({String name, Uint8List bytes})> files) {
    if (!mounted) return;
    setState(() => _isDragging = false);

    final droppedFiles = files.map((f) => PlatformFile(
      name: _sanitizeFilename(f.name),
      size: f.bytes.length,
      bytes: f.bytes,
    )).toList();

    final updated = List<PlatformFile>.from(_fileAttachments)
      ..addAll(droppedFiles);
    _onAttachmentsChanged(updated);
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
      agentId: _currentAgentId,
      prompt: text,
      attachedFiles: hasAttachement ? _fileAttachments : null,
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _textController.clear();
      _onAttachmentsChanged([]);

      // Scroll to bottom after sending
      if (_scrollController.hasClients && mounted) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
  }

  void _createNewThread() async {
    logger.i("[ChatScreen] Creating new thread");

    await withErrorHandling(
      operation: () async {
        // Create a new thread
        final newThread = await ref
            .read(threadsProvider.notifier)
            .addThread(name: 'New Conversation');

        if (newThread != null) {
          logger.i("[ChatScreen] Thread created: ${newThread.id}");

          // Clear current chat session
          final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
          chatNotifier.clearChatSession();

          // Set the new thread as current
          chatNotifier.setCurrentThread(newThread.id);

          // Check if the agent has an introduction to send
          _checkAndSendIntroductionIfNeeded();
        }
      },
      ref: ref,
      errorMessage: 'Failed to create new thread.',
      isCritical: false,
    );
  }

  @override
  void didUpdateWidget(covariant ChatScreen oldWidget) {
    super.didUpdateWidget(oldWidget);

    // Only re-initialize if we're actually changing to a different thread
    if (widget.agentId != oldWidget.agentId ||
        (widget.initialThreadId != oldWidget.initialThreadId &&
            widget.initialThreadId !=
                ref.read(chatSessionNotifierProvider).currentThreadId)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _initializeChatSession();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatSessionNotifierProvider);

    ref.listen<String?>(selectedThreadIdProvider, (previousId, newId) {
      if (widget.initialThreadId == null && previousId != newId) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            logger.i(
              "[ChatScreen] Global selected thread changed from $previousId to $newId. Re-initializing session (post-frame).",
            );
            _initializeChatSession();
          }
        });
      }
    });

    // Listen for pending system message changes
    ref.listen<PendingSystemMessage?>(pendingSystemMessageProvider, (
      previous,
      next,
    ) {
      if (next != null) {
        // Clear current chat session
        final chatNotifier = ref.read(chatSessionNotifierProvider.notifier);
        chatNotifier.clearChatSession();

        // Clear the pending message provider
        ref.read(pendingSystemMessageProvider.notifier).state = null;

        // Send the system message
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _sendPendingSystemMessage(
              next.message,
              next.agentId,
              threadName: next.threadName,
            );
          }
        });
      }
    });

    final colorScheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      drawer: const AppDrawer(),
      appBar: ChatAppBar(agentName: _currentAgentName),
      body: DropTarget(
        enable: !kIsWeb,
        onDragDone: _handleFileDrop,
        onDragEntered: (_) => setState(() => _isDragging = true),
        onDragExited: (_) => setState(() => _isDragging = false),
        child: Stack(
          children: [
            Row(
              children: [
                AgentSidebar(
                  currentAgentId: _currentAgentId,
                  onAgentSelected: _handleAgentSwitch,
                ),
                Expanded(
                  child: Column(
                    children: [
                      Expanded(
                        child: ChatMessagesList(
                          scrollController: _scrollController,
                          imageCache: _imageCache,
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
                        onCreateNewThread: _createNewThread,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (_isDragging)
              Positioned.fill(
                child: IgnorePointer(
                  child: Container(
                    decoration: BoxDecoration(
                      color: colorScheme.primary.withValues(alpha: 0.08),
                      border: Border.all(
                        color: colorScheme.primary,
                        width: 3,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.cloud_upload_outlined,
                            size: 64,
                            color: colorScheme.primary,
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Drop files here to attach',
                            style: TextStyle(
                              fontSize: 20,
                              color: colorScheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
