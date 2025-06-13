import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/core/theme/app_theme.dart';

class ProfileAppBar extends ConsumerWidget implements PreferredSizeWidget {
  const ProfileAppBar({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight + 8);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appTheme = ref.watch(appThemeProvider);
    final theme = Theme.of(context);

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
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
                color: theme.colorScheme.onSurface.withOpacity(0.1),
              ),
              child: Icon(
                Icons.person,
                size: 24,
                color: theme.colorScheme.onSurface,
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Profile',
              style: TextStyle(
                color: theme.colorScheme.onSurface,
                fontSize: 20,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        centerTitle: false,
        toolbarHeight: kToolbarHeight + 8,
      ),
    );
  }
}