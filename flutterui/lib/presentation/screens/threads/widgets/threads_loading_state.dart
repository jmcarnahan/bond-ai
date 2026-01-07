import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class ThreadsLoadingState extends StatelessWidget {
  const ThreadsLoadingState({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(
              theme.colorScheme.primary,
            ),
          ),
          SizedBox(height: AppSpacing.xl),
          Text(
            'Loading threads...',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }
}
