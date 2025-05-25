import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/theme/mcafee_theme.dart';
import 'package:flutterui/main.dart'; // Import for appThemeProvider
import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart'; // Corrected import
import 'package:flutterui/providers/thread_provider.dart';

class ChatAppBar extends ConsumerWidget implements PreferredSizeWidget {
  final String agentName;
  final VoidCallback onStartNewThread;
  final VoidCallback onViewThreads;

  const ChatAppBar({
    super.key,
    required this.agentName,
    required this.onStartNewThread,
    required this.onViewThreads,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final customColors = theme.extension<CustomColors>();
    final appBarBackgroundColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface;
    final appTheme = ref.watch(appThemeProvider);
    final textTheme = theme.textTheme;

    return AppBar(
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
            "Chat with $agentName",
            style: textTheme.titleLarge?.copyWith(color: Colors.white),
          ),
        ],
      ),
      actions: [
        IconButton(
          icon: const Icon(Icons.forum_outlined, color: Colors.white),
          tooltip: 'View/Change Threads',
          onPressed: onViewThreads,
        ),
        IconButton(
          icon: const Icon(Icons.add_comment_outlined, color: Colors.white),
          tooltip: 'Start New Thread',
          onPressed: onStartNewThread,
        ),
      ],
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
