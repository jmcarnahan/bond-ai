import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/main.dart';

class ThreadsAppBar extends ConsumerWidget implements PreferredSizeWidget {
  final VoidCallback? onBack;

  const ThreadsAppBar({
    super.key,
    this.onBack,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final appTheme = ref.watch(appThemeProvider);
    final customColors = theme.extension<CustomColors>();
    final appBarBackgroundColor = customColors?.brandingSurface ??
        theme.appBarTheme.backgroundColor ??
        theme.colorScheme.surface;

    return AppBar(
      backgroundColor: appBarBackgroundColor,
      leading: IconButton(
        icon: const Icon(Icons.arrow_back, color: Colors.white),
        onPressed: onBack,
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
            'Threads',
            style: theme.textTheme.titleLarge?.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }
}