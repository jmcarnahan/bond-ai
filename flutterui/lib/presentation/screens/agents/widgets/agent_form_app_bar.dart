import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/main.dart';

class AgentFormAppBar extends ConsumerWidget implements PreferredSizeWidget {
  final bool isEditing;
  final bool isLoading;
  final VoidCallback? onBack;
  final VoidCallback? onDelete;

  const AgentFormAppBar({
    super.key,
    required this.isEditing,
    required this.isLoading,
    this.onBack,
    this.onDelete,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final customColors = theme.extension<CustomColors>();
    final appBarBackgroundColor = customColors?.brandingSurface ?? 
        theme.appBarTheme.backgroundColor ?? 
        theme.colorScheme.surface;
    final appTheme = ref.watch(appThemeProvider);

    return AppBar(
      backgroundColor: appBarBackgroundColor,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back, color: Colors.white),
        onPressed: isLoading ? null : onBack,
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
            isEditing ? "Edit Agent" : "Create Agent",
            style: textTheme.titleLarge?.copyWith(color: Colors.white),
          ),
        ],
      ),
      actions: isEditing && onDelete != null
          ? [
              IconButton(
                icon: const Icon(Icons.delete, color: Colors.white),
                onPressed: isLoading ? null : onDelete,
                tooltip: 'Delete Agent',
              ),
            ]
          : null,
    );
  }
}