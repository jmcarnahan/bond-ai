import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class AgentErrorBanner extends StatelessWidget {
  final String? errorMessage;

  const AgentErrorBanner({
    super.key,
    this.errorMessage,
  });

  @override
  Widget build(BuildContext context) {
    if (errorMessage == null) return const SizedBox.shrink();

    final theme = Theme.of(context);

    return Padding(
      padding: AppSpacing.onlyBottomXl,
      child: Container(
        padding: AppSpacing.allXl,
        decoration: BoxDecoration(
          color: theme.colorScheme.errorContainer,
          borderRadius: AppBorderRadius.allMd,
          border: Border.all(
            color: theme.colorScheme.error.withValues(alpha: 0.3),
          ),
        ),
        child: Row(
          children: [
            Icon(
              Icons.error_outline,
              color: theme.colorScheme.error,
              size: AppSizes.iconMd,
            ),
            SizedBox(width: AppSpacing.md),
            Expanded(
              child: Text(
                errorMessage!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.error,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
