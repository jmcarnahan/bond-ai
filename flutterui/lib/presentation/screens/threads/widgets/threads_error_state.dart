import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class ThreadsErrorState extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;

  const ThreadsErrorState({
    super.key,
    required this.error,
    required this.onRetry,
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
              Icons.error_outline,
              color: theme.colorScheme.error,
              size: AppSizes.iconHuge,
            ),
            SizedBox(height: AppSpacing.xl),
            Text(
              'Failed to load threads',
              style: theme.textTheme.headlineSmall?.copyWith(
                color: theme.colorScheme.error,
                fontWeight: FontWeight.w500,
              ),
            ),
            SizedBox(height: AppSpacing.md),
            Text(
              error,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.8),
              ),
            ),
            SizedBox(height: AppSpacing.xxl),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
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