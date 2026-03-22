import 'package:flutter/material.dart';

import 'package:flutterui/core/constants/app_constants.dart';

class AgentErrorBanner extends StatelessWidget {
  final String? errorMessage;
  final VoidCallback? onDismiss;

  const AgentErrorBanner({
    super.key,
    this.errorMessage,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AnimatedSize(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeInOut,
      child: errorMessage == null
          ? const SizedBox.shrink()
          : Padding(
              padding: AppSpacing.onlyBottomXl,
              child: Container(
                padding: AppSpacing.allXl,
                decoration: BoxDecoration(
                  color: theme.colorScheme.error,
                  borderRadius: AppBorderRadius.allMd,
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.error_outline,
                      color: theme.colorScheme.onError,
                      size: AppSizes.iconMd,
                    ),
                    SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: SelectableText(
                        errorMessage!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onError,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    if (onDismiss != null) ...[
                      SizedBox(width: AppSpacing.md),
                      IconButton(
                        icon: Icon(
                          Icons.close,
                          color: theme.colorScheme.onError,
                          size: AppSizes.iconSm,
                        ),
                        onPressed: onDismiss,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                        tooltip: 'Dismiss',
                      ),
                    ],
                  ],
                ),
              ),
            ),
    );
  }
}
