import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../main_mobile.dart' show navigationIndexProvider;
import '../../providers/notification_provider.dart';
import '../../providers/config_provider.dart';

class MessageNotificationBanner extends ConsumerStatefulWidget {
  final String threadName;
  final String messageContent;
  final String agentId;
  final String? subject;
  final int duration;
  final VoidCallback onDismiss;
  
  const MessageNotificationBanner({
    super.key,
    required this.threadName,
    required this.messageContent,
    required this.agentId,
    this.subject,
    this.duration = 60,
    required this.onDismiss,
  });

  @override
  ConsumerState<MessageNotificationBanner> createState() => _MessageNotificationBannerState();
}

class _MessageNotificationBannerState extends ConsumerState<MessageNotificationBanner> 
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<Offset> _slideAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, -1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    ));
    
    _fadeAnimation = Tween<double>(
      begin: 0,
      end: 1,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeIn,
    ));
    
    _animationController.forward();
    
    // Auto dismiss after specified duration
    Future.delayed(Duration(seconds: widget.duration), () {
      if (mounted) {
        _dismiss();
      }
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  void _dismiss() async {
    await _animationController.reverse();
    widget.onDismiss();
  }

  void _navigateToChat() {
    print('[MessageNotificationBanner] _navigateToChat called');
    print('[MessageNotificationBanner] Agent ID: ${widget.agentId}');
    print('[MessageNotificationBanner] Thread Name: ${widget.threadName}');
    print('[MessageNotificationBanner] Message Content: ${widget.messageContent}');
    
    // Find the correct index for the chat screen
    final navItems = ref.read(bottomNavItemsProvider);
    final chatIndex = navItems.indexWhere((item) => item.label == 'Chat');
    
    print('[MessageNotificationBanner] Chat screen is at index: $chatIndex');
    
    // Navigate to chat tab first
    ref.read(navigationIndexProvider.notifier).state = chatIndex != -1 ? chatIndex : 1;
    
    // Pass the system message to the chat screen by storing it in a provider
    ref.read(pendingSystemMessageProvider.notifier).state = PendingSystemMessage(
      message: widget.messageContent,
      agentId: widget.agentId,
      threadName: widget.threadName,
    );
    
    print('[MessageNotificationBanner] PendingSystemMessage set with agentId: ${widget.agentId}');
    
    // Dismiss the banner
    _dismiss();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Positioned(
      top: MediaQuery.of(context).padding.top + 8,
      left: 16,
      right: 16,
      child: SlideTransition(
        position: _slideAnimation,
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: Material(
            elevation: 8,
            borderRadius: BorderRadius.circular(12),
            color: theme.colorScheme.primaryContainer,
            child: InkWell(
              onTap: _navigateToChat,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.primary,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        Icons.message,
                        color: theme.colorScheme.onPrimary,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (widget.subject != null) ...[
                            Text(
                              widget.subject!,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onPrimaryContainer,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Tap to view message',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onPrimaryContainer.withValues(alpha: 0.8),
                              ),
                            ),
                          ] else ...[
                            Text(
                              widget.threadName,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.onPrimaryContainer,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Tap to view message',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: theme.colorScheme.onPrimaryContainer.withValues(alpha: 0.8),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    IconButton(
                      icon: Icon(
                        Icons.close,
                        color: theme.colorScheme.onPrimaryContainer,
                      ),
                      onPressed: _dismiss,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}