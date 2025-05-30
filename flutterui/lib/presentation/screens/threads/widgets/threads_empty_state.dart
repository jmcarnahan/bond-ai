import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class ThreadsEmptyState extends StatelessWidget {
  final VoidCallback onCreateThread;

  const ThreadsEmptyState({
    super.key,
    required this.onCreateThread,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Padding(
        padding: AppSpacing.allXl,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.forum_outlined,
              size: AppSizes.iconEnormous,
              color: theme.colorScheme.onSurface.withOpacity(0.3),
            ),
            SizedBox(height: AppSpacing.xxl),
            Text(
              'No threads yet',
              style: theme.textTheme.headlineSmall?.copyWith(
                color: theme.colorScheme.onSurface.withOpacity(0.7),
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: AppSpacing.md),
            Text(
              'Create your first thread to start chatting with agents',
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurface.withOpacity(0.6),
              ),
              textAlign: TextAlign.center,
            ),
            SizedBox(height: AppSpacing.huge),
            FilledButton.icon(
              onPressed: onCreateThread,
              icon: const Icon(Icons.add),
              label: const Text('Create Thread'),
              style: FilledButton.styleFrom(
                padding: AppSpacing.horizontalXxl.add(AppSpacing.verticalLg),
              ),
            ),
          ],
        ),
      ),
    );
  }
}