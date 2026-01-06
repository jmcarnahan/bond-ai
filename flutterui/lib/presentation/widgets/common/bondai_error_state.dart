import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

class BondAIErrorState extends StatelessWidget {
  final String message;
  final String? errorDetails;
  final VoidCallback? onRetry;
  final Widget? actionButton;
  final bool showIcon;
  final EdgeInsetsGeometry? padding;

  const BondAIErrorState({
    super.key,
    required this.message,
    this.errorDetails,
    this.onRetry,
    this.actionButton,
    this.showIcon = true,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: padding ?? AppSpacing.allXl,
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer.withValues(alpha: 0.3),
        borderRadius: AppBorderRadius.allMd,
        border: Border.all(
          color: theme.colorScheme.error.withValues(alpha: 0.5),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              if (showIcon) ...[
                Icon(
                  Icons.error_outline,
                  color: theme.colorScheme.error,
                  size: AppSizes.iconMd,
                ),
                SizedBox(width: AppSpacing.md),
              ],
              Expanded(
                child: Text(
                  message,
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ),
            ],
          ),
          if (errorDetails != null) ...[
            SizedBox(height: AppSpacing.sm),
            Text(
              errorDetails!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error.withValues(alpha: 0.8),
              ),
            ),
          ],
          if (actionButton != null || onRetry != null) ...[
            SizedBox(height: AppSpacing.md),
            actionButton ?? TextButton.icon(
              onPressed: onRetry,
              icon: Icon(Icons.refresh, size: AppSizes.iconSm),
              label: Text('Retry'),
              style: TextButton.styleFrom(
                foregroundColor: theme.colorScheme.error,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
