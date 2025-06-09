import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

enum ResourceUnavailableType {
  empty,
  error,
  loading,
  info,
  permission,
  notFound,
}

class BondAIResourceUnavailable extends StatelessWidget {
  final String message;
  final String? description;
  final IconData? icon;
  final ResourceUnavailableType type;
  final Widget? actionButton;
  final VoidCallback? onRetry;
  final Color? backgroundColor;
  final Color? borderColor;
  final double? iconSize;
  final bool showBorder;
  final EdgeInsetsGeometry? padding;

  const BondAIResourceUnavailable({
    super.key,
    required this.message,
    this.description,
    this.icon,
    this.type = ResourceUnavailableType.empty,
    this.actionButton,
    this.onRetry,
    this.backgroundColor,
    this.borderColor,
    this.iconSize,
    this.showBorder = true,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Container(
      padding: padding ?? AppSpacing.allHuge,
      decoration: BoxDecoration(
        color: backgroundColor ?? _getBackgroundColor(theme),
        borderRadius: AppBorderRadius.allLg,
        border: showBorder
            ? Border.all(
                color: borderColor ?? _getBorderColor(theme),
                width: 1,
              )
            : null,
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon ?? _getIcon(),
              color: _getIconColor(theme),
              size: iconSize ?? AppSizes.iconEnormous,
            ),
            SizedBox(height: AppSpacing.xl),
            Text(
              message,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: _getTextColor(theme),
              ),
              textAlign: TextAlign.center,
            ),
            if (description != null) ...[
              SizedBox(height: AppSpacing.md),
              Text(
                description!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: _getTextColor(theme).withValues(alpha: 0.8),
                ),
                textAlign: TextAlign.center,
              ),
            ],
            if (actionButton != null || onRetry != null) ...[
              SizedBox(height: AppSpacing.xxl),
              actionButton ?? _buildRetryButton(context, theme),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildRetryButton(BuildContext context, ThemeData theme) {
    if (onRetry == null) return const SizedBox.shrink();
    
    return TextButton.icon(
      onPressed: onRetry,
      icon: Icon(Icons.refresh, size: AppSizes.iconSm),
      label: Text('Retry'),
      style: TextButton.styleFrom(
        foregroundColor: _getButtonColor(theme),
      ),
    );
  }

  Color _getBackgroundColor(ThemeData theme) {
    switch (type) {
      case ResourceUnavailableType.error:
        return theme.colorScheme.errorContainer.withValues(alpha: 0.1);
      case ResourceUnavailableType.loading:
        return theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3);
      case ResourceUnavailableType.info:
        return theme.colorScheme.primaryContainer.withValues(alpha: 0.1);
      case ResourceUnavailableType.permission:
        return theme.colorScheme.tertiaryContainer.withValues(alpha: 0.1);
      case ResourceUnavailableType.notFound:
        return theme.colorScheme.secondaryContainer.withValues(alpha: 0.1);
      case ResourceUnavailableType.empty:
        return theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3);
    }
  }

  Color _getBorderColor(ThemeData theme) {
    switch (type) {
      case ResourceUnavailableType.error:
        return theme.colorScheme.error.withValues(alpha: 0.3);
      case ResourceUnavailableType.loading:
        return theme.colorScheme.outlineVariant.withValues(alpha: 0.3);
      case ResourceUnavailableType.info:
        return theme.colorScheme.primary.withValues(alpha: 0.3);
      case ResourceUnavailableType.permission:
        return theme.colorScheme.tertiary.withValues(alpha: 0.3);
      case ResourceUnavailableType.notFound:
        return theme.colorScheme.secondary.withValues(alpha: 0.3);
      case ResourceUnavailableType.empty:
        return theme.colorScheme.outlineVariant.withValues(alpha: 0.2);
    }
  }

  Color _getIconColor(ThemeData theme) {
    switch (type) {
      case ResourceUnavailableType.error:
        return theme.colorScheme.error;
      case ResourceUnavailableType.loading:
        return theme.colorScheme.primary;
      case ResourceUnavailableType.info:
        return theme.colorScheme.primary;
      case ResourceUnavailableType.permission:
        return theme.colorScheme.tertiary;
      case ResourceUnavailableType.notFound:
        return theme.colorScheme.secondary;
      case ResourceUnavailableType.empty:
        return theme.colorScheme.onSurfaceVariant;
    }
  }

  Color _getTextColor(ThemeData theme) {
    switch (type) {
      case ResourceUnavailableType.error:
        return theme.colorScheme.error;
      case ResourceUnavailableType.info:
        return theme.colorScheme.primary;
      case ResourceUnavailableType.permission:
        return theme.colorScheme.tertiary;
      case ResourceUnavailableType.notFound:
        return theme.colorScheme.secondary;
      case ResourceUnavailableType.loading:
      case ResourceUnavailableType.empty:
        return theme.colorScheme.onSurfaceVariant;
    }
  }

  Color _getButtonColor(ThemeData theme) {
    switch (type) {
      case ResourceUnavailableType.error:
        return theme.colorScheme.error;
      case ResourceUnavailableType.info:
      case ResourceUnavailableType.loading:
        return theme.colorScheme.primary;
      case ResourceUnavailableType.permission:
        return theme.colorScheme.tertiary;
      case ResourceUnavailableType.notFound:
        return theme.colorScheme.secondary;
      case ResourceUnavailableType.empty:
        return theme.colorScheme.primary;
    }
  }

  IconData _getIcon() {
    switch (type) {
      case ResourceUnavailableType.error:
        return Icons.error_outline;
      case ResourceUnavailableType.loading:
        return Icons.hourglass_empty;
      case ResourceUnavailableType.info:
        return Icons.info_outline;
      case ResourceUnavailableType.permission:
        return Icons.lock_outline;
      case ResourceUnavailableType.notFound:
        return Icons.search_off;
      case ResourceUnavailableType.empty:
        return Icons.inbox;
    }
  }
}

