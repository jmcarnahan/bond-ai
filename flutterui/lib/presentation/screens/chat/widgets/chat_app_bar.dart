import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/presentation/widgets/connection_status_indicator.dart';
import 'package:flutterui/core/utils/logger.dart';

class ChatAppBar extends ConsumerStatefulWidget implements PreferredSizeWidget {
  final String agentName;
  final String? threadName;
  final String? threadId;
  final VoidCallback? onCreateNewThread;
  final VoidCallback? onAttachFile;
  final bool isSendingMessage;

  const ChatAppBar({
    super.key,
    required this.agentName,
    this.threadName,
    this.threadId,
    this.onCreateNewThread,
    this.onAttachFile,
    this.isSendingMessage = false,
  });

  @override
  ConsumerState<ChatAppBar> createState() => _ChatAppBarState();

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight + 8);
}

class _ChatAppBarState extends ConsumerState<ChatAppBar> {
  bool _isEditing = false;
  late TextEditingController _editController;
  late FocusNode _editFocusNode;

  @override
  void initState() {
    super.initState();
    _editController = TextEditingController();
    _editFocusNode = FocusNode();
    _editFocusNode.addListener(_onFocusLost);
  }

  @override
  void dispose() {
    _editFocusNode.removeListener(_onFocusLost);
    _editFocusNode.dispose();
    _editController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant ChatAppBar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.threadId != widget.threadId && _isEditing) {
      setState(() => _isEditing = false);
    }
  }

  void _onFocusLost() {
    if (!_editFocusNode.hasFocus && _isEditing) {
      _submitRename();
    }
  }

  void _startEditing() {
    if (widget.threadId == null) return;
    setState(() {
      _isEditing = true;
      _editController.text = widget.threadName ?? 'New Conversation';
      _editController.selection = TextSelection(
        baseOffset: 0,
        extentOffset: _editController.text.length,
      );
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _editFocusNode.requestFocus();
    });
  }

  void _submitRename() async {
    if (!_isEditing || !mounted) return;
    final newName = _editController.text.trim();
    setState(() => _isEditing = false);
    if (newName.isNotEmpty && newName != widget.threadName && widget.threadId != null) {
      try {
        await ref.read(threadsProvider.notifier).renameThread(widget.threadId!, newName);
      } catch (e) {
        logger.w('[ChatAppBar] Failed to rename thread: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final appTheme = ref.watch(appThemeProvider);
    final theme = Theme.of(context);
    final displayName = widget.threadName ?? 'New Conversation';
    final canEdit = widget.threadId != null;

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        automaticallyImplyLeading: false,
        leading: Builder(
          builder: (context) => IconButton(
            icon: Icon(Icons.menu, color: theme.colorScheme.onSurface),
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.1),
              ),
              child: Image.asset(
                appTheme.logoIcon,
                height: 24,
                width: 24,
              ),
            ),
            const SizedBox(width: 12),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (_isEditing)
                    SizedBox(
                      height: 24,
                      child: TextField(
                        controller: _editController,
                        focusNode: _editFocusNode,
                        style: TextStyle(
                          color: theme.colorScheme.onSurface,
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.5,
                        ),
                        decoration: const InputDecoration(
                          isDense: true,
                          contentPadding: EdgeInsets.zero,
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _submitRename(),
                      ),
                    )
                  else
                    GestureDetector(
                      onTap: canEdit ? _startEditing : null,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Flexible(
                            child: Text(
                              displayName,
                              style: TextStyle(
                                color: theme.colorScheme.onSurface,
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.5,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (canEdit) ...[
                            const SizedBox(width: 4),
                            Icon(
                              Icons.edit_outlined,
                              size: 14,
                              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                          ],
                        ],
                      ),
                    ),
                  Text(
                    appTheme.brandingMessage,
                    style: TextStyle(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          if (widget.onAttachFile != null)
            Tooltip(
              message: 'Attach File',
              child: IconButton(
                icon: Icon(
                  Icons.attach_file_rounded,
                  color: widget.isSendingMessage
                      ? theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4)
                      : theme.colorScheme.onSurfaceVariant,
                ),
                onPressed: widget.isSendingMessage ? null : widget.onAttachFile,
              ),
            ),
          if (widget.onCreateNewThread != null)
            Tooltip(
              message: 'New Conversation',
              child: IconButton(
                icon: Icon(
                  Icons.add_comment_outlined,
                  color: widget.isSendingMessage
                      ? theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4)
                      : theme.colorScheme.onSurfaceVariant,
                ),
                onPressed: widget.isSendingMessage ? null : widget.onCreateNewThread,
              ),
            ),
          const ConnectionStatusIndicator(),
          const SizedBox(width: 8),
        ],
      ),
    );
  }
}
