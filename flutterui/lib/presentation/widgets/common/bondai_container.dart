import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

class BondAIContainer extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final List<Widget> children;
  final Widget? actionButton;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final Color? backgroundColor;
  final Color? borderColor;
  final double? borderWidth;
  final bool showDividerAfterHeader;
  final CrossAxisAlignment crossAxisAlignment;

  const BondAIContainer({
    super.key,
    required this.icon,
    required this.title,
    required this.children,
    this.subtitle,
    this.actionButton,
    this.padding,
    this.margin,
    this.backgroundColor,
    this.borderColor,
    this.borderWidth,
    this.showDividerAfterHeader = false,
    this.crossAxisAlignment = CrossAxisAlignment.start,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Card(
      elevation: 0,
      margin: margin ?? EdgeInsets.only(top: AppSpacing.xxl),
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allLg,
        side: BorderSide(
          color: borderColor ?? theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
          width: borderWidth ?? 1.0,
        ),
      ),
      color: backgroundColor ?? theme.colorScheme.surface,
      child: Padding(
        padding: padding ?? AppSpacing.allXxxl,
        child: Column(
          crossAxisAlignment: crossAxisAlignment,
          children: [
            _buildHeader(context, theme),
            if (showDividerAfterHeader) ...[
              SizedBox(height: AppSpacing.xl),
              Divider(
                color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
                height: 1,
              ),
            ],
            if (subtitle != null) ...[
              SizedBox(height: AppSpacing.md),
              Text(
                subtitle!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
            ],
            SizedBox(height: AppSpacing.xxl),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ThemeData theme) {
    return Row(
      children: [
        Icon(
          icon,
          color: theme.colorScheme.primary,
          size: AppSizes.iconLg,
        ),
        SizedBox(width: AppSpacing.lg),
        Expanded(
          child: Text(
            title,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        if (actionButton != null) ...[
          SizedBox(width: AppSpacing.lg),
          actionButton!,
        ],
      ],
    );
  }
}

class BondAIContainerSection extends StatelessWidget {
  final String? title;
  final List<Widget> children;
  final EdgeInsetsGeometry? padding;
  final CrossAxisAlignment crossAxisAlignment;

  const BondAIContainerSection({
    super.key,
    this.title,
    required this.children,
    this.padding,
    this.crossAxisAlignment = CrossAxisAlignment.start,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Padding(
      padding: padding ?? EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: crossAxisAlignment,
        children: [
          if (title != null) ...[
            Text(
              title!,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: theme.colorScheme.onSurface,
              ),
            ),
            SizedBox(height: AppSpacing.md),
          ],
          ...children,
        ],
      ),
    );
  }
}